"""Tests for Phase 4 run-plan helpers."""

from __future__ import annotations

import unittest

from scireplicbench.run_plan import build_phase4a_plan, build_phase4b_plan


class RunPlanTest(unittest.TestCase):
    def test_phase4a_plan_shape(self) -> None:
        plan = build_phase4a_plan()
        self.assertEqual(len(plan), 9)
        command = plan[0].inspect_eval_command(log_dir="logs-pilot")
        self.assertIn("inspect", command[0])
        self.assertIn("src/scireplicbench/tasks.py@scireplicbench", command)
        self.assertIn("--model-role", command)

    def test_phase4b_plan_shape(self) -> None:
        plan = build_phase4b_plan()
        self.assertEqual(len(plan), 18)
        self.assertTrue(all(entry.phase == "phase4b_production" for entry in plan))


if __name__ == "__main__":
    unittest.main()
