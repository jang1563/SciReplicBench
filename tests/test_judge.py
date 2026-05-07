"""Tests for structured judge helpers."""

from __future__ import annotations

import asyncio
import unittest

from scireplicbench.judge import (
    LeafJudgement,
    format_leaf_judge_prompt,
    judge_leaf,
    majority_vote_judgements,
    needs_self_consistency_retry,
    parse_leaf_judgement,
)


class JudgeHelpersTest(unittest.TestCase):
    def test_prompt_contains_required_structure(self) -> None:
        prompt = format_leaf_judge_prompt(
            {
                "id": "demo/result_match/leaf_a",
                "category": "result_match",
                "requirement": "Recover the top ranked genes.",
                "grading_notes": "Use overlap@k against the reference list.",
            },
            paper_summary="Short paper summary.",
            reality_context="Observed output text.",
        )
        self.assertIn('"leaf_id":"..."', prompt)
        self.assertIn("evidence_quote", prompt)
        self.assertIn("For score 1, evidence_quote must appear verbatim", prompt)
        self.assertIn("no_valid_evidence", prompt)
        self.assertIn("Interpret words like `or` and `such as` literally", prompt)
        self.assertIn("a primary saved-source implementation can pass", prompt)
        self.assertIn("headers plus representative rows", prompt)

    def test_prompt_adds_code_development_evidence_policy(self) -> None:
        prompt = format_leaf_judge_prompt(
            {
                "id": "demo/code_development/leaf_a",
                "category": "code_development",
                "requirement": "Write the script.",
                "grading_notes": "README promises do not count.",
            },
            paper_summary="Short paper summary.",
            reality_context="Observed output text.",
        )
        self.assertIn("README text or planning prose is not valid evidence", prompt)
        self.assertIn("submission files", prompt)
        self.assertIn("`--- /workspace/submission/... ---` content block", prompt)
        self.assertIn("Do not quote output artifact text", prompt)

    def test_prompt_adds_result_match_evidence_policy(self) -> None:
        prompt = format_leaf_judge_prompt(
            {
                "id": "demo/result_match/leaf_a",
                "category": "result_match",
                "requirement": "Recover the benchmark metric.",
                "grading_notes": "Use the output artifact.",
            },
            paper_summary="Short paper summary.",
            reality_context="Observed output text.",
        )
        self.assertIn("submission-side claims are not valid evidence", prompt)
        self.assertIn("output artifacts", prompt)
        self.assertIn("`--- /workspace/output/... ---` content block", prompt)
        self.assertIn("Do not quote bare paths", prompt)

    def test_prompt_adds_execution_content_block_evidence_policy(self) -> None:
        prompt = format_leaf_judge_prompt(
            {
                "id": "demo/execution/leaf_a",
                "category": "execution",
                "requirement": "Run the workflow.",
                "grading_notes": "Use output artifacts.",
            },
            paper_summary="Short paper summary.",
            reality_context="Observed output text.",
        )
        self.assertIn("`--- /workspace/output/... ---` content block", prompt)
        self.assertIn("Do not quote bare output paths", prompt)
        self.assertIn("submission_manifest.json", prompt)

    def test_prompt_adds_exact_metric_guardrail_for_result_match(self) -> None:
        prompt = format_leaf_judge_prompt(
            {
                "id": "demo/result_match/top_moran_genes_overlap_threshold",
                "category": "result_match",
                "requirement": "The top Moran-ranked genes reach rank-biased overlap against the hidden reference.",
                "grading_notes": "Numeric-first comparator leaf.",
            },
            paper_summary="Short paper summary.",
            reality_context="Observed output text.",
        )
        self.assertIn("Do not reuse one overlap, correlation, or ranked-metric value", prompt)
        self.assertIn("Expected analysis anchors for this leaf include: moran", prompt)
        self.assertIn("different metric family", prompt)

    def test_prompt_adds_adjacent_step_guardrail_for_code_development(self) -> None:
        prompt = format_leaf_judge_prompt(
            {
                "id": "demo/code_development/join_image_features_to_adata",
                "category": "code_development",
                "requirement": "Join the image-derived features back to the expression object.",
                "grading_notes": "The scorer must be able to line up features with observations.",
            },
            paper_summary="Short paper summary.",
            reality_context="Observed output text.",
        )
        self.assertIn("A generic compute call does not automatically satisfy adjacent steps", prompt)
        self.assertIn("join/alignment to observations", prompt)
        self.assertIn("This category grades implementation only", prompt)
        self.assertIn("source code itself directly implements the leaf", prompt)

    def test_prompt_adds_explicit_runtime_success_guardrail_for_execution(self) -> None:
        prompt = format_leaf_judge_prompt(
            {
                "id": "demo/execution/visium_dataset_executes",
                "category": "execution",
                "requirement": "Load the benchmarked Visium dataset without fatal error.",
                "grading_notes": "Warnings are acceptable if the resulting object is usable.",
            },
            paper_summary="Short paper summary.",
            reality_context="Observed output text.",
        )
        self.assertIn("Execution evidence must correspond to the output family named by this leaf", prompt)
        self.assertIn("score 1 when a /workspace/output content block contains a header or row", prompt)
        self.assertIn("explicitly names the exact dataset, function, or artifact family required by the leaf", prompt)
        self.assertIn("successful completion", prompt)
        self.assertIn("benchmark-comparison score such as overlap, RBO, ARI, or correlation-to-reference is not enough", prompt)

    def test_parse_leaf_judgement_from_fenced_json(self) -> None:
        raw = """```json
        {
          "leaf_id": "demo/result_match/leaf_a",
          "expectations": "Recover the top ranked genes.",
          "reality": "Recovered 18 of the top 20 genes.",
          "evidence_quote": "top20_overlap=0.90",
          "score": 1
        }
        ```"""
        judgement = parse_leaf_judgement(raw, expected_leaf_id="demo/result_match/leaf_a")
        self.assertEqual(judgement.score, 1)
        self.assertEqual(judgement.evidence_quote, "top20_overlap=0.90")

    def test_parse_leaf_judgement_repairs_empty_quote_for_zero_score(self) -> None:
        judgement = parse_leaf_judgement(
            {
                "leaf_id": "demo/result_match/leaf_a",
                "expectations": "Recover the top ranked genes.",
                "reality": "No comparable output was present.",
                "evidence_quote": "",
                "score": 0,
            },
            expected_leaf_id="demo/result_match/leaf_a",
        )

        self.assertEqual(judgement.score, 0)
        self.assertEqual(judgement.evidence_quote, "no_valid_evidence")
        self.assertTrue(judgement.metadata["empty_evidence_quote_repaired"])

    def test_parse_leaf_judgement_rejects_empty_quote_for_passing_score(self) -> None:
        with self.assertRaisesRegex(ValueError, "evidence_quote must be non-empty"):
            parse_leaf_judgement(
                {
                    "leaf_id": "demo/result_match/leaf_a",
                    "expectations": "Recover the top ranked genes.",
                    "reality": "Claims success.",
                    "evidence_quote": "",
                    "score": 1,
                },
                expected_leaf_id="demo/result_match/leaf_a",
            )

    def test_majority_vote_and_retry_detection(self) -> None:
        judgements = [
            LeafJudgement("leaf", "exp", "real", "quote a", 1, confidence=0.7),
            LeafJudgement("leaf", "exp", "real", "quote b", 0, confidence=0.6),
            LeafJudgement("leaf", "exp", "real", "quote c", 1, confidence=0.8),
        ]
        self.assertTrue(needs_self_consistency_retry(judgements))
        consensus = majority_vote_judgements(judgements)
        self.assertEqual(consensus.score, 1)
        self.assertEqual(consensus.metadata["votes_for_score"], 2)

    def test_judge_leaf_accepts_sync_client(self) -> None:
        async def run() -> LeafJudgement:
            return await judge_leaf(
                lambda prompt: {
                    "leaf_id": "demo/leaf",
                    "expectations": "Expectation summary",
                    "reality": "Reality summary",
                    "evidence_quote": "observed_metric=0.81",
                    "score": 1,
                },
                leaf={"id": "demo/leaf", "requirement": "Requirement", "grading_notes": "Notes"},
                paper_summary="Paper summary",
                reality_context="Observed metrics",
            )

        judgement = asyncio.run(run())
        self.assertEqual(judgement.score, 1)


if __name__ == "__main__":
    unittest.main()
