"""Rubric-tree scoring helpers."""

from __future__ import annotations

import ast
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

from .judge import LeafJudgement, format_leaf_judge_prompt, parse_leaf_judgement
from .rubric_utils import collect_leaf_ids, collect_leaf_nodes, extract_rubric_tree, validate_rubric_payload

PROJECT_ROOT = Path(__file__).resolve().parents[2]
_JUDGE_MAX_SUBMISSION_CHARS = 8000
_JUDGE_MAX_PAPER_CHARS = 3000
_JUDGE_DEFAULT_MODEL = "openai/gpt-4o-mini"
_JUDGE_LEAF_LIMIT_ENV = "SCIREPLICBENCH_JUDGE_LEAF_LIMIT"
_PRECHECK_SUBMISSION_DIR = "/workspace/submission"
_PRECHECK_OUTPUT_DIR = "/workspace/output"
_PRECHECK_FILE_CAP = 20


def _is_trivial_stmt(stmt: ast.AST) -> bool:
    """Return True for statements that carry no executable intent.

    Trivial statements are `pass`, docstring / `...` expressions, and
    `raise NotImplementedError` (with or without call arguments). These
    are the markers of an empty scaffold that the v0.2 artifact-presence
    precheck rejects.
    """

    if isinstance(stmt, ast.Pass):
        return True
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
        # docstring, ellipsis literal, bare integer, etc.
        return True
    if isinstance(stmt, ast.Raise):
        exc = stmt.exc
        if isinstance(exc, ast.Name) and exc.id == "NotImplementedError":
            return True
        if (
            isinstance(exc, ast.Call)
            and isinstance(exc.func, ast.Name)
            and exc.func.id == "NotImplementedError"
        ):
            return True
    return False


def _has_nontrivial_body(source: str) -> bool:
    """Detect whether a Python source file contains non-trivial executable code.

    Walks every `FunctionDef` / `AsyncFunctionDef` in the module (which
    naturally covers class methods and nested functions) and checks each
    body for at least one non-trivial statement. Also inspects module-level
    statements, ignoring imports and function/class definitions themselves,
    so top-level assignments or calls count as non-trivial.

    Fails closed on `SyntaxError`: a file that does not parse cannot execute.
    """

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if any(not _is_trivial_stmt(stmt) for stmt in node.body):
                return True

    module_excluded = (
        ast.Import,
        ast.ImportFrom,
        ast.FunctionDef,
        ast.AsyncFunctionDef,
        ast.ClassDef,
    )
    for stmt in tree.body:
        if isinstance(stmt, module_excluded):
            continue
        if not _is_trivial_stmt(stmt):
            return True

    return False


@dataclass
class NodeScoreReport:
    """Hierarchical score report for one rubric node."""

    node_id: str
    name: str
    weight: float
    score: float
    category: str | None
    leaf_count: int
    missing_leaf_ids: list[str] = field(default_factory=list)
    children: list["NodeScoreReport"] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.node_id,
            "name": self.name,
            "weight": self.weight,
            "score": self.score,
            "category": self.category,
            "leaf_count": self.leaf_count,
            "missing_leaf_ids": list(self.missing_leaf_ids),
            "children": [child.to_dict() for child in self.children],
        }


@dataclass
class RubricScoreReport:
    """Top-level rubric score report."""

    paper_id: str
    overall_score: float
    category_scores: dict[str, float]
    missing_leaf_ids: list[str]
    extra_leaf_ids: list[str]
    root: NodeScoreReport

    def to_dict(self) -> dict[str, Any]:
        return {
            "paper_id": self.paper_id,
            "overall_score": self.overall_score,
            "category_scores": dict(self.category_scores),
            "missing_leaf_ids": list(self.missing_leaf_ids),
            "extra_leaf_ids": list(self.extra_leaf_ids),
            "root": self.root.to_dict(),
        }


try:  # pragma: no cover - optional Inspect integration
    from inspect_ai.scorer import Score as InspectScore
except ModuleNotFoundError:  # pragma: no cover - local fallback
    @dataclass
    class InspectScore:  # type: ignore[override]
        value: float
        explanation: str = ""
        metadata: dict[str, Any] | None = None


def leaf_score_map_from_judgements(judgements: Iterable[LeafJudgement]) -> dict[str, float]:
    """Convert leaf judgements to a numeric leaf-score map."""

    leaf_scores: dict[str, float] = {}
    for judgement in judgements:
        leaf_scores[judgement.leaf_id] = float(judgement.score)
    return leaf_scores


