"""Tests for rubric-tree scoring."""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import MagicMock, patch

from scireplicbench.judge import LeafJudgement
from scireplicbench.scorers import (
    _collect_submission_context,
    _enforce_leaf_evidence_policy,
    _focused_source_excerpt,
    _judge_leaf,
    _matching_evidence_sources,
    _reality_context_for_leaf,
    _skip_unhooked_genelab_sidecar_contents,
    _source_excerpt_for_leaf,
    leaf_score_map_from_judgements,
    score_rubric_payload,
    summarize_score_report,
    to_inspect_score,
)


def demo_rubric_payload() -> dict:
    return {
        "paper_id": "demo",
        "title": "Demo rubric",
        "total_leaf_nodes": 3,
        "rubric": {
            "id": "demo/rubric",
            "name": "Full Reproduction",
            "weight": 1.0,
            "is_leaf": False,
            "children": [
                {
                    "id": "demo/code_development",
                    "name": "Code Development",
                    "weight": 0.4,
                    "is_leaf": False,
                    "children": [
                        {
                            "id": "demo/code_development/shared_name",
                            "name": "Shared Name",
                            "weight": 1.0,
                            "is_leaf": True,
                            "requirement": "Write the script.",
                            "grading_notes": "Any honest implementation counts.",
                            "category": "code_development",
                        }
                    ],
                },
                {
                    "id": "demo/execution",
                    "name": "Execution",
                    "weight": 0.2,
                    "is_leaf": False,
                    "children": [
                        {
                            "id": "demo/execution/run_script",
                            "name": "Run Script",
                            "weight": 1.0,
                            "is_leaf": True,
                            "requirement": "Run the script.",
                            "grading_notes": "Must execute successfully.",
                            "category": "execution",
                        }
                    ],
                },
                {
                    "id": "demo/result_match",
                    "name": "Result Match",
                    "weight": 0.4,
                    "is_leaf": False,
                    "children": [
                        {
                            "id": "demo/result_match/shared_name",
                            "name": "Shared Name",
                            "weight": 1.0,
                            "is_leaf": True,
                            "requirement": "Recover the result.",
                            "grading_notes": "Use the reference metric.",
                            "category": "result_match",
                        }
                    ],
                },
            ],
        },
    }


class _FakeExecResult:
    def __init__(self, stdout: str) -> None:
        self.stdout = stdout


class _FakeContextSandbox:
    def __init__(self, *, listing: str, files: dict[str, str]) -> None:
        self.listing = listing
        self.files = files
        self.commands: list[list[str]] = []

    async def exec(self, argv):
        self.commands.append(list(argv))
        return _FakeExecResult(self.listing)

    async def read_file(self, path: str) -> str:
        if path not in self.files:
            raise FileNotFoundError(path)
        return self.files[path]


