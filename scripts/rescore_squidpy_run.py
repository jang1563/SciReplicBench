#!/usr/bin/env python
"""Rescore a frozen Squidpy unassisted run under the current rubric.

Loads the rubric tree, scores every leaf against the frozen agent workspace
at hpc_workspace/<job_id>/{output,submission}/, and reports per-category
scores plus the overall weighted score. Useful for sensitivity analysis when
the rubric changes.

Run on Cayuga only:

    /athena/.../envs/squidpy_spatial_py311/bin/python scripts/rescore_squidpy_run.py 2839395
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Mapping
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from scireplicbench import scorers  # noqa: E402
from scireplicbench.scorers import (  # noqa: E402
    _deterministic_code_development_judgement,
    _deterministic_execution_judgement,
    _deterministic_result_match_judgement,
    load_rubric_payload,
)


def _walk_leaves(node: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    if node.get("is_leaf"):
        return [node]
    out: list[Mapping[str, Any]] = []
    for ch in node.get("children", []) or []:
        out.extend(_walk_leaves(ch))
    return out


def _walk_score(node: Mapping[str, Any], leaf_scores: dict[str, float]) -> float:
    if node.get("is_leaf"):
        return float(leaf_scores.get(node["id"], 0.0))
    children = node.get("children", []) or []
    total_w = 0.0
    total_s = 0.0
    for ch in children:
        w = float(ch.get("weight", 1.0))
        total_w += w
        total_s += w * _walk_score(ch, leaf_scores)
    return total_s / total_w if total_w else 0.0


async def _score_code_development_leaves(
    leaves: list[Mapping[str, Any]],
    workspace: Path,
) -> dict[str, float]:
    fake_read = _file_reader_factory(workspace)
    out: dict[str, float] = {}
    with patch.object(scorers, "_read_sandbox_file", fake_read):
        for leaf in leaves:
            judgement = await _deterministic_code_development_judgement(
                leaf, paper_id="squidpy_spatial"
            )
            out[leaf["id"]] = float(judgement.score) if judgement else 0.0
    return out


def _file_reader_factory(workspace: Path):
    output_dir = workspace / "output"
    submission_dir = workspace / "submission"

    async def fake_read(path: str) -> str:
        if path.startswith("/workspace/output/"):
            local = output_dir / path.removeprefix("/workspace/output/")
        elif path.startswith("/workspace/submission/"):
            local = submission_dir / path.removeprefix("/workspace/submission/")
        else:
            raise FileNotFoundError(f"unknown sandbox path: {path}")
        if not local.exists():
            raise FileNotFoundError(f"workspace file not found: {local}")
        return local.read_text()

    return fake_read


async def _score_execution_leaves(
    leaves: list[Mapping[str, Any]],
    workspace: Path,
) -> dict[str, float]:
    fake_read = _file_reader_factory(workspace)
    out: dict[str, float] = {}
    with patch.object(scorers, "_read_sandbox_file", fake_read):
        for leaf in leaves:
            judgement = await _deterministic_execution_judgement(
                leaf, paper_id="squidpy_spatial"
            )
            out[leaf["id"]] = float(judgement.score) if judgement else 0.0
    return out


async def _score_result_match_leaves(
    leaves: list[Mapping[str, Any]],
    workspace: Path,
) -> dict[str, float]:
    fake_read = _file_reader_factory(workspace)
    out: dict[str, float] = {}
    with patch.object(scorers, "_read_sandbox_file", fake_read):
        for leaf in leaves:
            judgement = await _deterministic_result_match_judgement(
                leaf, paper_id="squidpy_spatial"
            )
            out[leaf["id"]] = float(judgement.score) if judgement else 0.0
    return out


async def main(job_id: str) -> None:
    workspace = (
        REPO_ROOT / "hpc_workspace" / job_id
    )
    if not workspace.exists():
        # Cayuga absolute path
        workspace = Path("/athena/cayuga_0003/scratch/users/jak4013/SciReplicBench_hpc") / (
            REPO_ROOT.name
        ) / "hpc_workspace" / job_id
    if not workspace.exists():
        print(f"workspace not found: {workspace}", file=sys.stderr)
        sys.exit(1)
    print(f"Rescoring against workspace: {workspace}")

    rubric = load_rubric_payload("squidpy_spatial")
    all_leaves = _walk_leaves(rubric["rubric"])

    by_cat: dict[str, list] = {"code_development": [], "execution": [], "result_match": []}
    for leaf in all_leaves:
        cat = leaf.get("category")
        if cat in by_cat:
            by_cat[cat].append(leaf)

    code_scores = await _score_code_development_leaves(by_cat["code_development"], workspace)
    exec_scores = await _score_execution_leaves(by_cat["execution"], workspace)
    result_scores = await _score_result_match_leaves(by_cat["result_match"], workspace)

    leaf_scores = {**code_scores, **exec_scores, **result_scores}

    # Walk the rubric tree to compute weighted scores
    overall = _walk_score(rubric["rubric"], leaf_scores)
    cat_scores: dict[str, float] = {}
    for child in rubric["rubric"]["children"]:
        cat_scores[child["id"].split("/")[-1]] = _walk_score(child, leaf_scores)

    summary = {
        "job_id": job_id,
        "rubric_total_leaves": rubric["total_leaf_nodes"],
        "overall_score": overall,
        "category_scores": cat_scores,
        "category_passed": {
            "code_development": (
                sum(1 for v in code_scores.values() if v >= 1.0),
                len(code_scores),
            ),
            "execution": (
                sum(1 for v in exec_scores.values() if v >= 1.0),
                len(exec_scores),
            ),
            "result_match": (
                sum(1 for v in result_scores.values() if v >= 1.0),
                len(result_scores),
            ),
        },
        "failed_leaves": sorted(lid for lid, v in leaf_scores.items() if v < 1.0),
    }

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    job_id = sys.argv[1] if len(sys.argv) > 1 else "2839395"
    asyncio.run(main(job_id))
