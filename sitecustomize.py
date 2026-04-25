"""Repo-local startup hooks for SciReplicBench development workflows."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

try:
    from scireplicbench._runtime_patches import apply_runtime_patches
except Exception:
    apply_runtime_patches = None

if apply_runtime_patches is not None:
    try:
        apply_runtime_patches()
    except Exception:
        # Keep startup resilient for tooling that only needs partial repo access.
        pass
