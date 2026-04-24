"""Tests for the artifact-presence precheck (v0.2 scaffold-bias guard)."""

from __future__ import annotations

import asyncio
import unittest
from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from scireplicbench.judge import LeafJudgement
from scireplicbench.scorers import (
    _artifact_presence_precheck,
    _has_nontrivial_body,
)


def _run(coro):
    return asyncio.run(coro)


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
                    "weight": 0.30,
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
                    "weight": 0.30,
                    "is_leaf": False,
                    "children": [
                        {
                            "id": "demo/execution/leaf_two",
                            "name": "Leaf Two",
                            "weight": 1.0,
                            "is_leaf": True,
                            "requirement": "Do the second thing.",
                            "grading_notes": "",
                            "category": "execution",
                        }
                    ],
                },
                {
                    "id": "demo/result_match",
                    "name": "Result Match",
                    "weight": 0.40,
                    "is_leaf": False,
                    "children": [
                        {
                            "id": "demo/result_match/leaf_three",
                            "name": "Leaf Three",
                            "weight": 1.0,
                            "is_leaf": True,
                            "requirement": "Recover the result.",
                            "grading_notes": "",
                            "category": "result_match",
                        }
                    ],
                },
            ],
        },
    }


class NontrivialBodyTest(unittest.TestCase):
    """AST-level behaviour of `_has_nontrivial_body`."""

    def test_nontrivial_body_pass_only(self) -> None:
        self.assertFalse(_has_nontrivial_body("def f():\n    pass\n"))

    def test_nontrivial_body_ellipsis_only(self) -> None:
        self.assertFalse(_has_nontrivial_body("def f():\n    ...\n"))

    def test_nontrivial_body_docstring_only(self) -> None:
        self.assertFalse(_has_nontrivial_body('def f():\n    """doc"""\n'))

    def test_nontrivial_body_raise_notimpl_bare(self) -> None:
        self.assertFalse(
            _has_nontrivial_body("def f():\n    raise NotImplementedError\n")
        )

    def test_nontrivial_body_raise_notimpl_call(self) -> None:
        self.assertFalse(
            _has_nontrivial_body(
                'def f():\n    raise NotImplementedError("todo")\n'
            )
        )

    def test_nontrivial_body_real_function(self) -> None:
        source = "def f(x):\n    y = x + 1\n    return y\n"
        self.assertTrue(_has_nontrivial_body(source))

    def test_nontrivial_body_class_only_trivial_methods(self) -> None:
        source = (
            "class Pipeline:\n"
            "    def run(self):\n"
            "        pass\n"
            "    def finalize(self):\n"
            "        \"\"\"todo\"\"\"\n"
        )
        self.assertFalse(_has_nontrivial_body(source))

    def test_nontrivial_body_class_with_real_method(self) -> None:
        source = (
            "class Pipeline:\n"
            "    def run(self):\n"
            "        pass\n"
            "    def finalize(self):\n"
            "        return 42\n"
        )
        self.assertTrue(_has_nontrivial_body(source))

    def test_nontrivial_body_module_level_statement(self) -> None:
        self.assertTrue(_has_nontrivial_body("import os\nfoo = os.getcwd()\n"))

    def test_nontrivial_body_syntax_error(self) -> None:
        # unparseable; treat as non-executable
        self.assertFalse(_has_nontrivial_body("def f(:\n    pass\n"))


@dataclass
class _FakeExecResult:
    stdout: str
    returncode: int = 0


class _FakeSandbox:
    """Minimal sandbox double for precheck unit tests."""

    def __init__(
        self,
        *,
        py_paths: list[str] | None = None,
        output_paths: list[str] | None = None,
        files: dict[str, str] | None = None,
        exec_raises: Exception | None = None,
    ) -> None:
        self._py_paths = py_paths or []
        self._output_paths = output_paths or []
        self._files = files or {}
        self._exec_raises = exec_raises

    async def exec(self, argv):
        if self._exec_raises is not None:
            raise self._exec_raises
        cmd = argv[-1] if argv else ""
        if "submission" in cmd and "*.py" in cmd:
            return _FakeExecResult(stdout="\n".join(self._py_paths) + "\n")
        if "output" in cmd and "README" in cmd:
            return _FakeExecResult(stdout="\n".join(self._output_paths) + "\n")
        return _FakeExecResult(stdout="")

    async def read_file(self, path: str) -> str:
        if path not in self._files:
            raise FileNotFoundError(path)
        return self._files[path]


