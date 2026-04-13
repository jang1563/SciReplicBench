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
