"""Tests for rubric-tree scoring."""

from __future__ import annotations

import unittest

from scireplicbench.judge import LeafJudgement
from scireplicbench.scorers import (
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


if __name__ == "__main__":
    unittest.main()
