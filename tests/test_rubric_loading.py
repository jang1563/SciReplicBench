"""Tests for rubric loading and validation."""

from __future__ import annotations

import unittest
from pathlib import Path

from scireplicbench.rubric_utils import (
    collect_leaf_ids,
    extract_rubric_tree,
    load_rubric,
    validate_rubric_payload,
)


ROOT = Path(__file__).resolve().parents[1]
PAPERS_DIR = ROOT / "papers"


class RubricLoadingTest(unittest.TestCase):
    def test_project_rubrics_validate(self) -> None:
        expected_leaf_counts = {
            "inspiration4_multiome": 90,
            "squidpy_spatial": 65,
            "genelab_benchmark": 55,
        }

        for paper_id, expected_count in expected_leaf_counts.items():
            with self.subTest(paper_id=paper_id):
                payload = load_rubric(PAPERS_DIR / paper_id / "rubric.json")
                result = validate_rubric_payload(payload)
                self.assertTrue(result.is_valid, msg="\n".join(result.errors))
                self.assertEqual(result.leaf_count, expected_count)
                self.assertEqual(payload["total_leaf_nodes"], expected_count)
                self.assertEqual(len(set(collect_leaf_ids(extract_rubric_tree(payload)))), expected_count)

                self.assertGreaterEqual(result.category_weights["result_match"], 0.40)
                self.assertGreaterEqual(result.category_weights["execution"], 0.20)
                self.assertLessEqual(result.category_weights["code_development"], 0.40)


if __name__ == "__main__":
    unittest.main()
