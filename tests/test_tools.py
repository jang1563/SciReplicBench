from __future__ import annotations

import asyncio
import unittest
from pathlib import Path

from scireplicbench.tools import (
    PROTECTED_GENELAB_OUTPUTS,
    PROTECTED_GENELAB_OUTPUT_MESSAGE,
    PROTECTED_GENELAB_SOURCE_MESSAGE,
    PROTECTED_STARTER_LAUNCHER,
    PROTECTED_STARTER_MAIN_ANALYSIS,
    PROTECTED_SUBMISSION_LAUNCHER,
    PROTECTED_SUBMISSION_MAIN_ANALYSIS,
    _bash_command_writes_protected_source,
    _bash_command_writes_protected_launcher,
    _is_protected_genelab_output_path,
    _is_protected_genelab_source_path,
    _is_protected_launcher_path,
    _looks_like_rich_genelab_source,
    _looks_like_rich_genelab_tsv,
    _normalize_workspace_text_path,
    _truncate_workspace_text,
    _would_append_to_protected_genelab_source,
    _would_downgrade_protected_genelab_output,
    _would_downgrade_protected_genelab_source,
)


class WorkspaceTextPathTest(unittest.TestCase):
    def test_normalize_workspace_text_path_accepts_allowed_roots(self) -> None:
        self.assertEqual(
            _normalize_workspace_text_path(
                "/workspace/submission/main.py",
                action="write",
            ),
            "/workspace/submission/main.py",
        )
        self.assertEqual(
            _normalize_workspace_text_path(
                "/workspace/output/agent/lomo/summary.tsv",
                action="append",
            ),
            "/workspace/output/agent/lomo/summary.tsv",
        )
        self.assertEqual(
            _normalize_workspace_text_path(
                "/workspace/logs/workflow.log",
                action="write",
            ),
            "/workspace/logs/workflow.log",
        )

    def test_normalize_workspace_text_path_normalizes_parent_segments(self) -> None:
        self.assertEqual(
            _normalize_workspace_text_path(
                "/workspace/submission/../submission/scripts/../main.py",
                action="write",
            ),
            "/workspace/submission/main.py",
        )

    def test_normalize_workspace_text_path_allows_workspace_input_for_reads(self) -> None:
        self.assertEqual(
            _normalize_workspace_text_path(
                "/workspace/input/paper_bundle/paper.md",
                action="read",
            ),
            "/workspace/input/paper_bundle/paper.md",
        )

    def test_normalize_workspace_text_path_rejects_relative_paths(self) -> None:
        with self.assertRaises(ValueError):
            _normalize_workspace_text_path("submission/main.py", action="write")

    def test_normalize_workspace_text_path_rejects_disallowed_roots(self) -> None:
        with self.assertRaises(ValueError):
            _normalize_workspace_text_path("/etc/passwd", action="read")

    def test_normalize_workspace_text_path_rejects_workspace_input_for_writes(self) -> None:
        with self.assertRaises(ValueError):
            _normalize_workspace_text_path("/workspace/input/paper_bundle/paper.md", action="write")


class ProtectedLauncherTest(unittest.TestCase):
    def test_protected_launcher_path_is_recognized(self) -> None:
        self.assertTrue(_is_protected_launcher_path(PROTECTED_SUBMISSION_LAUNCHER))
        self.assertFalse(_is_protected_launcher_path("/workspace/submission/main_analysis.py"))

    def test_bash_guard_detects_common_launcher_overwrites(self) -> None:
        blocked_commands = [
            "cat <<'EOF' > /workspace/submission/run.sh\n#!/bin/bash\nEOF",
            "printf '#!/bin/bash\\n' >> /workspace/submission/run.sh",
            "tee /workspace/submission/run.sh >/dev/null",
            "cp /tmp/run.sh /workspace/submission/run.sh",
            "sed -i 's/x/y/' /workspace/submission/run.sh",
        ]
        for cmd in blocked_commands:
            with self.subTest(cmd=cmd):
                self.assertTrue(_bash_command_writes_protected_launcher(cmd))

    def test_bash_guard_allows_launcher_reads_and_execution(self) -> None:
        allowed_commands = [
            "cat /workspace/submission/run.sh",
            "chmod +x /workspace/submission/run.sh",
            "/workspace/submission/run.sh",
            "bash /workspace/submission/run.sh",
        ]
        for cmd in allowed_commands:
            with self.subTest(cmd=cmd):
                self.assertFalse(_bash_command_writes_protected_launcher(cmd))


