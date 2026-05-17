"""Tests for rubric-tree scoring."""

from __future__ import annotations

import asyncio
import json
import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from scireplicbench.judge import LeafJudgement
from scireplicbench import scorers
from scireplicbench.scorers import (
    _judge_leaf,
    _deterministic_code_development_judgement,
    _deterministic_execution_judgement,
    _deterministic_leaf_judgement,
    _deterministic_result_match_judgement,
    _enforce_leaf_evidence_policy,
    _matching_evidence_sources,
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


class ScorerTest(unittest.TestCase):
    def test_judge_leaf_retries_once_after_parse_failure(self) -> None:
        class StubJudge:
            def __init__(self) -> None:
                self.calls = 0

            async def generate(self, prompt: str):
                self.calls += 1
                if self.calls == 1:
                    return type(
                        "JudgeResult",
                        (),
                        {
                            "completion": (
                                '{"leaf_id":"demo/result_match/leaf","expectations":"Recover the result.",'
                                '"reality":"Observed the metric.","evidence_quote":"","score":0}'
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

        judgement = asyncio.run(
            _judge_leaf(
                StubJudge(),
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
        # Raw weighted score is 0.6 but result_match=0 triggers severity cap
        # at 0.5 — the headline overall reflects the catastrophic failure.
        self.assertAlmostEqual(report.raw_overall_score, 0.6)
        self.assertEqual(report.overall_score, 0.5)
        self.assertIn(
            "result_match_below_0_30_caps_overall_at_0_50",
            report.severity_caps_applied,
        )
        self.assertEqual(report.missing_leaf_ids, [])
        self.assertEqual(report.extra_leaf_ids, [])
        self.assertEqual(report.category_scores["code_development"], 1.0)
        self.assertEqual(report.category_scores["result_match"], 0.0)
        self.assertIn("overall=0.500", summarize_score_report(report))
        self.assertIn("raw_overall=0.600", summarize_score_report(report))

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

    def test_deterministic_result_match_scores_json_shape_without_judge(self) -> None:
        leaf = {
            "id": "demo/result_match/shared_name",
            "category": "result_match",
            "requirement": "Recover the result.",
        }
        reference = {
            "strict_result_match": True,
            "leaves": {
                "demo/result_match/shared_name": {
                    "metric": "json_shape_within_tolerance",
                    "artifact": "/workspace/output/agent/dataset_manifest.json",
                    "json_path": ["shape"],
                    "expected": [100, 200],
                    "tolerance_pct": 1.0,
                }
            },
        }

        with patch.object(scorers, "load_result_match_reference", return_value=reference), patch.object(
            scorers,
            "_read_sandbox_file",
            AsyncMock(return_value='{"shape": [101, 200]}'),
        ):
            judgement = asyncio.run(
                _deterministic_result_match_judgement(leaf, paper_id="demo")
            )

        self.assertIsNotNone(judgement)
        assert judgement is not None
        self.assertEqual(judgement.score, 1)
        self.assertTrue(judgement.metadata["deterministic_result_match"])
        self.assertEqual(judgement.metadata["metric"], "json_shape_within_tolerance")

    def test_strict_result_match_missing_reference_scores_zero(self) -> None:
        leaf = {
            "id": "demo/result_match/missing",
            "category": "result_match",
            "requirement": "Recover the result.",
        }
        with patch.object(
            scorers,
            "load_result_match_reference",
            return_value={"strict_result_match": True, "leaves": {}},
        ):
            judgement = asyncio.run(
                _deterministic_result_match_judgement(leaf, paper_id="demo")
            )

        self.assertIsNotNone(judgement)
        assert judgement is not None
        self.assertEqual(judgement.score, 0)
        self.assertTrue(judgement.metadata["deterministic_reference_missing"])

    def test_deterministic_execution_scores_tsv_schema_without_judge(self) -> None:
        leaf = {
            "id": "demo/execution/table_written",
            "category": "execution",
            "requirement": "Write the table.",
        }
        reference = {
            "strict_execution": True,
            "leaves": {
                "demo/execution/table_written": {
                    "metric": "tsv_schema",
                    "artifact": "/workspace/output/agent/results.tsv",
                    "required_columns": ["gene", "score"],
                    "min_rows": 2,
                }
            },
        }
        with patch.object(scorers, "load_execution_reference", return_value=reference), patch.object(
            scorers,
            "_read_sandbox_file",
            AsyncMock(return_value="gene\tscore\nA\t1\nB\t2\n"),
        ):
            judgement = asyncio.run(
                _deterministic_execution_judgement(leaf, paper_id="demo")
            )

        self.assertIsNotNone(judgement)
        assert judgement is not None
        self.assertEqual(judgement.score, 1)
        self.assertTrue(judgement.metadata["deterministic_execution"])
        self.assertEqual(judgement.metadata["metric"], "tsv_schema")

    def test_strict_execution_missing_reference_scores_zero(self) -> None:
        leaf = {
            "id": "demo/execution/missing",
            "category": "execution",
            "requirement": "Write outputs.",
        }
        with patch.object(
            scorers,
            "load_execution_reference",
            return_value={"strict_execution": True, "leaves": {}},
        ):
            judgement = asyncio.run(
                _deterministic_execution_judgement(leaf, paper_id="demo")
            )

        self.assertIsNotNone(judgement)
        assert judgement is not None
        self.assertEqual(judgement.score, 0)
        self.assertTrue(judgement.metadata["deterministic_execution_reference_missing"])

    def test_deterministic_code_development_scores_source_patterns(self) -> None:
        leaf = {
            "id": "demo/code_development/source_leaf",
            "category": "code_development",
            "requirement": "Implement Squidpy source.",
        }
        reference = {
            "strict_code_development": True,
            "starter_assisted": True,
            "starter_profile": "demo_profile",
            "source_candidates": ["/workspace/submission/pipeline.py"],
            "leaves": {
                "demo/code_development/source_leaf": {
                    "metric": "source_patterns",
                    "all_literals": ["sq.gr.spatial_neighbors", "coord_type=\"grid\""],
                    "all_ast_calls": ["sq.gr.spatial_neighbors"],
                    "any_literals": ["sq.gr.nhood_enrichment", "sq.gr.co_occurrence"],
                }
            },
        }
        source = (
            "import squidpy as sq\n"
            "sq.gr.spatial_neighbors(adata, coord_type=\"grid\")\n"
            "sq.gr.nhood_enrichment(adata, cluster_key=\"cluster\")\n"
        )
        with patch.object(
            scorers,
            "load_code_development_reference",
            return_value=reference,
        ), patch.object(scorers, "_read_sandbox_file", AsyncMock(return_value=source)):
            judgement = asyncio.run(
                _deterministic_code_development_judgement(leaf, paper_id="demo")
            )

        self.assertIsNotNone(judgement)
        assert judgement is not None
        self.assertEqual(judgement.score, 1)
        self.assertTrue(judgement.metadata["deterministic_code_development"])
        self.assertTrue(judgement.metadata["starter_assisted"])

    def test_direct_svg_visualization_source_patterns_do_not_require_matplotlib(self) -> None:
        leaf = {
            "id": "demo/code_development/generate_spatial_visualizations",
            "category": "code_development",
            "requirement": "Generate spatial visualization artifacts.",
        }
        reference = {
            "strict_code_development": True,
            "source_candidates": ["/workspace/submission/pipeline.py"],
            "leaves": {
                "demo/code_development/generate_spatial_visualizations": {
                    "metric": "source_patterns",
                    "all_literals": [
                        "spatial_stats_plot.svg",
                        "marker_localization.svg",
                    ],
                }
            },
        }
        source = (
            "from pathlib import Path\n"
            "Path('visualizations/spatial_stats_plot.svg').write_text('<svg><title>Top Moran</title></svg>')\n"
            "Path('visualizations/marker_localization.svg').write_text('<svg><title>Marker localization</title></svg>')\n"
        )
        with patch.object(
            scorers,
            "load_code_development_reference",
            return_value=reference,
        ), patch.object(scorers, "_read_sandbox_file", AsyncMock(return_value=source)):
            judgement = asyncio.run(
                _deterministic_code_development_judgement(leaf, paper_id="demo")
            )

        self.assertIsNotNone(judgement)
        assert judgement is not None
        self.assertEqual(judgement.score, 1)
        self.assertEqual(judgement.metadata["expected"].get("any_ast_calls", []), [])

    def test_match_literals_accepts_flipped_quote_style(self) -> None:
        leaf = {
            "id": "demo/code_development/source_leaf",
            "category": "code_development",
            "requirement": "Implement Squidpy source.",
        }
        reference = {
            "strict_code_development": True,
            "source_candidates": ["/workspace/submission/pipeline.py"],
            "leaves": {
                "demo/code_development/source_leaf": {
                    "metric": "source_patterns",
                    "all_literals": [
                        "coord_type=\"grid\"",
                        "mode=\"L\"",
                        "method=\"watershed\"",
                    ],
                }
            },
        }
        # Source uses single quotes throughout; comparator must still match.
        source = (
            "import squidpy as sq\n"
            "sq.gr.spatial_neighbors(adata, coord_type='grid')\n"
            "sq.gr.ripley(adata, mode='L')\n"
            "sq.im.segment(image, method='watershed')\n"
        )
        with patch.object(
            scorers,
            "load_code_development_reference",
            return_value=reference,
        ), patch.object(scorers, "_read_sandbox_file", AsyncMock(return_value=source)):
            judgement = asyncio.run(
                _deterministic_code_development_judgement(leaf, paper_id="demo")
            )

        self.assertIsNotNone(judgement)
        assert judgement is not None
        self.assertEqual(judgement.score, 1)

    def test_severity_caps_dont_fire_when_categories_healthy(self) -> None:
        from scireplicbench.scorers import _apply_severity_caps

        capped, caps = _apply_severity_caps(
            0.935,
            {"code_development": 1.0, "execution": 0.933, "result_match": 0.892},
        )
        self.assertEqual(capped, 0.935)
        self.assertEqual(caps, [])

    def test_severity_caps_fire_when_result_match_catastrophic(self) -> None:
        from scireplicbench.scorers import _apply_severity_caps

        # code=1, exec=1, result=0 → weighted overall = 0.55, but result=0
        # is catastrophic so headline must cap at 0.50.
        capped, caps = _apply_severity_caps(
            0.55,
            {"code_development": 1.0, "execution": 1.0, "result_match": 0.0},
        )
        self.assertEqual(capped, 0.50)
        self.assertIn("result_match_below_0_30_caps_overall_at_0_50", caps)
        # The 0.50 trigger threshold also fires (0.0 < 0.50) but the more
        # aggressive 0.30 cap dominates.
        self.assertIn("result_match_below_0_50_caps_overall_at_0_70", caps)

    def test_severity_caps_fire_when_execution_below_threshold(self) -> None:
        from scireplicbench.scorers import _apply_severity_caps

        capped, caps = _apply_severity_caps(
            0.50,
            {"code_development": 1.0, "execution": 0.0, "result_match": 0.5},
        )
        self.assertEqual(capped, 0.40)
        self.assertIn("execution_below_0_30_caps_overall_at_0_40", caps)

    def test_severity_caps_use_lowest_when_multiple_fire(self) -> None:
        from scireplicbench.scorers import _apply_severity_caps

        # Both exec and result are catastrophic — the lower cap wins.
        capped, caps = _apply_severity_caps(
            0.30,
            {"code_development": 1.0, "execution": 0.0, "result_match": 0.0},
        )
        self.assertEqual(capped, 0.30)
        self.assertIn("execution_below_0_30_caps_overall_at_0_40", caps)
        self.assertIn("result_match_below_0_30_caps_overall_at_0_50", caps)

    def test_score_rubric_payload_records_raw_and_capped(self) -> None:
        from scireplicbench.scorers import score_rubric_payload

        payload = {
            "paper_id": "demo",
            "total_leaf_nodes": 3,
            "rubric": {
                "id": "demo/rubric",
                "name": "Demo",
                "weight": 1.0,
                "is_leaf": False,
                "children": [
                    {
                        "id": "demo/code_development",
                        "name": "Code",
                        "weight": 0.30,
                        "is_leaf": False,
                        "children": [
                            {
                                "id": "demo/code_development/leaf",
                                "name": "Leaf",
                                "weight": 1.0,
                                "is_leaf": True,
                                "category": "code_development",
                                "requirement": "demo",
                                "grading_notes": "demo",
                            }
                        ],
                    },
                    {
                        "id": "demo/execution",
                        "name": "Exec",
                        "weight": 0.25,
                        "is_leaf": False,
                        "children": [
                            {
                                "id": "demo/execution/leaf",
                                "name": "Leaf",
                                "weight": 1.0,
                                "is_leaf": True,
                                "category": "execution",
                                "requirement": "demo",
                                "grading_notes": "demo",
                            }
                        ],
                    },
                    {
                        "id": "demo/result_match",
                        "name": "Result",
                        "weight": 0.45,
                        "is_leaf": False,
                        "children": [
                            {
                                "id": "demo/result_match/leaf",
                                "name": "Leaf",
                                "weight": 1.0,
                                "is_leaf": True,
                                "category": "result_match",
                                "requirement": "demo",
                                "grading_notes": "demo",
                            }
                        ],
                    },
                ],
            },
        }
        leaf_scores = {
            "demo/code_development/leaf": 1.0,
            "demo/execution/leaf": 1.0,
            "demo/result_match/leaf": 0.0,
        }
        report = score_rubric_payload(payload, leaf_scores)
        self.assertAlmostEqual(report.raw_overall_score, 0.55, places=4)
        self.assertEqual(report.overall_score, 0.50)
        self.assertIn("result_match_below_0_30_caps_overall_at_0_50", report.severity_caps_applied)
        d = report.to_dict()
        self.assertAlmostEqual(d["raw_overall_score"], 0.55, places=4)
        self.assertEqual(d["overall_score"], 0.50)
        self.assertIn(
            "result_match_below_0_30_caps_overall_at_0_50",
            d["severity_caps_applied"],
        )

    def test_normalize_pair_key_canonical_collapses_symmetric_pairs(self) -> None:
        from scireplicbench.scorers import _normalize_pair_key_canonical

        self.assertEqual(_normalize_pair_key_canonical("Pyramidal_layer|Hippocampus"), "Hippocampus|Pyramidal_layer")
        self.assertEqual(_normalize_pair_key_canonical("Hippocampus|Pyramidal_layer"), "Hippocampus|Pyramidal_layer")
        self.assertEqual(_normalize_pair_key_canonical("Cortex_5|Cortex_4"), "Cortex_4|Cortex_5")
        # No pipe — unchanged.
        self.assertEqual(_normalize_pair_key_canonical("solo_label"), "solo_label")

    def test_normalizer_for_reference_recognises_pair_key_canonical(self) -> None:
        from scireplicbench.scorers import (
            _normalize_pair_key_canonical,
            _normalizer_for_reference,
        )

        for alias in ("pair_key_canonical", "pair_key", "symmetric_pair"):
            self.assertEqual(
                _normalizer_for_reference({"normalize": alias}),
                _normalize_pair_key_canonical,
            )

    def test_starter_mode_off_does_not_mark_code_reference_as_starter_assisted(self) -> None:
        leaf = {
            "id": "demo/code_development/source_leaf",
            "category": "code_development",
            "requirement": "Implement Squidpy source.",
        }
        reference = {
            "strict_code_development": True,
            "starter_assisted": True,
            "starter_profile": "demo_profile",
            "source_candidates": ["/workspace/submission/pipeline.py"],
            "leaves": {
                "demo/code_development/source_leaf": {
                    "metric": "source_patterns",
                    "all_literals": ["sq.gr.spatial_neighbors"],
                    "all_ast_calls": ["sq.gr.spatial_neighbors"],
                }
            },
        }
        source = "import squidpy as sq\nsq.gr.spatial_neighbors(adata)\n"
        with patch.dict(
            os.environ,
            {"SCIREPLICBENCH_STARTER_MODE": "off"},
            clear=False,
        ), patch.object(
            scorers,
            "load_code_development_reference",
            return_value=reference,
        ), patch.object(scorers, "_read_sandbox_file", AsyncMock(return_value=source)):
            judgement = asyncio.run(
                _deterministic_code_development_judgement(leaf, paper_id="demo")
            )

        self.assertIsNotNone(judgement)
        assert judgement is not None
        self.assertEqual(judgement.score, 1)
        self.assertTrue(judgement.metadata["reference_starter_assisted"])
        self.assertEqual(judgement.metadata["starter_mode"], "off")
        self.assertFalse(judgement.metadata["starter_assisted"])
        self.assertIsNone(judgement.metadata["starter_profile"])

    def test_deterministic_code_development_ast_calls_reject_comment_gaming(self) -> None:
        leaf = {
            "id": "demo/code_development/source_leaf",
            "category": "code_development",
            "requirement": "Implement Squidpy source.",
        }
        reference = {
            "strict_code_development": True,
            "source_candidates": ["/workspace/submission/pipeline.py"],
            "leaves": {
                "demo/code_development/source_leaf": {
                    "metric": "source_patterns",
                    "all_literals": ["sq.gr.spatial_neighbors", "coord_type=\"grid\""],
                    "all_ast_calls": ["sq.gr.spatial_neighbors"],
                }
            },
        }
        source = (
            "# sq.gr.spatial_neighbors(adata, coord_type=\"grid\")\n"
            "note = 'sq.gr.spatial_neighbors with coord_type=\"grid\"'\n"
        )
        with patch.object(
            scorers,
            "load_code_development_reference",
            return_value=reference,
        ), patch.object(scorers, "_read_sandbox_file", AsyncMock(return_value=source)):
            judgement = asyncio.run(
                _deterministic_code_development_judgement(leaf, paper_id="demo")
            )

        self.assertIsNotNone(judgement)
        assert judgement is not None
        self.assertEqual(judgement.score, 0)
        self.assertEqual(
            judgement.metadata["missing_all_ast_calls"],
            ["sq.gr.spatial_neighbors"],
        )

    def test_deterministic_leaf_dispatch_prefers_configured_category(self) -> None:
        execution_leaf = {
            "id": "demo/execution/run_script",
            "category": "execution",
            "requirement": "Run the script.",
        }
        execution_reference = {
            "strict_execution": True,
            "leaves": {
                "demo/execution/run_script": {
                    "metric": "artifact_exists",
                    "artifact": "/workspace/output/agent/run.log",
                    "contains": "ok",
                }
            },
        }
        with patch.object(scorers, "load_result_match_reference", return_value={}), patch.object(
            scorers,
            "load_execution_reference",
            return_value=execution_reference,
        ), patch.object(scorers, "_read_sandbox_file", AsyncMock(return_value="ok\n")):
            judgement = asyncio.run(_deterministic_leaf_judgement(execution_leaf, paper_id="demo"))

        self.assertIsNotNone(judgement)
        assert judgement is not None
        self.assertEqual(judgement.score, 1)
        self.assertTrue(judgement.metadata["deterministic_execution"])

    def test_deterministic_result_match_scores_tsv_gene_row_numeric(self) -> None:
        leaf = {
            "id": "demo/result_match/moran_gene",
            "category": "result_match",
            "requirement": "Recover a gene statistic.",
        }
        reference = {
            "strict_result_match": True,
            "leaves": {
                "demo/result_match/moran_gene": {
                    "metric": "tsv_row_numeric_within_tolerance",
                    "artifact": "/workspace/output/agent/autocorrelation/moran_ranked.tsv",
                    "key_column": "gene",
                    "key_value": "Olfm1",
                    "value_column": "moran_i",
                    "expected": 0.25,
                    "absolute_tolerance": 0.01,
                    "normalize": "gene_symbol",
                }
            },
        }
        with patch.object(scorers, "load_result_match_reference", return_value=reference), patch.object(
            scorers,
            "_read_sandbox_file",
            AsyncMock(return_value="gene\tmoran_i\nolfm1\t0.255\nPlp1\t0.1\n"),
        ):
            judgement = asyncio.run(
                _deterministic_result_match_judgement(leaf, paper_id="demo")
            )

        self.assertIsNotNone(judgement)
        assert judgement is not None
        self.assertEqual(judgement.score, 1)
        self.assertEqual(judgement.metadata["value_column"], "moran_i")

    def test_deterministic_result_match_scores_tsv_shape(self) -> None:
        leaf = {
            "id": "demo/result_match/feature_shape",
            "category": "result_match",
            "requirement": "Recover a feature matrix.",
        }
        reference = {
            "strict_result_match": True,
            "leaves": {
                "demo/result_match/feature_shape": {
                    "metric": "tsv_shape_within_tolerance",
                    "artifact": "/workspace/output/agent/image_features/feature_matrix.tsv",
                    "exclude_columns": ["obs_id"],
                    "expected": {"rows": 2, "columns": 3},
                    "tolerance_pct": 0.0,
                }
            },
        }
        with patch.object(scorers, "load_result_match_reference", return_value=reference), patch.object(
            scorers,
            "_read_sandbox_file",
            AsyncMock(return_value="obs_id\tf1\tf2\tf3\na\t1\t2\t3\nb\t4\t5\t6\n"),
        ):
            judgement = asyncio.run(
                _deterministic_result_match_judgement(leaf, paper_id="demo")
            )

        self.assertIsNotNone(judgement)
        assert judgement is not None
        self.assertEqual(judgement.score, 1)
        self.assertEqual(judgement.metadata["observed"], {"rows": 2, "columns": 3})

    def test_deterministic_result_match_scores_tsv_shape_with_exact_ids(self) -> None:
        leaf = {
            "id": "demo/result_match/feature_shape_ids",
            "category": "result_match",
            "requirement": "Recover an aligned feature matrix.",
        }
        reference = {
            "strict_result_match": True,
            "leaves": {
                "demo/result_match/feature_shape_ids": {
                    "metric": "tsv_shape_within_tolerance",
                    "artifact": "/workspace/output/agent/image_features/feature_matrix.tsv",
                    "reference_artifact": "generated/ref_feature_matrix.tsv",
                    "exclude_columns": ["obs_id"],
                    "id_column": "obs_id",
                    "min_shared_rows": 2,
                    "require_exact_ids": True,
                    "expected": {"rows": 2, "columns": 2},
                    "tolerance_pct": 0.0,
                }
            },
        }
        feature_matrix = "obs_id\tf1\tf2\na\t1\t2\nb\t4\t5\n"
        with patch.object(scorers, "load_result_match_reference", return_value=reference), patch.object(
            scorers,
            "_read_sandbox_file",
            AsyncMock(return_value=feature_matrix),
        ), patch.object(scorers, "_reference_artifact_text", return_value=feature_matrix):
            judgement = asyncio.run(
                _deterministic_result_match_judgement(leaf, paper_id="demo")
            )

        self.assertIsNotNone(judgement)
        assert judgement is not None
        self.assertEqual(judgement.score, 1)
        self.assertEqual(judgement.metadata["observed"]["shared_ids"], 2)
        self.assertEqual(judgement.metadata["missing_ids"], 0)

    def test_deterministic_result_match_scores_tsv_label_ari(self) -> None:
        leaf = {
            "id": "demo/result_match/cluster_ari",
            "category": "result_match",
            "requirement": "Recover feature clusters.",
        }
        reference = {
            "strict_result_match": True,
            "leaves": {
                "demo/result_match/cluster_ari": {
                    "metric": "tsv_label_ari",
                    "artifact": "/workspace/output/agent/image_features/feature_clusters.tsv",
                    "reference_artifact": "generated/ref_clusters.tsv",
                    "id_column": "obs_id",
                    "label_column": "image_cluster",
                    "minimum": 1.0,
                }
            },
        }
        clusters = "obs_id\timage_cluster\na\t0\nb\t0\nc\t1\nd\t1\n"
        with patch.object(scorers, "load_result_match_reference", return_value=reference), patch.object(
            scorers,
            "_read_sandbox_file",
            AsyncMock(return_value=clusters),
        ), patch.object(scorers, "_reference_artifact_text", return_value=clusters):
            judgement = asyncio.run(
                _deterministic_result_match_judgement(leaf, paper_id="demo")
            )

        self.assertIsNotNone(judgement)
        assert judgement is not None
        self.assertEqual(judgement.score, 1)
        self.assertEqual(judgement.metadata["shared_labels"], 4)

    def test_deterministic_result_match_scores_json_cluster_nondegenerate(self) -> None:
        leaf = {
            "id": "demo/result_match/nondegenerate",
            "category": "result_match",
            "requirement": "Recover nondegenerate clusters.",
        }
        reference = {
            "strict_result_match": True,
            "leaves": {
                "demo/result_match/nondegenerate": {
                    "metric": "json_cluster_nondegenerate",
                    "artifact": "/workspace/output/agent/image_features/feature_summary.json",
                    "json_path": ["cluster_counts"],
                    "min_clusters": 3,
                    "max_fraction": 0.6,
                }
            },
        }
        with patch.object(scorers, "load_result_match_reference", return_value=reference), patch.object(
            scorers,
            "_read_sandbox_file",
            AsyncMock(return_value='{"cluster_counts": {"a": 4, "b": 3, "c": 3}}'),
        ):
            judgement = asyncio.run(
                _deterministic_result_match_judgement(leaf, paper_id="demo")
            )

        self.assertIsNotNone(judgement)
        assert judgement is not None
        self.assertEqual(judgement.score, 1)
        self.assertEqual(judgement.metadata["observed"]["clusters"], 3)

    def test_deterministic_result_match_scores_json_set_match(self) -> None:
        leaf = {
            "id": "demo/result_match/labels",
            "category": "result_match",
            "requirement": "Recover labels.",
        }
        reference = {
            "strict_result_match": True,
            "leaves": {
                "demo/result_match/labels": {
                    "metric": "json_set_match",
                    "artifact": "/workspace/output/agent/dataset_manifest.json",
                    "json_path": ["cluster_labels"],
                    "expected": ["Cortex 1", "Fiber tract"],
                    "normalize": "label",
                    "minimum": 1.0,
                    "require_exact": True,
                }
            },
        }
        with patch.object(scorers, "load_result_match_reference", return_value=reference), patch.object(
            scorers,
            "_read_sandbox_file",
            AsyncMock(return_value='{"cluster_labels": ["fiber_tract", "Cortex-1"]}'),
        ):
            judgement = asyncio.run(
                _deterministic_result_match_judgement(leaf, paper_id="demo")
            )

        self.assertIsNotNone(judgement)
        assert judgement is not None
        self.assertEqual(judgement.score, 1)
        self.assertEqual(judgement.metadata["missing"], [])
        self.assertEqual(judgement.metadata["extra"], [])

    def test_deterministic_result_match_scores_aligned_numeric_correlation(self) -> None:
        leaf = {
            "id": "demo/result_match/centrality",
            "category": "result_match",
            "requirement": "Recover centrality.",
        }
        reference = {
            "strict_result_match": True,
            "leaves": {
                "demo/result_match/centrality": {
                    "metric": "tsv_aligned_numeric_correlation",
                    "artifact": "/workspace/output/agent/neighborhood/centrality_scores.tsv",
                    "reference_artifact": "generated/centrality_scores.tsv",
                    "key_column": "cluster",
                    "value_columns": ["degree_centrality", "closeness_centrality"],
                    "correlation": "spearman",
                    "minimum": 0.99,
                    "min_shared": 3,
                    "normalize": "label",
                }
            },
        }
        centrality = (
            "cluster\tdegree_centrality\tcloseness_centrality\n"
            "a\t1\t3\n"
            "b\t2\t2\n"
            "c\t3\t1\n"
        )
        with patch.object(scorers, "load_result_match_reference", return_value=reference), patch.object(
            scorers,
            "_read_sandbox_file",
            AsyncMock(return_value=centrality),
        ), patch.object(scorers, "_reference_artifact_text", return_value=centrality):
            judgement = asyncio.run(
                _deterministic_result_match_judgement(leaf, paper_id="demo")
            )

        self.assertIsNotNone(judgement)
        assert judgement is not None
        self.assertEqual(judgement.score, 1)
        self.assertEqual(judgement.metadata["shared_rows"], 3)
        self.assertAlmostEqual(judgement.metadata["observed"], 1.0)

    def test_deterministic_result_match_scores_grouped_curve_correlation(self) -> None:
        leaf = {
            "id": "demo/result_match/cooccurrence",
            "category": "result_match",
            "requirement": "Recover curves.",
        }
        reference = {
            "strict_result_match": True,
            "leaves": {
                "demo/result_match/cooccurrence": {
                    "metric": "tsv_grouped_curve_correlation",
                    "artifact": "/workspace/output/agent/neighborhood/cooccurrence_curves.tsv",
                    "reference_artifact": "generated/cooccurrence_curves.tsv",
                    "group_column": "pair_key",
                    "x_column": "radius_index",
                    "value_column": "cooccurrence",
                    "correlation": "pearson",
                    "minimum": 0.99,
                    "min_groups": 2,
                    "min_points": 3,
                }
            },
        }
        curves = (
            "pair_key\tradius_index\tcooccurrence\n"
            "a|b\t0\t1\n"
            "a|b\t1\t2\n"
            "a|b\t2\t3\n"
            "b|c\t0\t3\n"
            "b|c\t1\t2\n"
            "b|c\t2\t1\n"
        )
        with patch.object(scorers, "load_result_match_reference", return_value=reference), patch.object(
            scorers,
            "_read_sandbox_file",
            AsyncMock(return_value=curves),
        ), patch.object(scorers, "_reference_artifact_text", return_value=curves):
            judgement = asyncio.run(
                _deterministic_result_match_judgement(leaf, paper_id="demo")
            )

        self.assertIsNotNone(judgement)
        assert judgement is not None
        self.assertEqual(judgement.score, 1)
        self.assertEqual(judgement.metadata["aligned_curves"], 2)
        self.assertAlmostEqual(judgement.metadata["observed"], 1.0)

    def test_scorer_uses_deterministic_result_match_before_llm_judge(self) -> None:
        if not getattr(scorers, "_HAS_INSPECT_SCORING", False):
            self.skipTest("inspect-ai runtime not available")

        precheck_success = {
            "ok": True,
            "reason": None,
            "nontrivial_py_files": 1,
            "nontrivial_py_examples": ["/workspace/submission/pipeline.py"],
            "nontrivial_source_files": 1,
            "nontrivial_source_examples": ["/workspace/submission/pipeline.py"],
            "output_artifact_count": 2,
            "output_artifact_examples": [
                "/workspace/output/run.log",
                "/workspace/output/agent/dataset_manifest.json",
            ],
        }
        reference = {
            "strict_result_match": True,
            "leaves": {
                "demo/result_match/shared_name": {
                    "metric": "json_numeric_within_tolerance",
                    "artifact": "/workspace/output/agent/metrics.json",
                    "json_path": ["metric"],
                    "expected": 1.0,
                    "absolute_tolerance": 0.0,
                }
            },
        }
        judge_mock = AsyncMock(
            side_effect=[
                LeafJudgement(
                    leaf_id="demo/code_development/shared_name",
                    expectations="Write the code.",
                    reality="Observed code.",
                    evidence_quote="print('ok')",
                    score=1,
                ),
                LeafJudgement(
                    leaf_id="demo/execution/run_script",
                    expectations="Run the code.",
                    reality="Observed runtime output.",
                    evidence_quote="command exited with status 0",
                    score=1,
                ),
            ]
        )
        reality = (
            "Submission file list:\n"
            "/workspace/submission/pipeline.py\n"
            "/workspace/output/run.log\n"
            "\n--- /workspace/submission/pipeline.py ---\n"
            "print('ok')\n"
            "\n--- /workspace/output/run.log ---\n"
            "command exited with status 0\n"
        )
        state = SimpleNamespace(metadata={"paper_id": "demo"}, sample_id="demo_main", messages=[])
        target = SimpleNamespace()
        score_coro = scorers.rubric_tree_scorer(judge_model="openai/gpt-4o-mini")

        with patch.object(scorers, "load_rubric_payload", return_value=demo_rubric_payload()), patch.object(
            scorers, "load_paper_summary", return_value="demo paper summary"
        ), patch.object(scorers, "_collect_submission_context", AsyncMock(return_value=reality)), patch.object(
            scorers, "_artifact_presence_precheck", AsyncMock(return_value=precheck_success)
        ), patch.object(scorers, "load_result_match_reference", return_value=reference), patch.object(
            scorers, "_read_sandbox_file", AsyncMock(return_value='{"metric": 1.0}')
        ), patch.object(scorers, "_judge_leaf", judge_mock), patch.object(
            scorers, "get_model", MagicMock(return_value=MagicMock())
        ):
            result = asyncio.run(score_coro(state, target))

        self.assertEqual(judge_mock.await_count, 2)
        self.assertAlmostEqual(result.value, 1.0)
        self.assertEqual(result.metadata["deterministic_result_match_leaves"], 1)
        result_match_judgement = result.metadata["leaf_judgements"][2]
        self.assertTrue(result_match_judgement["metadata"]["deterministic_result_match"])
        self.assertNotIn("self_consistency_samples", result_match_judgement["metadata"])

    def test_starter_assisted_score_is_not_marked_as_model_performance(self) -> None:
        if not getattr(scorers, "_HAS_INSPECT_SCORING", False):
            self.skipTest("inspect-ai runtime not available")

        precheck_success = {
            "ok": True,
            "reason": None,
            "nontrivial_py_files": 1,
            "nontrivial_source_files": 1,
            "output_artifact_count": 2,
            "requires_output_artifact": True,
        }
        code_reference = {
            "strict_code_development": True,
            "starter_assisted": True,
            "starter_profile": "demo_starter",
            "source_candidates": ["/workspace/submission/pipeline.py"],
            "leaves": {
                "demo/code_development/shared_name": {
                    "metric": "source_patterns",
                    "all_literals": ["print('ok')"],
                }
            },
        }
        execution_reference = {
            "strict_execution": True,
            "leaves": {
                "demo/execution/run_script": {
                    "metric": "artifact_exists",
                    "artifact": "/workspace/output/run.log",
                    "contains": "command exited with status 0",
                    "min_bytes": 10,
                }
            },
        }
        result_reference = {
            "strict_result_match": True,
            "leaves": {
                "demo/result_match/shared_name": {
                    "metric": "json_numeric_within_tolerance",
                    "artifact": "/workspace/output/metrics.json",
                    "json_path": ["metric"],
                    "expected": 1.0,
                    "absolute_tolerance": 0.0,
                }
            },
        }

        async def fake_read(path: str) -> str:
            return {
                "/workspace/submission/pipeline.py": "print('ok')\n",
                "/workspace/output/run.log": "command exited with status 0\n",
                "/workspace/output/metrics.json": '{"metric": 1.0}',
            }[path]

        judge_mock = AsyncMock()
        state = SimpleNamespace(metadata={"paper_id": "demo"}, sample_id="demo_main", messages=[])
        target = SimpleNamespace()
        score_coro = scorers.rubric_tree_scorer(judge_model="openai/gpt-4o-mini")

        with patch.object(scorers, "load_rubric_payload", return_value=demo_rubric_payload()), patch.object(
            scorers, "load_paper_summary", return_value="demo paper summary"
        ), patch.object(scorers, "_collect_submission_context", AsyncMock(return_value="")), patch.object(
            scorers, "_artifact_presence_precheck", AsyncMock(return_value=precheck_success)
        ), patch.object(scorers, "load_code_development_reference", return_value=code_reference), patch.object(
            scorers, "load_execution_reference", return_value=execution_reference
        ), patch.object(scorers, "load_result_match_reference", return_value=result_reference), patch.object(
            scorers, "_read_sandbox_file", fake_read
        ), patch.object(scorers, "_judge_leaf", judge_mock), patch.object(
            scorers, "get_model", MagicMock(return_value=MagicMock())
        ):
            result = asyncio.run(score_coro(state, target))

        self.assertEqual(judge_mock.await_count, 0)
        self.assertAlmostEqual(result.value, 1.0)
        self.assertEqual(result.metadata["evaluation_lane"], "starter_assisted")
        self.assertEqual(result.metadata["starter_assisted_leaves"], 1)
        self.assertEqual(result.metadata["starter_profiles"], ["demo_starter"])
        self.assertEqual(result.metadata["raw_reproducibility_score"], 1.0)
        self.assertFalse(result.metadata["model_performance_score_available"])
        self.assertIsNone(result.metadata["model_performance_score"])
        self.assertFalse(result.metadata["production_comparable"])
        self.assertIn("model_performance_score=not_available", result.explanation)

    def test_unassisted_score_is_marked_as_model_performance_available(self) -> None:
        metadata = scorers._score_interpretation_metadata(0.75, [])

        self.assertEqual(metadata["evaluation_lane"], "blank_slate_or_unassisted")
        self.assertEqual(metadata["raw_reproducibility_score"], 0.75)
        self.assertEqual(metadata["model_performance_score"], 0.75)
        self.assertTrue(metadata["model_performance_score_available"])
        self.assertTrue(metadata["production_comparable"])

    def test_squidpy_result_match_negative_control_rejects_bad_visium_shape(self) -> None:
        leaf = {
            "id": "squidpy_spatial/result_match/datasets_and_containers/dataset_assets_correct_shape",
            "category": "result_match",
            "requirement": "Recover Visium H&E, seqFISH, and Visium H&E image shapes within tolerance.",
        }
        bad_manifest = {
            "datasets": {
                "visium_hne_adata": {
                    "shape": [10, 10],
                },
                "seqfish": {
                    "shape": [19416, 351],
                },
                "visium_hne_image": {
                    "sizes": {"y": 11757, "x": 11291, "channels": 3},
                },
            }
        }

        with patch.object(
            scorers,
            "_read_sandbox_file",
            AsyncMock(return_value=json.dumps(bad_manifest)),
        ):
            judgement = asyncio.run(
                _deterministic_result_match_judgement(
                    leaf,
                    paper_id="squidpy_spatial",
                )
            )

        self.assertIsNotNone(judgement)
        assert judgement is not None
        self.assertEqual(judgement.score, 0)
        self.assertTrue(judgement.metadata["deterministic_result_match"])
        # Gating leaf reports per-sub-check results; the failing sub-check is the
        # bad Visium shape (10, 10) while seqfish and image shapes pass.
        sub_results = judgement.metadata["observed"]
        assert isinstance(sub_results, list) and len(sub_results) == 3
        self.assertFalse(sub_results[0]["passed"])
        self.assertEqual(list(sub_results[0]["observed"]), [10, 10])
        self.assertTrue(sub_results[1]["passed"])
        self.assertTrue(sub_results[2]["passed"])

    def test_squidpy_execution_negative_control_rejects_incomplete_visual_report(self) -> None:
        leaf = {
            "id": "squidpy_spatial/execution/interaction_reporting/visualization_report_written",
            "category": "execution",
            "requirement": "Write marker localization and integrated HTML report artifacts.",
        }

        async def fake_read(path: str) -> str:
            if path.endswith("marker_localization.svg"):
                return "<svg>Marker localization</svg>" + ("x" * 240)
            if path.endswith("report.html"):
                return "<html>missing linked plot names</html>" + ("x" * 500)
            raise KeyError(path)

        with patch.object(scorers, "_read_sandbox_file", fake_read):
            judgement = asyncio.run(
                _deterministic_execution_judgement(
                    leaf,
                    paper_id="squidpy_spatial",
                )
            )

        self.assertIsNotNone(judgement)
        assert judgement is not None
        self.assertEqual(judgement.score, 0)
        self.assertTrue(judgement.metadata["deterministic_execution"])
        self.assertEqual(judgement.metadata["metric"], "all_checks")

    def test_squidpy_result_match_references_score_all_leaves_deterministically(self) -> None:
        paper_id = "squidpy_spatial"
        root = Path("papers") / paper_id
        generated = root / "reference_outputs" / "generated"
        summary = json.loads((generated / "squidpy_spatial_reference_summary.json").read_text())
        labels = json.loads((generated / "squidpy_label_vocabulary.json").read_text())
        rubric = scorers.load_rubric_payload(paper_id)
        leaves = [
            leaf
            for leaf in scorers.collect_leaf_nodes(scorers.extract_rubric_tree(rubric))
            if str(leaf.get("category", "")) == "result_match"
        ]
        manifest = {
            "datasets": {
                "visium_hne_adata": {
                    "shape": [2688, 18078],
                    "cluster_labels": labels["datasets"]["visium_hne_adata"]["cluster_labels"],
                },
                "seqfish": {"shape": [19416, 351]},
                "visium_hne_image": {
                    "sizes": {"y": 11757, "x": 11291, "channels": 3}
                },
            }
        }
        graph_metrics = {
            "visium": {
                "spatial_neighbors": {
                    "edges": summary["graph_metrics"]["visium"]["spatial_neighbors"]["edges"]
                }
            },
            "seqfish": {
                "spatial_neighbors": {
                    "edges": summary["graph_metrics"]["seqfish"]["spatial_neighbors"]["edges"]
                }
            },
        }
        artifact_map = {
            "/workspace/output/agent/neighborhood/nhood_enrichment_ranked.tsv": generated
            / "visium_hne_nhood_enrichment_ranked.tsv",
            "/workspace/output/agent/neighborhood/centrality_scores.tsv": generated
            / "visium_hne_centrality_scores.tsv",
            "/workspace/output/agent/neighborhood/cooccurrence_curves.tsv": generated
            / "visium_hne_cooccurrence_curves.tsv",
            "/workspace/output/agent/neighborhood/interaction_matrix.tsv": generated
            / "visium_hne_interaction_matrix.tsv",
            "/workspace/output/agent/autocorrelation/moran_ranked.tsv": generated
            / "visium_hne_moran_ranked.tsv",
            "/workspace/output/agent/autocorrelation/geary_ranked.tsv": generated
            / "visium_hne_geary_ranked.tsv",
            "/workspace/output/agent/spatial_stats/ripley_curves.tsv": generated
            / "seqfish_ripley_l_curves.tsv",
            "/workspace/output/agent/spatial_stats/svg_summary.json": generated
            / "visium_hne_svg_summary.json",
            "/workspace/output/agent/spatial_stats/gene_localization.tsv": generated
            / "visium_hne_gene_localization.tsv",
            "/workspace/output/agent/image_features/feature_matrix.tsv": generated
            / "visium_hne_image_feature_matrix.tsv",
            "/workspace/output/agent/image_features/feature_summary.json": generated
            / "visium_hne_image_feature_summary.json",
            "/workspace/output/agent/image_features/feature_clusters.tsv": generated
            / "visium_hne_image_feature_clusters.tsv",
            "/workspace/output/agent/image_features/feature_ranking.tsv": generated
            / "visium_hne_image_feature_ranking.tsv",
            "/workspace/output/agent/interactions/ligrec_ranked.tsv": generated
            / "visium_hne_ligrec_ranked.tsv",
            "/workspace/output/agent/interactions/ligrec_summary.json": generated
            / "visium_hne_ligrec_summary.json",
        }

        async def fake_read(path: str) -> str:
            if path == "/workspace/output/agent/dataset_manifest.json":
                return json.dumps(manifest)
            if path == "/workspace/output/agent/spatial_graph_metrics.json":
                return json.dumps(graph_metrics)
            return artifact_map[path].read_text()

        async def score_all() -> list[LeafJudgement]:
            judgements = []
            with patch.object(scorers, "_read_sandbox_file", fake_read):
                for leaf in leaves:
                    judgement = await _deterministic_result_match_judgement(
                        leaf,
                        paper_id=paper_id,
                    )
                    self.assertIsNotNone(judgement, msg=str(leaf["id"]))
                    assert judgement is not None
                    judgements.append(judgement)
            return judgements

        judgements = asyncio.run(score_all())
        self.assertEqual(len(judgements), 21)
        self.assertTrue(
            all(judgement.metadata.get("deterministic_result_match") for judgement in judgements)
        )
        self.assertTrue(all(judgement.score == 1 for judgement in judgements))

    def test_squidpy_execution_references_score_all_leaves_deterministically(self) -> None:
        paper_id = "squidpy_spatial"
        root = Path("papers") / paper_id
        generated = root / "reference_outputs" / "generated"
        summary = json.loads((generated / "squidpy_spatial_reference_summary.json").read_text())
        labels = json.loads((generated / "squidpy_label_vocabulary.json").read_text())
        rubric = scorers.load_rubric_payload(paper_id)
        leaves = [
            leaf
            for leaf in scorers.collect_leaf_nodes(scorers.extract_rubric_tree(rubric))
            if str(leaf.get("category", "")) == "execution"
        ]
        manifest = {
            "datasets": {
                "visium_hne_adata": {
                    "shape": [2688, 18078],
                    "cluster_key": "cluster",
                    "cluster_labels": labels["datasets"]["visium_hne_adata"][
                        "cluster_labels"
                    ],
                },
                "seqfish": {
                    "shape": [19416, 351],
                    "cluster_key": "celltype_mapped_refined",
                    "cluster_labels": labels["datasets"]["seqfish"]["cluster_labels"],
                },
                "visium_hne_image": {
                    "sizes": {"y": 11757, "x": 11291, "channels": 3}
                },
            }
        }
        artifact_map = {
            "/workspace/output/agent/dataset_manifest.json": json.dumps(manifest),
            "/workspace/output/agent/spatial_graph_metrics.json": json.dumps(
                summary["graph_metrics"]
            ),
            "/workspace/output/agent/neighborhood/nhood_enrichment_ranked.tsv": generated
            / "visium_hne_nhood_enrichment_ranked.tsv",
            "/workspace/output/agent/neighborhood/centrality_scores.tsv": generated
            / "visium_hne_centrality_scores.tsv",
            "/workspace/output/agent/neighborhood/cooccurrence_curves.tsv": generated
            / "visium_hne_cooccurrence_curves.tsv",
            "/workspace/output/agent/neighborhood/interaction_matrix.tsv": generated
            / "visium_hne_interaction_matrix.tsv",
            "/workspace/output/agent/autocorrelation/moran_ranked.tsv": generated
            / "visium_hne_moran_ranked.tsv",
            "/workspace/output/agent/autocorrelation/geary_ranked.tsv": generated
            / "visium_hne_geary_ranked.tsv",
            "/workspace/output/agent/spatial_stats/ripley_curves.tsv": generated
            / "seqfish_ripley_l_curves.tsv",
            "/workspace/output/agent/spatial_stats/svg_summary.json": generated
            / "visium_hne_svg_summary.json",
            "/workspace/output/agent/image_features/feature_matrix.tsv": generated
            / "visium_hne_image_feature_matrix.tsv",
            "/workspace/output/agent/image_features/feature_summary.json": generated
            / "visium_hne_image_feature_summary.json",
            "/workspace/output/agent/image_features/feature_clusters.tsv": generated
            / "visium_hne_image_feature_clusters.tsv",
            "/workspace/output/agent/interactions/ligrec_ranked.tsv": generated
            / "visium_hne_ligrec_ranked.tsv",
            "/workspace/output/agent/interactions/ligrec_summary.json": generated
            / "visium_hne_ligrec_summary.json",
            "/workspace/output/agent/visualizations/spatial_stats_plot.svg": (
                "<svg>"
                + " Top Moran" * 50
                + "</svg>"
            ),
            "/workspace/output/agent/visualizations/marker_localization.svg": (
                "<svg>"
                + " Marker localization" * 50
                + "</svg>"
            ),
            "/workspace/output/agent/visualizations/report.html": (
                "Squidpy spatial reviewer-path report spatial_stats_plot.svg "
                "marker_localization.svg "
                + "x" * 500
            ),
        }

        async def fake_read(path: str) -> str:
            artifact = artifact_map[path]
            if isinstance(artifact, Path):
                return artifact.read_text()
            return artifact

        async def score_all() -> list[LeafJudgement]:
            judgements = []
            with patch.object(scorers, "_read_sandbox_file", fake_read):
                for leaf in leaves:
                    judgement = await _deterministic_execution_judgement(
                        leaf,
                        paper_id=paper_id,
                    )
                    self.assertIsNotNone(judgement, msg=str(leaf["id"]))
                    assert judgement is not None
                    judgements.append(judgement)
            return judgements

        judgements = asyncio.run(score_all())
        self.assertEqual(len(judgements), 14)
        self.assertTrue(
            all(judgement.metadata.get("deterministic_execution") for judgement in judgements)
        )
        self.assertTrue(all(judgement.score == 1 for judgement in judgements))

    def test_squidpy_code_development_references_match_starter_sources(self) -> None:
        paper_id = "squidpy_spatial"
        starter = Path("papers") / paper_id / "starter"
        source_map = {
            "/workspace/submission/main_analysis.py": (starter / "main_analysis.py").read_text(),
            "/workspace/submission/squidpy_spatial_workflow.py": (
                starter / "squidpy_spatial_workflow.py"
            ).read_text(),
            "/workspace/submission/run.sh": (starter / "run.sh").read_text(),
        }
        rubric = scorers.load_rubric_payload(paper_id)
        leaves = [
            leaf
            for leaf in scorers.collect_leaf_nodes(scorers.extract_rubric_tree(rubric))
            if str(leaf.get("category", "")) == "code_development"
        ]

        async def fake_read(path: str) -> str:
            return source_map[path]

        async def score_all() -> list[LeafJudgement]:
            judgements = []
            with patch.object(scorers, "_read_sandbox_file", fake_read):
                for leaf in leaves:
                    judgement = await _deterministic_code_development_judgement(
                        leaf,
                        paper_id=paper_id,
                    )
                    self.assertIsNotNone(judgement, msg=str(leaf["id"]))
                    assert judgement is not None
                    judgements.append(judgement)
            return judgements

        judgements = asyncio.run(score_all())
        self.assertEqual(len(judgements), 23)
        self.assertTrue(
            all(
                judgement.metadata.get("deterministic_code_development")
                for judgement in judgements
            )
        )
        self.assertTrue(all(judgement.score == 1 for judgement in judgements))

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