class PrecheckFunctionTest(unittest.TestCase):
    """Behaviour of `_artifact_presence_precheck` against a mock sandbox."""

    def _patched(self, fake: _FakeSandbox):
        return patch(
            "scireplicbench.scorers.sandbox",
            new=MagicMock(return_value=fake),
        )

    def test_precheck_ok_when_any_code_present(self) -> None:
        fake = _FakeSandbox(
            py_paths=["/workspace/submission/analysis.py"],
            files={
                "/workspace/submission/analysis.py": (
                    "def analyse(x):\n    y = x * 2\n    return y\n"
                )
            },
        )
        with self._patched(fake):
            result = _run(_artifact_presence_precheck())
        self.assertTrue(result["ok"])
        self.assertEqual(result["nontrivial_py_files"], 1)
        self.assertEqual(result["nontrivial_py_examples"], ["/workspace/submission/analysis.py"])
        self.assertIsNone(result["reason"])

    def test_precheck_fails_when_only_output_artifact_present(self) -> None:
        # Zero .py files, but a CSV exists under /workspace/output.
        fake = _FakeSandbox(
            py_paths=[],
            output_paths=["/workspace/output/results.csv"],
        )
        with self._patched(fake):
            result = _run(_artifact_presence_precheck())
        self.assertFalse(result["ok"])
        self.assertEqual(result["nontrivial_py_files"], 0)
        self.assertEqual(result["output_artifact_count"], 1)
        self.assertIsNotNone(result["reason"])

    def test_precheck_fails_on_empty_scaffold(self) -> None:
        # One .py file whose body is only `pass`, no non-doc output files.
        fake = _FakeSandbox(
            py_paths=["/workspace/submission/scripts/load.py"],
            files={
                "/workspace/submission/scripts/load.py": "def load():\n    pass\n"
            },
            output_paths=[],
        )
        with self._patched(fake):
            result = _run(_artifact_presence_precheck())
        self.assertFalse(result["ok"])
        self.assertEqual(result["nontrivial_py_files"], 0)
        self.assertIn("non-trivial", result["reason"])

    def test_precheck_fail_open_on_sandbox_error(self) -> None:
        fake = _FakeSandbox(exec_raises=RuntimeError("daemon unreachable"))
        with self._patched(fake):
            result = _run(_artifact_presence_precheck())
        self.assertTrue(result["ok"])
        self.assertEqual(result.get("fallback"), "allow")
        self.assertIn("RuntimeError", result["reason"])
        self.assertIn("daemon unreachable", result["reason"])


class ScorerPrecheckIntegrationTest(unittest.TestCase):
    """End-to-end: when precheck fails, the judge is never called."""

    def test_scorer_auto_zeros_on_precheck_fail(self) -> None:
        from scireplicbench import scorers

        if not getattr(scorers, "_HAS_INSPECT_SCORING", False):
            self.skipTest("inspect-ai runtime not available")

        rubric_payload = _demo_rubric_payload()

        precheck_failure = {
            "ok": False,
            "reason": "no Python file with a non-trivial function body",
            "nontrivial_py_files": 0,
            "nontrivial_py_examples": [],
            "output_artifact_count": 0,
            "output_artifact_examples": [],
        }

        judge_that_would_pass = LeafJudgement(
            leaf_id="unused",
            expectations="would pass",
            reality="would pass",
            evidence_quote="would pass",
            score=1,
        )

        state = SimpleNamespace(
            metadata={"paper_id": "demo"},
            sample_id="demo_main",
            messages=[],
        )
        target = SimpleNamespace()

        judge_mock = AsyncMock(return_value=judge_that_would_pass)
        model_mock = MagicMock()

        scorer_factory = scorers.rubric_tree_scorer
        score_coro = scorer_factory(judge_model="openai/gpt-4o-mini")

        with patch.object(scorers, "load_rubric_payload", return_value=rubric_payload), patch.object(
            scorers, "load_paper_summary", return_value="demo paper summary"
        ), patch.object(scorers, "_collect_submission_context", AsyncMock(return_value="")), patch.object(
            scorers, "_artifact_presence_precheck", AsyncMock(return_value=precheck_failure)
        ), patch.object(scorers, "_judge_leaf", judge_mock), patch.object(
            scorers, "get_model", MagicMock(return_value=model_mock)
        ):
            result = _run(score_coro(state, target))

        self.assertEqual(judge_mock.await_count, 0)
        self.assertEqual(result.value, 0.0)
        self.assertEqual(result.metadata["precheck"]["ok"], False)
        self.assertEqual(result.metadata["leaves_graded"], 0)
        self.assertEqual(result.metadata["leaves_total"], 3)
        leaf_judgements = result.metadata["leaf_judgements"]
        self.assertEqual(len(leaf_judgements), 3)
        for judgement in leaf_judgements:
            self.assertEqual(judgement["score"], 0)
            self.assertIn("precheck_failed", judgement["evidence_quote"])


