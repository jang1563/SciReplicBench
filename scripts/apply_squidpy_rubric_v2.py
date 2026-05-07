#!/usr/bin/env python
"""Apply Squidpy rubric v2 changes (Q1, Q2, Q3) deterministically.

Q1 — collapse 3 trivial dataset_executes + 3 trivial shape leaves into 2 gating leaves.
Q2 — drop redundant plp1_moran, positive_neighbor_pair, known_spatial_association,
     marker_localization_consistency; modify spatial_localization_pattern to test both
     Olfm1 and Ttr with a stricter threshold.
Q3 — add code_development/interaction_reporting/seeded_permutation_pipeline leaf.

Run from repo root:
    python scripts/apply_squidpy_rubric_v2.py
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PAPER_DIR = REPO_ROOT / "papers" / "squidpy_spatial"
RUBRIC_PATH = PAPER_DIR / "rubric.json"
REF_RESULT = PAPER_DIR / "reference_outputs" / "result_match_reference.json"
REF_EXEC = PAPER_DIR / "reference_outputs" / "execution_reference.json"
REF_CODE = PAPER_DIR / "reference_outputs" / "code_development_reference.json"

DROPPED_LEAF_IDS = {
    "squidpy_spatial/execution/datasets_and_containers/visium_dataset_executes",
    "squidpy_spatial/execution/datasets_and_containers/seqfish_dataset_executes",
    "squidpy_spatial/execution/datasets_and_containers/image_container_executes",
    "squidpy_spatial/result_match/datasets_and_containers/visium_shape_within_tolerance",
    "squidpy_spatial/result_match/datasets_and_containers/seqfish_shape_within_tolerance",
    "squidpy_spatial/result_match/datasets_and_containers/image_shape_within_tolerance",
    "squidpy_spatial/result_match/spatial_statistics/plp1_moran_close",
    "squidpy_spatial/result_match/spatial_graph_neighbors/positive_neighbor_pair_recovered",
    "squidpy_spatial/result_match/spatial_graph_neighbors/known_spatial_association_recovered",
    "squidpy_spatial/result_match/interaction_reporting/marker_localization_consistency",
}

NEW_RUBRIC_LEAVES = {
    "squidpy_spatial/execution/datasets_and_containers/dataset_assets_loaded": {
        "name": "All benchmark dataset assets load with required schema",
        "category": "execution",
        "parent_path": ["squidpy_spatial", "execution", "datasets_and_containers"],
        "requirement": (
            "Load Visium H&E, seqFISH, and Visium H&E image assets and emit a manifest "
            "exposing shape, cluster_key, and label vocabulary for each, plus image "
            "container sizes."
        ),
        "grading_notes": (
            "Single gating leaf replacing per-dataset execute leaves (Q1). All three "
            "dataset assets must surface the required schema fields in dataset_manifest.json."
        ),
    },
    "squidpy_spatial/result_match/datasets_and_containers/dataset_assets_correct_shape": {
        "name": "All benchmark dataset assets match pinned shape",
        "category": "result_match",
        "parent_path": ["squidpy_spatial", "result_match", "datasets_and_containers"],
        "requirement": (
            "All three benchmark assets — Visium H&E AnnData, seqFISH AnnData, and "
            "Visium H&E image — match their pinned reference shape within tolerance."
        ),
        "grading_notes": (
            "Single gating leaf replacing per-asset shape leaves (Q1). All three asset "
            "shapes must lie within their pinned tolerance band."
        ),
    },
    "squidpy_spatial/code_development/interaction_reporting/seeded_permutation_pipeline": {
        "name": "Permutation-based pipeline is seeded",
        "category": "code_development",
        "parent_path": ["squidpy_spatial", "code_development", "interaction_reporting"],
        "requirement": (
            "Set explicit RNG seeds for the permutation-based methods used in the "
            "submission so the analysis is reproducible across reruns."
        ),
        "grading_notes": (
            "Deterministic comparator searches the submission source for an integer "
            "seed argument on `sq.gr.ligrec` and either a global seed call "
            "(np.random.seed / random.seed) or a `seed=` keyword on permutation methods. "
            "Operationalizes the Pineau ML reproducibility checklist seeding requirement."
        ),
    },
}


def _new_rubric_leaf(leaf_id: str) -> dict:
    spec = NEW_RUBRIC_LEAVES[leaf_id]
    return {
        "id": leaf_id,
        "name": spec["name"],
        "weight": 1.0,
        "is_leaf": True,
        "requirement": spec["requirement"],
        "grading_notes": spec["grading_notes"],
        "category": spec["category"],
    }


def _walk_and_modify(node: dict) -> tuple[dict, int]:
    """Drop nodes whose id is in DROPPED_LEAF_IDS; return (cleaned_node, leaf_count)."""
    if node.get("is_leaf"):
        if node.get("id") in DROPPED_LEAF_IDS:
            return None, 0
        return node, 1
    children = node.get("children", []) or []
    new_children: list[dict] = []
    leaf_count = 0
    for child in children:
        cleaned, child_leaves = _walk_and_modify(child)
        if cleaned is None:
            continue
        new_children.append(cleaned)
        leaf_count += child_leaves
    node["children"] = new_children
    return node, leaf_count


def _attach_new_leaves(node: dict) -> None:
    """Attach new leaves under their parent paths."""
    for leaf_id, spec in NEW_RUBRIC_LEAVES.items():
        parent_id = "/".join(spec["parent_path"])
        parent = _find_node_by_id(node, parent_id)
        if parent is None:
            raise RuntimeError(f"parent {parent_id} not found for {leaf_id}")
        # avoid duplicate insertion
        if any(c.get("id") == leaf_id for c in parent.get("children", [])):
            continue
        parent["children"].append(_new_rubric_leaf(leaf_id))


def _find_node_by_id(node: dict, target: str) -> dict | None:
    if node.get("id") == target:
        return node
    for child in node.get("children", []) or []:
        found = _find_node_by_id(child, target)
        if found is not None:
            return found
    return None


def _modify_localization_leaf(node: dict) -> None:
    """Q2c — broaden spatial_localization_pattern_recovered to test Olfm1 and Ttr."""
    target_id = "squidpy_spatial/result_match/spatial_statistics/spatial_localization_pattern_recovered"
    leaf = _find_node_by_id(node, target_id)
    if leaf is None:
        return
    leaf["name"] = "Marker spatial localization pattern recovered (Olfm1, Ttr)"
    leaf["requirement"] = (
        "Both Olfm1 and Ttr show the correct cluster-wise mean-expression "
        "localization pattern against the hidden reference (Pearson per gene above 0.7)."
    )
    leaf["grading_notes"] = (
        "Deterministic comparator merges the previous Olfm1-only spatial localization "
        "leaf and the Ttr-only marker localization leaf into a single stricter check; "
        "both genes must pass per-group Pearson >= 0.7 against the hidden reference."
    )


def edit_rubric() -> None:
    rubric = json.loads(RUBRIC_PATH.read_text())
    root = rubric["rubric"]
    cleaned, _ = _walk_and_modify(root)
    rubric["rubric"] = cleaned
    _attach_new_leaves(cleaned)
    _modify_localization_leaf(cleaned)

    # Recount leaves
    def _count_leaves(n: dict) -> int:
        if n.get("is_leaf"):
            return 1
        return sum(_count_leaves(c) for c in n.get("children", []) or [])
    rubric["total_leaf_nodes"] = _count_leaves(rubric["rubric"])

    RUBRIC_PATH.write_text(json.dumps(rubric, indent=2) + "\n")
    print(f"  rubric.json now has {rubric['total_leaf_nodes']} leaves")


def edit_execution_reference() -> None:
    ref = json.loads(REF_EXEC.read_text())
    leaves = ref["leaves"]
    # Drop 3 dataset_executes leaves
    for k in [
        "squidpy_spatial/execution/datasets_and_containers/visium_dataset_executes",
        "squidpy_spatial/execution/datasets_and_containers/seqfish_dataset_executes",
        "squidpy_spatial/execution/datasets_and_containers/image_container_executes",
    ]:
        leaves.pop(k, None)
    # Add Q1 gating leaf — combines all required dataset_manifest schema checks
    leaves["squidpy_spatial/execution/datasets_and_containers/dataset_assets_loaded"] = {
        "metric": "all_checks",
        "checks": [
            {
                "metric": "json_paths_present",
                "artifact": "/workspace/output/agent/dataset_manifest.json",
                "json_paths": [
                    ["datasets", "visium_hne_adata", "shape"],
                    ["datasets", "visium_hne_adata", "cluster_key"],
                    ["datasets", "visium_hne_adata", "cluster_labels"],
                ],
            },
            {
                "metric": "json_paths_present",
                "artifact": "/workspace/output/agent/dataset_manifest.json",
                "json_paths": [
                    ["datasets", "seqfish", "shape"],
                    ["datasets", "seqfish", "cluster_key"],
                    ["datasets", "seqfish", "cluster_labels"],
                ],
            },
            {
                "metric": "json_paths_present",
                "artifact": "/workspace/output/agent/dataset_manifest.json",
                "json_paths": [
                    ["datasets", "visium_hne_image", "sizes", "x"],
                    ["datasets", "visium_hne_image", "sizes", "y"],
                    ["datasets", "visium_hne_image", "sizes", "channels"],
                ],
            },
        ],
    }
    REF_EXEC.write_text(json.dumps(ref, indent=2) + "\n")
    print(f"  execution_reference.json now has {len(ref['leaves'])} leaves")


def edit_result_match_reference() -> None:
    ref = json.loads(REF_RESULT.read_text())
    leaves = ref["leaves"]

    # Drop redundant + trivial shape leaves
    drop_ids = [
        "squidpy_spatial/result_match/datasets_and_containers/visium_shape_within_tolerance",
        "squidpy_spatial/result_match/datasets_and_containers/seqfish_shape_within_tolerance",
        "squidpy_spatial/result_match/datasets_and_containers/image_shape_within_tolerance",
        "squidpy_spatial/result_match/spatial_statistics/plp1_moran_close",
        "squidpy_spatial/result_match/spatial_graph_neighbors/positive_neighbor_pair_recovered",
        "squidpy_spatial/result_match/spatial_graph_neighbors/known_spatial_association_recovered",
        "squidpy_spatial/result_match/interaction_reporting/marker_localization_consistency",
    ]
    for k in drop_ids:
        leaves.pop(k, None)

    # Add Q1 gating leaf
    leaves[
        "squidpy_spatial/result_match/datasets_and_containers/dataset_assets_correct_shape"
    ] = {
        "status": "ready",
        "metric": "all_checks",
        "checks": [
            {
                "metric": "json_shape_within_tolerance",
                "artifact": "/workspace/output/agent/dataset_manifest.json",
                "json_path_candidates": [
                    ["datasets", "visium_hne_adata", "shape"],
                    ["visium_hne_adata", "shape"],
                ],
                "expected": [2688, 18078],
                "tolerance_pct": 1.0,
            },
            {
                "metric": "json_shape_within_tolerance",
                "artifact": "/workspace/output/agent/dataset_manifest.json",
                "json_path_candidates": [
                    ["datasets", "seqfish", "shape"],
                    ["seqfish", "shape"],
                ],
                "expected": [19416, 351],
                "tolerance_pct": 1.0,
            },
            {
                "metric": "json_shape_within_tolerance",
                "artifact": "/workspace/output/agent/dataset_manifest.json",
                "json_path_candidates": [
                    ["datasets", "visium_hne_image", "sizes"],
                    ["visium_hne_image", "sizes"],
                ],
                "expected": {"y": 11757, "x": 11291, "channels": 3},
                "tolerance_pct": 2.0,
            },
        ],
    }

    # Q2c — broaden spatial_localization_pattern_recovered to test Olfm1 + Ttr with stricter threshold
    leaves[
        "squidpy_spatial/result_match/spatial_statistics/spatial_localization_pattern_recovered"
    ] = {
        "status": "ready",
        "metric": "tsv_grouped_curve_correlation",
        "artifact": "/workspace/output/agent/spatial_stats/gene_localization.tsv",
        "reference_artifact": "generated/visium_hne_gene_localization.tsv",
        "group_column": "gene",
        "x_column": "cluster",
        "value_column": "mean_expression",
        "groups": ["Olfm1", "Ttr"],
        "correlation": "pearson",
        "minimum": 0.7,
        "min_groups": 2,
        "min_points": 12,
    }

    REF_RESULT.write_text(json.dumps(ref, indent=2) + "\n")
    print(f"  result_match_reference.json now has {len(ref['leaves'])} leaves")


def edit_code_development_reference() -> None:
    ref = json.loads(REF_CODE.read_text())
    leaves = ref["leaves"]
    leaves[
        "squidpy_spatial/code_development/interaction_reporting/seeded_permutation_pipeline"
    ] = {
        "metric": "source_patterns",
        "all_regex": [
            "(?:np\\.random\\.seed|random\\.seed)\\s*\\(\\s*\\d+",
            "seed\\s*=\\s*\\d+",
        ],
    }
    REF_CODE.write_text(json.dumps(ref, indent=2) + "\n")
    print(f"  code_development_reference.json now has {len(ref['leaves'])} leaves")


def main() -> None:
    print("Applying Squidpy rubric v2 changes (Q1+Q2+Q3)...")
    edit_rubric()
    edit_execution_reference()
    edit_result_match_reference()
    edit_code_development_reference()
    print("Done.")


if __name__ == "__main__":
    main()