def _infer_category(node: dict[str, Any]) -> str | None:
    leaves = collect_leaf_nodes(node)
    categories = {leaf["category"] for leaf in leaves}
    return next(iter(categories)) if len(categories) == 1 else None


def _aggregate_node(
    node: dict[str, Any], leaf_scores: Mapping[str, float]
) -> NodeScoreReport:
    if node.get("is_leaf"):
        leaf_id = node["id"]
        score = float(leaf_scores.get(leaf_id, 0.0))
        missing = [] if leaf_id in leaf_scores else [leaf_id]
        return NodeScoreReport(
            node_id=leaf_id,
            name=str(node["name"]),
            weight=float(node["weight"]),
            score=score,
            category=str(node["category"]),
            leaf_count=1,
            missing_leaf_ids=missing,
            children=[],
        )

    child_reports = [_aggregate_node(child, leaf_scores) for child in node.get("children", []) or []]
    total_child_weight = sum(child.weight for child in child_reports)
    score = (
        sum(child.score * child.weight for child in child_reports) / total_child_weight
        if total_child_weight
        else 0.0
    )
    missing_leaf_ids: list[str] = []
    for child in child_reports:
        missing_leaf_ids.extend(child.missing_leaf_ids)

    return NodeScoreReport(
        node_id=str(node["id"]),
        name=str(node["name"]),
        weight=float(node["weight"]),
        score=score,
        category=_infer_category(node),
        leaf_count=sum(child.leaf_count for child in child_reports),
        missing_leaf_ids=missing_leaf_ids,
        children=child_reports,
    )


def score_rubric_payload(
    payload: dict[str, Any], leaf_scores: Mapping[str, float]
) -> RubricScoreReport:
    """Aggregate leaf scores into the full weighted rubric score."""

    validation = validate_rubric_payload(payload)
    if not validation.is_valid:
        raise ValueError(
            "Rubric payload failed validation: " + "; ".join(validation.errors)
        )

    tree = extract_rubric_tree(payload)
    known_leaf_ids = set(collect_leaf_ids(tree))
    extra_leaf_ids = sorted(set(leaf_scores) - known_leaf_ids)
    root_report = _aggregate_node(tree, leaf_scores)
    category_scores = {
        child.category or child.name: child.score for child in root_report.children
    }
    return RubricScoreReport(
        paper_id=str(payload["paper_id"]),
        overall_score=root_report.score,
        category_scores=category_scores,
        missing_leaf_ids=sorted(root_report.missing_leaf_ids),
        extra_leaf_ids=extra_leaf_ids,
        root=root_report,
    )


def summarize_score_report(report: RubricScoreReport) -> str:
    """Render a compact summary string for logging or Inspect metadata."""

    category_summary = ", ".join(
        f"{category}={score:.3f}" for category, score in sorted(report.category_scores.items())
    )
    missing = f", missing_leaves={len(report.missing_leaf_ids)}" if report.missing_leaf_ids else ""
    extras = f", extra_leaf_scores={len(report.extra_leaf_ids)}" if report.extra_leaf_ids else ""
    return (
        f"overall={report.overall_score:.3f}, {category_summary}{missing}{extras}"
    )


def to_inspect_score(report: RubricScoreReport) -> InspectScore:
    """Convert a rubric score report into an Inspect-compatible score object."""

    return InspectScore(
        value=report.overall_score,
        explanation=summarize_score_report(report),
        metadata=report.to_dict(),
    )


def load_rubric_payload(paper_id: str) -> dict[str, Any]:
    """Load the rubric JSON for a given paper from the repo `papers/` tree."""

    rubric_path = PROJECT_ROOT / "papers" / paper_id / "rubric.json"
    with rubric_path.open() as handle:
        return json.load(handle)


def load_paper_summary(paper_id: str, *, max_chars: int = _JUDGE_MAX_PAPER_CHARS) -> str:
    """Load the paper-summary markdown with a conservative truncation."""

    paper_path = PROJECT_ROOT / "papers" / paper_id / "paper.md"
    if paper_path.exists():
        return paper_path.read_text()[:max_chars]
    return f"Paper `{paper_id}`: paper.md is not available to the judge."


try:  # pragma: no cover - optional Inspect-only integration
    from inspect_ai.model import get_model
    from inspect_ai.scorer import Target, mean, scorer, stderr
    from inspect_ai.solver import TaskState
    from inspect_ai.util import sandbox

    _HAS_INSPECT_SCORING = True
except ModuleNotFoundError:  # pragma: no cover - local fallback
    _HAS_INSPECT_SCORING = False


