"""Readiness gates for SciReplicBench papers and evaluation phases."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .rubric_utils import collect_leaf_nodes, extract_rubric_tree

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PAPERS_DIR = PROJECT_ROOT / "papers"
JUDGE_GRADES_PATH = PROJECT_ROOT / "judge_eval" / "human_grades.json"
RESULT_MATCH_REFERENCE_FILENAME = "result_match_reference.json"
EXECUTION_REFERENCE_FILENAME = "execution_reference.json"
CODE_DEVELOPMENT_REFERENCE_FILENAME = "code_development_reference.json"

_PENDING_HIDDEN_REFERENCE_STATUSES = {
    "pending",
    "pending_benchmark_author_fill_in",
    "todo",
    "disabled",
}

_INSPIRATION4_READY_SUFFIXES = (
    ".h5ad",
    ".h5mu",
    ".mudata",
    ".zarr",
)


def _version_tuple(version: str) -> tuple[int, ...]:
    parts: list[int] = []
    for part in version.split("."):
        match = re.match(r"(\d+)", part)
        if not match:
            break
        parts.append(int(match.group(1)))
    return tuple(parts) or (0,)


def _version_lt(left: str, right: str) -> bool:
    left_tuple = _version_tuple(left)
    right_tuple = _version_tuple(right)
    max_len = max(len(left_tuple), len(right_tuple))
    left_tuple += (0,) * (max_len - len(left_tuple))
    right_tuple += (0,) * (max_len - len(right_tuple))
    return left_tuple < right_tuple


def _requirement_has_safe_upper_bound(text: str, package: str, upper: str) -> bool:
    """Return whether a requirements file pins `package` below `upper`."""

    pattern = re.compile(rf"^\s*{re.escape(package)}\s*(?P<op>==|<)\s*(?P<version>[^\s#]+)", re.MULTILINE)
    for match in pattern.finditer(text):
        op = match.group("op")
        version = match.group("version")
        if op == "==":
            return _version_lt(version, upper)
        if op == "<":
            return _version_tuple(version) <= _version_tuple(upper)
    return False


@dataclass
class ReadinessGate:
    """One readiness gate for a paper/phase combination."""

    phase: str
    paper_id: str
    lane: str
    run_allowed: bool
    pilot_ready: bool
    production_ready: bool
    blocking_reasons: list[str] = field(default_factory=list)
    advisories: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "phase": self.phase,
            "paper_id": self.paper_id,
            "lane": self.lane,
            "run_allowed": self.run_allowed,
            "pilot_ready": self.pilot_ready,
            "production_ready": self.production_ready,
            "blocking_reasons": list(self.blocking_reasons),
            "advisories": list(self.advisories),
        }


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def load_novel_contrast(paper_id: str) -> dict[str, Any]:
    """Load a paper's hidden-reference descriptor."""

    return _load_json(PAPERS_DIR / paper_id / "novel_contrast.json")


def hidden_reference_ready(paper_id: str) -> tuple[bool, str | None]:
    """Return whether a paper's hidden reference is complete enough for claims."""

    payload = load_novel_contrast(paper_id)
    generation = payload.get("hidden_reference_generation")
    if not isinstance(generation, dict):
        return False, "hidden_reference_generation is missing"

    status = str(generation.get("status", "")).strip().lower()
    if not status or status in _PENDING_HIDDEN_REFERENCE_STATUSES:
        return False, "hidden reference is still pending benchmark-author fill-in"
    return True, None


def result_match_reference_ready(paper_id: str) -> tuple[bool, str | None]:
    """Check whether all result_match leaves have sealed comparator references."""

    return _category_reference_ready(
        paper_id,
        category="result_match",
        filename=RESULT_MATCH_REFERENCE_FILENAME,
        label="result_match",
    )


def execution_reference_ready(paper_id: str) -> tuple[bool, str | None]:
    """Check whether execution leaves have deterministic artifact checks."""

    return _category_reference_ready(
        paper_id,
        category="execution",
        filename=EXECUTION_REFERENCE_FILENAME,
        label="execution",
    )


def code_development_reference_ready(paper_id: str) -> tuple[bool, str | None]:
    """Check whether code-development leaves have deterministic source checks."""

    return _category_reference_ready(
        paper_id,
        category="code_development",
        filename=CODE_DEVELOPMENT_REFERENCE_FILENAME,
        label="code_development",
    )


def _category_reference_ready(
    paper_id: str,
    *,
    category: str,
    filename: str,
    label: str,
) -> tuple[bool, str | None]:
    """Check whether every rubric leaf in a category has a ready reference config."""

    rubric_path = PAPERS_DIR / paper_id / "rubric.json"
    if not rubric_path.exists():
        return False, "rubric.json is missing"

    rubric = _load_json(rubric_path)
    category_leaves = [
        str(leaf["id"])
        for leaf in collect_leaf_nodes(extract_rubric_tree(rubric))
        if str(leaf.get("category", "")) == category
    ]
    if not category_leaves:
        return True, None

    reference_path = PAPERS_DIR / paper_id / "reference_outputs" / filename
    if not reference_path.exists():
        return False, f"{filename} is missing"

    reference = _load_json(reference_path)
    leaves = reference.get("leaves")
    if not isinstance(leaves, dict):
        return False, f"{filename} lacks a leaves object"

    missing = [leaf_id for leaf_id in category_leaves if leaf_id not in leaves]
    pending = []
    for leaf_id in category_leaves:
        config = leaves.get(leaf_id)
        if not isinstance(config, dict):
            continue
        status = str(config.get("status", "ready")).strip().lower()
        if config.get("enabled") is False or status in _PENDING_HIDDEN_REFERENCE_STATUSES:
            pending.append(leaf_id)

    if missing or pending:
        pieces = []
        if missing:
            pieces.append(f"{len(missing)} {label} leaves lack deterministic references")
        if pending:
            pieces.append(f"{len(pending)} {label} references are pending")
        return False, "; ".join(pieces)

    return True, None


