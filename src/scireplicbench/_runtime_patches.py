"""Runtime patch helpers for repo-local bootstrap customization.

These patches let the repo exercise the requested realignment even when the
workspace is ahead of the checked-in baseline. They are applied via the
repo-local ``sitecustomize.py`` during Python startup inside this workspace.
"""

from __future__ import annotations

from typing import Any

from .readiness import phase_readiness_gate


def _apply_run_plan_patch() -> None:
    from . import run_plan

    if getattr(run_plan, "_REALIGNMENT_PATCHED", False) or getattr(
        run_plan, "_REALIGNMENT_NATIVE", False
    ):
        return

    original_to_dict = run_plan.RunPlanEntry.to_dict
    original_inspect_eval_command = run_plan.RunPlanEntry.inspect_eval_command
    original_build_phase4a_plan = run_plan.build_phase4a_plan
    original_build_phase4b_plan = run_plan.build_phase4b_plan

    def _annotate(entries: list[Any]) -> list[Any]:
        for entry in entries:
            gate = phase_readiness_gate(entry.paper_id, entry.phase).to_dict()
            entry.readiness_gate = gate
            entry.judge_self_consistency_n = (
                3 if entry.phase == "phase4b_production" else 1
            )
            entry.judge_self_consistency_min_confidence = 0.6
        return entries

    def inspect_eval_command(self: Any, *, log_dir: str = "logs") -> list[str]:
        command = original_inspect_eval_command(self, log_dir=log_dir)
        extras = [
            "--metadata",
            f"judge_self_consistency_n={getattr(self, 'judge_self_consistency_n', 1)}",
            "--metadata",
            "judge_self_consistency_min_confidence="
            f"{getattr(self, 'judge_self_consistency_min_confidence', 0.6):.2f}",
        ]
        try:
            insert_at = command.index("--model-role")
        except ValueError:
            command.extend(extras)
        else:
            command[insert_at:insert_at] = extras
        return command

    def to_dict(self: Any) -> dict[str, Any]:
        payload = original_to_dict(self)
        payload["judge_self_consistency_n"] = getattr(
            self, "judge_self_consistency_n", 1
        )
        payload["judge_self_consistency_min_confidence"] = getattr(
            self, "judge_self_consistency_min_confidence", 0.6
        )
        payload["readiness_gate"] = getattr(self, "readiness_gate", {})
        return payload

    def build_phase4a_plan() -> list[Any]:
        return _annotate(original_build_phase4a_plan())

    def build_phase4b_plan(seeds: tuple[int, ...] = (1, 2, 3)) -> list[Any]:
        return _annotate(original_build_phase4b_plan(seeds=seeds))

    def render_plan_markdown(entries: list[Any]) -> str:
        lines = [
            "# Run Plan",
            "",
            "| Phase | Paper | Gate | Lane | Agent | Judge | Seed | Cost Limit |",
            "|---|---|---|---|---|---|---:|---:|",
        ]
        for entry in entries:
            gate = getattr(entry, "readiness_gate", {}) or {}
            gate_status = "ready" if gate.get("run_allowed") else "blocked"
            lane = gate.get("lane", "evaluation")
            lines.append(
                f"| {entry.phase} | {entry.paper_id} | {gate_status} | {lane} | "
                f"{entry.agent.label} | {entry.judge.label} | {entry.seed} | "
                f"{entry.cost_limit_usd or 0:.2f} |"
            )
        return "\n".join(lines) + "\n"

    run_plan.RunPlanEntry.inspect_eval_command = inspect_eval_command
    run_plan.RunPlanEntry.to_dict = to_dict
    run_plan.build_phase4a_plan = build_phase4a_plan
    run_plan.build_phase4b_plan = build_phase4b_plan
    run_plan.render_plan_markdown = render_plan_markdown
    run_plan._REALIGNMENT_PATCHED = True