async def _artifact_presence_precheck(
    submission_dir: str = _PRECHECK_SUBMISSION_DIR,
    output_dir: str = _PRECHECK_OUTPUT_DIR,
    file_cap: int = _PRECHECK_FILE_CAP,
) -> dict[str, Any]:
    """Preflight scan of the sandbox to detect empty-scaffold submissions.

    Returns a dict with ``ok=True`` only when at least one Python file
    under ``submission_dir`` contains a non-trivial function body or
    module-level statement. Output artifact counts are recorded as
    forensic metadata but do not satisfy the gate on their own -- an
    agent that only downloaded data or produced READMEs has not done
    anything a grader would call "replication."

    Fails open on sandbox exceptions: the agent should not be penalised
    for a Docker hiccup during scoring.
    """

    env = sandbox()
    try:
        py_res = await env.exec(
            [
                "bash",
                "-lc",
                (
                    f"find {submission_dir} -maxdepth 4 -type f -name '*.py' "
                    f"2>/dev/null | head -{file_cap}"
                ),
            ]
        )
        py_files = [p for p in (py_res.stdout or "").splitlines() if p.strip()]
    except Exception as exc:  # pragma: no cover - sandbox is a live dependency
        return {
            "ok": True,
            "reason": f"sandbox unreachable ({type(exc).__name__}: {exc})",
            "fallback": "allow",
            "nontrivial_py_files": 0,
            "nontrivial_py_examples": [],
            "output_artifact_count": 0,
            "output_artifact_examples": [],
        }

    nontrivial = 0
    examples: list[str] = []
    for path in py_files[:file_cap]:
        try:
            src = await env.read_file(path)
        except Exception:
            continue
        if _has_nontrivial_body(src):
            nontrivial += 1
            if len(examples) < 3:
                examples.append(path)

    try:
        out_res = await env.exec(
            [
                "bash",
                "-lc",
                (
                    f"find {output_dir} -maxdepth 4 -type f "
                    f"! -name 'README*' ! -iname '*.md' 2>/dev/null | head -{file_cap}"
                ),
            ]
        )
        output_files = [p for p in (out_res.stdout or "").splitlines() if p.strip()]
    except Exception:
        output_files = []

    ok = nontrivial > 0
    reason = (
        None
        if ok
        else (
            "no Python file with a non-trivial function or module body was produced "
            f"under {submission_dir}"
        )
    )
    return {
        "ok": ok,
        "reason": reason,
        "nontrivial_py_files": nontrivial,
        "nontrivial_py_examples": examples,
        "output_artifact_count": len(output_files),
        "output_artifact_examples": output_files[:3],
    }


async def _collect_submission_context(max_chars: int = _JUDGE_MAX_SUBMISSION_CHARS) -> str:
    """Read a compact summary of the agent's submission artifacts from the sandbox."""

    env = sandbox()
    chunks: list[str] = []
    try:
        listing = await env.exec(
            [
                "bash",
                "-lc",
                (
                    "{ find /workspace/submission -maxdepth 4 -type f 2>/dev/null; "
                    "find /workspace/output -maxdepth 4 -type f 2>/dev/null; } | head -40"
                ),
            ]
        )
        file_list = (listing.stdout or "").strip()
    except Exception as exc:  # pragma: no cover - sandbox is a live dependency
        return f"(sandbox unreachable during scoring: {exc})"

    if not file_list:
        return "(no submission artifacts were produced in /workspace/submission or /workspace/output)"

    chunks.append("Submission file list:\n" + file_list)
    total = len(chunks[0])
    budget = max_chars - total

    for path in file_list.splitlines():
        path = path.strip()
        if not path or budget <= 0:
            break
        try:
            contents = await env.read_file(path)
        except Exception:
            continue
        header = f"\n--- {path} ---\n"
        snippet = contents[: max(budget - len(header), 0)]
        if not snippet:
            break
        chunks.append(header + snippet)
        budget -= len(header) + len(snippet)

    return "\n".join(chunks)


def _resolve_paper_id(state: Any) -> str:
    metadata = getattr(state, "metadata", None) or {}
    paper_id = metadata.get("paper_id")
    if paper_id:
        return str(paper_id)
    sample_id = getattr(state, "sample_id", None) or ""
    if isinstance(sample_id, str) and sample_id.endswith("_main"):
        return sample_id[: -len("_main")]
    raise ValueError(
        "Could not resolve paper_id from sample state; expected metadata.paper_id or '<paper>_main' sample id."
    )


