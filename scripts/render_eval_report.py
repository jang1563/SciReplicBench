#!/usr/bin/env python3
"""Render the evaluation and cost-accounting reports from run records."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from scireplicbench.evaluation import aggregate_eval_runs, load_eval_run_records, render_eval_markdown


def render_cost_markdown(run_records) -> str:
    summary = aggregate_eval_runs(run_records)
    lines = [
        "# Cost Accounting",
        "",
        "## Summary",
        "",
        f"- Runs: {summary.run_count}",
        f"- Total cost (USD): {summary.total_cost_usd:.2f}",
        f"- Mean cost per run (USD): {summary.mean_cost_usd:.2f}",
        f"- Total prompt tokens: {summary.total_prompt_tokens}",
        f"- Total completion tokens: {summary.total_completion_tokens}",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_records", help="Path to the evaluation JSON or JSONL file.")
    args = parser.parse_args()

    records = load_eval_run_records(args.run_records)
    (ROOT / "reports" / "evaluation_report.md").write_text(render_eval_markdown(records))
    (ROOT / "reports" / "cost_accounting.md").write_text(render_cost_markdown(records))


if __name__ == "__main__":
    main()