class ProtectedGeneLabOutputTest(unittest.TestCase):
    def test_protected_genelab_output_paths_are_recognized(self) -> None:
        for path in PROTECTED_GENELAB_OUTPUTS:
            with self.subTest(path=path):
                self.assertTrue(_is_protected_genelab_output_path(path))
        self.assertFalse(_is_protected_genelab_output_path("/workspace/output/other.tsv"))

    def test_rich_genelab_tsv_detection_requires_rows_and_columns(self) -> None:
        rich = (
            "tissue\tfold\tmodel\tstatus\tauroc\tci_lower\n"
            "A\tf1\tElasticNetLogReg\tok\t0.7\t0.6\n"
            "A\tf1\tRandomForest\tok\t0.6\t0.5\n"
            "A\tf2\tElasticNetLogReg\tok\t0.8\t0.7\n"
            "A\tf2\tRandomForest\tok\t0.7\t0.6\n"
        )
        shallow = "Feature\tImportance\nGene_1\t0.25\nGene_2\t0.20\n"
        self.assertTrue(_looks_like_rich_genelab_tsv(rich))
        self.assertFalse(_looks_like_rich_genelab_tsv(shallow))

    def test_downgrade_guard_blocks_shallow_replacement_after_fallback(self) -> None:
        class FakeEnv:
            def __init__(self, files: dict[str, str]) -> None:
                self.files = files

            async def read_file(self, path: str) -> str:
                if path not in self.files:
                    raise FileNotFoundError(path)
                return self.files[path]

        protected_path = "/workspace/output/agent/lomo/summary.tsv"
        rich_existing = (
            "tissue\tfold\tmodel\tstatus\tauroc\tci_lower\n"
            "A\tf1\tElasticNetLogReg\tok\t0.7\t0.6\n"
            "A\tf1\tRandomForest\tok\t0.6\t0.5\n"
            "A\tf2\tElasticNetLogReg\tok\t0.8\t0.7\n"
            "A\tf2\tRandomForest\tok\t0.7\t0.6\n"
        )
        shallow_replacement = "Tissue\tFold\tAUROC\nA\tf1\t0.7\n"
        rich_replacement = rich_existing + "A\tf3\tXGBoost\tok\t0.9\t0.8\n"
        env = FakeEnv(
            {
                PROTECTED_STARTER_LAUNCHER: "#!/usr/bin/env bash\n",
                protected_path: rich_existing,
            }
        )

        self.assertTrue(
            asyncio.run(
                _would_downgrade_protected_genelab_output(
                    env,
                    protected_path,
                    shallow_replacement,
                )
            )
        )
        self.assertFalse(
            asyncio.run(
                _would_downgrade_protected_genelab_output(
                    env,
                    protected_path,
                    rich_replacement,
                )
            )
        )
        self.assertIn("rich benchmark-style table", PROTECTED_GENELAB_OUTPUT_MESSAGE)


