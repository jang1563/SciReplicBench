"""Runtime readiness checks for executing SciReplicBench runs."""

from __future__ import annotations

import importlib
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ReadinessCheck:
    """Result of one runtime readiness check."""

    name: str
    ok: bool
    detail: str


def python_version_check(minimum: tuple[int, int] = (3, 11)) -> ReadinessCheck:
    version = sys.version_info[:3]
    ok = version >= minimum
    return ReadinessCheck(
        name="python",
        ok=ok,
        detail=f"Detected Python {version[0]}.{version[1]}.{version[2]} (requires >= {minimum[0]}.{minimum[1]})",
    )


def import_check(module_name: str) -> ReadinessCheck:
    try:
        importlib.import_module(module_name)
    except Exception as exc:
        return ReadinessCheck(name=f"import:{module_name}", ok=False, detail=f"{type(exc).__name__}: {exc}")
    return ReadinessCheck(name=f"import:{module_name}", ok=True, detail=f"Module '{module_name}' import OK")


def command_check(command_name: str) -> ReadinessCheck:
    resolved = shutil.which(command_name)
    return ReadinessCheck(
        name=f"command:{command_name}",
        ok=resolved is not None,
        detail=resolved or f"'{command_name}' is not on PATH",
    )


def env_var_check(name: str) -> ReadinessCheck:
    present = bool(os.getenv(name))
    return ReadinessCheck(
        name=f"env:{name}",
        ok=present,
        detail="present" if present else "missing",
    )


def sourced_env_var_check(
    name: str, *, source_file: str | Path = "~/.api_keys"
) -> ReadinessCheck:
    """Check whether a provider key is live in env or available in a source file."""

    if os.getenv(name):
        return ReadinessCheck(name=f"env:{name}", ok=True, detail="present in current environment")

    source_path = Path(source_file).expanduser()
    if source_path.exists():
        needle = f"export {name}="
        try:
            text = source_path.read_text()
        except Exception as exc:
            return ReadinessCheck(
                name=f"env:{name}",
                ok=False,
                detail=f"source file exists but could not be read: {type(exc).__name__}",
            )
        if needle in text:
            return ReadinessCheck(
                name=f"env:{name}",
                ok=True,
                detail=f"available via {source_path}",
            )

    return ReadinessCheck(name=f"env:{name}", ok=False, detail="missing")


def project_file_check(relative_path: str) -> ReadinessCheck:
    path = Path(relative_path)
    return ReadinessCheck(
        name=f"file:{relative_path}",
        ok=path.exists(),
        detail=str(path.resolve()) if path.exists() else "missing",
    )


def default_readiness_checks() -> list[ReadinessCheck]:
    """Run the default Phase 4 runtime checks."""

    checks = [
        python_version_check(),
        import_check("inspect_ai"),
        command_check("docker"),
        project_file_check("scireplicbench/environments/compose.yaml"),
        project_file_check("scireplicbench/src/scireplicbench/tasks.py"),
    ]

    for env_name in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "DEEPSEEK_API_KEY"):
        checks.append(sourced_env_var_check(env_name))

    return checks


def render_readiness_markdown(checks: list[ReadinessCheck]) -> str:
    lines = [
        "# Runtime Readiness",
        "",
        "| Check | Status | Detail |",
        "|---|---|---|",
    ]
    for check in checks:
        lines.append(
            f"| {check.name} | {'ok' if check.ok else 'blocked'} | {check.detail} |"
        )
    return "\n".join(lines) + "\n"


__all__ = [
    "ReadinessCheck",
    "command_check",
    "default_readiness_checks",
    "env_var_check",
    "import_check",
    "project_file_check",
    "python_version_check",
    "render_readiness_markdown",
    "sourced_env_var_check",
]
