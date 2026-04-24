"""Inspect task definitions for SciReplicBench."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent
from typing import Any

try:
    from inspect_ai import Task, task
    from inspect_ai.agent import react
    from inspect_ai.dataset import Sample
    from inspect_ai.tool import python
except ModuleNotFoundError as exc:  # pragma: no cover - local fallback for import-only validation
    _INSPECT_IMPORT_ERROR = exc

    @dataclass
    class Sample:  # type: ignore[override]
        input: str
        id: str | None = None
        metadata: dict[str, Any] | None = None
        files: dict[str, str] | None = None
        setup: str | None = None
        target: str | None = None

    @dataclass
    class Task:  # type: ignore[override]
        dataset: list[Sample]
        solver: Any
        sandbox: Any = None
        scorer: Any = None
        message_limit: int | None = None
        time_limit: int | None = None
        working_limit: int | None = None

    def task(*args, **kwargs):  # type: ignore[override]
        if args and callable(args[0]) and len(args) == 1 and not kwargs:
            return args[0]

        def decorator(func):
            return func

        return decorator

    def react(*args, **kwargs):  # type: ignore[override]
        raise RuntimeError(
            "inspect-ai is required to construct SciReplicBench agents."
        ) from _INSPECT_IMPORT_ERROR

    def python(*args, **kwargs):  # type: ignore[override]
        raise RuntimeError(
            "inspect-ai is required to construct SciReplicBench agents."
        ) from _INSPECT_IMPORT_ERROR

try:
    from .tools import guarded_bash, scratchpad, workspace_text_file
    from .scorers import rubric_tree_scorer
except ImportError:  # pragma: no cover - file-based Inspect loading fallback
    PACKAGE_PARENT = Path(__file__).resolve().parent.parent
    if str(PACKAGE_PARENT) not in sys.path:
        sys.path.insert(0, str(PACKAGE_PARENT))
    from scireplicbench.tools import guarded_bash, scratchpad, workspace_text_file
    from scireplicbench.scorers import rubric_tree_scorer

_JUDGE_MODEL_ENV = "SCIREPLICBENCH_JUDGE_MODEL"

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PAPERS_DIR = PROJECT_ROOT / "papers"
COMPOSE_FILE = PROJECT_ROOT / "environments" / "compose.yaml"
COMPOSE_TEMPLATE = "compose.{paper_id}.yaml"
COMPOSE_VARIANT_TEMPLATE = "compose.{paper_id}.{variant}.yaml"
GENERIC_VARIANT_TEMPLATE = "compose.{variant}.yaml"
COMPOSE_OVERRIDE_ENV = "SCIREPLICBENCH_COMPOSE_FILE"
ENV_VARIANT_ENV = "SCIREPLICBENCH_ENV_VARIANT"

DEFAULT_MESSAGE_LIMIT = 60
DEFAULT_TIME_LIMIT_SECONDS = 90 * 60
DEFAULT_WORKING_LIMIT_SECONDS = 90 * 60


def available_paper_ids() -> list[str]:
    """Return paper ids that have task manifests."""

    return sorted(
        path.parent.name for path in PAPERS_DIR.glob("*/task.json") if path.is_file()
    )


def load_task_records(paper_id: str) -> list[dict[str, Any]]:
    """Load one or more task records for a paper."""

    manifest_path = PAPERS_DIR / paper_id / "task.json"
    payload = json.loads(manifest_path.read_text())
    if isinstance(payload, dict):
        payload = [payload]
    if not isinstance(payload, list) or not payload:
        raise ValueError(f"Task manifest for {paper_id} must be a non-empty JSON object/list.")
    return payload


def compose_file_for_paper(paper_id: str) -> Path:
    """Return the docker compose file for a paper-specific sandbox image."""

    compose_override = os.getenv(COMPOSE_OVERRIDE_ENV, "").strip()
    if compose_override:
        override_path = Path(compose_override).expanduser()
        if not override_path.is_absolute():
            override_path = (PROJECT_ROOT / override_path).resolve()
        return override_path

    variant = os.getenv(ENV_VARIANT_ENV, "").strip()
    candidate_paths: list[Path] = []
    if variant:
        candidate_paths.extend(
            [
                PROJECT_ROOT
                / "environments"
                / COMPOSE_VARIANT_TEMPLATE.format(paper_id=paper_id, variant=variant),
                PROJECT_ROOT
                / "environments"
                / GENERIC_VARIANT_TEMPLATE.format(variant=variant),
            ]
        )

    candidate_paths.extend(
        [
            PROJECT_ROOT / "environments" / COMPOSE_TEMPLATE.format(paper_id=paper_id),
            COMPOSE_FILE,
        ]
    )

    for compose_file in candidate_paths:
        if compose_file.exists():
            return compose_file
    return COMPOSE_FILE


def _should_stage_bundle_file(local_path: Path, paper_dir: Path) -> bool:
    """Skip VCS internals that are irrelevant inside the sandbox."""

    relative_path = local_path.relative_to(paper_dir)
    relative_parts = relative_path.parts
    relative_posix = relative_path.as_posix()
    if ".git" in relative_parts:
        return False
    if "__pycache__" in relative_parts or local_path.suffix == ".pyc":
        return False
    if paper_dir.name == "genelab_benchmark":
        raw_prefix = ("data", "raw", "GeneLab_benchmark")
        task_prefix = ("data", "raw", "GeneLab_benchmark", "tasks")
        if (
            relative_posix.startswith("data/huggingface_dataset/v4/")
            or relative_posix.startswith("data/huggingface_dataset/v5/")
            or relative_posix.startswith("data/huggingface_dataset/v6/")
            or relative_posix.startswith("data/raw/GeneLab_benchmark/evaluation/")
            or relative_posix.startswith("data/raw/GeneLab_benchmark/processed/")
            or relative_posix.startswith("data/raw/GeneLab_benchmark/docs/")
            or relative_posix.startswith("data/raw/GeneLab_benchmark/figures/")
        ):
            return False
        if relative_parts[:3] == raw_prefix:
            if relative_parts[:4] != task_prefix:
                return False
        if relative_parts[:4] == task_prefix:
            if len(relative_parts) == 4:
                return False
            task_group = relative_parts[4]
            filename = relative_parts[-1]
            if task_group == "README.md" or not task_group.startswith("A"):
                return False
            if not (paper_dir / "data" / "huggingface_dataset" / task_group).is_dir():
                return False
            if filename in {
                "selected_genes.txt",
                "fold_info.json",
                "task_info.json",
                "geneformer_v1_tokenize_summary.json",
            }:
                return False
    return True


def _paper_bundle_file_map(paper_id: str) -> dict[str, str]:
    paper_dir = PAPERS_DIR / paper_id
    if not paper_dir.exists():
        raise FileNotFoundError(f"Unknown paper id: {paper_id}")

    files: dict[str, str] = {}
    for local_path in sorted(path for path in paper_dir.rglob("*") if path.is_file()):
        if not _should_stage_bundle_file(local_path, paper_dir):
            continue
        relative = local_path.relative_to(paper_dir).as_posix()
        files[f"agent:/workspace/input/paper_bundle/{relative}"] = str(local_path)
        files[f"reproducer:/workspace/input/paper_bundle/{relative}"] = str(local_path)
    return files


def _sample_setup_script() -> str:
    return dedent(
        """\
        #!/usr/bin/env bash
        set -euo pipefail

        mkdir -p /workspace/input/paper_bundle
        mkdir -p /workspace/submission
        mkdir -p /workspace/output/agent
        mkdir -p /workspace/output/reproducer
        mkdir -p /workspace/logs

        if [ -d /workspace/input/paper_bundle/starter ]; then
          cp -R /workspace/input/paper_bundle/starter/. /workspace/submission/
          chmod 0555 /workspace/submission/run.sh || true
        fi

        chmod -R a+rX /workspace/input || true
        """
    )


def _bullet_block(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def _starter_block(record: dict[str, Any]) -> str:
    starter_files = record.get("starter_files", [])
    if not starter_files:
        return ""
    bullets = _bullet_block(
        [f"`/workspace/input/paper_bundle/{path}`" for path in starter_files]
    )
    seeded_submission_note = ""
    if record.get("seed_submission_from_starter"):
        seeded_submission_note = (
            "\n- For GeneLab, the same baseline files are already seeded under "
            "`/workspace/submission`, so run them in place before deciding what to rewrite."
        )
    return dedent(
        f"""\

        Starter files available for this paper:
        {bullets}
        - For this paper, prefer copying/adapting these starter files into the matching paths under `/workspace/submission` rather than starting from a blank script.
        - For GeneLab, these files already implement a runnable reviewer-path baseline, so preserve the fold discovery and structured outputs unless you have a better benchmark-consistent replacement.
        - Keep the seeded `/workspace/submission/run.sh` launcher intact and put substantive edits in Python source files under `/workspace/submission` instead of rewriting the launcher from scratch.
        - The seeded launcher includes required artifact checks, a primary-script timeout, and fallback to the pristine staged starter; preserve those guardrails if you inspect or lightly edit `run.sh`.
        - The benchmark tools may reject attempts to overwrite the seeded GeneLab `run.sh`; edit `/workspace/submission/main_analysis.py` or add helper source files instead.
        - Do not replace the runnable GeneLab baseline with a shorter placeholder or file-enumeration stub; if you edit it, preserve the required output writers and the saved launcher workflow.
        {seeded_submission_note}
        """
    )


def build_sample_input(record: dict[str, Any]) -> str:
    """Render the agent-facing prompt for a single manifest record."""

    focus = _bullet_block(record["analysis_focus"])
    outputs = _bullet_block(record["required_outputs"])
    success_checks = _bullet_block(record["success_checks"])
    public_sources = _bullet_block(record["public_data_sources"])
    starter_block = _starter_block(record)

    return dedent(
        f"""\
        You are reproducing the computational-biology benchmark task `{record["paper_id"]}`:
        {record["paper_title"]}.

        Start by reading these benchmark package files inside the sandbox:
        - `/workspace/input/paper_bundle/paper.md`
        - `/workspace/input/paper_bundle/rubric.json`
        - `/workspace/input/paper_bundle/task.json`
        - `/workspace/input/paper_bundle/novel_contrast.json`
        - `/workspace/input/paper_bundle/method_equivalence.md` if present
        - `/workspace/input/paper_bundle/data/prepare_data.sh` if the required public inputs have not been staged yet

        Objective:
        {record["task_brief"]}

        Analysis focus:
        {focus}

        Public data / code sources expected by this paper package:
        {public_sources}
        {starter_block}

        Reproducibility contract:
        - Write agent-authored scripts, notebooks, configs, and rerun instructions under `/workspace/submission`.
        - If `/workspace/submission/run.sh` is a required output, use it as a thin launcher that calls substantive source files under `/workspace/submission` (for example `.py`, `.R`, or notebook-backed workflows) rather than placing the whole analysis or planning notes directly in `run.sh`.
        - Put the main analysis logic in saved source files under `/workspace/submission` before running it. Work that exists only inside ad-hoc `python()` tool calls or scratchpad notes will not survive the reproducer pass and should be treated as disposable exploration only.
        - Prefer the `workspace_text_file` tool for exact multi-line source files, launcher scripts, README files, manifests, and small text outputs. Use `bash` for directory creation and program execution, not fragile shell-quoted file bodies.
        - When writing multi-line code or documentation files, prefer heredocs or another method that preserves real newlines. Avoid `echo "...\\n..."` patterns for substantive files because they often create broken one-line outputs.
        - Before you submit, execute the saved workflow from `/workspace/submission` (for example via `run.sh` or the project entrypoint), inspect the resulting files under `{record["primary_output_root"]}`, and make sure they contain real outputs rather than empty placeholders.
        - Write analysis outputs from this run under `{record["primary_output_root"]}`.
        - Assume a fresh `reproducer` container will later receive `/workspace/submission` as a read-only input and will rerun against the same `/workspace/input/paper_bundle`.
        - Do not rely on shell history, unstaged temp files, or state outside `/workspace/submission` and `{record["primary_output_root"]}`.
        - Do not copy scratchpad or planning text into deliverable files; the deliverables must be runnable code or explicit documentation.
        - Do not create empty files with `touch` just to satisfy required outputs. Required outputs should be generated or filled by the saved workflow whenever the task is feasible.
        - If a benchmark-prepared input is missing, stage the workflow honestly and document the remaining gap instead of fabricating results.

        Required outputs:
        {outputs}

        Success checks:
        {success_checks}

        Reviewer path:
        {record["reviewer_path"]}

        Held-out anti-memorization target:
        `{record["novel_contrast_id"]}`

        Use the scratchpad tool to keep short working notes when helpful, and finish by writing `/workspace/output/submission_manifest.json` that lists the important commands, inputs, and deliverables.
        """
    ).strip()


def record_to_sample(record: dict[str, Any]) -> Sample:
    """Convert a manifest record into an Inspect Sample."""

    paper_id = record["paper_id"]
    metadata = {
        "paper_id": paper_id,
        "paper_title": record["paper_title"],
        "task_manifest": str(PAPERS_DIR / paper_id / "task.json"),
        "cpu_limit": str(record["resource_hints"]["cpu_limit"]),
        "memory_limit": str(record["resource_hints"]["memory_limit"]),
        "novel_contrast_id": record["novel_contrast_id"],
    }
    return Sample(
        id=record["id"],
        input=build_sample_input(record),
        metadata=metadata,
        files=_paper_bundle_file_map(paper_id),
        setup=_sample_setup_script(),
    )


def _paper_task(
    paper_id: str,
    *,
    attempts: int = 1,
    message_limit: int | None = None,
    time_limit_seconds: int | None = None,
    working_limit_seconds: int | None = None,
) -> Task:
    records = load_task_records(paper_id)
    dataset = [record_to_sample(record) for record in records]
    first = records[0]
    agent_limits = first.get("agent_limits", {})

    judge_model = os.getenv(_JUDGE_MODEL_ENV, "").strip() or "openai/gpt-4o-mini"
    return Task(
        dataset=dataset,
        solver=react(
            description=(
                "Reproduce a computational-biology paper analysis inside a sandboxed "
                "benchmark environment and leave a rerunnable submission package."
            ),
            tools=[guarded_bash(), python(), scratchpad(), workspace_text_file()],
            attempts=attempts,
        ),
        scorer=rubric_tree_scorer(judge_model=judge_model),
        sandbox=("docker", str(compose_file_for_paper(paper_id))),
        message_limit=message_limit or int(
            agent_limits.get("message_limit", DEFAULT_MESSAGE_LIMIT)
        ),
        time_limit=time_limit_seconds
        or int(agent_limits.get("time_limit_minutes", DEFAULT_TIME_LIMIT_SECONDS // 60)) * 60,
        working_limit=working_limit_seconds
        or int(
            agent_limits.get("working_limit_minutes", DEFAULT_WORKING_LIMIT_SECONDS // 60)
        )
        * 60,
    )


@task
def scireplicbench(
    paper_id: str = "inspiration4_multiome",
    attempts: int = 1,
    message_limit: int | None = None,
    time_limit_seconds: int | None = None,
    working_limit_seconds: int | None = None,
) -> Task:
    """Generic entrypoint for a SciReplicBench paper task."""

    if paper_id not in available_paper_ids():
        raise ValueError(
            f"Unknown paper_id '{paper_id}'. Expected one of: {', '.join(available_paper_ids())}"
        )
    return _paper_task(
        paper_id,
        attempts=attempts,
        message_limit=message_limit,
        time_limit_seconds=time_limit_seconds,
        working_limit_seconds=working_limit_seconds,
    )


@task
def inspiration4_multiome(
    attempts: int = 1,
    message_limit: int | None = None,
    time_limit_seconds: int | None = None,
    working_limit_seconds: int | None = None,
) -> Task:
    """Inspect task for the Inspiration4 multimodal paper."""

    return _paper_task(
        "inspiration4_multiome",
        attempts=attempts,
        message_limit=message_limit,
        time_limit_seconds=time_limit_seconds,
        working_limit_seconds=working_limit_seconds,
    )


@task
def squidpy_spatial(
    attempts: int = 1,
    message_limit: int | None = None,
    time_limit_seconds: int | None = None,
    working_limit_seconds: int | None = None,
) -> Task:
    """Inspect task for the Squidpy external-anchor paper."""

    return _paper_task(
        "squidpy_spatial",
        attempts=attempts,
        message_limit=message_limit,
        time_limit_seconds=time_limit_seconds,
        working_limit_seconds=working_limit_seconds,
    )


@task
def genelab_benchmark(
    attempts: int = 1,
    message_limit: int | None = None,
    time_limit_seconds: int | None = None,
    working_limit_seconds: int | None = None,
) -> Task:
    """Inspect task for the GeneLab benchmark paper."""

    return _paper_task(
        "genelab_benchmark",
        attempts=attempts,
        message_limit=message_limit,
        time_limit_seconds=time_limit_seconds,
        working_limit_seconds=working_limit_seconds,
    )


__all__ = [
    "COMPOSE_FILE",
    "COMPOSE_OVERRIDE_ENV",
    "ENV_VARIANT_ENV",
    "compose_file_for_paper",
    "PROJECT_ROOT",
    "available_paper_ids",
    "build_sample_input",
    "genelab_benchmark",
    "inspiration4_multiome",
    "load_task_records",
    "record_to_sample",
    "scireplicbench",
    "squidpy_spatial",
]
