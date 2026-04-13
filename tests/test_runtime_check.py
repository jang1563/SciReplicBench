"""Tests for runtime readiness checks."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scireplicbench.runtime_check import (
    default_readiness_checks,
    render_readiness_markdown,
    sourced_env_var_check,
)


class RuntimeCheckTest(unittest.TestCase):
    def test_default_checks_render(self) -> None:
        checks = default_readiness_checks()
        self.assertTrue(any(check.name == "python" for check in checks))
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


if __name__ == "__main__":
    unittest.main()
