#!/usr/bin/env python3
"""Export a blinded second-rater packet from an annotated review packet."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from judge_eval.judge_benchmark import write_blinded_review_packet_outputs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        default="judge_eval/review_packet_v0_1_false_positive_and_mZHU6eGr.json",
        help="Annotated source review packet to blind for a second rater.",
    )
    parser.add_argument(
        "--json-output",
        default="",
        help="Optional explicit JSON output path. Defaults to <input>_blinded.json.",
    )
    parser.add_argument(
        "--csv-output",
        default="",
        help="Optional explicit CSV output path. Defaults to <input>_blinded.csv.",
    )
    args = parser.parse_args()

    input_path = ROOT / args.input
    if args.json_output:
        json_output = ROOT / args.json_output
    else:
        json_output = input_path.with_name(f"{input_path.stem}_blinded.json")

    if args.csv_output:
        csv_output = ROOT / args.csv_output
    else:
        csv_output = input_path.with_name(f"{input_path.stem}_blinded.csv")

    write_blinded_review_packet_outputs(
        input_path,
        json_output_path=json_output,
        csv_output_path=csv_output,
    )
    print(json_output)
    print(csv_output)


if __name__ == "__main__":
    main()
