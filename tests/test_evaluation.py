"""Tests for evaluation aggregation helpers."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scireplicbench.evaluation import (
    EvalRunRecord,
    aggregate_eval_runs,
    group_eval_runs,
    load_eval_run_records,
    render_eval_markdown,
)


class EvaluationHelpersTest(unittest.TestCase):
    def test_aggregate_eval_runs(self) -> None:
        records = [
            EvalRunRecord(
                run_id="r1",
                paper_id="p1",
                agent_model="agent-a",
                judge_model="judge-a",
                seed=1,
                status="completed",
                overall_score=0.6,
                category_scores={"execution": 0.5, "result_match": 0.7},
                cost_usd=1.2,
                prompt_tokens=100,
                completion_tokens=20,
                judge_retries=1,
                failure_modes=["environment_setup_drift"],
            ),
            EvalRunRecord(
                run_id="r2",
                paper_id="p1",
                agent_model="agent-a",
                judge_model="judge-a",
                seed=2,
                status="completed",
                overall_score=0.8,
                category_scores={"execution": 0.9, "result_match": 0.7},
                cost_usd=1.8,
                prompt_tokens=140,
                completion_tokens=40,
                judge_retries=0,
                failure_modes=["result_match_near_miss"],
            ),
        ]
        summary = aggregate_eval_runs(records)
        self.assertEqual(summary.run_count, 2)
        self.assertAlmostEqual(summary.mean_overall_score, 0.7)
        self.assertAlmostEqual(summary.mean_category_scores["execution"], 0.7)
        self.assertAlmostEqual(summary.total_cost_usd, 3.0)
        self.assertEqual(summary.failure_mode_counts["environment_setup_drift"], 1)

    def test_group_and_render_eval_runs(self) -> None:
        records = [
            EvalRunRecord(
                run_id="r1",
                paper_id="inspiration4_multiome",
                agent_model="gpt-4o-mini",
                judge_model="gpt-4o-mini",
                seed=1,
                status="completed",
                overall_score=0.55,
                category_scores={"execution": 0.6},
            ),
            EvalRunRecord(
                run_id="r2",
                paper_id="squidpy_spatial",
                agent_model="gpt-4o-mini",
                judge_model="gpt-4o-mini",
                seed=1,
                status="failed",
                overall_score=0.10,
                category_scores={"execution": 0.1},
                failure_modes=["environment_setup_drift"],
            ),
        ]
        grouped = group_eval_runs(records, keys=("agent_model", "paper_id"))
        self.assertEqual(len(grouped), 2)
        markdown = render_eval_markdown(records)
        self.assertIn("Evaluation Report", markdown)
        self.assertIn("gpt-4o-mini", markdown)
        self.assertIn("environment_setup_drift", markdown)

    def test_load_eval_run_records_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "runs.jsonl"
            path.write_text(
                '{"run_id":"r1","paper_id":"p1","agent_model":"a","judge_model":"j","seed":1,"status":"completed","overall_score":0.2,"category_scores":{"execution":0.2}}\n'
                '{"run_id":"r2","paper_id":"p2","agent_model":"a","judge_model":"j","seed":2,"status":"completed","overall_score":0.4,"category_scores":{"execution":0.4}}\n'
            )
            records = load_eval_run_records(path)
            self.assertEqual(len(records), 2)
            self.assertEqual(records[0].run_id, "r1")


if __name__ == "__main__":
    unittest.main()
