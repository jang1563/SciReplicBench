#!/usr/bin/env python3
"""Merge completed blinded second-rater responses into human grades."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from judge_eval.judge_benchmark import (
    load_blinded_review_responses,
    merge_blinded_review_responses,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "responses",
        help="Completed blinded JSON or CSV review packet.",
    )
    parser.add_argument(
        "--grades",
        default="judge_eval/human_grades.json",
        help="Existing human/judge grades manifest.",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Merged grades output path. Defaults to <grades>_merged.json unless --in-place is set.",
    )
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="Overwrite --grades after validation.",
    )
    parser.add_argument(
        "--allow-incomplete",
        action="store_true",
        help="Skip blank response rows instead of requiring every row to be filled.",
    )
    parser.add_argument(
        "--overwrite-existing",
        action="store_true",
        help="Allow a response to replace an existing score for the same rater.",
    )
    args = parser.parse_args()

    grades_path = ROOT / args.grades
    responses_path = ROOT / args.responses
    if args.in_place:
        output_path = grades_path
    elif args.output:
        output_path = ROOT / args.output
    else:
        output_path = grades_path.with_name(f"{grades_path.stem}_merged.json")

    grade_payload = json.loads(grades_path.read_text())
    responses = load_blinded_review_responses(
        responses_path,
        allow_incomplete=args.allow_incomplete,
    )
    merged, merged_count = merge_blinded_review_responses(
        grade_payload,
        responses,
        overwrite_existing=args.overwrite_existing,
    )
    output_path.write_text(json.dumps(merged, indent=2) + "\n")
    print(f"merged_responses={merged_count}")
    print(output_path)


if __name__ == "__main__":
    main()
