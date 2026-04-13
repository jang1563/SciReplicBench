"""Phase 4 run-plan helpers for pilot and production evaluations."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from . import PAPER_IDS

DEFAULT_TASK_SPEC = "src/scireplicbench/tasks.py@scireplicbench"


@dataclass
class ModelPlan:
    """Model configuration for an evaluation phase."""

    label: str
    inspect_model: str
    reasoning_effort: str | None = None
    verbosity: str | None = None
    notes: str = ""


@dataclass
class RunPlanEntry:
    """One concrete evaluation run specification."""

    phase: str
    paper_id: str
    agent: ModelPlan
    judge: ModelPlan
    seed: int
    task_spec: str = DEFAULT_TASK_SPEC
    message_limit: int | None = None
    time_limit_seconds: int | None = None
    working_limit_seconds: int | None = None
    cost_limit_usd: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def run_id(self) -> str:
        return f"{self.phase}__{self.paper_id}__{self.agent.label}__seed{self.seed}"

    def inspect_eval_command(self, *, log_dir: str = "logs") -> list[str]:
        """Build the `inspect eval` CLI command for this run."""

        command = [
            "inspect",
            "eval",
            self.task_spec,
            "--model",
            self.agent.inspect_model,
            "--log-dir",
            log_dir,
            "-T",
            f"paper_id={self.paper_id}",
            "--metadata",
            f"phase={self.phase}",
            "--metadata",
            f"run_id={self.run_id}",
            "--metadata",
            f"paper_id={self.paper_id}",
            "--metadata",
            f"seed={self.seed}",
            "--model-role",
            f"grader={self.judge.inspect_model}",
        ]
        if self.message_limit is not None:
            command.extend(["--message-limit", str(self.message_limit)])
        if self.time_limit_seconds is not None:
            command.extend(["--time-limit", str(self.time_limit_seconds)])
        if self.working_limit_seconds is not None:
            command.extend(["--working-limit", str(self.working_limit_seconds)])
        if self.cost_limit_usd is not None:
            command.extend(["--cost-limit", str(self.cost_limit_usd)])
        if self.agent.reasoning_effort:
            command.extend(["--reasoning-effort", self.agent.reasoning_effort])
        if self.agent.verbosity:
            command.extend(["--verbosity", self.agent.verbosity])
        return command

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["run_id"] = self.run_id
        payload["inspect_eval_command"] = self.inspect_eval_command()
        return payload


def pilot_agent_models() -> list[ModelPlan]:
    """Default 4a pilot agent lineup from the approved plan."""

    return [
        ModelPlan(
            label="gpt-4o-mini",
            inspect_model="openai/gpt-4o-mini",
            verbosity="medium",
            notes="Cheap-model pilot anchor from approved plan.",
        ),
        ModelPlan(
            label="claude-haiku-4-5",
            inspect_model="anthropic/claude-haiku-4-5",
            notes="Verify provider-specific Inspect model string before running.",
        ),
        ModelPlan(
            label="deepseek-v3",
            inspect_model="deepseek/deepseek-chat",
            notes="Use the deployment string configured for your DeepSeek provider.",
        ),
    ]


def pilot_judge_model() -> ModelPlan:
    return ModelPlan(label="gpt-4o-mini", inspect_model="openai/gpt-4o-mini")


def production_agent_models() -> list[ModelPlan]:
    """Default 4b production agent lineup from the approved plan."""

    return [
        ModelPlan(
            label="gpt-4o",
            inspect_model="openai/gpt-4o",
            verbosity="medium",
        ),
        ModelPlan(
            label="claude-sonnet-4-6",
            inspect_model="anthropic/claude-sonnet-4-6",
            notes="Verify provider-specific Inspect model string before running.",
        ),
    ]


def production_judge_model() -> ModelPlan:
    return ModelPlan(
        label="o3-mini",
        inspect_model="openai/o3-mini",
        reasoning_effort="medium",
    )


def build_phase4a_plan() -> list[RunPlanEntry]:
    """Build the cheap-model pilot run matrix."""

    runs: list[RunPlanEntry] = []
    judge = pilot_judge_model()
    for paper_id in PAPER_IDS:
        for agent in pilot_agent_models():
            runs.append(
                RunPlanEntry(
                    phase="phase4a_pilot",
                    paper_id=paper_id,
                    agent=agent,
                    judge=judge,
                    seed=1,
                    message_limit=50 if paper_id == "squidpy_spatial" else 60,
                    time_limit_seconds=3600 if paper_id == "squidpy_spatial" else 5400,
                    working_limit_seconds=3600 if paper_id == "squidpy_spatial" else 5400,
                    cost_limit_usd=2.5,
                )
            )
    return runs


def build_phase4b_plan(seeds: tuple[int, ...] = (1, 2, 3)) -> list[RunPlanEntry]:
    """Build the production run matrix."""

    runs: list[RunPlanEntry] = []
    judge = production_judge_model()
    for paper_id in PAPER_IDS:
        for agent in production_agent_models():
            for seed in seeds:
                runs.append(
                    RunPlanEntry(
                        phase="phase4b_production",
                        paper_id=paper_id,
                        agent=agent,
                        judge=judge,
                        seed=seed,
                        message_limit=50 if paper_id == "squidpy_spatial" else 60,
                        time_limit_seconds=3600 if paper_id == "squidpy_spatial" else 5400,
                        working_limit_seconds=3600 if paper_id == "squidpy_spatial" else 5400,
                        cost_limit_usd=6.0,
                    )
                )
    return runs


def write_plan_json(entries: list[RunPlanEntry], path: str | Path) -> None:
    """Write a run-plan manifest to JSON."""

    Path(path).write_text(json.dumps([entry.to_dict() for entry in entries], indent=2) + "\n")


def render_plan_markdown(entries: list[RunPlanEntry]) -> str:
    """Render a compact markdown summary of a run plan."""

    lines = [
        "# Run Plan",
        "",
        "| Phase | Paper | Agent | Judge | Seed | Cost Limit |",
        "|---|---|---|---|---:|---:|",
    ]
    for entry in entries:
        lines.append(
            f"| {entry.phase} | {entry.paper_id} | {entry.agent.label} | "
            f"{entry.judge.label} | {entry.seed} | {entry.cost_limit_usd or 0:.2f} |"
        )
    return "\n".join(lines) + "\n"


__all__ = [
    "DEFAULT_TASK_SPEC",
    "ModelPlan",
    "RunPlanEntry",
    "build_phase4a_plan",
    "build_phase4b_plan",
    "pilot_agent_models",
    "pilot_judge_model",
    "production_agent_models",
    "production_judge_model",
    "render_plan_markdown",
    "write_plan_json",
]