def second_human_rater_ready(path: Path = JUDGE_GRADES_PATH) -> tuple[bool, str | None]:
    """Check whether the judge-review packet has at least two human scores per item."""

    payload = _load_json(path)
    records = payload.get("human_grades", payload)
    if not isinstance(records, list) or not records:
        return False, "judge reliability panel is empty"

    for record in records:
        human_scores = record.get("human_scores", {})
        if not isinstance(human_scores, dict) or len(human_scores) < 2:
            return False, "judge reliability panel still has only one human rater per item"
    return True, None


def inspiration4_object_ready() -> tuple[bool, str | None]:
    """Check whether the reviewer-ready multimodal object exists locally."""

    cache_dir = PAPERS_DIR / "inspiration4_multiome" / "data" / "cache"
    for path in cache_dir.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() in _INSPIRATION4_READY_SUFFIXES:
            return True, None
    return False, "benchmark-ready AnnData or MuData object is not staged under papers/inspiration4_multiome/data/cache"


def squidpy_runtime_hardening_ready() -> tuple[bool, str | None]:
    """Check whether the pinned Squidpy stack includes the known numcodecs guardrail."""

    requirements_path = PROJECT_ROOT / "environments" / "requirements.squidpy_spatial.txt"
    text = requirements_path.read_text()
    if not _requirement_has_safe_upper_bound(text, "numcodecs", "0.16"):
        return False, "requirements.squidpy_spatial.txt still lacks a numcodecs<0.16-compatible pin"
    if not _requirement_has_safe_upper_bound(text, "setuptools", "82"):
        return False, "requirements.squidpy_spatial.txt still lacks a setuptools<82-compatible pin for pkg_resources compatibility"
    return True, None


def _paper_pilot_gate(paper_id: str) -> tuple[bool, str, list[str], list[str]]:
    lane = "evaluation"
    blockers: list[str] = []
    advisories: list[str] = []

    if paper_id == "inspiration4_multiome":
        ready, reason = inspiration4_object_ready()
        if not ready:
            lane = "enablement"
            blockers.append(reason or "reviewer-ready object is missing")

    if paper_id == "squidpy_spatial":
        hardened, reason = squidpy_runtime_hardening_ready()
        if not hardened and reason:
            advisories.append(reason)

    return not blockers, lane, blockers, advisories


def _paper_production_blockers(paper_id: str) -> list[str]:
    blockers: list[str] = []

    hidden_reference_ok, hidden_reference_reason = hidden_reference_ready(paper_id)
    if not hidden_reference_ok and hidden_reference_reason:
        blockers.append(hidden_reference_reason)

    for ready_check in (
        code_development_reference_ready,
        execution_reference_ready,
        result_match_reference_ready,
    ):
        reference_ok, reference_reason = ready_check(paper_id)
        if not reference_ok and reference_reason:
            blockers.append(reference_reason)

    if paper_id == "inspiration4_multiome":
        object_ready, object_reason = inspiration4_object_ready()
        if not object_ready and object_reason:
            blockers.append(object_reason)

    if paper_id == "squidpy_spatial":
        hardened, hardening_reason = squidpy_runtime_hardening_ready()
        if not hardened and hardening_reason:
            blockers.append(hardening_reason)

    return blockers


def phase_readiness_gate(paper_id: str, phase: str) -> ReadinessGate:
    """Return the readiness gate for one paper in one evaluation phase."""

    pilot_ready, lane, pilot_blockers, advisories = _paper_pilot_gate(paper_id)
    production_blockers = _paper_production_blockers(paper_id)

    reviewer_ready, reviewer_reason = second_human_rater_ready()
    if not reviewer_ready and reviewer_reason:
        production_blockers = [reviewer_reason, *production_blockers]

    production_ready = not production_blockers
    if phase == "phase4a_pilot":
        run_allowed = pilot_ready
        blockers = pilot_blockers
    else:
        run_allowed = production_ready
        blockers = production_blockers

    return ReadinessGate(
        phase=phase,
        paper_id=paper_id,
        lane=lane,
        run_allowed=run_allowed,
        pilot_ready=pilot_ready,
        production_ready=production_ready,
        blocking_reasons=blockers,
        advisories=advisories,
    )


__all__ = [
    "JUDGE_GRADES_PATH",
    "PROJECT_ROOT",
    "ReadinessGate",
    "code_development_reference_ready",
    "execution_reference_ready",
    "hidden_reference_ready",
    "inspiration4_object_ready",
    "load_novel_contrast",
    "phase_readiness_gate",
    "result_match_reference_ready",
    "second_human_rater_ready",
    "squidpy_runtime_hardening_ready",
]
