"""Script-local startup hook that delegates to the repo root bootstrap."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from sitecustomize import *  # type: ignore[F403]
except Exception:
    pass
