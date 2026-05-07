from __future__ import annotations

import unittest

from scireplicbench.readiness import (
    code_development_reference_ready,
    execution_reference_ready,
    hidden_reference_ready,
    phase_readiness_gate,
    result_match_reference_ready,
    second_human_rater_ready,
    squidpy_runtime_hardening_ready,
)


class HiddenReferenceReadinessTest(unittest.TestCase):
    def test_real_papers_are_not_production_ready_while_hidden_reference_is_pending(self) -> None:
        for paper_id in (
            "genelab_benchmark",
            "inspiration4_multiome",
        ):
            ready, reason = hidden_reference_ready(paper_id)
            self.assertFalse(ready)
            self.assertIsNotNone(reason)
            self.assertIn("pending", reason or "")

    def test_squidpy_deterministic_references_are_ready(self) -> None:
        hidden_ready, hidden_reason = hidden_reference_ready("squidpy_spatial")
        self.assertTrue(hidden_ready)
        self.assertIsNone(hidden_reason)

        result_ready, result_reason = result_match_reference_ready("squidpy_spatial")
        self.assertTrue(result_ready)
        self.assertIsNone(result_reason)

        execution_ready, execution_reason = execution_reference_ready("squidpy_spatial")
        self.assertTrue(execution_ready)
        self.assertIsNone(execution_reason)

        code_ready, code_reason = code_development_reference_ready("squidpy_spatial")
        self.assertTrue(code_ready)
        self.assertIsNone(code_reason)


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

    def test_squidpy_runtime_hardening_guardrail_is_present(self) -> None:
        ready, reason = squidpy_runtime_hardening_ready()
        self.assertTrue(ready)
        self.assertIsNone(reason)

    def test_squidpy_production_still_blocked_by_single_rater_panel(self) -> None:
        gate = phase_readiness_gate("squidpy_spatial", "phase4b_production")
        self.assertFalse(gate.run_allowed)
        self.assertTrue(
            any("one human rater" in reason for reason in gate.blocking_reasons)
        )