class ProtectedGeneLabSourceTest(unittest.TestCase):
    def _rich_source(self) -> str:
        markers = [
            "LOMO_FIELDS",
            "TRANSFER_FIELDS",
            "NEGATIVE_FIELDS",
            "INTERPRETABILITY_FIELDS",
            "GO_NOGO_FIELDS",
            "FOUNDATION_FIELDS",
            "heldout_mission",
            "ci_lower",
            "ci_upper",
            "perm_pvalue",
            "bootstrap",
            "permutation",
            "feature_rank",
            "Geneformer",
            "lomo/summary.tsv",
            "transfer/cross_tissue.tsv",
            "negative_controls/summary.tsv",
            "interpretability/top_features.tsv",
            "go_nogo/summary.tsv",
            "foundation/geneformer_staging.tsv",
            "submission_manifest.json",
        ]
        filler = [f"# line {index}" for index in range(90)]
        return "\n".join(markers + filler)

    def test_protected_genelab_source_path_is_recognized(self) -> None:
        self.assertTrue(_is_protected_genelab_source_path(PROTECTED_SUBMISSION_MAIN_ANALYSIS))
        self.assertFalse(_is_protected_genelab_source_path("/workspace/submission/other.py"))

    def test_rich_genelab_source_detection_requires_outputs_and_methods(self) -> None:
        shallow = (
            "import pandas as pd\n"
            "results_df.to_csv('/workspace/output/agent/lomo/summary.tsv', sep='\\t')\n"
        )
        self.assertTrue(_looks_like_rich_genelab_source(self._rich_source()))
        self.assertFalse(_looks_like_rich_genelab_source(shallow))

    def test_rich_genelab_source_detection_accepts_real_starter(self) -> None:
        starter_path = Path("papers/genelab_benchmark/starter/main_analysis.py")

        self.assertTrue(_looks_like_rich_genelab_source(starter_path.read_text()))

    def test_source_downgrade_guard_blocks_thin_replacement(self) -> None:
        class FakeEnv:
            def __init__(self, files: dict[str, str]) -> None:
                self.files = files

            async def read_file(self, path: str) -> str:
                if path not in self.files:
                    raise FileNotFoundError(path)
                return self.files[path]

        shallow_replacement = (
            "import pandas as pd\n"
            "results_df.to_csv('/workspace/output/agent/lomo/summary.tsv', sep='\\t')\n"
        )
        rich_source = self._rich_source()
        env = FakeEnv(
            {
                PROTECTED_STARTER_MAIN_ANALYSIS: rich_source,
                PROTECTED_SUBMISSION_MAIN_ANALYSIS: rich_source,
            }
        )

        self.assertTrue(
            asyncio.run(
                _would_downgrade_protected_genelab_source(
                    env,
                    PROTECTED_SUBMISSION_MAIN_ANALYSIS,
                    shallow_replacement,
                )
            )
        )
        self.assertFalse(
            asyncio.run(
                _would_downgrade_protected_genelab_source(
                    env,
                    PROTECTED_SUBMISSION_MAIN_ANALYSIS,
                    rich_source,
                )
            )
        )
        self.assertIn("thin partial script", PROTECTED_GENELAB_SOURCE_MESSAGE)

    def test_source_downgrade_guard_uses_starter_when_submission_missing(self) -> None:
        class FakeEnv:
            def __init__(self, files: dict[str, str]) -> None:
                self.files = files

            async def read_file(self, path: str) -> str:
                if path not in self.files:
                    raise FileNotFoundError(path)
                return self.files[path]

        shallow_replacement = (
            "import pandas as pd\n"
            "results_df.to_csv('/workspace/output/agent/lomo/summary.tsv', sep='\\t')\n"
        )
        env = FakeEnv({PROTECTED_STARTER_MAIN_ANALYSIS: self._rich_source()})

        self.assertTrue(
            asyncio.run(
                _would_downgrade_protected_genelab_source(
                    env,
                    PROTECTED_SUBMISSION_MAIN_ANALYSIS,
                    shallow_replacement,
                )
            )
        )

    def test_source_append_guard_blocks_mutating_rich_seeded_source(self) -> None:
        class FakeEnv:
            def __init__(self, files: dict[str, str]) -> None:
                self.files = files

            async def read_file(self, path: str) -> str:
                if path not in self.files:
                    raise FileNotFoundError(path)
                return self.files[path]

        rich_source = self._rich_source()
        env = FakeEnv(
            {
                PROTECTED_STARTER_MAIN_ANALYSIS: rich_source,
                PROTECTED_SUBMISSION_MAIN_ANALYSIS: rich_source,
            }
        )

        self.assertTrue(
            asyncio.run(
                _would_append_to_protected_genelab_source(
                    env,
                    PROTECTED_SUBMISSION_MAIN_ANALYSIS,
                )
            )
        )
        self.assertFalse(
            asyncio.run(
                _would_append_to_protected_genelab_source(
                    env,
                    "/workspace/submission/helper.py",
                )
            )
        )

    def test_source_append_guard_uses_starter_when_submission_missing(self) -> None:
        class FakeEnv:
            def __init__(self, files: dict[str, str]) -> None:
                self.files = files

            async def read_file(self, path: str) -> str:
                if path not in self.files:
                    raise FileNotFoundError(path)
                return self.files[path]

        env = FakeEnv({PROTECTED_STARTER_MAIN_ANALYSIS: self._rich_source()})

        self.assertTrue(
            asyncio.run(
                _would_append_to_protected_genelab_source(
                    env,
                    PROTECTED_SUBMISSION_MAIN_ANALYSIS,
                )
            )
        )

    def test_bash_guard_blocks_source_mutations_but_allows_starter_copy(self) -> None:
        blocked_commands = [
            "cat <<'PY' > /workspace/submission/main_analysis.py\nprint('thin')\nPY",
            "tee /workspace/submission/main_analysis.py >/dev/null",
            "cp /tmp/main_analysis.py /workspace/submission/main_analysis.py",
            "sed -i 's/x/y/' /workspace/submission/main_analysis.py",
        ]
        for cmd in blocked_commands:
            with self.subTest(cmd=cmd):
                self.assertTrue(_bash_command_writes_protected_source(cmd))

        allowed = (
            "cp /workspace/input/paper_bundle/starter/main_analysis.py "
            "/workspace/submission/main_analysis.py"
        )
        self.assertFalse(_bash_command_writes_protected_source(allowed))
        self.assertFalse(
            _bash_command_writes_protected_source(
                "python3 /workspace/submission/main_analysis.py"
            )
        )


class WorkspaceTextTruncationTest(unittest.TestCase):
    def test_truncate_workspace_text_returns_full_text_when_small(self) -> None:
        contents = "hello\nworld\n"
        self.assertEqual(
            _truncate_workspace_text(contents, path="/workspace/submission/README.md", max_chars=100),
            contents,
        )

    def test_truncate_workspace_text_appends_notice(self) -> None:
        contents = "abcdef"
        truncated = _truncate_workspace_text(
            contents,
            path="/workspace/submission/main.py",
            max_chars=3,
        )
        self.assertEqual(
            truncated,
            "abc\n\n[truncated 3 characters from /workspace/submission/main.py]",
        )

    def test_truncate_workspace_text_rejects_nonpositive_max_chars(self) -> None:
        with self.assertRaises(ValueError):
            _truncate_workspace_text("abc", path="/workspace/submission/main.py", max_chars=0)
