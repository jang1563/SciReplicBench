"""Workspace path helpers for sandboxed and HPC-backed runs."""

from __future__ import annotations

import os
import posixpath
from pathlib import PurePosixPath

DEFAULT_WORKSPACE_ROOT = "/workspace"
WORKSPACE_ROOT_ENV = "SCIREPLICBENCH_WORKSPACE_ROOT"


def workspace_root() -> str:
    """Return the workspace root used inside the active sandbox/run backend."""

    root = os.getenv(WORKSPACE_ROOT_ENV, DEFAULT_WORKSPACE_ROOT).strip()
    if not root:
        root = DEFAULT_WORKSPACE_ROOT
    normalized = PurePosixPath(posixpath.normpath(root)).as_posix()
    if not normalized.startswith("/"):
        raise ValueError(
            f"{WORKSPACE_ROOT_ENV} must be an absolute POSIX path, got: {root!r}"
        )
    return normalized


def workspace_path(*parts: str) -> str:
    """Join path parts under the configured workspace root."""

    return PurePosixPath(workspace_root(), *parts).as_posix()


def rewrite_workspace_paths(text: str, *, root: str | None = None) -> str:
    """Rewrite literal /workspace paths in text for non-Docker local runs."""

    target_root = root or workspace_root()
    if target_root == DEFAULT_WORKSPACE_ROOT:
        return text
    return text.replace(DEFAULT_WORKSPACE_ROOT, target_root)


__all__ = [
    "DEFAULT_WORKSPACE_ROOT",
    "WORKSPACE_ROOT_ENV",
    "rewrite_workspace_paths",
    "workspace_path",
    "workspace_root",
]