class ScorerTest(unittest.TestCase):
    def test_collect_submission_context_prioritizes_outputs_and_caps_each_file(self) -> None:
        listing = "\n".join(
            [
                "/workspace/output/agent/lomo/summary.tsv",
                "/workspace/output/agent/transfer/cross_tissue.tsv",
                "/workspace/output/agent/negative_controls/summary.tsv",
                "/workspace/output/submission_manifest.json",
                "/workspace/submission/main_analysis.py",
                "/workspace/submission/README.md",
            ]
        )
        fake = _FakeContextSandbox(
            listing=listing,
            files={
                "/workspace/output/agent/lomo/summary.tsv": (
                    "model\tfold\tauroc\n"
                    "random_forest\tfold_RR-1_test\t0.71\n"
                    + ("lomo-extra\n" * 80)
                ),
                "/workspace/output/agent/transfer/cross_tissue.tsv": (
                    "source_tissue\ttarget_tissue\tmodel\tauroc\n"
                    "A2_gastrocnemius_lomo\tA4_thymus_lomo\telasticnet\t0.62\n"
                ),
                "/workspace/output/agent/negative_controls/summary.tsv": (
                    "control\tmodel\tauroc\npermuted_labels\trandom_forest\t0.51\n"
                ),
                "/workspace/output/submission_manifest.json": (
                    '{"issues_found": ["missing train/test label files"]}\n'
                ),
                "/workspace/submission/main_analysis.py": (
                    "def align_datasets(train_X, test_X, train_y, test_y):\n"
                    "    return train_X, test_X, train_y, test_y\n"
                ),
                "/workspace/submission/README.md": "missing train/test label files\n" * 20,
            },
        )

        with patch(
            "scireplicbench.scorers.sandbox",
            new=MagicMock(return_value=fake),
            create=True,
        ):
            reality = asyncio.run(
                _collect_submission_context(max_chars=900, per_file_chars=120)
            )

        listing_cmd = fake.commands[0][-1]
        self.assertLess(
            listing_cmd.find("/workspace/output/agent/lomo/summary.tsv"),
            listing_cmd.find("find /workspace/submission"),
        )
        self.assertLess(
            reality.find("/workspace/output/agent/lomo/summary.tsv"),
            reality.find("/workspace/submission/main_analysis.py"),
        )
        self.assertIn("--- /workspace/output/agent/lomo/summary.tsv ---", reality)
        self.assertIn("--- /workspace/output/agent/transfer/cross_tissue.tsv ---", reality)
        self.assertIn("source_tissue\ttarget_tissue\tmodel\tauroc", reality)
        self.assertIn("--- /workspace/output/agent/negative_controls/summary.tsv ---", reality)
        self.assertIn("def align_datasets", reality)
        self.assertIn("[truncated]", reality)
        self.assertIn("/workspace/output/submission_manifest.json", reality)
        self.assertNotIn("--- /workspace/output/submission_manifest.json ---", reality)
        self.assertNotIn("missing train/test label files", reality)

    def test_collect_submission_context_skips_known_unhooked_genelab_sidecar_contents(self) -> None:
        listing = "\n".join(
            [
                "/workspace/output/agent/lomo/summary.tsv",
                "/workspace/output/submission_manifest.json",
                "/workspace/submission/main_analysis.py",
                "/workspace/submission/model_analysis.py",
            ]
        )
        fake = _FakeContextSandbox(
            listing=listing,
            files={
                "/workspace/output/agent/lomo/summary.tsv": "model\tauroc\nXGBoost\t0.82\n",
                "/workspace/output/submission_manifest.json": '{"paper_id": "genelab_benchmark"}\n',
                "/workspace/submission/main_analysis.py": (
                    "def _xgboost_scores():\n"
                    "    return 'canonical starter source'\n"
                ),
                "/workspace/submission/model_analysis.py": "SHALLOW_SIDE_CAR = True\n",
            },
        )

        with patch(
            "scireplicbench.scorers.sandbox",
            new=MagicMock(return_value=fake),
            create=True,
        ):
            reality = asyncio.run(
                _collect_submission_context(max_chars=1200, per_file_chars=200)
            )

        self.assertIn("/workspace/submission/model_analysis.py", reality)
        self.assertNotIn("--- /workspace/submission/model_analysis.py ---", reality)
        self.assertNotIn("SHALLOW_SIDE_CAR", reality)
        self.assertIn("canonical starter source", reality)

    def test_skip_unhooked_genelab_sidecar_requires_canonical_anchors(self) -> None:
        anchors = {
            "/workspace/output/agent/lomo/summary.tsv",
            "/workspace/output/submission_manifest.json",
            "/workspace/submission/main_analysis.py",
            "/workspace/submission/model_analysis.py",
        }

        self.assertTrue(
            _skip_unhooked_genelab_sidecar_contents(
                "/workspace/submission/model_analysis.py",
                anchors,
            )
        )
        self.assertFalse(
            _skip_unhooked_genelab_sidecar_contents(
                "/workspace/submission/main_analysis.py",
                anchors,
            )
        )
        self.assertFalse(
            _skip_unhooked_genelab_sidecar_contents(
                "/workspace/submission/helper.py",
                anchors,
            )
        )
        self.assertFalse(
            _skip_unhooked_genelab_sidecar_contents(
                "/workspace/submission/model_analysis.py",
                {"/workspace/submission/model_analysis.py"},
            )
        )

    def test_focused_source_excerpt_keeps_late_implementation_regions(self) -> None:
        source = "\n".join(
            [
                "import csv",
                *[f"# filler {index}" for index in range(200)],
                "def _build_transfer_rows(fold_data):",
                "    rows = []",
                "    return rows",
                *[f"# more filler {index}" for index in range(200)],
                "def main():",
                "    write_tsv(OUTPUT_ROOT / 'transfer/cross_tissue.tsv', TRANSFER_FIELDS, _build_transfer_rows([]))",
                "",
            ]
        )

        excerpt = _focused_source_excerpt(source, max_chars=800)
        self.assertIn("def _build_transfer_rows", excerpt)
        self.assertIn("transfer/cross_tissue.tsv", excerpt)
        self.assertLess(len(excerpt), len(source))

    def test_source_excerpt_for_leaf_centers_relevant_model_function(self) -> None:
        source = "\n".join(
            [
                "import csv",
                "def _elasticnet_scores(train_x, train_y, test_x):",
                "    from sklearn.linear_model import LogisticRegression",
                "    model = LogisticRegression(penalty='elasticnet', solver='saga')",
                "    return model.predict_proba(test_x)",
                *[f"# filler {index}" for index in range(300)],
                "def _random_forest_scores(train_x, train_y, test_x):",
                "    from sklearn.ensemble import RandomForestClassifier",
                "    model = RandomForestClassifier(n_estimators=100)",
                "    return model.predict_proba(test_x)",
                "",
            ]
        )

        excerpt = _source_excerpt_for_leaf(
            source,
            {
                "category": "code_development",
                "name": "Fit random forest",
                "requirement": "Implement a random-forest baseline.",
                "grading_notes": "The model should produce probability outputs for AUROC.",
            },
            max_chars=500,
        )

        self.assertIn("def _random_forest_scores", excerpt)
        self.assertIn("RandomForestClassifier", excerpt)
        self.assertIn("predict_proba", excerpt)
        self.assertNotIn("LogisticRegression", excerpt)

    def test_reality_context_for_leaf_filters_to_eligible_source_family(self) -> None:
        reality = (
            "Submission file list:\n"
            "/workspace/output/agent/lomo/summary.tsv\n"
            "/workspace/submission/main_analysis.py\n"
            "\n--- /workspace/output/agent/lomo/summary.tsv ---\n"
            "model\tauroc\nElasticNetLogReg\t0.72\n"
            "\n--- /workspace/submission/main_analysis.py ---\n"
            "model = LogisticRegression(penalty='elasticnet')\n"
        )

        code_context = _reality_context_for_leaf(
            {"category": "code_development"},
            reality,
        )
        self.assertIn("/workspace/submission/main_analysis.py", code_context)
        self.assertIn("LogisticRegression", code_context)
        self.assertNotIn("/workspace/output/agent/lomo/summary.tsv", code_context)

        execution_context = _reality_context_for_leaf(
            {"category": "execution"},
            reality,
        )
        self.assertIn("/workspace/output/agent/lomo/summary.tsv", execution_context)
        self.assertIn("ElasticNetLogReg\t0.72", execution_context)
        self.assertNotIn("/workspace/submission/main_analysis.py", execution_context)

    def test_reality_context_for_leaf_uses_leaf_focused_source(self) -> None:
        reality = (
            "Submission file list:\n"
            "/workspace/submission/main_analysis.py\n"
            "\n--- /workspace/submission/main_analysis.py ---\n"
            "def _elasticnet_scores(train_x, train_y, test_x):\n"
            "    from sklearn.linear_model import LogisticRegression\n"
            "    model = LogisticRegression(penalty='elasticnet', solver='saga')\n"
            "    return model.predict_proba(test_x)\n"
            + "\n".join(f"# filler {index}" for index in range(300))
            + "\n"
            "def _random_forest_scores(train_x, train_y, test_x):\n"
            "    from sklearn.ensemble import RandomForestClassifier\n"
            "    model = RandomForestClassifier(n_estimators=100)\n"
            "    return model.predict_proba(test_x)\n"
        )

        code_context = _reality_context_for_leaf(
            {
                "category": "code_development",
                "name": "Fit random forest",
                "requirement": "Implement a random-forest baseline.",
            },
            reality,
        )

        self.assertIn("def _random_forest_scores", code_context)
        self.assertIn("RandomForestClassifier", code_context)
        self.assertNotIn("LogisticRegression", code_context)

    def test_judge_leaf_retries_once_after_parse_failure(self) -> None:
        class StubJudge:
            def __init__(self) -> None:
                self.calls = 0
                self.prompts: list[str] = []

            async def generate(self, prompt: str):
                self.prompts.append(prompt)
                self.calls += 1
                if self.calls == 1:
                    return type(
                        "JudgeResult",
                        (),
                        {
                            "completion": (
                                '{"leaf_id":"demo/result_match/leaf","expectations":"Recover the result.",'
                                '"reality":"Observed the metric.","evidence_quote":"top20_overlap=0.90",'
                                '"score":1'
                            )
                        },
                    )()
                return type(
                    "JudgeResult",
                    (),
                    {
                        "completion": (
                            '{"leaf_id":"demo/result_match/leaf","expectations":"Recover the result.",'
                            '"reality":"Observed the metric.","evidence_quote":"top20_overlap=0.90","score":1}'
                        )
                    },
                )()

        stub = StubJudge()
        judgement = asyncio.run(
            _judge_leaf(
                stub,
                {
                    "id": "demo/result_match/leaf",
                    "category": "result_match",
                    "requirement": "Recover the result.",
                    "grading_notes": "Use the output artifact.",
                },
                paper_summary="Short paper summary.",
                reality_context="top20_overlap=0.90",
            )
        )
        self.assertEqual(judgement.score, 1)
        self.assertEqual(judgement.metadata["judge_attempts"], 2)
        self.assertIn("Previous judge response was invalid", stub.prompts[1])
        self.assertIn("no_valid_evidence", stub.prompts[1])

    def test_leaf_score_map_from_judgements(self) -> None:
        judgements = [
            LeafJudgement("demo/code_development/shared_name", "exp", "real", "q", 1),
            LeafJudgement("demo/result_match/shared_name", "exp", "real", "q", 0),
        ]
        self.assertEqual(
            leaf_score_map_from_judgements(judgements),
            {
                "demo/code_development/shared_name": 1.0,
                "demo/result_match/shared_name": 0.0,
            },
        )

    def test_score_rubric_uses_leaf_ids_not_names(self) -> None:
        report = score_rubric_payload(
            demo_rubric_payload(),
            {
                "demo/code_development/shared_name": 1.0,
                "demo/execution/run_script": 1.0,
                "demo/result_match/shared_name": 0.0,
            },
        )
        self.assertAlmostEqual(report.overall_score, 0.6)
        self.assertEqual(report.missing_leaf_ids, [])
        self.assertEqual(report.extra_leaf_ids, [])
        self.assertEqual(report.category_scores["code_development"], 1.0)
        self.assertEqual(report.category_scores["result_match"], 0.0)
        self.assertIn("overall=0.600", summarize_score_report(report))

    def test_missing_and_extra_leaf_scores_are_reported(self) -> None:
        report = score_rubric_payload(
            demo_rubric_payload(),
            {
                "demo/code_development/shared_name": 1.0,
                "demo/unknown_leaf": 1.0,
            },
        )
        self.assertIn("demo/execution/run_script", report.missing_leaf_ids)
        self.assertIn("demo/result_match/shared_name", report.missing_leaf_ids)
        self.assertEqual(report.extra_leaf_ids, ["demo/unknown_leaf"])

    def test_to_inspect_score(self) -> None:
        report = score_rubric_payload(
            demo_rubric_payload(),
            {
                "demo/code_development/shared_name": 1.0,
                "demo/execution/run_script": 1.0,
                "demo/result_match/shared_name": 1.0,
            },
        )
        inspect_score = to_inspect_score(report)
        self.assertAlmostEqual(inspect_score.value, 1.0)
        self.assertIsNotNone(inspect_score.metadata)

    def test_matching_evidence_sources_finds_readme_and_output_paths(self) -> None:
        reality = (
            "Submission file list:\n"
            "/workspace/submission/README.md\n"
            "/workspace/submission/pipeline.py\n"
            "/workspace/output/results.csv\n"
            "\n--- /workspace/submission/README.md ---\n"
            "This README provides instructions on running the workflow.\n"
            "\n--- /workspace/submission/pipeline.py ---\n"
            "sq.gr.spatial_neighbors(adata)\n"
        )
        matches = _matching_evidence_sources(
            reality,
            "This README provides instructions on running the workflow.",
        )
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].path, "/workspace/submission/README.md")

        output_matches = _matching_evidence_sources(
            reality,
            "/workspace/output/results.csv",
        )
        self.assertEqual(len(output_matches), 1)
        self.assertEqual(output_matches[0].source_type, "file_list")

    def test_code_development_pass_is_zeroed_when_evidence_only_from_readme(self) -> None:
        reality = (
            "Submission file list:\n"
            "/workspace/submission/README.md\n"
            "/workspace/submission/pipeline.py\n"
            "\n--- /workspace/submission/README.md ---\n"
            "This README provides instructions on running the Squidpy workflow.\n"
            "\n--- /workspace/submission/pipeline.py ---\n"
            "pass\n"
        )
        leaf = {
            "id": "demo/code_development/leaf",
            "category": "code_development",
        }
        judgement = LeafJudgement(
            leaf_id="demo/code_development/leaf",
            expectations="Write the script.",
            reality="Observed a README.",
            evidence_quote="This README provides instructions on running the Squidpy workflow.",
            score=1,
        )

        hardened = _enforce_leaf_evidence_policy(
            leaf,
            judgement,
            reality_context=reality,
        )
        self.assertEqual(hardened.score, 0)
        self.assertIn("README-style prose", hardened.evidence_quote)
        self.assertEqual(
            hardened.metadata["original_evidence_quote"],
            "This README provides instructions on running the Squidpy workflow.",
        )

    def test_code_development_pass_survives_non_markdown_submission_code(self) -> None:
        reality = (
            "Submission file list:\n"
            "/workspace/submission/pipeline.py\n"
            "\n--- /workspace/submission/pipeline.py ---\n"
            "sq.gr.spatial_neighbors(adata, coord_type='grid')\n"
        )
        leaf = {
            "id": "demo/code_development/leaf",
            "category": "code_development",
        }
        judgement = LeafJudgement(
            leaf_id="demo/code_development/leaf",
            expectations="Write the script.",
            reality="Observed code.",
            evidence_quote="sq.gr.spatial_neighbors(adata, coord_type='grid')",
            score=1,
        )

        hardened = _enforce_leaf_evidence_policy(
            leaf,
            judgement,
            reality_context=reality,
        )
        self.assertEqual(hardened.score, 1)
        self.assertEqual(
            hardened.metadata["evidence_sources"][0]["path"],
            "/workspace/submission/pipeline.py",
        )

    def test_code_development_pass_survives_unindented_multiline_code_quote(self) -> None:
        reality = (
            "Submission file list:\n"
            "/workspace/submission/main_analysis.py\n"
            "\n--- /workspace/submission/main_analysis.py ---\n"
            "        shuffled_aurocs: list[float] = []\n"
            "        for repeat in range(NEGATIVE_CONTROL_REPEATS):\n"
            "            shuffled = list(fold.train_y)\n"
            "            rng.shuffle(shuffled)\n"
        )
        leaf = {
            "id": "demo/code_development/leaf",
            "category": "code_development",
        }
        judgement = LeafJudgement(
            leaf_id="demo/code_development/leaf",
            expectations="Implement label permutation controls.",
            reality="Observed label permutation code.",
            evidence_quote=(
                "shuffled_aurocs: list[float] = []\n"
                "for repeat in range(NEGATIVE_CONTROL_REPEATS):\n"
                "shuffled = list(fold.train_y)\n"
                "rng.shuffle(shuffled)"
            ),
            score=1,
        )

        hardened = _enforce_leaf_evidence_policy(
            leaf,
            judgement,
            reality_context=reality,
        )
        self.assertEqual(hardened.score, 1)

    def test_code_development_pass_survives_compacted_multiline_constructor_quote(self) -> None:
        reality = (
            "Submission file list:\n"
            "/workspace/submission/main_analysis.py\n"
            "\n--- /workspace/submission/main_analysis.py ---\n"
            "    model = LogisticRegression(\n"
            "        penalty=\"elasticnet\",\n"
            "        solver=\"saga\",\n"
            "        l1_ratio=0.5,\n"
            "        C=1.0,\n"
            "        class_weight=\"balanced\",\n"
            "        max_iter=500,\n"
            "        tol=1e-3,\n"
            "        random_state=42,\n"
            "    )\n"
        )
        leaf = {
            "id": "demo/code_development/leaf",
            "category": "code_development",
        }
        judgement = LeafJudgement(
            leaf_id="demo/code_development/leaf",
            expectations="Fit elastic-net logistic regression.",
            reality="Observed elastic-net LogisticRegression code.",
            evidence_quote=(
                'model = LogisticRegression(penalty="elasticnet", solver="saga", '
                'l1_ratio=0.5, C=1.0, class_weight="balanced", max_iter=500, '
                'tol=1e-3, random_state=42)'
            ),
            score=1,
        )

        hardened = _enforce_leaf_evidence_policy(
            leaf,
            judgement,
            reality_context=reality,
        )
        self.assertEqual(hardened.score, 1)

    def test_code_development_pass_survives_trailing_semicolon_quote_artifact(self) -> None:
        reality = (
            "Submission file list:\n"
            "/workspace/submission/main_analysis.py\n"
            "\n--- /workspace/submission/main_analysis.py ---\n"
            "    model = RandomForestClassifier(\n"
            "        n_estimators=24,\n"
            "        max_features=\"sqrt\",\n"
            "        class_weight=\"balanced_subsample\",\n"
            "        random_state=42,\n"
            "    )\n"
        )
        leaf = {
            "id": "demo/code_development/leaf",
            "category": "code_development",
        }
        judgement = LeafJudgement(
            leaf_id="demo/code_development/leaf",
            expectations="Fit random forest baseline.",
            reality="Observed RandomForestClassifier code.",
            evidence_quote=(
                'model = RandomForestClassifier(n_estimators=24, max_features="sqrt", '
                'class_weight="balanced_subsample", random_state=42);'
            ),
            score=1,
        )

        hardened = _enforce_leaf_evidence_policy(
            leaf,
            judgement,
            reality_context=reality,
        )
        self.assertEqual(hardened.score, 1)

    def test_code_development_pass_survives_requirements_txt(self) -> None:
        reality = (
            "Submission file list:\n"
            "/workspace/submission/requirements.txt\n"
            "\n--- /workspace/submission/requirements.txt ---\n"
            "squidpy==1.6.0\n"
        )
        leaf = {
            "id": "demo/code_development/leaf",
            "category": "code_development",
        }
        judgement = LeafJudgement(
            leaf_id="demo/code_development/leaf",
            expectations="Pin the dependency version.",
            reality="Observed dependency pin.",
            evidence_quote="squidpy==1.6.0",
            score=1,
        )

        hardened = _enforce_leaf_evidence_policy(
            leaf,
            judgement,
            reality_context=reality,
        )
        self.assertEqual(hardened.score, 1)
        self.assertEqual(
            hardened.metadata["evidence_sources"][0]["path"],
            "/workspace/submission/requirements.txt",
        )

    def test_execution_pass_survives_output_artifact_evidence(self) -> None:
        reality = (
            "Submission file list:\n"
            "/workspace/output/results.csv\n"
            "\n--- /workspace/output/results.csv ---\n"
            "command exited with status 0\n"
        )
        leaf = {
            "id": "demo/execution/leaf",
            "category": "execution",
        }
        judgement = LeafJudgement(
            leaf_id="demo/execution/leaf",
            expectations="Run the pipeline.",
            reality="Observed output artifact.",
            evidence_quote="command exited with status 0",
            score=1,
        )

        hardened = _enforce_leaf_evidence_policy(
            leaf,
            judgement,
            reality_context=reality,
        )
        self.assertEqual(hardened.score, 1)

    def test_execution_pass_survives_output_block_header_plus_content_quote(self) -> None:
        reality = (
            "Submission file list:\n"
            "/workspace/output/results.tsv\n"
            "\n--- /workspace/output/results.tsv ---\n"
            "metric\tvalue\n"
            "auroc\t0.91\n"
        )
        leaf = {
            "id": "demo/execution/leaf",
            "category": "execution",
        }
        judgement = LeafJudgement(
            leaf_id="demo/execution/leaf",
            expectations="Write the AUROC table.",
            reality="Observed an AUROC output table.",
            evidence_quote="--- /workspace/output/results.tsv ---\nmetric\tvalue\nauroc\t0.91",
            score=1,
        )

        hardened = _enforce_leaf_evidence_policy(
            leaf,
            judgement,
            reality_context=reality,
        )
        self.assertEqual(hardened.score, 1)
        self.assertEqual(
            hardened.metadata["evidence_sources"][0]["path"],
            "/workspace/output/results.tsv",
        )

    def test_execution_pass_survives_whitespace_normalized_tsv_header_quote(self) -> None:
        reality = (
            "Submission file list:\n"
            "/workspace/output/agent/lomo/summary.tsv\n"
            "\n--- /workspace/output/agent/lomo/summary.tsv ---\n"
            "tissue\tfold\theldout_mission\tmodel\tstatus\tauroc\tci_lower\tci_upper\n"
            "A2\tfold_RR-1_test\tRR-1\tElasticNetLogReg\tok\t0.7310\t0.6020\t0.8420\n"
        )
        leaf = {
            "id": "demo/execution/leaf",
            "category": "execution",
        }
        judgement = LeafJudgement(
            leaf_id="demo/execution/leaf",
            expectations="Write a LOMO AUROC table.",
            reality="Observed LOMO summary TSV.",
            evidence_quote="tissue fold heldout_mission model status auroc ci_lower ci_upper",
            score=1,
        )

        hardened = _enforce_leaf_evidence_policy(
            leaf,
            judgement,
            reality_context=reality,
        )
        self.assertEqual(hardened.score, 1)
        self.assertEqual(
            hardened.metadata["evidence_sources"][0]["path"],
            "/workspace/output/agent/lomo/summary.tsv",
        )

    def test_execution_header_only_quote_is_zeroed(self) -> None:
        reality = (
            "Submission file list:\n"
            "/workspace/output/results.tsv\n"
            "\n--- /workspace/output/results.tsv ---\n"
            "metric\tvalue\n"
            "auroc\t0.91\n"
        )
        leaf = {
            "id": "demo/execution/leaf",
            "category": "execution",
        }
        judgement = LeafJudgement(
            leaf_id="demo/execution/leaf",
            expectations="Write the AUROC table.",
            reality="Observed an output table path.",
            evidence_quote="--- /workspace/output/results.tsv ---",
            score=1,
        )

        hardened = _enforce_leaf_evidence_policy(
            leaf,
            judgement,
            reality_context=reality,
        )
        self.assertEqual(hardened.score, 0)
        self.assertIn("not found verbatim", hardened.evidence_quote)

    def test_execution_pass_survives_output_metric_content_when_not_comparator_style(self) -> None:
        reality = (
            "Submission file list:\n"
            "/workspace/output/geary.txt\n"
            "\n--- /workspace/output/geary.txt ---\n"
            "geary_c=0.12\n"
        )
        leaf = {
            "id": "demo/execution/leaf",
            "category": "execution",
        }
        judgement = LeafJudgement(
            leaf_id="demo/execution/leaf",
            expectations="Write the analysis output.",
            reality="Observed output metric artifact.",
            evidence_quote="geary_c=0.12",
            score=1,
        )

        hardened = _enforce_leaf_evidence_policy(
            leaf,
            judgement,
            reality_context=reality,
        )
        self.assertEqual(hardened.score, 1)

    def test_execution_path_only_is_zeroed_without_output_contents(self) -> None:
        reality = "Submission file list:\n/workspace/output/results.csv\n"
        leaf = {
            "id": "demo/execution/leaf",
            "category": "execution",
        }
        judgement = LeafJudgement(
            leaf_id="demo/execution/leaf",
            expectations="Run the pipeline.",
            reality="Observed output artifact.",
            evidence_quote="/workspace/output/results.csv",
            score=1,
        )

        hardened = _enforce_leaf_evidence_policy(
            leaf,
            judgement,
            reality_context=reality,
        )
        self.assertEqual(hardened.score, 0)
        self.assertIn("bare output-file path", hardened.evidence_quote)

    def test_execution_hidden_reference_comparator_metric_is_zeroed(self) -> None:
        reality = (
            "Submission file list:\n"
            "/workspace/output/geary_metrics.txt\n"
            "\n--- /workspace/output/geary_metrics.txt ---\n"
            "geary_top20_rbo=0.90\n"
        )
        leaf = {
            "id": "demo/execution/leaf",
            "category": "execution",
        }
        judgement = LeafJudgement(
            leaf_id="demo/execution/leaf",
            expectations="Write the analysis output.",
            reality="Observed benchmark-comparison metric in output file.",
            evidence_quote="geary_top20_rbo=0.90",
            score=1,
        )

        hardened = _enforce_leaf_evidence_policy(
            leaf,
            judgement,
            reality_context=reality,
        )
        self.assertEqual(hardened.score, 0)
        self.assertIn("hidden-reference comparison metrics", hardened.evidence_quote)

    def test_execution_path_only_is_zeroed_even_when_output_file_has_contents(self) -> None:
        reality = (
            "Submission file list:\n"
            "/workspace/output/results.csv\n"
            "\n--- /workspace/output/results.csv ---\n"
            "command exited with status 0\n"
        )
        leaf = {
            "id": "demo/execution/leaf",
            "category": "execution",
        }
        judgement = LeafJudgement(
            leaf_id="demo/execution/leaf",
            expectations="Run the pipeline.",
            reality="Observed output artifact path.",
            evidence_quote="/workspace/output/results.csv",
            score=1,
        )

        hardened = _enforce_leaf_evidence_policy(
            leaf,
            judgement,
            reality_context=reality,
        )
        self.assertEqual(hardened.score, 0)
        self.assertIn("bare output-file path", hardened.evidence_quote)

    def test_execution_path_only_is_zeroed_when_path_reappears_in_output_manifest(self) -> None:
        reality = (
            "Submission file list:\n"
            "/workspace/output/results.csv\n"
            "/workspace/output/submission_manifest.json\n"
            "\n--- /workspace/output/submission_manifest.json ---\n"
            "{\"output_files\": [\"/workspace/output/results.csv\"]}\n"
        )
        leaf = {
            "id": "demo/execution/leaf",
            "category": "execution",
        }
        judgement = LeafJudgement(
            leaf_id="demo/execution/leaf",
            expectations="Run the pipeline.",
            reality="Observed output artifact path recorded in a manifest.",
            evidence_quote="/workspace/output/results.csv",
            score=1,
        )

        hardened = _enforce_leaf_evidence_policy(
            leaf,
            judgement,
            reality_context=reality,
        )
        self.assertEqual(hardened.score, 0)
        self.assertIn("bare output-file path", hardened.evidence_quote)

    def test_execution_pass_is_zeroed_when_quote_not_in_reality_context(self) -> None:
        reality = "Submission file list:\n/workspace/output/results.csv\n"
        leaf = {
            "id": "demo/execution/leaf",
            "category": "execution",
        }
        judgement = LeafJudgement(
            leaf_id="demo/execution/leaf",
            expectations="Run the pipeline.",
            reality="Observed output artifact.",
            evidence_quote="command exited with status 0",
            score=1,
        )

        hardened = _enforce_leaf_evidence_policy(
            leaf,
            judgement,
            reality_context=reality,
        )
        self.assertEqual(hardened.score, 0)
        self.assertIn("not found verbatim", hardened.evidence_quote)

    def test_result_match_pass_is_zeroed_when_evidence_only_in_submission(self) -> None:
        reality = (
            "Submission file list:\n"
            "/workspace/submission/pipeline.py\n"
            "\n--- /workspace/submission/pipeline.py ---\n"
            "# top20_overlap=0.90\n"
        )
        leaf = {
            "id": "demo/result_match/leaf",
            "category": "result_match",
        }
        judgement = LeafJudgement(
            leaf_id="demo/result_match/leaf",
            expectations="Recover the ranked genes.",
            reality="Observed a claimed metric in submission code.",
            evidence_quote="top20_overlap=0.90",
            score=1,
        )

        hardened = _enforce_leaf_evidence_policy(
            leaf,
            judgement,
            reality_context=reality,
        )
        self.assertEqual(hardened.score, 0)
        self.assertIn("submission-side claims", hardened.evidence_quote)

    def test_result_match_pass_survives_output_metric_content(self) -> None:
        reality = (
            "Submission file list:\n"
            "/workspace/output/metrics.txt\n"
            "\n--- /workspace/output/metrics.txt ---\n"
            "top20_overlap=0.90\n"
        )
        leaf = {
            "id": "demo/result_match/leaf",
            "category": "result_match",
        }
        judgement = LeafJudgement(
            leaf_id="demo/result_match/leaf",
            expectations="Recover the ranked genes.",
            reality="Observed output metric.",
            evidence_quote="top20_overlap=0.90",
            score=1,
        )

        hardened = _enforce_leaf_evidence_policy(
            leaf,
            judgement,
            reality_context=reality,
        )
        self.assertEqual(hardened.score, 1)
        self.assertEqual(
            hardened.metadata["evidence_sources"][0]["path"],
            "/workspace/output/metrics.txt",
        )

    def test_backtick_wrapped_quote_matches_submission_code(self) -> None:
        reality = (
            "Submission file list:\n"
            "/workspace/submission/pipeline.py\n"
            "\n--- /workspace/submission/pipeline.py ---\n"
            "sq.gr.spatial_neighbors(adata)\n"
        )
        leaf = {
            "id": "demo/code_development/leaf",
            "category": "code_development",
        }
        judgement = LeafJudgement(
            leaf_id="demo/code_development/leaf",
            expectations="Write the script.",
            reality="Observed code.",
            evidence_quote="`sq.gr.spatial_neighbors(adata)`",
            score=1,
        )

        hardened = _enforce_leaf_evidence_policy(
            leaf,
            judgement,
            reality_context=reality,
        )
        self.assertEqual(hardened.score, 1)


if __name__ == "__main__":
    unittest.main()
