from __future__ import annotations

import unittest

from scireplicbench.run_plan import build_phase4a_plan, build_phase4b_plan


class RunPlanReadinessTest(unittest.TestCase):
    def test_phase4a_plan_carries_readiness_gate_metadata(self) -> None:
        entries = build_phase4a_plan()
        inspiration4_entry = next(
            entry
            for entry in entries
            if entry.paper_id == "inspiration4_multiome"
            and entry.agent.label == "gpt-4o-mini"
        )
        self.assertIn("lane", inspiration4_entry.readiness_gate)
        self.assertFalse(inspiration4_entry.readiness_gate["run_allowed"])
        self.assertEqual(inspiration4_entry.readiness_gate["lane"], "enablement")
        payload = inspiration4_entry.to_dict()
        self.assertIn("readiness_gate", payload)

    def test_phase4b_plan_enables_self_consistency_metadata(self) -> None:
        entries = build_phase4b_plan(seeds=(1,))
        genelab_entry = next(
            entry
            for entry in entries
            if entry.paper_id == "genelab_benchmark"
            and entry.agent.label == "gpt-4o"
        )
        self.assertEqual(genelab_entry.judge_self_consistency_n, 3)
        command = genelab_entry.inspect_eval_command()
        self.assertIn("judge_self_consistency_n=3", command)
        self.assertFalse(genelab_entry.readiness_gate["run_allowed"])
