"""Rubric-tree scoring helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from .judge import LeafJudgement
from .rubric_utils import collect_leaf_ids, collect_leaf_nodes, extract_rubric_tree, validate_rubric_payload


@dataclass
class NodeScoreReport:
    """Hierarchical score report for one rubric node."""

    node_id: str
    name: str
    weight: float
    score: float
    category: str | None
    leaf_count: int
    missing_leaf_ids: list[str] = field(default_factory=list)
    children: list["NodeScoreReport"] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.node_id,
            "name": self.name,
            "weight": self.weight,
            "score": self.score,
            "category": self.category,
            "leaf_count": self.leaf_count,
            "missing_leaf_ids": list(self.missing_leaf_ids),
            "children": [child.to_dict() for child in self.children],
        }


@dataclass
class RubricScoreReport:
    """Top-level rubric score report."""

    paper_id: str
    overall_score: float
    category_scores: dict[str, float]
    missing_leaf_ids: list[str]
    extra_leaf_ids: list[str]
    root: NodeScoreReport

    def to_dict(self) -> dict[str, Any]:
        return {
            "paper_id": self.paper_id,
            "overall_score": self.overall_score,
            "category_scores": dict(self.category_scores),
            "missing_leaf_ids": list(self.missing_leaf_ids),
            "extra_leaf_ids": list(self.extra_leaf_ids),
            "root": self.root.to_dict(),
        }


try:  # pragma: no cover - optional Inspect integration
    from inspect_ai.scorer import Score as InspectScore
except ModuleNotFoundError:  # pragma: no cover - local fallback
    @dataclass
    class InspectScore:  # type: ignore[override]
        value: float
        explanation: str = ""
        metadata: dict[str, Any] | None = None


def leaf_score_map_from_judgements(judgements: Iterable[LeafJudgement]) -> dict[str, float]:
    """Convert leaf judgements to a numeric leaf-score map."""

    leaf_scores: dict[str, float] = {}
    for judgement in judgements:
        leaf_scores[judgement.leaf_id] = float(judgement.score)
    return leaf_scores


def _infer_category(node: dict[str, Any]) -> str | None:
    leaves = collect_leaf_nodes(node)
    categories = {leaf["category"] for leaf in leaves}
    return next(iter(categories)) if len(categories) == 1 else None


def _aggregate_node(
    node: dict[str, Any], leaf_scores: Mapping[str, float]
) -> NodeScoreReport:
    if node.get("is_leaf"):
        leaf_id = node["id"]
        score = float(leaf_scores.get(leaf_id, 0.0))
        missing = [] if leaf_id in leaf_scores else [leaf_id]
        return NodeScoreReport(
            node_id=leaf_id,
            name=str(node["name"]),
            weight=float(node["weight"]),
            score=score,
            category=str(node["category"]),
            leaf_count=1,
            missing_leaf_ids=missing,
            children=[],
        )

    child_reports = [_aggregate_node(child, leaf_scores) for child in node.get("children", []) or []]
    total_child_weight = sum(child.weight for child in child_reports)
    score = (
        sum(child.score * child.weight for child in child_reports) / total_child_weight
        if total_child_weight
        else 0.0
    )
    missing_leaf_ids: list[str] = []
    for child in child_reports:
        missing_leaf_ids.extend(child.missing_leaf_ids)

    return NodeScoreReport(
        node_id=str(node["id"]),
        name=str(node["name"]),
        weight=float(node["weight"]),
        score=score,
        category=_infer_category(node),
        leaf_count=sum(child.leaf_count for child in child_reports),
        missing_leaf_ids=missing_leaf_ids,
        children=child_reports,
    )


def score_rubric_payload(
    payload: dict[str, Any], leaf_scores: Mapping[str, float]
) -> RubricScoreReport:
    """Aggregate leaf scores into the full weighted rubric score."""

    validation = validate_rubric_payload(payload)
    if not validation.is_valid:
        raise ValueError(
            "Rubric payload failed validation: " + "; ".join(validation.errors)
        )

    tree = extract_rubric_tree(payload)
    known_leaf_ids = set(collect_leaf_ids(tree))
    extra_leaf_ids = sorted(set(leaf_scores) - known_leaf_ids)
    root_report = _aggregate_node(tree, leaf_scores)
    category_scores = {
        child.category or child.name: child.score for child in root_report.children
    }
    return RubricScoreReport(
        paper_id=str(payload["paper_id"]),
        overall_score=root_report.score,
        category_scores=category_scores,
        missing_leaf_ids=sorted(root_report.missing_leaf_ids),
        extra_leaf_ids=extra_leaf_ids,
        root=root_report,
    )


def summarize_score_report(report: RubricScoreReport) -> str:
    """Render a compact summary string for logging or Inspect metadata."""

    category_summary = ", ".join(
        f"{category}={score:.3f}" for category, score in sorted(report.category_scores.items())
    )
    missing = f", missing_leaves={len(report.missing_leaf_ids)}" if report.missing_leaf_ids else ""
    extras = f", extra_leaf_scores={len(report.extra_leaf_ids)}" if report.extra_leaf_ids else ""
    return (
        f"overall={report.overall_score:.3f}, {category_summary}{missing}{extras}"
    )


def to_inspect_score(report: RubricScoreReport) -> InspectScore:
    """Convert a rubric score report into an Inspect-compatible score object."""

    return InspectScore(
        value=report.overall_score,
        explanation=summarize_score_report(report),
        metadata=report.to_dict(),
    )


__all__ = [
    "InspectScore",
    "NodeScoreReport",
    "RubricScoreReport",
    "leaf_score_map_from_judgements",
    "score_rubric_payload",
    "summarize_score_report",
    "to_inspect_score",
]
