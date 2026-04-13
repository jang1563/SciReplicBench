"""Tests for judge reliability utilities."""

from __future__ import annotations

import importlib.util
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


if __name__ == "__main__":
    unittest.main()
