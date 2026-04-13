#!/usr/bin/env python3
"""Check whether the local environment is ready for Phase 4 runs."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from scireplicbench.runtime_check import default_readiness_checks, render_readiness_markdown


def main() -> None:
    markdown = render_readiness_markdown(default_readiness_checks())
    output = ROOT / "reports" / "runtime_readiness.md"
    output.write_text(markdown)
    print(markdown)


if __name__ == "__main__":
    main()
