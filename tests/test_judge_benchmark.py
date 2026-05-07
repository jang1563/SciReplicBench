"""Tests for judge reliability utilities."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "judge_eval" / "judge_benchmark.py"
SPEC = importlib.util.spec_from_file_location("judge_benchmark", MODULE_PATH)
judge_benchmark = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = judge_benchmark
SPEC.loader.exec_module(judge_benchmark)


class JudgeBenchmarkTest(unittest.TestCase):
    def test_krippendorff_alpha_nominal(self) -> None:
        perfect = [[1, 1, 1], [0, 0, 0], [1, 1]]
        mixed = [[1, 0, 1], [0, 1, 0], [1, 0]]
        self.assertAlmostEqual(judge_benchmark.krippendorff_alpha_nominal(perfect), 1.0)
        self.assertLess(judge_benchmark.krippendorff_alpha_nominal(mixed), 1.0)

    def test_load_and_summarize_reliability(self) -> None:
        payload = {
            "human_grades": [
                {
                    "example_id": "ex1",
                    "paper_id": "squidpy_spatial",
                    "leaf_id": "leaf1",
                    "human_scores": {"r1": 1, "r2": 1, "r3": 1},
                    "judge_scores": {"gpt-4o-mini": 1},
                },
                {
                    "example_id": "ex2",
                    "paper_id": "squidpy_spatial",
                    "leaf_id": "leaf2",
                    "human_scores": {"r1": 0, "r2": 0, "r3": 1},
                    "judge_scores": {"gpt-4o-mini": 0},
                },
            ]
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "grades.json"
            path.write_text(__import__("json").dumps(payload))
            records = judge_benchmark.load_grade_records(path)
            summary = judge_benchmark.summarize_reliability(records, n_bootstrap=50, seed=0)
            self.assertEqual(summary.items_scored, 2)
            self.assertIn("gpt-4o-mini", summary.judge_exact_match)
            markdown = judge_benchmark.render_reliability_markdown(summary)
            self.assertIn("Krippendorff's alpha", markdown)

    def test_single_rater_panel_reports_agreement_as_na(self) -> None:
        payload = {
            "human_grades": [
                {
                    "example_id": "ex1",
                    "paper_id": "squidpy_spatial",
                    "leaf_id": "leaf1",
                    "human_scores": {"r1": 1},
                    "judge_scores": {"openai/o3-mini": 1},
                }
            ]
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "grades.json"
            path.write_text(__import__("json").dumps(payload))
            records = judge_benchmark.load_grade_records(path)
            summary = judge_benchmark.summarize_reliability(records, n_bootstrap=50, seed=0)
            self.assertEqual(summary.items_scored, 1)
            self.assertIsNone(summary.krippendorff_alpha)
            self.assertEqual(summary.judge_exact_match["openai/o3-mini"], 1.0)
            markdown = judge_benchmark.render_reliability_markdown(summary)
            self.assertIn("N/A (need >=2 human raters per item)", markdown)

    def test_build_blinded_review_packet_hides_scores_and_models(self) -> None:
        packet = {
            "schema_version": "0.1.0",
            "description": "Annotated packet",
            "examples": [
                {
                    "example_id": "ex1",
                    "run_id": "run1",
                    "sample_id": "sample1",
                    "paper_id": "squidpy_spatial",
                    "judge_model": "openai/o3-mini",
                    "leaf_id": "leaf1",
                    "category": "execution",
                    "requirement": "Write output",
                    "grading_notes": "Need a file",
                    "judge_score": 1,
                    "evidence_quote": "output.txt",
                    "judge_reality": "The file exists.",
                    "provisional_human_score": 0,
                    "provisional_note": "Disagree.",
                }
            ],
        }
        blinded = judge_benchmark.build_blinded_review_packet(packet)
        self.assertEqual(blinded["hidden_fields"], [
            "run_id",
            "sample_id",
            "judge_model",
            "judge_score",
            "provisional_human_score",
            "provisional_note",
        ])
        example = blinded["examples"][0]
        self.assertEqual(example["example_id"], "ex1")
        self.assertEqual(example["paper_id"], "squidpy_spatial")
        self.assertEqual(example["leaf_id"], "leaf1")
        self.assertEqual(example["judge_reality"], "The file exists.")
        self.assertNotIn("judge_score", example)
        self.assertNotIn("judge_model", example)
        self.assertNotIn("provisional_human_score", example)
        self.assertEqual(
            example["response_template"],
            {"rater_id": "", "human_score": None, "note": ""},
        )

    def test_write_blinded_review_packet_outputs_writes_json_and_csv(self) -> None:
        packet = {
            "schema_version": "0.1.0",
            "description": "Annotated packet",
            "examples": [
                {
                    "example_id": "ex1",
                    "run_id": "run1",
                    "sample_id": "sample1",
                    "paper_id": "squidpy_spatial",
                    "judge_model": "openai/o3-mini",
                    "leaf_id": "leaf1",
                    "category": "execution",
                    "requirement": "Write output",
                    "grading_notes": "Need a file",
                    "judge_score": 1,
                    "evidence_quote": "output.txt",
                    "judge_reality": "The file exists.",
                    "provisional_human_score": 0,
                    "provisional_note": "Disagree.",
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "packet.json"
            json_output = Path(tmpdir) / "packet_blinded.json"
            csv_output = Path(tmpdir) / "packet_blinded.csv"
            source.write_text(json.dumps(packet))

            blinded = judge_benchmark.write_blinded_review_packet_outputs(
                source,
                json_output_path=json_output,
                csv_output_path=csv_output,
            )

            self.assertTrue(json_output.exists())
            self.assertTrue(csv_output.exists())
            self.assertEqual(blinded["examples"][0]["example_id"], "ex1")
            csv_text = csv_output.read_text()
            self.assertIn("example_id,paper_id,leaf_id,category", csv_text)
            self.assertIn("ex1,squidpy_spatial,leaf1,execution", csv_text)
            self.assertNotIn("openai/o3-mini", csv_text)
            self.assertNotIn("judge_score", csv_text)

    def test_load_blinded_review_responses_from_json(self) -> None:
        packet = {
            "examples": [
                {
                    "example_id": "ex1",
                    "response_template": {
                        "rater_id": "reviewer_2",
                        "human_score": 0,
                        "note": "No written output was shown.",
                    },
                }
            ]
        }
        responses = judge_benchmark.blinded_review_responses_from_packet(packet)
        self.assertEqual(len(responses), 1)
        self.assertEqual(responses[0].example_id, "ex1")
        self.assertEqual(responses[0].rater_id, "reviewer_2")
        self.assertEqual(responses[0].human_score, 0)
        self.assertEqual(responses[0].note, "No written output was shown.")

    def test_load_blinded_review_responses_from_csv_skips_blank_when_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "responses.csv"
            csv_path.write_text(
                "example_id,rater_id,human_score,note\n"
                "ex1,reviewer_2,1,Looks valid.\n"
                "ex2,,,\n"
            )

            responses = judge_benchmark.blinded_review_responses_from_csv(
                csv_path,
                allow_incomplete=True,
            )

        self.assertEqual(len(responses), 1)
        self.assertEqual(responses[0].example_id, "ex1")
        self.assertEqual(responses[0].human_score, 1)

    def test_blank_blinded_review_response_is_rejected_by_default(self) -> None:
        packet = {
            "examples": [
                {
                    "example_id": "ex1",
                    "response_template": {
                        "rater_id": "",
                        "human_score": None,
                        "note": "",
                    },
                }
            ]
        }
        with self.assertRaisesRegex(ValueError, "response is incomplete"):
            judge_benchmark.blinded_review_responses_from_packet(packet)

    def test_merge_blinded_review_responses_adds_second_rater_notes(self) -> None:
        grade_payload = {
            "schema_version": "0.1.0",
            "human_grades": [
                {
                    "example_id": "ex1",
                    "paper_id": "squidpy_spatial",
                    "leaf_id": "leaf1",
                    "human_scores": {"reviewer_provisional": 1},
                    "judge_scores": {"openai/o3-mini": 1},
                    "metadata": {"provisional_single_rater": True},
                }
            ],
        }
        responses = [
            judge_benchmark.BlindedReviewResponse(
                example_id="ex1",
                rater_id="reviewer_2",
                human_score=0,
                note="I do not see runtime evidence.",
            )
        ]

        merged, merged_count = judge_benchmark.merge_blinded_review_responses(
            grade_payload,
            responses,
        )

        self.assertEqual(merged_count, 1)
        record = merged["human_grades"][0]
        self.assertEqual(record["human_scores"]["reviewer_provisional"], 1)
        self.assertEqual(record["human_scores"]["reviewer_2"], 0)
        self.assertFalse(record["metadata"]["provisional_single_rater"])
        self.assertEqual(
            record["metadata"]["human_review_notes"]["reviewer_2"],
            "I do not see runtime evidence.",
        )

    def test_merge_blinded_review_responses_rejects_conflicting_existing_score(self) -> None:
        grade_payload = {
            "human_grades": [
                {
                    "example_id": "ex1",
                    "paper_id": "squidpy_spatial",
                    "leaf_id": "leaf1",
                    "human_scores": {"reviewer_2": 1},
                    "judge_scores": {},
                    "metadata": {},
                }
            ]
        }
        responses = [
            judge_benchmark.BlindedReviewResponse(
                example_id="ex1",
                rater_id="reviewer_2",
                human_score=0,
            )
        ]

        with self.assertRaisesRegex(ValueError, "already has a different score"):
            judge_benchmark.merge_blinded_review_responses(grade_payload, responses)


if __name__ == "__main__":
    unittest.main()
