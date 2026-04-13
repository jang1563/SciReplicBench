#!/usr/bin/env python3
"""Render the judge reliability report from human/judge grades."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from judge_eval.judge_benchmark import (
    load_grade_records,
    render_reliability_markdown,
    summarize_reliability,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--grades",
        default="judge_eval/human_grades.json",
        help="Path to the human/judge grades JSON file.",
    )
    parser.add_argument("--bootstrap-samples", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    records = load_grade_records(ROOT / args.grades)
    summary = summarize_reliability(records, n_bootstrap=args.bootstrap_samples, seed=args.seed)
    markdown = render_reliability_markdown(summary)
    (ROOT / "reports" / "judge_reliability.md").write_text(markdown)
    print(markdown)


if __name__ == "__main__":
    main()
