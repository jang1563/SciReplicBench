from __future__ import annotations

import unittest

from scireplicbench.readiness import (
    hidden_reference_ready,
    phase_readiness_gate,
    second_human_rater_ready,
)


class HiddenReferenceReadinessTest(unittest.TestCase):
    def test_real_papers_are_not_production_ready_while_hidden_reference_is_pending(self) -> None:
        for paper_id in (
            "genelab_benchmark",
            "inspiration4_multiome",
            "squidpy_spatial",
        ):
            ready, reason = hidden_reference_ready(paper_id)
            self.assertFalse(ready)
            self.assertIsNotNone(reason)
            self.assertIn("pending", reason or "")


class JudgePanelReadinessTest(unittest.TestCase):
    def test_single_rater_panel_is_not_production_ready(self) -> None:
        ready, reason = second_human_rater_ready()
        self.assertFalse(ready)
        self.assertIsNotNone(reason)
        self.assertIn("one human rater", reason or "")


class PhaseGateTest(unittest.TestCase):
    def test_inspiration4_pilot_is_gated_to_enablement_lane(self) -> None:
        gate = phase_readiness_gate("inspiration4_multiome", "phase4a_pilot")
        self.assertFalse(gate.run_allowed)
        self.assertEqual(gate.lane, "enablement")
        self.assertTrue(gate.blocking_reasons)

    def test_genelab_pilot_remains_allowed_but_not_production_ready(self) -> None:
        pilot_gate = phase_readiness_gate("genelab_benchmark", "phase4a_pilot")
        production_gate = phase_readiness_gate(
            "genelab_benchmark", "phase4b_production"
        )
        self.assertTrue(pilot_gate.run_allowed)
        self.assertEqual(pilot_gate.lane, "evaluation")
        self.assertFalse(production_gate.run_allowed)
        self.assertFalse(production_gate.production_ready)

