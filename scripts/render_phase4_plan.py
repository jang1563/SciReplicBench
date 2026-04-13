#!/usr/bin/env python3
"""Render the default Phase 4 run plans."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from scireplicbench.run_plan import (
    build_phase4a_plan,
    build_phase4b_plan,
    render_plan_markdown,
    write_plan_json,
)


def main() -> None:
    configs_dir = ROOT / "configs"

    pilot = build_phase4a_plan()
    production = build_phase4b_plan()

    write_plan_json(pilot, configs_dir / "phase4a_pilot_plan.json")
    write_plan_json(production, configs_dir / "phase4b_production_plan.json")

    (ROOT / "reports" / "phase4a_pilot_plan.md").write_text(render_plan_markdown(pilot))
    (ROOT / "reports" / "phase4b_production_plan.md").write_text(
        render_plan_markdown(production)
    )


if __name__ == "__main__":
    main()
