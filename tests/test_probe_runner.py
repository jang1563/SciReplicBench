from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace


def _load_probe_runner():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "run_evidence_policy_probe.py"
    spec = importlib.util.spec_from_file_location("run_evidence_policy_probe", script_path)
    if spec is None or spec.loader is None:
        raise AssertionError("Unable to load run_evidence_policy_probe.py for testing.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_materialize_config_keeps_default_agent_example_path() -> None:
    module = _load_probe_runner()
    config = module._materialize_config(
        module.PROBE_CONFIGS["squidpy-agent"],
        model_override=None,
        artifact_label=None,
        judge_model_override=None,
    )
    assert Path(config["example_path"]).name == "squidpy_evidence_policy_agent_probe_v1_2.json"
    assert config["version"] == "v1.2"
    assert config["notes"]["authoring_model"] == module.SQUIDPY_AGENT_PROBE_DEFAULT_MODEL
    assert config["notes"]["judge_model"] == module.PROBE_JUDGE_MODEL
    assert config["notes"]["judge_type"] == "local mock judge"
    assert config["notes"]["artifact_label"] is None


def test_materialize_config_uses_model_slug_when_override_changes_model() -> None:
    module = _load_probe_runner()
    config = module._materialize_config(
        module.PROBE_CONFIGS["squidpy-agent"],
        model_override="anthropic/claude-sonnet-4-6",
        artifact_label=None,
        judge_model_override=None,
    )
    assert (
        Path(config["example_path"]).name
        == "squidpy_evidence_policy_agent_probe_v1_2_anthropic_claude_sonnet_4_6.json"
    )
    assert config["version"] == "v1.2-anthropic_claude_sonnet_4_6"
    assert config["notes"]["authoring_model"] == "anthropic/claude-sonnet-4-6"
    assert config["notes"]["artifact_label"] == "anthropic_claude_sonnet_4_6"


def test_materialize_config_prefers_explicit_artifact_label() -> None:
    module = _load_probe_runner()
    config = module._materialize_config(
        module.PROBE_CONFIGS["squidpy-agent"],
        model_override="anthropic/claude-sonnet-4-6",
        artifact_label="sonnet",
        judge_model_override=None,
    )
    assert Path(config["example_path"]).name == "squidpy_evidence_policy_agent_probe_v1_2_sonnet.json"
    assert config["version"] == "v1.2-sonnet"
    assert config["notes"]["authoring_model"] == "anthropic/claude-sonnet-4-6"
    assert config["notes"]["artifact_label"] == "sonnet"


def test_materialize_config_uses_judge_slug_when_override_changes_judge() -> None:
    module = _load_probe_runner()
    config = module._materialize_config(
        module.PROBE_CONFIGS["squidpy-agent"],
        model_override=None,
        artifact_label=None,
        judge_model_override="openai/gpt-4o-mini",
    )
    assert (
        Path(config["example_path"]).name
        == "squidpy_evidence_policy_agent_probe_v1_2_judge_openai_gpt_4o_mini.json"
    )
    assert config["version"] == "v1.2-judge_openai_gpt_4o_mini"
    assert config["judge_model"] == "openai/gpt-4o-mini"
    assert config["notes"]["judge_model"] == "openai/gpt-4o-mini"
    assert config["notes"]["judge_type"] == "live model judge"
    assert config["notes"]["artifact_label"] == "judge_openai_gpt_4o_mini"
    assert "live, non-mock leaf grader" in config["about"]


def test_apply_live_judge_limits_extends_task_budget() -> None:
    module = _load_probe_runner()

    class StubTask:
        time_limit = 900
        working_limit = 900

    task = module._apply_live_judge_limits(StubTask(), "openai/o3-mini")
    assert task.time_limit == 1800
    assert task.working_limit == 1800


def test_apply_live_judge_limits_keeps_mock_budget() -> None:
    module = _load_probe_runner()

    class StubTask:
        time_limit = 900
        working_limit = 900

    task = module._apply_live_judge_limits(StubTask(), module.PROBE_JUDGE_MODEL)
    assert task.time_limit == 900
    assert task.working_limit == 900


def test_ensure_log_complete_rejects_error_status() -> None:
    module = _load_probe_runner()
    log = SimpleNamespace(
        status="error",
        error=SimpleNamespace(message="Error code: 429 - insufficient_quota"),
        results=None,
        samples=[],
    )

    try:
        module._ensure_log_complete(log, location="logs-prod/fake.eval")
    except RuntimeError as exc:
        assert "Probe run failed before completion" in str(exc)
        assert "insufficient_quota" in str(exc)
        assert "logs-prod/fake.eval" in str(exc)
    else:
        raise AssertionError("Expected _ensure_log_complete to reject error logs.")


def test_ensure_log_complete_rejects_missing_sample_scores() -> None:
    module = _load_probe_runner()
    log = SimpleNamespace(
        status="success",
        error=None,
        results=SimpleNamespace(completed_samples=2, total_samples=2),
        samples=[
            SimpleNamespace(id="sample_ok", scores={"rubric_tree_scorer": object()}),
            SimpleNamespace(id="sample_missing", scores={}),
        ],
    )

    try:
        module._ensure_log_complete(log, location="logs-prod/fake.eval")
    except RuntimeError as exc:
        assert "scorer output missing" in str(exc)
        assert "sample_missing" in str(exc)
        assert "logs-prod/fake.eval" in str(exc)
    else:
        raise AssertionError("Expected _ensure_log_complete to reject incomplete sample scores.")
