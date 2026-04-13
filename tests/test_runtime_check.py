"""Tests for runtime readiness checks."""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from scireplicbench.runtime_check import (
    PROJECT_ROOT,
    default_readiness_checks,
    docker_engine_check,
    project_file_check,
    render_readiness_markdown,
    sourced_env_var_check,
)


class RuntimeCheckTest(unittest.TestCase):
    def test_default_checks_render(self) -> None:
        checks = default_readiness_checks()
        self.assertTrue(any(check.name == "python" for check in checks))
        self.assertTrue(any(check.name == "docker_engine" for check in checks))
        markdown = render_readiness_markdown(checks)
        self.assertIn("Runtime Readiness", markdown)
        self.assertIn("| Check | Status | Detail |", markdown)

    def test_sourced_env_var_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            source_file = Path(tmpdir) / ".api_keys"
            source_file.write_text('export OPENAI_API_KEY="redacted"\n')
            check = sourced_env_var_check("OPENAI_API_KEY", source_file=source_file)
            self.assertTrue(check.ok)
            self.assertIn(".api_keys", check.detail)

    def test_project_file_check_resolves_against_project_root(self) -> None:
        check = project_file_check("src/scireplicbench/tasks.py")
        self.assertTrue(check.ok)
        self.assertEqual(check.detail, "src/scireplicbench/tasks.py")
        self.assertTrue((PROJECT_ROOT / "src/scireplicbench/tasks.py").exists())

    def test_docker_engine_check_success(self) -> None:
        def runner(*args, **kwargs):
            return subprocess.CompletedProcess(args[0], 0, stdout="29.3.1\n", stderr="")

        check = docker_engine_check(runner=runner)
        self.assertTrue(check.ok)
        self.assertIn("29.3.1", check.detail)

    def test_docker_engine_check_failure(self) -> None:
        def runner(*args, **kwargs):
            return subprocess.CompletedProcess(
                args[0],
                1,
                stdout="",
                stderr="request returned 500 Internal Server Error",
            )

        check = docker_engine_check(runner=runner)
        self.assertFalse(check.ok)
        self.assertIn("500 Internal Server Error", check.detail)


if __name__ == "__main__":
    unittest.main()
