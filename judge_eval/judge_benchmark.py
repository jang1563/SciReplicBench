"""Judge reliability analysis for SciReplicBench."""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


@dataclass
class GradeRecord:
    """One human/judge grading example."""

    example_id: str
    paper_id: str
    leaf_id: str
    human_scores: dict[str, int]
    judge_scores: dict[str, int]
    metadata: dict[str, Any]


@dataclass
class ReliabilitySummary:
    """Aggregated reliability metrics."""

    krippendorff_alpha: float
    bootstrap_ci_low: float
    bootstrap_ci_high: float
    items_scored: int
    raters_per_item_min: int
    raters_per_item_max: int
    judge_exact_match: dict[str, float]


def load_grade_records(path: str | Path) -> list[GradeRecord]:
    """Load human/judge grade records from JSON."""

    payload = json.loads(Path(path).read_text())
    records = payload.get("human_grades", payload)
    if not isinstance(records, list):
        raise ValueError("Grade file must contain a list or {'human_grades': [...]} object.")
    output: list[GradeRecord] = []
    for item in records:
        output.append(
            GradeRecord(
                example_id=str(item["example_id"]),
                paper_id=str(item["paper_id"]),
                leaf_id=str(item["leaf_id"]),
                human_scores={k: int(v) for k, v in item.get("human_scores", {}).items()},
                judge_scores={k: int(v) for k, v in item.get("judge_scores", {}).items()},
                metadata=dict(item.get("metadata", {})),
            )
        )
    return output


def krippendorff_alpha_nominal(value_sets: Iterable[Iterable[int]]) -> float:
    """Compute Krippendorff's alpha for nominal labels."""

    items = [list(values) for values in value_sets if list(values)]
    if not items:
        return 1.0

    total_disagreement = 0.0
    total_pairs = 0
    label_counts: Counter[int] = Counter()

    for values in items:
        n = len(values)
        if n < 2:
            continue
        label_counts.update(values)
        counts = Counter(values)
        item_pairs = n * (n - 1)
        disagreement = item_pairs - sum(count * (count - 1) for count in counts.values())
        total_disagreement += disagreement / item_pairs
        total_pairs += 1

    if total_pairs == 0:
        return 1.0

    observed_disagreement = total_disagreement / total_pairs
    total_labels = sum(label_counts.values())
    if total_labels <= 1:
        return 1.0

    expected_disagreement = 1.0 - sum(
        (count / total_labels) ** 2 for count in label_counts.values()
    )
    if expected_disagreement == 0:
        return 1.0
    return 1.0 - (observed_disagreement / expected_disagreement)


def bootstrap_alpha_ci(
    value_sets: list[list[int]],
    *,
    n_bootstrap: int = 1000,
    confidence: float = 0.95,
    seed: int = 0,
) -> tuple[float, float]:
    """Bootstrap a confidence interval for Krippendorff's alpha."""

    if not value_sets:
        return (1.0, 1.0)

    rng = random.Random(seed)
    estimates: list[float] = []
    for _ in range(n_bootstrap):
        sample = [list(rng.choice(value_sets)) for _ in range(len(value_sets))]
        estimates.append(krippendorff_alpha_nominal(sample))

    estimates.sort()
    alpha = (1.0 - confidence) / 2.0
    low_index = max(0, int(alpha * len(estimates)))
    high_index = min(len(estimates) - 1, int((1.0 - alpha) * len(estimates)) - 1)
    return estimates[low_index], estimates[high_index]


def judge_exact_match_rates(records: Iterable[GradeRecord]) -> dict[str, float]:
    """Compare judge scores to the majority human label for each example."""

    totals: Counter[str] = Counter()
    matches: Counter[str] = Counter()
    for record in records:
        if not record.human_scores:
            continue
        human_votes = Counter(record.human_scores.values())
        majority_score, _ = max(human_votes.items(), key=lambda item: (item[1], item[0]))
        for judge_name, judge_score in record.judge_scores.items():
            totals[judge_name] += 1
            if judge_score == majority_score:
                matches[judge_name] += 1
    return {
        judge_name: matches[judge_name] / totals[judge_name]
        for judge_name in sorted(totals)
        if totals[judge_name]
    }


def summarize_reliability(
    records: list[GradeRecord],
    *,
    n_bootstrap: int = 1000,
    confidence: float = 0.95,
    seed: int = 0,
) -> ReliabilitySummary:
    """Build the main reliability summary."""

    value_sets = [list(record.human_scores.values()) for record in records if record.human_scores]
    alpha = krippendorff_alpha_nominal(value_sets)
    ci_low, ci_high = bootstrap_alpha_ci(
        value_sets, n_bootstrap=n_bootstrap, confidence=confidence, seed=seed
    )
    rater_counts = [len(values) for values in value_sets] or [0]
    return ReliabilitySummary(
        krippendorff_alpha=alpha,
        bootstrap_ci_low=ci_low,
        bootstrap_ci_high=ci_high,
        items_scored=len(value_sets),
        raters_per_item_min=min(rater_counts),
        raters_per_item_max=max(rater_counts),
        judge_exact_match=judge_exact_match_rates(records),
    )


def render_reliability_markdown(summary: ReliabilitySummary) -> str:
    """Render a markdown summary for the report."""

    lines = [
        "# Judge Reliability",
        "",
        "## Human Agreement",
        "",
        f"- Krippendorff's alpha: {summary.krippendorff_alpha:.3f}",
        f"- Bootstrap 95% CI: [{summary.bootstrap_ci_low:.3f}, {summary.bootstrap_ci_high:.3f}]",
        f"- Items scored: {summary.items_scored}",
        f"- Human raters per item: {summary.raters_per_item_min} to {summary.raters_per_item_max}",
        "",
        "## Judge Versus Human Majority",
        "",
    ]
    if summary.judge_exact_match:
        for judge_name, exact_match in sorted(summary.judge_exact_match.items()):
            lines.append(f"- {judge_name}: {exact_match:.3f} exact-match rate")
    else:
        lines.append("- No judge scores available yet.")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--grades",
        default="human_grades.json",
        help="Path to the human/judge grades JSON file.",
    )
    parser.add_argument(
        "--bootstrap-samples",
        type=int,
        default=1000,
        help="Number of bootstrap samples for the confidence interval.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="Random seed for bootstrap resampling.",
    )
    parser.add_argument(
        "--markdown-output",
        default="",
        help="Optional path to write a markdown summary.",
    )
    args = parser.parse_args()

    records = load_grade_records(args.grades)
    summary = summarize_reliability(
        records,
        n_bootstrap=args.bootstrap_samples,
        seed=args.seed,
    )
    markdown = render_reliability_markdown(summary)
    print(markdown)
    if args.markdown_output:
        Path(args.markdown_output).write_text(markdown)


if __name__ == "__main__":
    main()
