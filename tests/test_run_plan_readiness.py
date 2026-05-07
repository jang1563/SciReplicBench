from __future__ import annotations

import json
import unittest

from scireplicbench.readiness import PROJECT_ROOT
from scireplicbench.run_plan import (
    build_phase4a_plan,
    build_phase4b_plan,
    render_plan_markdown,
)


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

    def test_committed_phase4b_manifest_matches_builder_output(self) -> None:
        manifest_path = PROJECT_ROOT / "configs" / "phase4b_production_plan.json"
        committed_manifest = json.loads(manifest_path.read_text())
        expected_manifest = [entry.to_dict() for entry in build_phase4b_plan()]
        self.assertEqual(committed_manifest, expected_manifest)

    def test_run_plan_markdown_summarizes_blocking_reasons_once_per_paper(self) -> None:
        markdown = render_plan_markdown(build_phase4b_plan(seeds=(1,)))
        self.assertIn("## Blocking Reasons", markdown)
        self.assertEqual(markdown.count("squidpy_spatial | evaluation |"), 1)
        self.assertIn("only one human rater", markdown)
