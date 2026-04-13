"""Runtime readiness checks for executing SciReplicBench runs."""

from __future__ import annotations

import importlib
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]


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


def docker_engine_check(
    command_name: str = "docker",
    *,
    timeout_seconds: int = 10,
    runner: Any = subprocess.run,
) -> ReadinessCheck:
    """Check that the Docker CLI can reach a healthy engine."""

    resolved = shutil.which(command_name)
    if resolved is None:
        return ReadinessCheck(
            name="docker_engine",
            ok=False,
            detail=f"'{command_name}' is not on PATH",
        )

    try:
        result = runner(
            [command_name, "version", "--format", "{{.Server.Version}}"],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except Exception as exc:
        return ReadinessCheck(
            name="docker_engine",
            ok=False,
            detail=f"{type(exc).__name__}: {exc}",
        )

    server_version = (result.stdout or "").strip()
    if result.returncode == 0 and server_version:
        return ReadinessCheck(
            name="docker_engine",
            ok=True,
            detail=f"Server version {server_version}",
        )

    detail = ((result.stderr or "").strip() or server_version or f"exit code {result.returncode}")
    return ReadinessCheck(name="docker_engine", ok=False, detail=detail.splitlines()[-1])


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
    path = PROJECT_ROOT / relative_path
    return ReadinessCheck(
        name=f"file:{relative_path}",
        ok=path.exists(),
        # Report the repo-relative path rather than an absolute one so the
        # generated readiness report does not leak a user's filesystem layout.
        detail=relative_path if path.exists() else "missing",
    )


def default_readiness_checks() -> list[ReadinessCheck]:
    """Run the default Phase 4 runtime checks."""

    checks = [
        python_version_check(),
        import_check("inspect_ai"),
        command_check("docker"),
        docker_engine_check(),
        project_file_check("environments/compose.yaml"),
        project_file_check("src/scireplicbench/tasks.py"),
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
    "docker_engine_check",
    "env_var_check",
    "import_check",
    "PROJECT_ROOT",
    "project_file_check",
    "python_version_check",
    "render_readiness_markdown",
    "sourced_env_var_check",
]
