"""Helpers for fresh-container reproduction and output diffing."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class FileSnapshot:
    """Digest summary for one file."""

    relative_path: str
    size_bytes: int
    sha256: str


@dataclass
class DirectoryDiff:
    """Directory-level diff between expected and reproduced outputs."""

    identical_files: list[str] = field(default_factory=list)
    changed_files: list[str] = field(default_factory=list)
    missing_files: list[str] = field(default_factory=list)
    unexpected_files: list[str] = field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        return not (self.changed_files or self.missing_files or self.unexpected_files)


def sha256_file(path: str | Path) -> str:
    """Compute a SHA256 digest for a file."""

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def snapshot_directory(root: str | Path) -> dict[str, FileSnapshot]:
    """Create a recursive snapshot of a directory tree."""

    root_path = Path(root)
    snapshots: dict[str, FileSnapshot] = {}
    if not root_path.exists():
        return snapshots

    for file_path in sorted(path for path in root_path.rglob("*") if path.is_file()):
        relative = file_path.relative_to(root_path).as_posix()
        snapshots[relative] = FileSnapshot(
            relative_path=relative,
            size_bytes=file_path.stat().st_size,
            sha256=sha256_file(file_path),
        )
    return snapshots


def diff_directory_snapshots(
    expected: dict[str, FileSnapshot], observed: dict[str, FileSnapshot]
) -> DirectoryDiff:
    """Diff two directory snapshots."""

    expected_paths = set(expected)
    observed_paths = set(observed)

    identical_files: list[str] = []
    changed_files: list[str] = []
    for path in sorted(expected_paths & observed_paths):
        if expected[path].sha256 == observed[path].sha256:
            identical_files.append(path)
        else:
            changed_files.append(path)

    return DirectoryDiff(
        identical_files=identical_files,
        changed_files=changed_files,
        missing_files=sorted(expected_paths - observed_paths),
        unexpected_files=sorted(observed_paths - expected_paths),
    )


def diff_output_directories(expected_root: str | Path, observed_root: str | Path) -> DirectoryDiff:
    """Diff two output directories by content hash."""

    return diff_directory_snapshots(
        snapshot_directory(expected_root),
        snapshot_directory(observed_root),
    )


def build_reproducer_command(
    *,
    compose_file: str | Path,
    service: str = "reproducer",
    submission_script: str = "/workspace/submission/run.sh",
) -> list[str]:
    """Build the docker compose command for a fresh-container rerun."""

    return [
        "docker",
        "compose",
        "-f",
        str(compose_file),
        "run",
        "--rm",
        service,
        "bash",
        submission_script,
    ]


__all__ = [
    "DirectoryDiff",
    "FileSnapshot",
    "build_reproducer_command",
    "diff_directory_snapshots",
    "diff_output_directories",
    "sha256_file",
    "snapshot_directory",
]