def _apply_scorer_patch() -> None:
    import os

    from . import scorers
    from .judge import majority_vote_judgements, needs_self_consistency_retry

    if getattr(scorers, "_REALIGNMENT_PATCHED", False):
        return

    scorers._JUDGE_SELF_CONSISTENCY_N_ENV = "SCIREPLICBENCH_JUDGE_SELF_CONSISTENCY_N"
    scorers._JUDGE_SELF_CONSISTENCY_MIN_CONFIDENCE_ENV = (
        "SCIREPLICBENCH_JUDGE_SELF_CONSISTENCY_MIN_CONFIDENCE"
    )

    async def _judge_leaf_with_self_consistency(
        judge: Any,
        leaf: dict[str, Any],
        *,
        paper_summary: str,
        reality_context: str,
        self_consistency_n: int = 1,
        self_consistency_min_confidence: float = 0.6,
    ) -> Any:
        total_samples = max(1, int(self_consistency_n))
        initial_samples = 1 if total_samples == 1 else min(2, total_samples)

        judgements = []
        for _ in range(initial_samples):
            judgements.append(
                await scorers._judge_leaf(
                    judge,
                    leaf,
                    paper_summary=paper_summary,
                    reality_context=reality_context,
                )
            )

        while len(judgements) < total_samples and needs_self_consistency_retry(
            judgements, min_confidence=self_consistency_min_confidence
        ):
            judgements.append(
                await scorers._judge_leaf(
                    judge,
                    leaf,
                    paper_summary=paper_summary,
                    reality_context=reality_context,
                )
            )

        if len(judgements) == 1:
            judgement = judgements[0]
            metadata = dict(judgement.metadata)
            metadata.update(
                {
                    "self_consistency_samples": 1,
                    "self_consistency_requested_n": total_samples,
                    "self_consistency_min_confidence": self_consistency_min_confidence,
                    "self_consistency_triggered": False,
                    "self_consistency_consensus": True,
                    "self_consistency_judgements": [judgement.to_dict()],
                }
            )
            return scorers.LeafJudgement(
                leaf_id=judgement.leaf_id,
                expectations=judgement.expectations,
                reality=judgement.reality,
                evidence_quote=judgement.evidence_quote,
                score=judgement.score,
                confidence=judgement.confidence,
                metadata=metadata,
            )

        consensus = majority_vote_judgements(judgements)
        metadata = dict(consensus.metadata)
        metadata.update(
            {
                "self_consistency_samples": len(judgements),
                "self_consistency_requested_n": total_samples,
                "self_consistency_min_confidence": self_consistency_min_confidence,
                "self_consistency_triggered": len(judgements) > 1,
                "self_consistency_consensus": len({j.score for j in judgements}) == 1,
                "self_consistency_judgements": [judgement.to_dict() for judgement in judgements],
            }
        )
        return scorers.LeafJudgement(
            leaf_id=consensus.leaf_id,
            expectations=consensus.expectations,
            reality=consensus.reality,
            evidence_quote=consensus.evidence_quote,
            score=consensus.score,
            confidence=consensus.confidence,
            metadata=metadata,
        )

    scorers._judge_leaf_with_self_consistency = _judge_leaf_with_self_consistency

    if getattr(scorers, "_HAS_INSPECT_SCORING", False):

        @scorers.scorer(metrics=[scorers.mean(), scorers.stderr()])
        def rubric_tree_scorer(
            judge_model: str = scorers._JUDGE_DEFAULT_MODEL,
            *,
            leaf_limit: int | None = None,
            self_consistency_n: int = 1,
            self_consistency_min_confidence: float = 0.6,
        ):
            async def score(state: Any, target: Any):
                paper_id = scorers._resolve_paper_id(state)
                rubric = scorers.load_rubric_payload(paper_id)
                paper_summary = scorers.load_paper_summary(paper_id)
                reality = await scorers._collect_submission_context()

                tree = scorers.extract_rubric_tree(rubric)
                leaves = scorers.collect_leaf_nodes(tree)

                env_cap = os.getenv(scorers._JUDGE_LEAF_LIMIT_ENV)
                cap = leaf_limit if leaf_limit is not None else (int(env_cap) if env_cap else None)
                requested_n = int(
                    os.getenv(
                        scorers._JUDGE_SELF_CONSISTENCY_N_ENV,
                        str(self_consistency_n),
                    )
                )
                min_confidence = float(
                    os.getenv(
                        scorers._JUDGE_SELF_CONSISTENCY_MIN_CONFIDENCE_ENV,
                        str(self_consistency_min_confidence),
                    )
                )

                precheck = await scorers._artifact_presence_precheck()
                if not precheck["ok"]:
                    judgements = [
                        scorers.LeafJudgement(
                            leaf_id=str(leaf["id"]),
                            expectations="",
                            reality="",
                            evidence_quote=f"precheck_failed: {precheck['reason']}",
                            score=0,
                            metadata={
                                "precheck_failed": True,
                                "nontrivial_py_files": precheck["nontrivial_py_files"],
                                "output_artifact_count": precheck["output_artifact_count"],
                            },
                        )
                        for leaf in leaves
                    ]
                else:
                    judge = scorers.get_model(judge_model)
                    judgements = []
                    for index, leaf in enumerate(leaves):
                        if cap is not None and index >= cap:
                            judgements.append(
                                scorers.LeafJudgement(
                                    leaf_id=str(leaf["id"]),
                                    expectations="",
                                    reality="",
                                    evidence_quote=f"skipped by leaf_limit={cap}",
                                    score=0,
                                    metadata={"skipped": True},
                                )
                            )
                            continue
                        judged = await _judge_leaf_with_self_consistency(
                            judge,
                            leaf,
                            paper_summary=paper_summary,
                            reality_context=reality,
                            self_consistency_n=requested_n,
                            self_consistency_min_confidence=min_confidence,
                        )
                        judgements.append(
                            scorers._enforce_leaf_evidence_policy(
                                leaf,
                                judged,
                                reality_context=reality,
                            )
                        )

                leaf_map = scorers.leaf_score_map_from_judgements(judgements)
                report = scorers.score_rubric_payload(rubric, leaf_map)
                base_score = scorers.to_inspect_score(report)

                metadata = dict(base_score.metadata or {})
                metadata.update(
                    {
                        "paper_id": paper_id,
                        "judge_model": judge_model,
                        "leaf_limit": cap,
                        "judge_self_consistency_n": requested_n,
                        "judge_self_consistency_min_confidence": min_confidence,
                        "leaves_graded": sum(
                            1
                            for judgement in judgements
                            if not judgement.metadata.get("skipped")
                            and not judgement.metadata.get("precheck_failed")
                        ),
                        "leaves_total": len(leaves),
                        "judge_failures": sum(
                            1 for judgement in judgements if judgement.metadata.get("judge_failure")
                        ),
                        "precheck": precheck,
                        "leaf_judgements": [judgement.to_dict() for judgement in judgements],
                    }
                )
                return scorers.InspectScore(
                    value=base_score.value,
                    explanation=base_score.explanation,
                    metadata=metadata,
                )

            return score

    else:

        def rubric_tree_scorer(*args: Any, **kwargs: Any):  # type: ignore[no-redef]
            raise RuntimeError(
                "inspect-ai is not installed; rubric_tree_scorer requires the Inspect AI runtime."
            )

    scorers.rubric_tree_scorer = rubric_tree_scorer
    scorers._REALIGNMENT_PATCHED = True


def apply_runtime_patches() -> None:
    _apply_run_plan_patch()
    _apply_scorer_patch()


__all__ = ["apply_runtime_patches"]
