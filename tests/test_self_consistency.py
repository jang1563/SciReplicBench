from __future__ import annotations

import asyncio
import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from scireplicbench import scorers


def _demo_rubric_payload() -> dict[str, object]:
    return {
        "paper_id": "demo",
        "title": "Demo rubric",
        "total_leaf_nodes": 3,
        "rubric": {
            "id": "demo/rubric",
            "name": "Full Reproduction",
            "weight": 1.0,
            "is_leaf": False,
            "children": [
                {
                    "id": "demo/code_development",
                    "name": "Code Development",
                    "weight": 0.3,
                    "is_leaf": False,
                    "children": [
                        {
                            "id": "demo/code_development/leaf_one",
                            "name": "Leaf One",
                            "weight": 1.0,
                            "is_leaf": True,
                            "requirement": "Do the first thing.",
                            "grading_notes": "",
                            "category": "code_development",
                        }
                    ],
                },
                {
                    "id": "demo/execution",
                    "name": "Execution",
                    "weight": 0.2,
                    "is_leaf": False,
                    "children": [
                        {
                            "id": "demo/execution/leaf_two",
                            "name": "Leaf Two",
                            "weight": 1.0,
                            "is_leaf": True,
                            "requirement": "Run the thing.",
                            "grading_notes": "",
                            "category": "execution",
                        }
                    ],
                },
                {
                    "id": "demo/result_match",
                    "name": "Result Match",
                    "weight": 0.5,
                    "is_leaf": False,
                    "children": [
                        {
                            "id": "demo/result_match/leaf_three",
                            "name": "Leaf Three",
                            "weight": 1.0,
                            "is_leaf": True,
                            "requirement": "Match the expected result.",
                            "grading_notes": "",
                            "category": "result_match",
                        }
                    ],
                }
            ],
        },
    }


class _FakeJudge:
    def __init__(self, completions: list[str]) -> None:
        self._completions = completions
        self.calls = 0

    async def generate(self, prompt: str) -> SimpleNamespace:
        completion = self._completions[self.calls]
        self.calls += 1
        return SimpleNamespace(completion=completion)


def _judgement_payload(score: int, *, evidence_quote: str = "print('real code')") -> str:
    return json.dumps(
        {
            "leaf_id": "demo/code_development/leaf_one",
            "expectations": "Need real code.",
            "reality": "Observed code.",
            "evidence_quote": evidence_quote,
            "score": score,
        }
    )


class SelfConsistencyHelperTest(unittest.TestCase):
    def test_helper_runs_single_sample_when_disabled(self) -> None:
        fake_judge = _FakeJudge([_judgement_payload(1)])
        leaf = _demo_rubric_payload()["rubric"]["children"][0]["children"][0]  # type: ignore[index]
        judgement = asyncio.run(
            scorers._judge_leaf_with_self_consistency(  # type: ignore[attr-defined]
                fake_judge,
                leaf,
                paper_summary="demo",
                reality_context="--- /workspace/submission/main.py ---\nprint('real code')",
                self_consistency_n=1,
            )
        )
        self.assertEqual(fake_judge.calls, 1)
        self.assertEqual(judgement.metadata["self_consistency_samples"], 1)
        self.assertTrue(judgement.metadata["self_consistency_consensus"])

    def test_helper_retries_to_majority_vote_on_disagreement(self) -> None:
        fake_judge = _FakeJudge(
            [
                _judgement_payload(0),
                _judgement_payload(1),
                _judgement_payload(0),
            ]
        )
        leaf = _demo_rubric_payload()["rubric"]["children"][0]["children"][0]  # type: ignore[index]
        judgement = asyncio.run(
            scorers._judge_leaf_with_self_consistency(  # type: ignore[attr-defined]
                fake_judge,
                leaf,
                paper_summary="demo",
                reality_context="--- /workspace/submission/main.py ---\nprint('real code')",
                self_consistency_n=3,
            )
        )
        self.assertEqual(fake_judge.calls, 3)
        self.assertEqual(judgement.score, 0)
        self.assertEqual(judgement.metadata["votes_for_score"], 2)
        self.assertEqual(judgement.metadata["total_votes"], 3)
        self.assertEqual(judgement.metadata["self_consistency_samples"], 3)
        self.assertFalse(judgement.metadata["self_consistency_consensus"])


class SelfConsistencyScorerIntegrationTest(unittest.TestCase):
    def test_scorer_metadata_records_self_consistency(self) -> None:
        if not getattr(scorers, "_HAS_INSPECT_SCORING", False):
            self.skipTest("inspect-ai runtime not available")

        fake_judge = _FakeJudge(
            [
                _judgement_payload(0),
                _judgement_payload(1),
                _judgement_payload(0),
            ]
        )
        state = SimpleNamespace(metadata={"paper_id": "demo"}, sample_id="demo_main")
        rubric_payload = _demo_rubric_payload()

        async def run_score():
            with (
                patch.object(scorers, "load_rubric_payload", return_value=rubric_payload),
                patch.object(scorers, "load_paper_summary", return_value="demo summary"),
                patch.object(
                    scorers,
                    "_collect_submission_context",
                    return_value="--- /workspace/submission/main.py ---\nprint('real code')",
                ),
                patch.object(
                    scorers,
                    "_artifact_presence_precheck",
                    return_value={
                        "ok": True,
                        "reason": None,
                        "nontrivial_py_files": 1,
                        "output_artifact_count": 0,
                    },
                ),
                patch.object(scorers, "get_model", return_value=fake_judge),
                patch.dict(
                    os.environ,
                    {
                        "SCIREPLICBENCH_JUDGE_SELF_CONSISTENCY_N": "3",
                        "SCIREPLICBENCH_JUDGE_SELF_CONSISTENCY_MIN_CONFIDENCE": "0.6",
                    },
                    clear=False,
                ),
            ):
                score_fn = scorers.rubric_tree_scorer(judge_model="mockllm/model")
                return await score_fn(state, None)

        result = asyncio.run(run_score())
        self.assertEqual(result.metadata["judge_self_consistency_n"], 3)
        judgement = result.metadata["leaf_judgements"][0]
        self.assertEqual(judgement["metadata"]["self_consistency_samples"], 3)
        self.assertEqual(judgement["metadata"]["votes_for_score"], 2)
