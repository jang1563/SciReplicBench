"""Tests for reproduction-pass helpers."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scireplicbench.reproduce import build_reproducer_command, diff_output_directories


class ReproduceHelpersTest(unittest.TestCase):
    def test_diff_output_directories(self) -> None:
        with tempfile.TemporaryDirectory() as expected_dir, tempfile.TemporaryDirectory() as observed_dir:
            expected_root = Path(expected_dir)
            observed_root = Path(observed_dir)

            (expected_root / "match.txt").write_text("same\n")
            (expected_root / "changed.txt").write_text("expected\n")
            (expected_root / "missing.txt").write_text("expected\n")

            (observed_root / "match.txt").write_text("same\n")
            (observed_root / "changed.txt").write_text("observed\n")
            (observed_root / "extra.txt").write_text("extra\n")

            diff = diff_output_directories(expected_root, observed_root)
            self.assertFalse(diff.is_clean)
            self.assertEqual(diff.identical_files, ["match.txt"])
            self.assertEqual(diff.changed_files, ["changed.txt"])
            self.assertEqual(diff.missing_files, ["missing.txt"])
            self.assertEqual(diff.unexpected_files, ["extra.txt"])

    def test_build_reproducer_command(self) -> None:
        command = build_reproducer_command(compose_file="environments/compose.yaml")
        self.assertEqual(
            command,
            [
                "docker",
                "compose",
                "-f",
                "environments/compose.yaml",
                "run",
                "--rm",
                "reproducer",
                "bash",
                "/workspace/submission/run.sh",
            ],
        )


if __name__ == "__main__":
    unittest.main()