async def _judge_leaf(
    judge: Any,
    leaf: dict[str, Any],
    *,
    paper_summary: str,
    reality_context: str,
) -> LeafJudgement:
    prompt = format_leaf_judge_prompt(
        leaf,
        paper_summary=paper_summary,
        reality_context=reality_context,
    )
    try:
        result = await judge.generate(prompt)
        raw = getattr(result, "completion", None) or str(result)
        return parse_leaf_judgement(raw, expected_leaf_id=leaf["id"])
    except Exception as exc:  # capture judge/model failures as leaf-level 0
        return LeafJudgement(
            leaf_id=str(leaf["id"]),
            expectations="",
            reality="",
            evidence_quote=f"judge_error: {type(exc).__name__}: {exc}",
            score=0,
            metadata={"judge_failure": True},
        )


if _HAS_INSPECT_SCORING:

    @scorer(metrics=[mean(), stderr()])
    def rubric_tree_scorer(
        judge_model: str = _JUDGE_DEFAULT_MODEL,
        *,
        leaf_limit: int | None = None,
    ):
        """Grade each rubric leaf with an LLM judge and aggregate to a weighted score.

        Each leaf is graded independently using the structured judge prompt
        (Expectations → Reality → Evidence Quote → Score). Leaf scores flow
        bottom-up through the rubric tree's existing weighted aggregation.

        Args:
          judge_model: Inspect-style model identifier for the judge.
          leaf_limit: Optional cap on leaves graded per sample. When provided,
            the remaining leaves are scored 0 with an informational evidence
            quote. Mainly useful for cheap smoke runs.
        """

        import os

        async def score(state: "TaskState", target: "Target"):  # type: ignore[name-defined]
            paper_id = _resolve_paper_id(state)
            rubric = load_rubric_payload(paper_id)
            paper_summary = load_paper_summary(paper_id)
            reality = await _collect_submission_context()

            tree = extract_rubric_tree(rubric)
            leaves = collect_leaf_nodes(tree)

            env_cap = os.getenv(_JUDGE_LEAF_LIMIT_ENV)
            cap = leaf_limit if leaf_limit is not None else (int(env_cap) if env_cap else None)

            precheck = await _artifact_presence_precheck()
            if not precheck["ok"]:
                # Scaffold-over-substance guard: no non-trivial Python file was produced
                # under /workspace/submission, so no leaf can claim executable backing.
                # Zero the rubric without billing a single judge call.
                judgements: list[LeafJudgement] = [
                    LeafJudgement(
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
                judge = get_model(judge_model)
                judgements = []
                for index, leaf in enumerate(leaves):
                    if cap is not None and index >= cap:
                        judgements.append(
                            LeafJudgement(
                                leaf_id=str(leaf["id"]),
                                expectations="",
                                reality="",
                                evidence_quote=f"skipped by leaf_limit={cap}",
                                score=0,
                                metadata={"skipped": True},
                            )
                        )
                        continue
                    judgements.append(
                        await _judge_leaf(
                            judge,
                            leaf,
                            paper_summary=paper_summary,
                            reality_context=reality,
                        )
                    )

            leaf_map = leaf_score_map_from_judgements(judgements)
            report = score_rubric_payload(rubric, leaf_map)
            base_score = to_inspect_score(report)

            metadata = dict(base_score.metadata or {})
            metadata.update(
                {
                    "paper_id": paper_id,
                    "judge_model": judge_model,
                    "leaf_limit": cap,
                    "leaves_graded": sum(
                        1
                        for j in judgements
                        if not j.metadata.get("skipped")
                        and not j.metadata.get("precheck_failed")
                    ),
                    "leaves_total": len(leaves),
                    "judge_failures": sum(
                        1 for j in judgements if j.metadata.get("judge_failure")
                    ),
                    "precheck": precheck,
                    "leaf_judgements": [j.to_dict() for j in judgements],
                }
            )
            return InspectScore(
                value=base_score.value,
                explanation=base_score.explanation,
                metadata=metadata,
            )

        return score

else:  # pragma: no cover - pure-library fallback so imports succeed outside Inspect

    def rubric_tree_scorer(*args: Any, **kwargs: Any):  # type: ignore[no-redef]
        raise RuntimeError(
            "inspect-ai is not installed; rubric_tree_scorer requires the Inspect AI runtime."
        )


__all__ = [
    "InspectScore",
    "NodeScoreReport",
    "RubricScoreReport",
    "_artifact_presence_precheck",
    "_has_nontrivial_body",
    "leaf_score_map_from_judgements",
    "load_paper_summary",
    "load_rubric_payload",
    "rubric_tree_scorer",
    "score_rubric_payload",
    "summarize_score_report",
    "to_inspect_score",
]