class ScorerEvidencePolicyIntegrationTest(unittest.TestCase):
    """End-to-end scorer behaviour once precheck succeeds."""

    def test_scorer_zeroes_prose_inflated_passes_after_precheck_success(self) -> None:
        from scireplicbench import scorers

        if not getattr(scorers, "_HAS_INSPECT_SCORING", False):
            self.skipTest("inspect-ai runtime not available")

        precheck_success = {
            "ok": True,
            "reason": None,
            "nontrivial_py_files": 1,
            "nontrivial_py_examples": ["/workspace/submission/pipeline.py"],
            "output_artifact_count": 1,
            "output_artifact_examples": ["/workspace/output/results.csv"],
        }
        reality = (
            "Submission file list:\n"
            "/workspace/submission/README.md\n"
            "/workspace/submission/pipeline.py\n"
            "/workspace/output/results.csv\n"
            "\n--- /workspace/submission/README.md ---\n"
            "This README provides instructions on running the Squidpy workflow.\n"
            "\n--- /workspace/submission/pipeline.py ---\n"
            "def run_pipeline():\n"
            "    top20_overlap = 0.90\n"
            "    return top20_overlap\n"
        )
        judge_mock = AsyncMock(
            side_effect=[
                LeafJudgement(
                    leaf_id="demo/code_development/leaf_one",
                    expectations="Write the code.",
                    reality="Observed README prose.",
                    evidence_quote="This README provides instructions on running the Squidpy workflow.",
                    score=1,
                ),
                LeafJudgement(
                    leaf_id="demo/execution/leaf_two",
                    expectations="Run the code.",
                    reality="Observed an output path.",
                    evidence_quote="/workspace/output/results.csv",
                    score=1,
                ),
                LeafJudgement(
                    leaf_id="demo/result_match/leaf_three",
                    expectations="Recover the metric.",
                    reality="Observed a claimed metric in submission code.",
                    evidence_quote="top20_overlap = 0.90",
                    score=1,
                ),
            ]
        )

        state = SimpleNamespace(
            metadata={"paper_id": "demo"},
            sample_id="demo_main",
            messages=[],
        )
        target = SimpleNamespace()
        score_coro = scorers.rubric_tree_scorer(judge_model="openai/gpt-4o-mini")

        with patch.object(scorers, "load_rubric_payload", return_value=_demo_rubric_payload()), patch.object(
            scorers, "load_paper_summary", return_value="demo paper summary"
        ), patch.object(scorers, "_collect_submission_context", AsyncMock(return_value=reality)), patch.object(
            scorers, "_artifact_presence_precheck", AsyncMock(return_value=precheck_success)
        ), patch.object(scorers, "_judge_leaf", judge_mock), patch.object(
            scorers, "get_model", MagicMock(return_value=MagicMock())
        ):
            result = _run(score_coro(state, target))

        self.assertEqual(judge_mock.await_count, 3)
        self.assertEqual(result.metadata["precheck"]["ok"], True)
        self.assertEqual(result.metadata["leaves_graded"], 3)
        self.assertEqual(result.value, 0.0)

        leaf_judgements = {
            judgement["leaf_id"]: judgement for judgement in result.metadata["leaf_judgements"]
        }
        self.assertEqual(leaf_judgements["demo/code_development/leaf_one"]["score"], 0)
        self.assertIn(
            "README-style prose",
            leaf_judgements["demo/code_development/leaf_one"]["evidence_quote"],
        )
        self.assertEqual(leaf_judgements["demo/execution/leaf_two"]["score"], 0)
        self.assertIn(
            "bare output-file path",
            leaf_judgements["demo/execution/leaf_two"]["evidence_quote"],
        )
        self.assertEqual(leaf_judgements["demo/result_match/leaf_three"]["score"], 0)
        self.assertIn(
            "submission-side claims",
            leaf_judgements["demo/result_match/leaf_three"]["evidence_quote"],
        )

    def test_scorer_preserves_valid_evidence_after_precheck_success(self) -> None:
        from scireplicbench import scorers

        if not getattr(scorers, "_HAS_INSPECT_SCORING", False):
            self.skipTest("inspect-ai runtime not available")

        precheck_success = {
            "ok": True,
            "reason": None,
            "nontrivial_py_files": 1,
            "nontrivial_py_examples": ["/workspace/submission/pipeline.py"],
            "output_artifact_count": 2,
            "output_artifact_examples": [
                "/workspace/output/results.csv",
                "/workspace/output/metrics.txt",
            ],
        }
        reality = (
            "Submission file list:\n"
            "/workspace/submission/pipeline.py\n"
            "/workspace/output/results.csv\n"
            "/workspace/output/metrics.txt\n"
            "\n--- /workspace/submission/pipeline.py ---\n"
            "sq.gr.spatial_neighbors(adata, coord_type='grid')\n"
            "\n--- /workspace/output/results.csv ---\n"
            "command exited with status 0\n"
            "\n--- /workspace/output/metrics.txt ---\n"
            "top20_overlap=0.90\n"
        )
        judge_mock = AsyncMock(
            side_effect=[
                LeafJudgement(
                    leaf_id="demo/code_development/leaf_one",
                    expectations="Write the code.",
                    reality="Observed real code.",
                    evidence_quote="sq.gr.spatial_neighbors(adata, coord_type='grid')",
                    score=1,
                ),
                LeafJudgement(
                    leaf_id="demo/execution/leaf_two",
                    expectations="Run the code.",
                    reality="Observed runtime output.",
                    evidence_quote="command exited with status 0",
                    score=1,
                ),
                LeafJudgement(
                    leaf_id="demo/result_match/leaf_three",
                    expectations="Recover the metric.",
                    reality="Observed output metric.",
                    evidence_quote="top20_overlap=0.90",
                    score=1,
                ),
            ]
        )

        state = SimpleNamespace(
            metadata={"paper_id": "demo"},
            sample_id="demo_main",
            messages=[],
        )
        target = SimpleNamespace()
        score_coro = scorers.rubric_tree_scorer(judge_model="openai/gpt-4o-mini")

        with patch.object(scorers, "load_rubric_payload", return_value=_demo_rubric_payload()), patch.object(
            scorers, "load_paper_summary", return_value="demo paper summary"
        ), patch.object(scorers, "_collect_submission_context", AsyncMock(return_value=reality)), patch.object(
            scorers, "_artifact_presence_precheck", AsyncMock(return_value=precheck_success)
        ), patch.object(scorers, "_judge_leaf", judge_mock), patch.object(
            scorers, "get_model", MagicMock(return_value=MagicMock())
        ):
            result = _run(score_coro(state, target))

        self.assertEqual(judge_mock.await_count, 3)
        self.assertEqual(result.metadata["precheck"]["ok"], True)
        self.assertEqual(result.metadata["leaves_graded"], 3)
        self.assertEqual(result.value, 1.0)

        leaf_judgements = {
            judgement["leaf_id"]: judgement for judgement in result.metadata["leaf_judgements"]
        }
        self.assertEqual(leaf_judgements["demo/code_development/leaf_one"]["score"], 1)
        self.assertEqual(
            leaf_judgements["demo/code_development/leaf_one"]["metadata"]["evidence_sources"][0][
                "path"
            ],
            "/workspace/submission/pipeline.py",
        )
        self.assertEqual(leaf_judgements["demo/execution/leaf_two"]["score"], 1)
        self.assertEqual(
            leaf_judgements["demo/execution/leaf_two"]["metadata"]["evidence_sources"][0]["path"],
            "/workspace/output/results.csv",
        )
        self.assertEqual(leaf_judgements["demo/result_match/leaf_three"]["score"], 1)
        self.assertEqual(
            leaf_judgements["demo/result_match/leaf_three"]["metadata"]["evidence_sources"][0][
                "path"
            ],
            "/workspace/output/metrics.txt",
        )


if __name__ == "__main__":
    unittest.main()
