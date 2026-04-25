#!/usr/bin/env python3
"""Run deterministic SciReplicBench evidence-policy probes and write sanitized examples."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from unittest.mock import patch

from inspect_ai import eval
from inspect_ai.log import read_eval_log
from inspect_ai.model import ModelOutput, get_model

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from scireplicbench import scorers
from scireplicbench.probes import (
    PROBE_CONTROL_SAMPLE_ID,
    PROBE_FAIL_SAMPLE_ID,
    PROBE_JUDGE_MODEL,
    SQUIDPY_AGENT_PROBE_DEFAULT_MODEL,
    SQUIDPY_PROBE_CONTROL_SAMPLE_ID,
    SQUIDPY_PROBE_FAIL_SAMPLE_ID,
    SQUIDPY_TARGET_LEAF_IDS,
    evidence_policy_probe,
    mock_probe_judge_completion,
    mock_squidpy_probe_judge_completion,
    squidpy_evidence_policy_agent_probe,
    squidpy_evidence_policy_probe,
)

PROBE_CONFIGS = {
    "internal": {
        "task_factory": evidence_policy_probe,
        "judge_completion": mock_probe_judge_completion,
        "judge_model": PROBE_JUDGE_MODEL,
        "log_dir": ROOT / "logs-smoke",
        "example_path": ROOT / "examples" / "evidence_policy_probe_v0_4.json",
        "sample_order": [PROBE_FAIL_SAMPLE_ID, PROBE_CONTROL_SAMPLE_ID],
        "version": "v0.4",
        "about": (
            "Sanitized summary of the deterministic SciReplicBench v0.4 evidence-policy "
            "probe. This is the first live Inspect-level run where the artifact-presence "
            "precheck passes and the scorer visibly emits evidence_policy_failed on a "
            "sample that still tries to win on prose."
        ),
        "notes": {
            "judge_model": PROBE_JUDGE_MODEL,
            "judge_type": "local mock judge",
            "probe_type": "internal harness",
        },
        "leaf_filter": None,
    },
    "squidpy": {
        "task_factory": squidpy_evidence_policy_probe,
        "judge_completion": mock_squidpy_probe_judge_completion,
        "judge_model": PROBE_JUDGE_MODEL,
        "log_dir": ROOT / "logs-prod",
        "example_path": ROOT / "examples" / "squidpy_evidence_policy_probe_v0_5.json",
        "sample_order": [SQUIDPY_PROBE_FAIL_SAMPLE_ID, SQUIDPY_PROBE_CONTROL_SAMPLE_ID],
        "version": "v0.5",
        "about": (
            "Sanitized summary of the deterministic SciReplicBench v0.5 Squidpy evidence "
            "probe. This run uses the real squidpy_spatial paper bundle and full rubric, "
            "but a deterministic solver plus local mock judge, to prove that the live "
            "Inspect scorer now emits evidence_policy_failed on the exact historical "
            "false-positive leaf types once precheck succeeds."
        ),
        "notes": {
            "judge_model": PROBE_JUDGE_MODEL,
            "judge_type": "local mock judge",
            "probe_type": "real-paper Squidpy harness",
        },
        "leaf_filter": set(SQUIDPY_TARGET_LEAF_IDS),
        "model": "none",
    },
    "squidpy-agent": {
        "task_factory": squidpy_evidence_policy_agent_probe,
        "judge_completion": mock_squidpy_probe_judge_completion,
        "judge_model": PROBE_JUDGE_MODEL,
        "log_dir": ROOT / "logs-prod",
        "example_path": ROOT / "examples" / "squidpy_evidence_policy_agent_probe_v1_2.json",
        "sample_order": [SQUIDPY_PROBE_FAIL_SAMPLE_ID, SQUIDPY_PROBE_CONTROL_SAMPLE_ID],
        "version": "v1.2",
        "about": (
            "Sanitized summary of the SciReplicBench v1.2 Squidpy agent evidence probe. "
            "This run uses the real squidpy_spatial paper bundle and scientific image, a "
            "frontier agent to author the sample artifacts, and a local mock judge so the "
            "evidence-policy outcome stays deterministic."
        ),
        "notes": {
            "judge_model": PROBE_JUDGE_MODEL,
            "judge_type": "local mock judge",
            "probe_type": "real-paper Squidpy frontier-agent harness",
        },
        "leaf_filter": set(SQUIDPY_TARGET_LEAF_IDS),
        "model": SQUIDPY_AGENT_PROBE_DEFAULT_MODEL,
    },
}

_LIVE_JUDGE_MIN_TIME_LIMIT = 1800
_LIVE_JUDGE_MIN_WORKING_LIMIT = 1800


def _load_api_keys_from_home() -> None:
    api_keys_path = Path.home() / ".api_keys"
    if not api_keys_path.exists():
        return

    pattern = re.compile(r"^(?:export\s+)?([A-Z0-9_]+)=(.*)$")
    for raw_line in api_keys_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = pattern.match(line)
        if match is None:
            continue
        name, value = match.groups()
        if not name.endswith("_API_KEY"):
            continue
        if os.getenv(name):
            continue
        value = value.strip().strip("'").strip('"')
        if value:
            os.environ[name] = value


def _probe_model(judge_completion):
    def custom_outputs(input_messages, tools, tool_choice, config):
        prompt = input_messages[-1].text
        return ModelOutput.from_content(PROBE_JUDGE_MODEL, judge_completion(prompt))

    return get_model(PROBE_JUDGE_MODEL, custom_outputs=custom_outputs)


def _slugify_label(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug or "probe"


def _judge_type_for_model(model: str) -> str:
    if model == PROBE_JUDGE_MODEL:
        return "local mock judge"
    return "live model judge"


def _about_for_judge(about: str, judge_model: str) -> str:
    if judge_model == PROBE_JUDGE_MODEL:
        return about
    canonical = "and a local mock judge so the evidence-policy outcome stays deterministic."
    if canonical in about:
        return about.replace(
            canonical,
            f"and the live judge `{judge_model}` to test a live, non-mock leaf grader.",
        )
    return (
        f"{about.rstrip()} This artifact overrides the default mock judge with "
        f"`{judge_model}` to test a live, non-mock leaf grader."
    )


def _materialize_config(
    config: dict[str, object],
    *,
    model_override: str | None,
    artifact_label: str | None,
    judge_model_override: str | None,
) -> dict[str, object]:
    materialized = dict(config)
    default_model = config.get("model")
    effective_model = model_override or default_model
    default_judge_model = str(config.get("judge_model", PROBE_JUDGE_MODEL))
    effective_judge_model = judge_model_override or default_judge_model
    if artifact_label:
        label = _slugify_label(artifact_label)
    else:
        label_parts: list[str] = []
        if model_override and model_override != default_model:
            label_parts.append(_slugify_label(model_override))
        if judge_model_override and judge_model_override != default_judge_model:
            label_parts.append(f"judge_{_slugify_label(effective_judge_model)}")
        label = "_".join(label_parts) if label_parts else None

    example_path = Path(config["example_path"])
    if label:
        example_path = example_path.with_name(
            f"{example_path.stem}_{label}{example_path.suffix}"
        )
        materialized["version"] = f"{config['version']}-{label}"
    materialized["about"] = _about_for_judge(str(config["about"]), effective_judge_model)
    materialized["example_path"] = example_path
    materialized["model"] = effective_model
    materialized["judge_model"] = effective_judge_model
    materialized["notes"] = {
        **config["notes"],
        "judge_model": effective_judge_model,
        "judge_type": _judge_type_for_model(effective_judge_model),
        "authoring_model": effective_model,
        "artifact_label": label,
    }
    return materialized


def _sample_summary(sample, *, leaf_filter: set[str] | None) -> dict[str, object]:
    score_map = sample.scores or {}
    if not score_map:
        raise RuntimeError(
            f"Sample {sample.id} has no scorer output; the probe run is incomplete."
        )
    score = next(iter(score_map.values()))
    judgements = (score.metadata or {}).get("leaf_judgements", [])
    if leaf_filter is not None:
        judgements = [judgement for judgement in judgements if judgement["leaf_id"] in leaf_filter]
    return {
        "sample_id": sample.id,
        "overall_score": float(score.value),
        "explanation": score.explanation,
        "precheck": (score.metadata or {}).get("precheck"),
        "leaf_judgement_count": len((score.metadata or {}).get("leaf_judgements", [])),
        "leaf_judgements": [
            {
                "leaf_id": judgement["leaf_id"],
                "score": judgement["score"],
                "evidence_quote": judgement["evidence_quote"],
            }
            for judgement in judgements
        ],
    }


def _write_example(log, config: dict[str, object]) -> None:
    samples = {
        str(sample.id): _sample_summary(sample, leaf_filter=config["leaf_filter"])
        for sample in log.samples or []
    }
    summary = {
        "about": config["about"],
        "version": config["version"],
        "eval": {
            "eval_id": log.eval.eval_id,
            "task": log.eval.task,
            "task_args": log.eval.task_args,
            "model": log.eval.model,
            "created": log.eval.created,
        },
        "status": log.status,
        "stats": {
            "started_at": log.stats.started_at,
            "completed_at": log.stats.completed_at,
            "model_usage": {
                model_name: usage.model_dump(mode="json")
                for model_name, usage in log.stats.model_usage.items()
            },
        },
        "results_summary": {
            "total_samples": log.results.total_samples if log.results else 0,
            "completed_samples": log.results.completed_samples if log.results else 0,
            "scorer": log.results.scores[0].name if log.results and log.results.scores else None,
        },
        "samples": [samples[sample_id] for sample_id in config["sample_order"]],
        "notes": {
            **config["notes"],
            "sandbox": str(log.eval.sandbox.config) if log.eval.sandbox else None,
        },
    }
    Path(config["example_path"]).write_text(json.dumps(summary, indent=2) + "\n")


def _ensure_log_complete(log, *, location: str) -> None:
    if getattr(log, "status", None) != "success":
        error = getattr(log, "error", None)
        message = getattr(error, "message", None) or "see log for details"
        raise RuntimeError(
            "Probe run failed before completion "
            f"(status={getattr(log, 'status', None)}): {message}. "
            f"See {location}"
        )

    if not log.results:
        raise RuntimeError(
            f"Probe run did not produce aggregate results. See {location}"
        )

    if log.results.completed_samples != log.results.total_samples:
        raise RuntimeError(
            "Probe run incomplete: "
            f"{log.results.completed_samples}/{log.results.total_samples} samples completed. "
            f"See {location}"
        )

    missing_scores = [
        str(sample.id) for sample in (log.samples or []) if not (sample.scores or {})
    ]
    if missing_scores:
        raise RuntimeError(
            "Probe run incomplete: scorer output missing for sample(s) "
            f"{', '.join(missing_scores)}. See {location}"
        )


def _apply_live_judge_limits(task: object, judge_model: str) -> object:
    if judge_model == PROBE_JUDGE_MODEL:
        return task

    time_limit = getattr(task, "time_limit", None)
    working_limit = getattr(task, "working_limit", None)
    if time_limit is None or time_limit < _LIVE_JUDGE_MIN_TIME_LIMIT:
        setattr(task, "time_limit", _LIVE_JUDGE_MIN_TIME_LIMIT)
    if working_limit is None or working_limit < _LIVE_JUDGE_MIN_WORKING_LIMIT:
        setattr(task, "working_limit", _LIVE_JUDGE_MIN_WORKING_LIMIT)
    return task


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--probe",
        choices=sorted(PROBE_CONFIGS),
        default="internal",
        help="Which deterministic evidence-policy probe to run.",
    )
    parser.add_argument(
        "--model",
        help="Optional eval model override. Mainly used for agent-authored probes.",
    )
    parser.add_argument(
        "--artifact-label",
        help=(
            "Optional label for the written example artifact. Useful when running the "
            "same probe with multiple authoring models."
        ),
    )
    parser.add_argument(
        "--judge-model",
        help=(
            "Optional judge model override. Defaults to the probe's configured judge "
            "(mockllm/model for the deterministic baseline)."
        ),
    )
    args = parser.parse_args()

    config = _materialize_config(
        PROBE_CONFIGS[args.probe],
        model_override=args.model,
        artifact_label=args.artifact_label,
        judge_model_override=args.judge_model,
    )
    log_dir = Path(config["log_dir"])
    example_path = Path(config["example_path"])
    trace_path = ROOT / f".inspect-trace-{args.probe}.log"

    log_dir.mkdir(exist_ok=True)
    os.environ.setdefault("INSPECT_TRACE_FILE", str(trace_path))
    _load_api_keys_from_home()
    task = _apply_live_judge_limits(
        config["task_factory"](judge_model=config["judge_model"]),
        str(config["judge_model"]),
    )

    if config["judge_model"] == PROBE_JUDGE_MODEL:
        probe_model = _probe_model(config["judge_completion"])
        original_get_model = scorers.get_model

        def patched_get_model(model: str, *args, **kwargs):
            if model == PROBE_JUDGE_MODEL:
                return probe_model
            return original_get_model(model, *args, **kwargs)

        with patch.object(scorers, "get_model", side_effect=patched_get_model):
            logs = eval(
                tasks=[task],
                model=config["model"],
                log_dir=str(log_dir),
                log_level="warning",
                log_format="eval",
            )
    else:
        logs = eval(
            tasks=[task],
            model=config["model"],
            log_dir=str(log_dir),
            log_level="warning",
            log_format="eval",
        )

    if not logs:
        raise RuntimeError("inspect_ai.eval returned no logs for the probe run.")
    log = read_eval_log(logs[0].location)
    _ensure_log_complete(log, location=logs[0].location)
    _write_example(log, config)
    print(log.location)
    print(example_path)


if __name__ == "__main__":
    main()
