"""Evaluation aggregation helpers for pilot and production runs."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable


@dataclass
class EvalRunRecord:
    """Normalized representation of one benchmark run."""

    run_id: str
    paper_id: str
    agent_model: str
    judge_model: str
    seed: int
    status: str
    overall_score: float
    category_scores: dict[str, float]
    cost_usd: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    judge_retries: int = 0
    failure_modes: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EvalAggregate:
    """Aggregate summary over a collection of evaluation runs."""

    run_count: int
    status_counts: dict[str, int]
    mean_overall_score: float
    mean_category_scores: dict[str, float]
    total_cost_usd: float
    mean_cost_usd: float
    total_prompt_tokens: int
    total_completion_tokens: int
    mean_judge_retries: float
    failure_mode_counts: dict[str, int]


def _coerce_record(payload: dict[str, Any]) -> EvalRunRecord:
    return EvalRunRecord(
        run_id=str(payload["run_id"]),
        paper_id=str(payload["paper_id"]),
        agent_model=str(payload["agent_model"]),
        judge_model=str(payload["judge_model"]),
        seed=int(payload.get("seed", 0)),
        status=str(payload.get("status", "unknown")),
        overall_score=float(payload.get("overall_score", 0.0)),
        category_scores={k: float(v) for k, v in payload.get("category_scores", {}).items()},
        cost_usd=float(payload.get("cost_usd", 0.0)),
        prompt_tokens=int(payload.get("prompt_tokens", 0)),
        completion_tokens=int(payload.get("completion_tokens", 0)),
        judge_retries=int(payload.get("judge_retries", 0)),
        failure_modes=[str(item) for item in payload.get("failure_modes", [])],
        metadata=dict(payload.get("metadata", {})),
    )


def load_eval_run_records(path: str | Path) -> list[EvalRunRecord]:
    """Load evaluation records from JSON or JSONL."""

    input_path = Path(path)
    text = input_path.read_text().strip()
    if not text:
        return []
    if input_path.suffix == ".jsonl":
        return [_coerce_record(json.loads(line)) for line in text.splitlines() if line.strip()]

    payload = json.loads(text)
    if isinstance(payload, dict):
        payload = payload.get("runs", [])
    if not isinstance(payload, list):
        raise ValueError("Evaluation run file must contain a list or a {'runs': [...]} object.")
    return [_coerce_record(item) for item in payload]


def aggregate_eval_runs(records: Iterable[EvalRunRecord]) -> EvalAggregate:
    """Aggregate run-level metrics across a set of evaluation records."""

    items = list(records)
    if not items:
        return EvalAggregate(
            run_count=0,
            status_counts={},
            mean_overall_score=0.0,
            mean_category_scores={},
            total_cost_usd=0.0,
            mean_cost_usd=0.0,
            total_prompt_tokens=0,
            total_completion_tokens=0,
            mean_judge_retries=0.0,
            failure_mode_counts={},
        )

    status_counts = Counter(record.status for record in items)
    failure_mode_counts = Counter(
        failure_mode for record in items for failure_mode in record.failure_modes
    )
    category_totals: dict[str, float] = defaultdict(float)
    category_counts: dict[str, int] = defaultdict(int)
    for record in items:
        for category, value in record.category_scores.items():
            category_totals[category] += value
            category_counts[category] += 1

    run_count = len(items)
    total_cost = sum(record.cost_usd for record in items)
    total_prompt_tokens = sum(record.prompt_tokens for record in items)
    total_completion_tokens = sum(record.completion_tokens for record in items)

    return EvalAggregate(
        run_count=run_count,
        status_counts=dict(status_counts),
        mean_overall_score=sum(record.overall_score for record in items) / run_count,
        mean_category_scores={
            category: category_totals[category] / category_counts[category]
            for category in sorted(category_totals)
        },
        total_cost_usd=total_cost,
        mean_cost_usd=total_cost / run_count,
        total_prompt_tokens=total_prompt_tokens,
        total_completion_tokens=total_completion_tokens,
        mean_judge_retries=sum(record.judge_retries for record in items) / run_count,
        failure_mode_counts=dict(failure_mode_counts),
    )


def group_eval_runs(
    records: Iterable[EvalRunRecord], *, keys: tuple[str, ...]
) -> dict[tuple[Any, ...], EvalAggregate]:
    """Group evaluation records by one or more EvalRunRecord fields."""

    grouped: dict[tuple[Any, ...], list[EvalRunRecord]] = defaultdict(list)
    for record in records:
        group_key = tuple(getattr(record, key) for key in keys)
        grouped[group_key].append(record)
    return {key: aggregate_eval_runs(group_records) for key, group_records in grouped.items()}


def render_eval_markdown(records: Iterable[EvalRunRecord]) -> str:
    """Render a compact markdown summary for reports."""

    items = list(records)
    overall = aggregate_eval_runs(items)
    grouped = group_eval_runs(items, keys=("agent_model", "paper_id"))

    lines = [
        "# Evaluation Report",
        "",
        "## Run Summary",
        "",
        f"- Runs: {overall.run_count}",
        f"- Mean overall score: {overall.mean_overall_score:.3f}",
        f"- Total cost (USD): {overall.total_cost_usd:.2f}",
        f"- Mean cost per run (USD): {overall.mean_cost_usd:.2f}",
        f"- Total prompt tokens: {overall.total_prompt_tokens}",
        f"- Total completion tokens: {overall.total_completion_tokens}",
        "",
        "## Status Counts",
        "",
    ]
    for status, count in sorted(overall.status_counts.items()):
        lines.append(f"- {status}: {count}")

    lines.extend(["", "## By Agent Model And Paper", "", "| Agent | Paper | Runs | Mean Score | Mean Cost |", "|---|---|---:|---:|---:|"])
    for (agent_model, paper_id), aggregate in sorted(grouped.items()):
        lines.append(
            f"| {agent_model} | {paper_id} | {aggregate.run_count} | "
            f"{aggregate.mean_overall_score:.3f} | {aggregate.mean_cost_usd:.2f} |"
        )

    lines.extend(["", "## Failure Modes", ""])
    if overall.failure_mode_counts:
        for failure_mode, count in sorted(
            overall.failure_mode_counts.items(), key=lambda item: (-item[1], item[0])
        ):
            lines.append(f"- {failure_mode}: {count}")
    else:
        lines.append("- No failure modes annotated yet.")

    return "\n".join(lines) + "\n"


__all__ = [
    "EvalAggregate",
    "EvalRunRecord",
    "aggregate_eval_runs",
    "group_eval_runs",
    "load_eval_run_records",
    "render_eval_markdown",
]
