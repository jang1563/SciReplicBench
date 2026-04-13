"""Helpers for loading, traversing, and validating rubric trees."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

ROOT_CATEGORY_FLOORS = {
    "result_match": {"minimum": 0.40},
    "execution": {"minimum": 0.20},
    "code_development": {"maximum": 0.40},
}

LEAF_REQUIRED_FIELDS = {
    "id",
    "name",
    "weight",
    "is_leaf",
    "requirement",
    "grading_notes",
    "category",
}
NODE_REQUIRED_FIELDS = {"id", "name", "weight", "is_leaf"}


@dataclass
class RubricValidationResult:
    """Structured validation result for a rubric payload."""

    paper_id: str
    leaf_count: int
    category_weights: dict[str, float]
    errors: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not self.errors


def load_rubric(path: str | Path) -> dict[str, Any]:
    """Load a rubric payload from JSON."""

    return json.loads(Path(path).read_text())


def extract_rubric_tree(payload: dict[str, Any]) -> dict[str, Any]:
    """Extract the rubric tree from a payload."""

    tree = payload.get("rubric", payload)
    if not isinstance(tree, dict):
        raise ValueError("Rubric payload must contain an object-valued 'rubric' key.")
    return tree


def iter_rubric_nodes(
    node: dict[str, Any], *, ancestors: tuple[str, ...] = ()
) -> Iterator[tuple[tuple[str, ...], dict[str, Any]]]:
    """Yield rubric nodes in depth-first order."""

    yield ancestors, node
    for child in node.get("children", []) or []:
        child_id = str(child.get("id", child.get("name", "")))
        yield from iter_rubric_nodes(child, ancestors=ancestors + (child_id,))


def collect_leaf_nodes(node: dict[str, Any]) -> list[dict[str, Any]]:
    """Collect all leaf nodes beneath a rubric node."""

    leaves: list[dict[str, Any]] = []
    for _, current in iter_rubric_nodes(node):
        if current.get("is_leaf"):
            leaves.append(current)
    return leaves


def collect_leaf_ids(node: dict[str, Any]) -> list[str]:
    """Return leaf ids in traversal order."""

    return [leaf["id"] for leaf in collect_leaf_nodes(node)]


def infer_node_categories(node: dict[str, Any]) -> set[str]:
    """Return the set of categories represented beneath a node."""

    return {leaf["category"] for leaf in collect_leaf_nodes(node)}


def root_category_weights(payload: dict[str, Any]) -> dict[str, float]:
    """Infer root-level category weights from the top-level rubric branches."""

    tree = extract_rubric_tree(payload)
    weights: dict[str, float] = {}
    for child in tree.get("children", []) or []:
        categories = infer_node_categories(child)
        if len(categories) != 1:
            raise ValueError(
                f"Root child '{child.get('id', child.get('name'))}' spans multiple categories: "
                f"{sorted(categories)}"
            )
        category = next(iter(categories))
        weights[category] = float(child.get("weight", 0.0))
    return weights


def validate_rubric_payload(payload: dict[str, Any]) -> RubricValidationResult:
    """Validate the rubric payload against benchmark invariants."""

    paper_id = str(payload.get("paper_id", "unknown"))
    errors: list[str] = []
    tree = extract_rubric_tree(payload)
    seen_ids: set[str] = set()

    for _, node in iter_rubric_nodes(tree):
        node_id = node.get("id")
        node_name = node.get("name", "<unnamed>")
        node_ref = node_id or node_name

        for field in NODE_REQUIRED_FIELDS:
            if field not in node:
                errors.append(f"{node_ref}: missing required field '{field}'")

        weight = node.get("weight")
        if not isinstance(weight, (int, float)):
            errors.append(f"{node_ref}: weight must be numeric")
        elif float(weight) < 0:
            errors.append(f"{node_ref}: weight must be non-negative")

        if node_id:
            if node_id in seen_ids:
                errors.append(f"{node_ref}: duplicate node id")
            seen_ids.add(node_id)
            if paper_id != "unknown" and not str(node_id).startswith(f"{paper_id}/"):
                errors.append(f"{node_ref}: node id must start with '{paper_id}/'")

        is_leaf = bool(node.get("is_leaf"))
        children = node.get("children", []) or []
        if is_leaf:
            if children:
                errors.append(f"{node_ref}: leaf nodes must not define children")
            missing_leaf_fields = sorted(field for field in LEAF_REQUIRED_FIELDS if field not in node)
            for field in missing_leaf_fields:
                errors.append(f"{node_ref}: missing leaf field '{field}'")
        else:
            if not children:
                errors.append(f"{node_ref}: non-leaf nodes must define children")

    leaves = collect_leaf_nodes(tree)
    declared_leaf_count = payload.get("total_leaf_nodes")
    if declared_leaf_count is not None and declared_leaf_count != len(leaves):
        errors.append(
            f"Declared total_leaf_nodes={declared_leaf_count} does not match actual leaf count={len(leaves)}"
        )

    try:
        category_weights = root_category_weights(payload)
    except ValueError as exc:
        category_weights = {}
        errors.append(str(exc))
    else:
        root_children = tree.get("children", []) or []
        root_total = sum(float(child.get("weight", 0.0)) for child in root_children)
        if abs(root_total - 1.0) > 1e-9:
            errors.append(f"Root child weights must sum to 1.0, observed {root_total:.6f}")

        for category, rule in ROOT_CATEGORY_FLOORS.items():
            weight = category_weights.get(category)
            if weight is None:
                errors.append(f"Missing root category branch for '{category}'")
                continue
            minimum = rule.get("minimum")
            maximum = rule.get("maximum")
            if minimum is not None and weight < minimum:
                errors.append(
                    f"Root category '{category}' must be >= {minimum:.2f}, observed {weight:.2f}"
                )
            if maximum is not None and weight > maximum:
                errors.append(
                    f"Root category '{category}' must be <= {maximum:.2f}, observed {weight:.2f}"
                )

    return RubricValidationResult(
        paper_id=paper_id,
        leaf_count=len(leaves),
        category_weights=category_weights,
        errors=errors,
    )


__all__ = [
    "LEAF_REQUIRED_FIELDS",
    "NODE_REQUIRED_FIELDS",
    "ROOT_CATEGORY_FLOORS",
    "RubricValidationResult",
    "collect_leaf_ids",
    "collect_leaf_nodes",
    "extract_rubric_tree",
    "infer_node_categories",
    "iter_rubric_nodes",
    "load_rubric",
    "root_category_weights",
    "validate_rubric_payload",
]
