"""Rubric-tree scoring helpers."""

from __future__ import annotations

import ast
import csv
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .comparators import (
    adjusted_rand_index,
    normalize_gene_symbol,
    normalize_pathway_name,
    overlap_at_k,
    pearson_correlation,
    rank_biased_overlap,
    spearman_correlation,
    within_percent_tolerance,
)
from .judge import LeafJudgement, format_leaf_judge_prompt, parse_leaf_judgement
from .rubric_utils import collect_leaf_ids, collect_leaf_nodes, extract_rubric_tree, validate_rubric_payload
from .workspace import workspace_path, workspace_root

PROJECT_ROOT = Path(__file__).resolve().parents[2]
_JUDGE_MAX_SUBMISSION_CHARS = 72000
_JUDGE_MAX_SUBMISSION_FILE_CHARS = 3600
_JUDGE_MAX_SOURCE_FILE_CHARS = 22000
_JUDGE_MAX_PAPER_CHARS = 3000
_JUDGE_DEFAULT_MODEL = "openai/gpt-4o-mini"
_JUDGE_LEAF_LIMIT_ENV = "SCIREPLICBENCH_JUDGE_LEAF_LIMIT"
_STARTER_MODE_ENV = "SCIREPLICBENCH_STARTER_MODE"
_JUDGE_PARSE_RETRIES = 2
_REFERENCE_OUTPUTS_DIRNAME = "reference_outputs"
_RESULT_MATCH_REFERENCE_FILENAME = "result_match_reference.json"
_EXECUTION_REFERENCE_FILENAME = "execution_reference.json"
_CODE_DEVELOPMENT_REFERENCE_FILENAME = "code_development_reference.json"
_WORKSPACE_ROOT = workspace_root()
_PRECHECK_SUBMISSION_DIR = workspace_path("submission")
_PRECHECK_OUTPUT_DIR = workspace_path("output")
_SUBMISSION_PREFIX = f"{_PRECHECK_SUBMISSION_DIR}/"
_OUTPUT_PREFIX = f"{_PRECHECK_OUTPUT_DIR}/"
_SUBMISSION_MANIFEST_PATH = workspace_path("output", "submission_manifest.json")
_PRECHECK_FILE_CAP = 20
_REALITY_SECTION_HEADER_RE = re.compile(r"^--- (?P<path>.+?) ---$", re.MULTILINE)
_MARKDOWN_EXTENSIONS = {".md", ".markdown", ".rst"}
_SUBMISSION_CONTEXT_PRIORITY_PATHS = (
    workspace_path("submission", "squidpy_spatial_workflow.py"),
    workspace_path("submission", "main_analysis.py"),
    workspace_path("submission", "genelab_scaffold.py"),
    workspace_path("submission", "run.sh"),
    workspace_path("output", "agent", "dataset_manifest.json"),
    workspace_path("output", "agent", "spatial_graph_metrics.json"),
    workspace_path("output", "agent", "neighborhood", "nhood_enrichment_ranked.tsv"),
    workspace_path("output", "agent", "neighborhood", "centrality_scores.tsv"),
    workspace_path("output", "agent", "neighborhood", "cooccurrence_curves.tsv"),
    workspace_path("output", "agent", "neighborhood", "interaction_matrix.tsv"),
    workspace_path("output", "agent", "autocorrelation", "geary_ranked.tsv"),
    workspace_path("output", "agent", "autocorrelation", "moran_ranked.tsv"),
    workspace_path("output", "agent", "spatial_stats", "ripley_curves.tsv"),
    workspace_path("output", "agent", "spatial_stats", "svg_summary.json"),
    workspace_path("output", "agent", "spatial_stats", "gene_localization.tsv"),
    workspace_path("output", "agent", "image_features", "feature_matrix.tsv"),
    workspace_path("output", "agent", "image_features", "feature_summary.json"),
    workspace_path("output", "agent", "interactions", "ligrec_ranked.tsv"),
    workspace_path("output", "agent", "visualizations", "spatial_stats_plot.svg"),
    workspace_path("output", "agent", "visualizations", "marker_localization.svg"),
    workspace_path("output", "agent", "visualizations", "report.html"),
    workspace_path("output", "agent", "run_summary.json"),
    workspace_path("output", "agent", "run.log"),
    workspace_path("output", "agent", "lomo", "summary.tsv"),
    workspace_path("output", "agent", "lomo", "split_manifest.tsv"),
    workspace_path("output", "agent", "lomo", "preprocessed_features.tsv"),
    workspace_path("output", "agent", "transfer", "cross_tissue.tsv"),
    workspace_path("output", "agent", "negative_controls", "summary.tsv"),
    workspace_path("output", "agent", "interpretability", "top_features.tsv"),
    workspace_path("output", "agent", "go_nogo", "summary.tsv"),
    workspace_path("output", "agent", "foundation", "geneformer_staging.tsv"),
    workspace_path("output", "submission_manifest.json"),
    workspace_path("submission", "README.md"),
)
_SOURCE_FOCUS_PATTERNS = (
    "FEATURE_ROOT",
    "LABEL_ROOT",
    "OUTPUT_ROOT",
    "LOMO_FIELDS",
    "TRANSFER_FIELDS",
    "NEGATIVE_FIELDS",
    "INTERPRETABILITY_FIELDS",
    "GO_NOGO_FIELDS",
    "FOUNDATION_FIELDS",
    "SPLIT_FIELDS",
    "PREPROCESSED_FIELDS",
    "FoldSpec",
    "AlignedFoldData",
    "def discover_fold_specs",
    "def _read_feature_rows",
    "def _read_label_rows",
    "def _read_meta_rows",
    "def _align_train_test_features",
    "def _align_rows",
    "def load_aligned_fold",
    "train_meta",
    "test_meta",
    "heldout_mission",
    "def _variance_screened_matrices",
    "def _elasticnet_scores",
    "LogisticRegression",
    "penalty=\"elasticnet\"",
    "def _random_forest_scores",
    "RandomForestClassifier",
    "def _xgboost_scores",
    "XGBClassifier",
    "GradientBoostingClassifier",
    "def _pca_logreg_scores",
    "PCA",
    "def _score_model",
    "def _bootstrap_ci",
    "def _permutation_pvalue",
    "def _evaluate_lomo",
    "go_nogo",
    "def _build_go_nogo_rows",
    "decision",
    "def _build_negative_control_rows",
    "label_permutation",
    "housekeeping_proxy_low_variance",
    "def _build_interpretability_rows",
    "feature_rank",
    "def _feature_intersection",
    "def _build_transfer_rows",
    "source_tissue",
    "target_tissue",
    "def _build_split_manifest_rows",
    "train_missions",
    "test_missions",
    "def _build_preprocessed_rows",
    "def _build_foundation_rows",
    "Geneformer",
    "def write_tsv",
    "def _write_manifest",
    "squidpy",
    "scanpy",
    "def generate_references",
    "def _generate_autocorr_reference",
    "def _generate_graph_reference",
    "def _generate_spatial_pattern_reference",
    "def _generate_image_reference",
    "def _generate_ligrec_reference",
    "sq.datasets.visium_hne_adata",
    "sq.datasets.seqfish",
    "sq.datasets.visium_hne_image",
    "spatial_neighbors",
    "nhood_enrichment",
    "centrality_scores",
    "interaction_matrix",
    "co_occurrence",
    "spatial_autocorr",
    "geary",
    "moran",
    "ripley",
    "segment(",
    "ImageContainer",
    "calculate_image_features",
    "ligrec",
    "def main",
)


def _is_trivial_stmt(stmt: ast.AST) -> bool:
    """Return True for statements that carry no executable intent.

    Trivial statements are `pass`, docstring / `...` expressions, and
    `raise NotImplementedError` (with or without call arguments). These
    are the markers of an empty scaffold that the v0.2 artifact-presence
    precheck rejects.
    """

    if isinstance(stmt, ast.Pass):
        return True
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
        # docstring, ellipsis literal, bare integer, etc.
        return True
    if isinstance(stmt, ast.Raise):
        exc = stmt.exc
        if isinstance(exc, ast.Name) and exc.id == "NotImplementedError":
            return True
        if (
            isinstance(exc, ast.Call)
            and isinstance(exc.func, ast.Name)
            and exc.func.id == "NotImplementedError"
        ):
            return True
    return False


def _has_nontrivial_body(source: str) -> bool:
    """Detect whether a Python source file contains non-trivial executable code.

    Walks every `FunctionDef` / `AsyncFunctionDef` in the module (which
    naturally covers class methods and nested functions) and checks each
    body for at least one non-trivial statement. Also inspects module-level
    statements, ignoring imports and function/class definitions themselves,
    so top-level assignments or calls count as non-trivial.

    Fails closed on `SyntaxError`: a file that does not parse cannot execute.
    """

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if any(not _is_trivial_stmt(stmt) for stmt in node.body):
                return True

    module_excluded = (
        ast.Import,
        ast.ImportFrom,
        ast.FunctionDef,
        ast.AsyncFunctionDef,
        ast.ClassDef,
    )
    for stmt in tree.body:
        if isinstance(stmt, module_excluded):
            continue
        if not _is_trivial_stmt(stmt):
            return True

    return False


def _has_nontrivial_shell_body(source: str) -> bool:
    """Detect shell workflows that launch real analysis instead of placeholders."""

    substantive_patterns = (
        "python ",
        "python3 ",
        "uv run",
        "Rscript ",
        "R CMD",
        "jupyter ",
        "papermill ",
        "snakemake",
        "nextflow",
        "squidpy",
        "scanpy",
        "awk ",
        "R -",
    )
    ignored_exact = {
        "set -e",
        "set -eu",
        "set -euo pipefail",
        "set -o pipefail",
    }
    for raw_line in source.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("#!"):
            continue
        if line in ignored_exact:
            continue
        if line.startswith(("echo ", "touch ", "mkdir ", "chmod ", "cp ")):
            continue
        if any(pattern in f"{line} " for pattern in substantive_patterns):
            return True
    return False


def _has_nontrivial_r_body(source: str) -> bool:
    """Detect non-placeholder R source files for non-Python submissions."""

    for raw_line in source.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        lowered = line.lower()
        if "todo" in lowered or "notimplemented" in lowered:
            continue
        if lowered.startswith(("library(", "suppresspackagestartupmessages(")):
            continue
        if "<-" in line or "=" in line or "(" in line:
            return True
    return False


def _has_nontrivial_notebook_body(source: str) -> bool:
    """Treat notebooks as source only when they contain substantive code cells."""

    try:
        payload = json.loads(source)
    except json.JSONDecodeError:
        return False
    for cell in payload.get("cells", []):
        if cell.get("cell_type") != "code":
            continue
        cell_source = cell.get("source", "")
        if isinstance(cell_source, list):
            cell_source = "".join(str(part) for part in cell_source)
        if _has_nontrivial_body(str(cell_source)) or _has_nontrivial_shell_body(str(cell_source)):
            return True
    return False


def _has_nontrivial_workflow_source(path: str, source: str) -> bool:
    suffix = Path(path).suffix.lower()
    if suffix == ".py":
        return _has_nontrivial_body(source)
    if suffix == ".sh":
        return _has_nontrivial_shell_body(source)
    if suffix == ".r":
        return _has_nontrivial_r_body(source)
    if suffix == ".ipynb":
        return _has_nontrivial_notebook_body(source)
    return False


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
    raw_overall_score: float = 0.0
    severity_caps_applied: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "paper_id": self.paper_id,
            "overall_score": self.overall_score,
            "raw_overall_score": self.raw_overall_score,
            "severity_caps_applied": list(self.severity_caps_applied),
            "category_scores": dict(self.category_scores),
            "missing_leaf_ids": list(self.missing_leaf_ids),
            "extra_leaf_ids": list(self.extra_leaf_ids),
            "root": self.root.to_dict(),
        }


# Edison-style severity caps. Each rule fires when a category falls into
# catastrophic territory and caps the headline score so a model with one badly
# broken category cannot read as "halfway reproducing" through the weighted
# average alone. Order is fixed; multiple caps may fire and the most aggressive
# (lowest) wins.
SEVERITY_CAP_RULES: tuple[tuple[str, str, float, float], ...] = (
    # rule_name, category_key, trigger_threshold, cap_value
    ("execution_below_0_30_caps_overall_at_0_40", "execution", 0.30, 0.40),
    ("result_match_below_0_30_caps_overall_at_0_50", "result_match", 0.30, 0.50),
    ("result_match_below_0_50_caps_overall_at_0_70", "result_match", 0.50, 0.70),
)


def _apply_severity_caps(
    overall: float, category_scores: Mapping[str, float]
) -> tuple[float, list[str]]:
    """Apply severity caps to the overall score.

    Returns (capped_overall, list_of_rule_names_applied). The capped overall is
    the minimum of the original overall and every triggered cap, so the most
    aggressive failure dominates. The original score is preserved on the report
    as `raw_overall_score`.
    """

    capped = float(overall)
    rules_applied: list[str] = []
    for rule_name, category, threshold, cap_value in SEVERITY_CAP_RULES:
        score = float(category_scores.get(category, 1.0))
        if score < threshold:
            rules_applied.append(rule_name)
            if capped > cap_value:
                capped = cap_value
    return capped, rules_applied


@dataclass(frozen=True)
class EvidenceSource:
    """Resolved source for a judge evidence quote inside scorer reality context."""

    source_type: str
    path: str | None
    matched_text: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_type": self.source_type,
            "path": self.path,
            "matched_text": self.matched_text,
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
    raw_overall = root_report.score
    capped_overall, caps_applied = _apply_severity_caps(raw_overall, category_scores)
    return RubricScoreReport(
        paper_id=str(payload["paper_id"]),
        overall_score=capped_overall,
        raw_overall_score=raw_overall,
        severity_caps_applied=tuple(caps_applied),
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
    cap_note = ""
    if report.severity_caps_applied:
        cap_note = (
            f", raw_overall={report.raw_overall_score:.3f}, "
            f"severity_caps={','.join(report.severity_caps_applied)}"
        )
    return (
        f"overall={report.overall_score:.3f}{cap_note}, {category_summary}{missing}{extras}"
    )


def to_inspect_score(report: RubricScoreReport) -> InspectScore:
    """Convert a rubric score report into an Inspect-compatible score object."""

    return InspectScore(
        value=report.overall_score,
        explanation=summarize_score_report(report),
        metadata=report.to_dict(),
    )


def _score_interpretation_metadata(
    score_value: float, judgements: Sequence[LeafJudgement]
) -> dict[str, Any]:
    """Describe how a raw score should be compared across evaluation lanes."""

    starter_assisted_leaves = sum(
        1 for judgement in judgements if judgement.metadata.get("starter_assisted")
    )
    starter_profiles = sorted(
        {
            str(judgement.metadata["starter_profile"])
            for judgement in judgements
            if judgement.metadata.get("starter_profile")
        }
    )
    metadata: dict[str, Any] = {
        "starter_assisted_leaves": starter_assisted_leaves,
        "starter_profiles": starter_profiles,
        "raw_reproducibility_score": score_value,
    }
    if starter_assisted_leaves:
        metadata.update(
            {
                "evaluation_lane": "starter_assisted",
                "score_interpretation": (
                    "starter-assisted reproducibility score; compare separately from "
                    "blank-slate submissions"
                ),
                "score_validity": (
                    "golden-path/starter validation score, not a blank-slate model "
                    "performance estimate"
                ),
                "model_performance_score": None,
                "model_performance_score_available": False,
                "production_comparable": False,
                "production_comparison_blocker": (
                    "starter-assisted source/reference path detected; run an "
                    "unassisted submission to compare model performance"
                ),
            }
        )
    else:
        metadata.update(
            {
                "evaluation_lane": "blank_slate_or_unassisted",
                "score_interpretation": (
                    "blank-slate or unassisted reproducibility score"
                ),
                "score_validity": "candidate model-performance score",
                "model_performance_score": score_value,
                "model_performance_score_available": True,
                "production_comparable": True,
            }
        )
    return metadata


def _score_explanation_with_lane(explanation: str, metadata: Mapping[str, Any]) -> str:
    """Append lane information so a raw 1.000 is not mistaken for model performance."""

    lane = metadata.get("evaluation_lane")
    if lane == "starter_assisted":
        return (
            f"{explanation}, lane=starter_assisted, "
            "model_performance_score=not_available"
        )
    if lane:
        return f"{explanation}, lane={lane}"
    return explanation


def _starter_mode_for_scoring() -> str:
    """Return the current starter mode without importing task construction helpers."""

    import os

    raw = os.getenv(_STARTER_MODE_ENV, "seed").strip().lower().replace("-", "_")
    aliases = {
        "": "seed",
        "on": "seed",
        "copy": "seed",
        "seed": "seed",
        "seeded": "seed",
        "available": "available",
        "bundle": "available",
        "bundle_only": "available",
        "off": "off",
        "none": "off",
        "no": "off",
        "false": "off",
        "disabled": "off",
        "unassisted": "off",
    }
    return aliases.get(raw, raw)


def _reference_starter_assisted_active(reference: Mapping[str, Any]) -> bool:
    """Only mark starter-assisted credit when the starter path is actually active."""

    return bool(reference.get("starter_assisted", False)) and _starter_mode_for_scoring() != "off"


def load_rubric_payload(paper_id: str) -> dict[str, Any]:
    """Load the rubric JSON for a given paper from the repo `papers/` tree."""

    rubric_path = PROJECT_ROOT / "papers" / paper_id / "rubric.json"
    with rubric_path.open() as handle:
        return json.load(handle)


def load_paper_summary(paper_id: str, *, max_chars: int = _JUDGE_MAX_PAPER_CHARS) -> str:
    """Load the paper-summary markdown with a conservative truncation."""

    paper_path = PROJECT_ROOT / "papers" / paper_id / "paper.md"
    if paper_path.exists():
        return paper_path.read_text()[:max_chars]
    return f"Paper `{paper_id}`: paper.md is not available to the judge."


def _load_reference_payload(paper_id: str, filename: str) -> dict[str, Any]:
    reference_path = (
        PROJECT_ROOT
        / "papers"
        / paper_id
        / _REFERENCE_OUTPUTS_DIRNAME
        / filename
    )
    if not reference_path.exists():
        return {}
    payload = json.loads(reference_path.read_text())
    if not isinstance(payload, dict):
        raise ValueError(f"{reference_path} must contain a JSON object.")
    return payload


def load_result_match_reference(paper_id: str) -> dict[str, Any]:
    """Load sealed result-match comparator definitions for a paper if present."""

    return _load_reference_payload(paper_id, _RESULT_MATCH_REFERENCE_FILENAME)


def load_execution_reference(paper_id: str) -> dict[str, Any]:
    """Load deterministic execution artifact checks for a paper if present."""

    return _load_reference_payload(paper_id, _EXECUTION_REFERENCE_FILENAME)


def load_code_development_reference(paper_id: str) -> dict[str, Any]:
    """Load deterministic source-code checks for a paper if present."""

    return _load_reference_payload(paper_id, _CODE_DEVELOPMENT_REFERENCE_FILENAME)


def _result_match_requires_output_artifact(paper_id: str) -> bool:
    """Return whether the paper has sealed result-match checks that need outputs."""

    reference = load_result_match_reference(paper_id)
    if not reference:
        return False
    if bool(reference.get("strict_result_match", False)):
        return True
    leaves = reference.get("leaves", {})
    if not isinstance(leaves, Mapping):
        return False
    for config in leaves.values():
        if not isinstance(config, Mapping):
            continue
        status = str(config.get("status", "ready")).strip().lower()
        if config.get("enabled") is False or status in {
            "pending",
            "pending_benchmark_author_fill_in",
            "todo",
            "disabled",
        }:
            continue
        if str(config.get("artifact", "")).strip():
            return True
    return False


try:  # pragma: no cover - optional Inspect-only integration
    from inspect_ai.model import get_model
    from inspect_ai.scorer import Target, mean, scorer, stderr
    from inspect_ai.solver import TaskState
    from inspect_ai.util import sandbox

    _HAS_INSPECT_SCORING = True
except ModuleNotFoundError:  # pragma: no cover - local fallback
    _HAS_INSPECT_SCORING = False


def _sandbox_artifact_path(path: str) -> str:
    """Map canonical `/workspace` references onto the configured workspace root."""

    if path.startswith("/workspace/") and _WORKSPACE_ROOT != "/workspace":
        return f"{_WORKSPACE_ROOT}{path[len('/workspace'):]}"
    if path.startswith("/"):
        return path
    return workspace_path(*Path(path).parts)


async def _read_sandbox_file(path: str) -> str:
    if not _HAS_INSPECT_SCORING:  # pragma: no cover - import-only fallback guard
        raise RuntimeError("Inspect sandbox is not available.")
    return await sandbox().read_file(_sandbox_artifact_path(path))


def _json_pointer(payload: Any, path: Iterable[Any]) -> Any:
    """Resolve a tiny JSON-pointer-like path made of dict keys and list indexes."""

    current = payload
    for part in path:
        if isinstance(current, Mapping):
            current = current[str(part)]
            continue
        if isinstance(current, list):
            current = current[int(part)]
            continue
        raise KeyError(f"Cannot descend through {type(current).__name__} at {part!r}.")
    return current


def _reference_json_paths(config: Mapping[str, Any]) -> list[list[Any]]:
    if "json_path_candidates" in config:
        candidates = config["json_path_candidates"]
        if not isinstance(candidates, list):
            raise TypeError("json_path_candidates must be a list of paths.")
        return [list(candidate) for candidate in candidates]
    return [list(config.get("json_path", []))]


def _json_pointer_first(payload: Any, config: Mapping[str, Any]) -> tuple[Any, list[Any]]:
    last_exc: Exception | None = None
    for path in _reference_json_paths(config):
        try:
            return _json_pointer(payload, path), path
        except Exception as exc:
            last_exc = exc
    raise KeyError(f"No configured JSON path matched: {last_exc}")


def _reference_artifact_text(paper_id: str, relative_path: str) -> str:
    path = PROJECT_ROOT / "papers" / paper_id / _REFERENCE_OUTPUTS_DIRNAME / relative_path
    if not path.is_file():
        raise FileNotFoundError(path)
    return path.read_text()


def _coerce_float(value: Any) -> float:
    if isinstance(value, bool):
        raise TypeError("Boolean values are not numeric comparator values.")
    return float(value)


def _numeric_within_tolerance(
    observed: Any,
    expected: Any,
    *,
    tolerance_pct: float | None = None,
    absolute_tolerance: float | None = None,
) -> bool:
    observed_value = _coerce_float(observed)
    expected_value = _coerce_float(expected)
    if absolute_tolerance is not None:
        return abs(observed_value - expected_value) <= float(absolute_tolerance)
    return within_percent_tolerance(
        observed_value,
        expected_value,
        tolerance_pct=float(tolerance_pct if tolerance_pct is not None else 0.0),
    )


def _shape_within_tolerance(
    observed: Any,
    expected: Any,
    *,
    tolerance_pct: float,
) -> bool:
    if isinstance(expected, Mapping):
        if not isinstance(observed, Mapping):
            return False
        return all(
            _numeric_within_tolerance(
                observed[key],
                expected_value,
                tolerance_pct=tolerance_pct,
            )
            for key, expected_value in expected.items()
        )

    if not isinstance(observed, (list, tuple)) or not isinstance(expected, (list, tuple)):
        return False
    if len(observed) != len(expected):
        return False
    return all(
        _numeric_within_tolerance(
            observed_value,
            expected_value,
            tolerance_pct=tolerance_pct,
        )
        for observed_value, expected_value in zip(observed, expected)
    )


def _normalizer_for_reference(config: Mapping[str, Any]):
    normalizer = str(config.get("normalize", "")).strip().lower()
    if normalizer in {"gene", "gene_symbol", "gene-symbol"}:
        return normalize_gene_symbol
    if normalizer in {"label", "cluster", "cell_label", "cell-type", "cell_type"}:
        return normalize_pathway_name
    if normalizer in {"pair_key_canonical", "pair_key", "symmetric_pair"}:
        return _normalize_pair_key_canonical
    if not normalizer:
        return None
    raise ValueError(f"Unsupported normalizer: {normalizer}")


def _normalize_pair_key_canonical(text: str) -> str:
    """Sort the two halves of a pair_key 'X|Y' alphabetically.

    Squidpy neighborhood-enrichment exports list each unordered cluster pair
    twice (cluster_1|cluster_2 and cluster_2|cluster_1). Canonicalising the
    pair_key collapses those duplicates so rank-overlap metrics see the same
    set of unique pairs the benchmark reference uses.
    """

    text = text.strip()
    if "|" not in text:
        return text
    left, right = text.split("|", 1)
    parts = sorted([left.strip(), right.strip()])
    return "|".join(parts)


def _normalized_string(value: Any, normalize: Any = None) -> str:
    text = str(value).strip()
    return normalize(text) if normalize else text


def _ensure_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, Mapping):
        return list(value.values())
    raise TypeError(f"Expected a list-like value, got {type(value).__name__}.")


def _tsv_table(text: str) -> tuple[list[str], list[dict[str, str]]]:
    reader = csv.DictReader(text.splitlines(), delimiter="\t")
    if reader.fieldnames is None:
        raise KeyError("TSV header row is missing.")
    rows = [
        {str(key): str(value) for key, value in row.items() if key is not None}
        for row in reader
    ]
    return list(reader.fieldnames), rows


def _tsv_column_values(text: str, *, column: str) -> list[str]:
    fieldnames, rows = _tsv_table(text)
    if column not in fieldnames:
        fields = ", ".join(fieldnames)
        raise KeyError(f"TSV column {column!r} not found; available columns: {fields}")
    values: list[str] = []
    for row in rows:
        value = (row.get(column) or "").strip()
        if value:
            values.append(value)
    return values


def _tsv_rows(text: str) -> list[dict[str, str]]:
    return _tsv_table(text)[1]


def _reference_path_key(path: Iterable[Any]) -> str:
    return "/" + "/".join(str(part) for part in path)


def _compact_observed_value(value: Any) -> Any:
    """Keep deterministic scorer metadata useful without embedding large artifacts."""

    if isinstance(value, Mapping):
        items = list(value.items())
        return {
            "type": "object",
            "keys": [str(key) for key, _ in items[:8]],
            "size": len(items),
        }
    if isinstance(value, list):
        return {
            "type": "list",
            "size": len(value),
            "sample": value[:5],
        }
    if isinstance(value, str) and len(value) > 160:
        return value[:157] + "..."
    return value


def _tsv_row_by_key(
    text: str,
    *,
    key_column: str,
    key_value: str,
    normalize: Any = None,
) -> dict[str, str]:
    expected = normalize(key_value) if normalize else key_value
    for row in _tsv_rows(text):
        observed = row.get(key_column, "")
        observed_key = normalize(observed) if normalize else observed
        if observed_key == expected:
            return row
    raise KeyError(f"TSV row {key_column}={key_value!r} not found.")


def _rows_by_key(
    rows: Iterable[Mapping[str, str]],
    *,
    key_column: str,
    normalize: Any = None,
) -> dict[str, Mapping[str, str]]:
    by_key: dict[str, Mapping[str, str]] = {}
    for row in rows:
        raw_key = row.get(key_column)
        if raw_key is None or str(raw_key).strip() == "":
            continue
        key = _normalized_string(raw_key, normalize)
        by_key[key] = row
    return by_key


def _coerce_float_list(rows: Iterable[Mapping[str, str]], *, value_column: str) -> list[float]:
    return [_coerce_float(row[value_column]) for row in rows]


def _correlation(method: str, left: list[float], right: list[float]) -> float:
    if method == "pearson":
        return pearson_correlation(left, right)
    if method == "spearman":
        return spearman_correlation(left, right)
    raise ValueError(f"Unsupported correlation method: {method}")


def _sort_curve_rows(rows: list[Mapping[str, str]], *, x_column: str) -> list[Mapping[str, str]]:
    def sort_key(row: Mapping[str, str]) -> tuple[int, float | str]:
        value = row.get(x_column, "")
        try:
            return (0, float(value))
        except (TypeError, ValueError):
            return (1, str(value))

    return sorted(rows, key=sort_key)


def _group_curve_rows(
    rows: Iterable[Mapping[str, str]],
    *,
    group_column: str,
    x_column: str,
    normalize: Any = None,
) -> dict[str, dict[str, Mapping[str, str]]]:
    grouped: dict[str, dict[str, Mapping[str, str]]] = {}
    for row in rows:
        raw_group = row.get(group_column)
        raw_x = row.get(x_column)
        if raw_group is None or raw_x is None:
            continue
        group = _normalized_string(raw_group, normalize)
        x_value = str(raw_x).strip()
        if not group or not x_value:
            continue
        grouped.setdefault(group, {})[x_value] = row
    return grouped


def _deterministic_result_match_zero(
    leaf: Mapping[str, Any],
    *,
    reason: str,
    metadata: Mapping[str, Any] | None = None,
) -> LeafJudgement:
    payload = {
        "deterministic_result_match": True,
        **dict(metadata or {}),
    }
    return LeafJudgement(
        leaf_id=str(leaf["id"]),
        expectations=str(leaf.get("requirement", "")),
        reality=reason,
        evidence_quote=reason,
        score=0,
        confidence=1.0,
        metadata=payload,
    )


def _deterministic_result_match_passfail(
    leaf: Mapping[str, Any],
    *,
    artifact: str,
    metric: str,
    observed: Any,
    expected: Any,
    passed: bool,
    threshold: Any | None,
    metadata: Mapping[str, Any] | None = None,
) -> LeafJudgement:
    score = 1 if passed else 0
    status = "passed" if passed else "failed"
    evidence_quote = (
        f"deterministic_result_match_{status}: metric={metric}; "
        f"observed={observed!r}; expected={expected!r}; threshold={threshold!r}"
    )
    payload = {
        "deterministic_result_match": True,
        "artifact": _sandbox_artifact_path(artifact),
        "metric": metric,
        "observed": observed,
        "expected": expected,
        "threshold": threshold,
        **dict(metadata or {}),
    }
    return LeafJudgement(
        leaf_id=str(leaf["id"]),
        expectations=str(leaf.get("requirement", "")),
        reality=evidence_quote,
        evidence_quote=evidence_quote,
        score=score,
        confidence=1.0,
        metadata=payload,
    )


async def _evaluate_result_match_subcheck(
    config: Mapping[str, Any],
    *,
    paper_id: str,
) -> dict[str, Any]:
    """Evaluate a single sub-check for result_match all_checks/any_checks gates.

    Supports a subset of result_match metrics that are practical to compose into
    a gating leaf — currently json_shape_within_tolerance and
    json_numeric_within_tolerance. Returns a dict shaped like
    `_deterministic_result_match_passfail` body but without leaf wrapping.
    """

    metric = str(config.get("metric", "")).strip()
    artifact = str(config.get("artifact", "")).strip()
    if not metric or not artifact:
        return {
            "passed": False,
            "metric": metric or "unknown",
            "observed": "missing metric or artifact",
            "expected": dict(config),
            "threshold": None,
        }
    try:
        text = await _read_sandbox_file(artifact)
        payload = json.loads(text)
        if metric == "json_shape_within_tolerance":
            observed, _ = _json_pointer_first(payload, config)
            expected = config["expected"]
            tolerance = float(config.get("tolerance_pct", 0.0))
            passed = _shape_within_tolerance(
                observed, expected, tolerance_pct=tolerance
            )
            return {
                "passed": passed,
                "metric": metric,
                "observed": observed,
                "expected": expected,
                "threshold": tolerance,
            }
        if metric == "json_numeric_within_tolerance":
            observed, _ = _json_pointer_first(payload, config)
            expected = config["expected"]
            passed = _numeric_within_tolerance(
                observed,
                expected,
                tolerance_pct=config.get("tolerance_pct"),
                absolute_tolerance=config.get("absolute_tolerance"),
            )
            return {
                "passed": passed,
                "metric": metric,
                "observed": observed,
                "expected": expected,
                "threshold": config.get("absolute_tolerance", config.get("tolerance_pct")),
            }
        raise ValueError(
            f"unsupported metric {metric!r} in result_match all_checks sub-check; "
            "supported: json_shape_within_tolerance, json_numeric_within_tolerance"
        )
    except Exception as exc:
        return {
            "passed": False,
            "metric": metric,
            "observed": f"{type(exc).__name__}: {exc}",
            "expected": dict(config),
            "threshold": None,
        }


async def _deterministic_result_match_judgement(
    leaf: Mapping[str, Any],
    *,
    paper_id: str,
) -> LeafJudgement | None:
    """Grade result-match leaves with sealed comparator refs before any LLM judge.

    Returning ``None`` means no deterministic policy is configured for this paper
    or leaf, so the caller may fall back to the existing judge path.
    """

    if str(leaf.get("category", "")) != "result_match":
        return None

    reference = load_result_match_reference(paper_id)
    if not reference:
        return None

    leaf_id = str(leaf["id"])
    strict = bool(reference.get("strict_result_match", False))
    leaves = reference.get("leaves", {})
    if not isinstance(leaves, Mapping):
        raise ValueError("result_match_reference.json field `leaves` must be an object.")

    config = leaves.get(leaf_id)
    if not config:
        if not strict:
            return None
        return _deterministic_result_match_zero(
            leaf,
            reason=f"deterministic_reference_missing: no sealed comparator for {leaf_id}",
            metadata={
                "deterministic_reference_missing": True,
                "strict_result_match": True,
            },
        )
    if not isinstance(config, Mapping):
        return _deterministic_result_match_zero(
            leaf,
            reason=f"deterministic_reference_invalid: comparator config for {leaf_id} is not an object",
            metadata={"deterministic_reference_invalid": True},
        )

    status = str(config.get("status", "ready")).strip().lower()
    if config.get("enabled") is False or status in {
        "pending",
        "pending_benchmark_author_fill_in",
        "todo",
        "disabled",
    }:
        return _deterministic_result_match_zero(
            leaf,
            reason=f"deterministic_reference_pending: sealed comparator for {leaf_id} is {status}",
            metadata={
                "deterministic_reference_missing": True,
                "reference_status": status,
            },
        )

    metric = str(config.get("metric", "")).strip()
    artifact = str(config.get("artifact", "")).strip()
    if not metric:
        return _deterministic_result_match_zero(
            leaf,
            reason=f"deterministic_reference_invalid: comparator for {leaf_id} needs metric",
            metadata={"deterministic_reference_invalid": True},
        )
    if metric not in {"all_checks", "any_checks"} and not artifact:
        return _deterministic_result_match_zero(
            leaf,
            reason=f"deterministic_reference_invalid: comparator for {leaf_id} needs artifact",
            metadata={"deterministic_reference_invalid": True},
        )

    try:
        if metric in {"all_checks", "any_checks"}:
            sub_checks = config.get("checks", [])
            if not isinstance(sub_checks, list) or not sub_checks:
                return _deterministic_result_match_zero(
                    leaf,
                    reason=f"deterministic_reference_invalid: {metric} needs non-empty checks list",
                    metadata={"deterministic_reference_invalid": True},
                )
            sub_results: list[dict[str, Any]] = []
            for sub in sub_checks:
                if not isinstance(sub, Mapping):
                    raise TypeError(f"{metric} sub-check must be an object.")
                sub_results.append(
                    await _evaluate_result_match_subcheck(sub, paper_id=paper_id)
                )
            if metric == "all_checks":
                passed = all(r["passed"] for r in sub_results)
            else:
                passed = any(r["passed"] for r in sub_results)
            return _deterministic_result_match_passfail(
                leaf,
                artifact=f"<{metric} over {len(sub_results)} sub-checks>",
                metric=metric,
                observed=sub_results,
                expected=f"{metric} of {len(sub_results)} sub-checks",
                passed=passed,
                threshold="all" if metric == "all_checks" else "any",
                metadata={"deterministic_result_match_subchecks": sub_results},
            )
        if metric in {"json_shape_within_tolerance", "json_numeric_within_tolerance"}:
            payload = json.loads(await _read_sandbox_file(artifact))
            observed, matched_json_path = _json_pointer_first(payload, config)
            expected = config["expected"]
            if metric == "json_shape_within_tolerance":
                threshold = config.get("tolerance_pct", 0.0)
                passed = _shape_within_tolerance(
                    observed,
                    expected,
                    tolerance_pct=float(threshold),
                )
            else:
                threshold = config.get("absolute_tolerance", config.get("tolerance_pct", 0.0))
                passed = _numeric_within_tolerance(
                    observed,
                    expected,
                    tolerance_pct=config.get("tolerance_pct"),
                    absolute_tolerance=config.get("absolute_tolerance"),
                )
            return _deterministic_result_match_passfail(
                leaf,
                artifact=artifact,
                metric=metric,
                observed=observed,
                expected=expected,
                passed=passed,
                threshold=threshold,
                metadata={"json_path": matched_json_path},
            )

        if metric == "json_set_match":
            payload = json.loads(await _read_sandbox_file(artifact))
            observed, matched_json_path = _json_pointer_first(payload, config)
            normalizer = _normalizer_for_reference(config)
            observed_values = {
                _normalized_string(item, normalizer) for item in _ensure_list(observed)
            }
            expected_values = {
                _normalized_string(item, normalizer) for item in _ensure_list(config["expected"])
            }
            if not expected_values:
                value = 1.0 if not observed_values else 0.0
            else:
                value = len(observed_values & expected_values) / len(expected_values | observed_values)
            minimum = float(config.get("minimum", 1.0))
            missing = sorted(expected_values - observed_values)
            extra = sorted(observed_values - expected_values)
            passed = value >= minimum
            if config.get("require_exact", minimum >= 1.0):
                passed = passed and not missing and not extra
            return _deterministic_result_match_passfail(
                leaf,
                artifact=artifact,
                metric=metric,
                observed=round(value, 6),
                expected=f"{len(expected_values)} reference labels",
                passed=passed,
                threshold=minimum,
                metadata={
                    "json_path": matched_json_path,
                    "observed_count": len(observed_values),
                    "expected_count": len(expected_values),
                    "missing": missing,
                    "extra": extra,
                },
            )

        if metric in {"tsv_rank_biased_overlap", "tsv_overlap_at_k"}:
            predicted = _tsv_column_values(
                await _read_sandbox_file(artifact),
                column=str(config.get("column", "gene")),
            )
            expected = [str(item) for item in config.get("expected", [])]
            top_k = int(config.get("top_k", len(expected) or len(predicted) or 1))
            normalizer = _normalizer_for_reference(config)
            if metric == "tsv_rank_biased_overlap":
                value = rank_biased_overlap(
                    predicted,
                    expected,
                    p=float(config.get("p", 0.9)),
                    k=top_k,
                    normalize=normalizer,
                )
                threshold = float(config.get("minimum", config.get("min_score", 0.0)))
            else:
                value = overlap_at_k(
                    predicted,
                    expected,
                    k=top_k,
                    normalize=normalizer,
                )
                threshold = float(config.get("minimum", config.get("min_score", 0.0)))
            return _deterministic_result_match_passfail(
                leaf,
                artifact=artifact,
                metric=metric,
                observed=round(value, 6),
                expected=f"{len(expected)} reference ranks",
                passed=value >= threshold,
                threshold=threshold,
                metadata={"top_k": top_k},
            )

        if metric == "tsv_row_numeric_within_tolerance":
            normalizer = _normalizer_for_reference(config)
            row = _tsv_row_by_key(
                await _read_sandbox_file(artifact),
                key_column=str(config.get("key_column", "gene")),
                key_value=str(config["key_value"]),
                normalize=normalizer,
            )
            value_column = str(config["value_column"])
            observed = _coerce_float(row[value_column])
            expected = _coerce_float(config["expected"])
            threshold = config.get("absolute_tolerance", config.get("tolerance_pct", 0.0))
            passed = _numeric_within_tolerance(
                observed,
                expected,
                tolerance_pct=config.get("tolerance_pct"),
                absolute_tolerance=config.get("absolute_tolerance"),
            )
            return _deterministic_result_match_passfail(
                leaf,
                artifact=artifact,
                metric=metric,
                observed=observed,
                expected=expected,
                passed=passed,
                threshold=threshold,
                metadata={
                    "key_column": str(config.get("key_column", "gene")),
                    "key_value": str(config["key_value"]),
                    "value_column": value_column,
                },
            )

        if metric == "tsv_aligned_numeric_correlation":
            normalizer = _normalizer_for_reference(config)
            method = str(config.get("correlation", "spearman")).strip().lower()
            key_column = str(config.get("key_column", "key"))
            value_columns = config.get("value_columns", config.get("value_column", "value"))
            if isinstance(value_columns, str):
                value_columns = [value_columns]
            if not isinstance(value_columns, list) or not value_columns:
                raise TypeError("value_column or value_columns must define at least one TSV column.")
            predicted_rows = _tsv_rows(await _read_sandbox_file(artifact))
            reference_rows = _tsv_rows(
                _reference_artifact_text(paper_id, str(config["reference_artifact"]))
            )
            predicted_by_key = _rows_by_key(
                predicted_rows,
                key_column=key_column,
                normalize=normalizer,
            )
            reference_by_key = _rows_by_key(
                reference_rows,
                key_column=key_column,
                normalize=normalizer,
            )
            shared_keys = sorted(set(predicted_by_key) & set(reference_by_key))
            min_shared = int(config.get("min_shared", len(reference_by_key)))
            if len(shared_keys) < min_shared:
                return _deterministic_result_match_zero(
                    leaf,
                    reason=(
                        "deterministic_comparator_error: insufficient aligned numeric rows "
                        f"({len(shared_keys)} < {min_shared})"
                    ),
                    metadata={
                        "deterministic_comparator_error": True,
                        "artifact": _sandbox_artifact_path(artifact),
                        "metric": metric,
                    },
                )
            correlations: dict[str, float] = {}
            for value_column in [str(column) for column in value_columns]:
                observed_values = [
                    _coerce_float(predicted_by_key[key][value_column]) for key in shared_keys
                ]
                reference_values = [
                    _coerce_float(reference_by_key[key][value_column]) for key in shared_keys
                ]
                correlations[value_column] = _correlation(
                    method,
                    observed_values,
                    reference_values,
                )
            value = sum(correlations.values()) / len(correlations)
            minimum = float(config.get("minimum", 0.0))
            return _deterministic_result_match_passfail(
                leaf,
                artifact=artifact,
                metric=metric,
                observed=round(value, 6),
                expected=f"{len(reference_by_key)} reference rows",
                passed=value >= minimum,
                threshold=minimum,
                metadata={
                    "key_column": key_column,
                    "value_columns": [str(column) for column in value_columns],
                    "correlation": method,
                    "shared_rows": len(shared_keys),
                    "column_correlations": {
                        key: round(val, 6) for key, val in correlations.items()
                    },
                    "reference_artifact": str(config["reference_artifact"]),
                },
            )

        if metric == "tsv_grouped_curve_correlation":
            normalizer = _normalizer_for_reference(config)
            method = str(config.get("correlation", "pearson")).strip().lower()
            group_column = str(config.get("group_column", "curve"))
            x_column = str(config.get("x_column", "x"))
            value_column = str(config.get("value_column", "value"))
            predicted_rows = _tsv_rows(await _read_sandbox_file(artifact))
            reference_rows = _tsv_rows(
                _reference_artifact_text(paper_id, str(config["reference_artifact"]))
            )
            predicted_groups = _group_curve_rows(
                predicted_rows,
                group_column=group_column,
                x_column=x_column,
                normalize=normalizer,
            )
            reference_groups = _group_curve_rows(
                reference_rows,
                group_column=group_column,
                x_column=x_column,
                normalize=normalizer,
            )
            if "groups" in config:
                requested_groups = {
                    _normalized_string(group, normalizer) for group in _ensure_list(config["groups"])
                }
            else:
                requested_groups = set(reference_groups)
            shared_groups = sorted(requested_groups & set(predicted_groups) & set(reference_groups))
            min_groups = int(config.get("min_groups", len(requested_groups)))
            min_points = int(config.get("min_points", 2))
            correlations: dict[str, float] = {}
            point_counts: dict[str, int] = {}
            for group in shared_groups:
                shared_x = set(predicted_groups[group]) & set(reference_groups[group])
                if len(shared_x) < min_points:
                    continue
                paired_rows = _sort_curve_rows(
                    [
                        {"x": x_value, "pred": predicted_groups[group][x_value][value_column], "ref": reference_groups[group][x_value][value_column]}
                        for x_value in shared_x
                    ],
                    x_column="x",
                )
                observed_values = [_coerce_float(row["pred"]) for row in paired_rows]
                reference_values = [_coerce_float(row["ref"]) for row in paired_rows]
                correlations[group] = _correlation(method, observed_values, reference_values)
                point_counts[group] = len(paired_rows)
            if len(correlations) < min_groups:
                return _deterministic_result_match_zero(
                    leaf,
                    reason=(
                        "deterministic_comparator_error: insufficient aligned curves "
                        f"({len(correlations)} < {min_groups})"
                    ),
                    metadata={
                        "deterministic_comparator_error": True,
                        "artifact": _sandbox_artifact_path(artifact),
                        "metric": metric,
                        "aligned_curves": len(correlations),
                    },
                )
            value = sum(correlations.values()) / len(correlations)
            minimum = float(config.get("minimum", 0.0))
            return _deterministic_result_match_passfail(
                leaf,
                artifact=artifact,
                metric=metric,
                observed=round(value, 6),
                expected=f"{len(reference_groups)} reference curves",
                passed=value >= minimum,
                threshold=minimum,
                metadata={
                    "group_column": group_column,
                    "x_column": x_column,
                    "value_column": value_column,
                    "correlation": method,
                    "aligned_curves": len(correlations),
                    "point_counts": point_counts,
                    "curve_correlations": {
                        key: round(val, 6) for key, val in correlations.items()
                    },
                    "reference_artifact": str(config["reference_artifact"]),
                },
            )

        if metric == "tsv_shape_within_tolerance":
            fieldnames, rows = _tsv_table(await _read_sandbox_file(artifact))
            excluded = {str(column) for column in config.get("exclude_columns", [])}
            observed = {
                "rows": len(rows),
                "columns": len([column for column in fieldnames if column not in excluded]),
            }
            expected = config["expected"]
            if not isinstance(expected, Mapping):
                raise TypeError("tsv_shape_within_tolerance expected value must be an object.")
            threshold = config.get("tolerance_pct", 0.0)
            passed = _shape_within_tolerance(
                observed,
                expected,
                tolerance_pct=float(threshold),
            )
            metadata: dict[str, Any] = {"exclude_columns": sorted(excluded)}
            if config.get("reference_artifact") and config.get("id_column"):
                id_column = str(config["id_column"])
                if id_column not in fieldnames:
                    raise KeyError(f"TSV id column {id_column!r} not found.")
                reference_fieldnames, reference_rows = _tsv_table(
                    _reference_artifact_text(paper_id, str(config["reference_artifact"]))
                )
                if id_column not in reference_fieldnames:
                    raise KeyError(f"Reference TSV id column {id_column!r} not found.")
                predicted_ids = {
                    str(row.get(id_column, "")).strip()
                    for row in rows
                    if str(row.get(id_column, "")).strip()
                }
                reference_ids = {
                    str(row.get(id_column, "")).strip()
                    for row in reference_rows
                    if str(row.get(id_column, "")).strip()
                }
                shared_ids = predicted_ids & reference_ids
                min_shared = int(config.get("min_shared_rows", len(reference_ids)))
                missing_ids = len(reference_ids - predicted_ids)
                extra_ids = len(predicted_ids - reference_ids)
                exact_ids = bool(config.get("require_exact_ids", False))
                passed = (
                    passed
                    and len(shared_ids) >= min_shared
                    and (not exact_ids or (missing_ids == 0 and extra_ids == 0))
                )
                observed["shared_ids"] = len(shared_ids)
                metadata.update(
                    {
                        "id_column": id_column,
                        "min_shared_rows": min_shared,
                        "missing_ids": missing_ids,
                        "extra_ids": extra_ids,
                        "require_exact_ids": exact_ids,
                        "reference_artifact": str(config["reference_artifact"]),
                    }
                )
            return _deterministic_result_match_passfail(
                leaf,
                artifact=artifact,
                metric=metric,
                observed=observed,
                expected=dict(expected),
                passed=passed,
                threshold=threshold,
                metadata=metadata,
            )

        if metric == "tsv_label_ari":
            predicted_text = await _read_sandbox_file(artifact)
            reference_text = _reference_artifact_text(
                paper_id,
                str(config["reference_artifact"]),
            )
            id_column = str(config.get("id_column", "obs_id"))
            label_column = str(config.get("label_column", "cluster"))
            reference_label_column = str(config.get("reference_label_column", label_column))
            predicted_rows = _tsv_rows(predicted_text)
            reference_rows = _tsv_rows(reference_text)
            predicted_map = {
                row[id_column]: row[label_column]
                for row in predicted_rows
                if row.get(id_column) and row.get(label_column)
            }
            reference_map = {
                row[id_column]: row[reference_label_column]
                for row in reference_rows
                if row.get(id_column) and row.get(reference_label_column)
            }
            shared_ids = sorted(set(predicted_map) & set(reference_map))
            min_shared = int(config.get("min_shared", len(reference_map)))
            if len(shared_ids) < min_shared:
                return _deterministic_result_match_zero(
                    leaf,
                    reason=(
                        "deterministic_comparator_error: insufficient aligned labels "
                        f"({len(shared_ids)} < {min_shared})"
                    ),
                    metadata={
                        "deterministic_comparator_error": True,
                        "artifact": _sandbox_artifact_path(artifact),
                        "metric": metric,
                    },
                )
            value = adjusted_rand_index(
                [reference_map[obs_id] for obs_id in shared_ids],
                [predicted_map[obs_id] for obs_id in shared_ids],
            )
            threshold = float(config.get("minimum", config.get("min_score", 0.0)))
            return _deterministic_result_match_passfail(
                leaf,
                artifact=artifact,
                metric=metric,
                observed=round(value, 6),
                expected=f"{len(reference_map)} reference labels",
                passed=value >= threshold,
                threshold=threshold,
                metadata={
                    "shared_labels": len(shared_ids),
                    "reference_artifact": str(config["reference_artifact"]),
                },
            )

        if metric == "json_cluster_nondegenerate":
            payload = json.loads(await _read_sandbox_file(artifact))
            counts = _json_pointer(payload, config.get("json_path", ["cluster_counts"]))
            if not isinstance(counts, Mapping):
                raise TypeError("cluster count JSON path must resolve to an object.")
            numeric_counts = {str(key): int(value) for key, value in counts.items()}
            total = sum(numeric_counts.values())
            observed = {
                "clusters": len([value for value in numeric_counts.values() if value > 0]),
                "max_fraction": max(numeric_counts.values()) / total if total else 1.0,
            }
            min_clusters = int(config.get("min_clusters", 1))
            max_fraction = float(config.get("max_fraction", 1.0))
            passed = observed["clusters"] >= min_clusters and observed["max_fraction"] <= max_fraction
            return _deterministic_result_match_passfail(
                leaf,
                artifact=artifact,
                metric=metric,
                observed=observed,
                expected={"min_clusters": min_clusters, "max_fraction": max_fraction},
                passed=passed,
                threshold={"min_clusters": min_clusters, "max_fraction": max_fraction},
            )

    except Exception as exc:
        return _deterministic_result_match_zero(
            leaf,
            reason=f"deterministic_comparator_error: {type(exc).__name__}: {exc}",
            metadata={
                "deterministic_comparator_error": True,
                "artifact": _sandbox_artifact_path(artifact),
                "metric": metric,
            },
        )

    return _deterministic_result_match_zero(
        leaf,
        reason=f"deterministic_metric_unsupported: {metric}",
        metadata={"deterministic_metric_unsupported": True, "metric": metric},
    )


def _deterministic_category_zero(
    leaf: Mapping[str, Any],
    *,
    category_key: str,
    reason: str,
    metadata: Mapping[str, Any] | None = None,
) -> LeafJudgement:
    payload = {
        f"deterministic_{category_key}": True,
        **dict(metadata or {}),
    }
    return LeafJudgement(
        leaf_id=str(leaf["id"]),
        expectations=str(leaf.get("requirement", "")),
        reality=reason,
        evidence_quote=reason,
        score=0,
        confidence=1.0,
        metadata=payload,
    )


def _deterministic_category_passfail(
    leaf: Mapping[str, Any],
    *,
    category_key: str,
    metric: str,
    observed: Any,
    expected: Any,
    passed: bool,
    threshold: Any | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> LeafJudgement:
    status = "passed" if passed else "failed"
    compact_observed = _compact_observed_value(observed)
    compact_expected = _compact_observed_value(expected)
    evidence_quote = (
        f"deterministic_{category_key}_{status}: metric={metric}; "
        f"observed={compact_observed!r}; expected={compact_expected!r}; "
        f"threshold={threshold!r}"
    )
    payload = {
        f"deterministic_{category_key}": True,
        "metric": metric,
        "observed": compact_observed,
        "expected": compact_expected,
        "threshold": threshold,
        **dict(metadata or {}),
    }
    return LeafJudgement(
        leaf_id=str(leaf["id"]),
        expectations=str(leaf.get("requirement", "")),
        reality=evidence_quote,
        evidence_quote=evidence_quote,
        score=1 if passed else 0,
        confidence=1.0,
        metadata=payload,
    )


async def _safe_execution_check(
    config: Mapping[str, Any],
    *,
    paper_id: str,
) -> dict[str, Any]:
    try:
        return await _evaluate_execution_check(config, paper_id=paper_id)
    except Exception as exc:
        return {
            "passed": False,
            "metric": str(config.get("metric", "unknown")),
            "observed": f"{type(exc).__name__}: {exc}",
            "expected": dict(config),
            "threshold": None,
            "metadata": {
                "deterministic_execution_check_error": True,
                "error_type": type(exc).__name__,
                "artifact": _sandbox_artifact_path(str(config.get("artifact", "")))
                if config.get("artifact")
                else None,
            },
        }


async def _evaluate_execution_check(
    config: Mapping[str, Any],
    *,
    paper_id: str,
) -> dict[str, Any]:
    metric = str(config.get("metric", "")).strip()
    if not metric:
        raise ValueError("Execution check requires a metric.")

    if metric in {"all_checks", "any_checks"}:
        checks = config.get("checks", [])
        if not isinstance(checks, list) or not checks:
            raise TypeError(f"{metric} requires a non-empty checks list.")
        results = [
            await _safe_execution_check(check, paper_id=paper_id)
            for check in checks
            if isinstance(check, Mapping)
        ]
        if len(results) != len(checks):
            raise TypeError(f"{metric} checks must all be objects.")
        passed = all(result["passed"] for result in results)
        if metric == "any_checks":
            passed = any(result["passed"] for result in results)
        return {
            "passed": passed,
            "metric": metric,
            "observed": [
                {
                    "metric": result["metric"],
                    "passed": result["passed"],
                    "observed": result["observed"],
                }
                for result in results
            ],
            "expected": f"{metric} over {len(results)} checks",
            "threshold": "all" if metric == "all_checks" else "any",
            "metadata": {
                "child_checks": results,
            },
        }

    artifact = str(config.get("artifact", "")).strip()
    if not artifact:
        raise ValueError(f"{metric} requires an artifact path.")
    text = await _read_sandbox_file(artifact)

    if metric in {"artifact_exists", "html_contains"}:
        min_bytes = int(config.get("min_bytes", 1))
        needles = config.get("contains", [])
        if isinstance(needles, str):
            needles = [needles]
        if not isinstance(needles, list):
            raise TypeError("contains must be a string or list of strings.")
        contains = {str(needle): str(needle) in text for needle in needles}
        observed = {"bytes": len(text.encode()), "contains": contains}
        passed = observed["bytes"] >= min_bytes and all(contains.values())
        return {
            "passed": passed,
            "metric": metric,
            "observed": observed,
            "expected": {"min_bytes": min_bytes, "contains": list(contains)},
            "threshold": min_bytes,
            "metadata": {"artifact": _sandbox_artifact_path(artifact)},
        }

    if metric == "json_paths_present":
        payload = json.loads(text)
        raw_paths = config.get("json_paths", [config.get("json_path", [])])
        if not isinstance(raw_paths, list) or not raw_paths:
            raise TypeError("json_paths_present requires json_paths or json_path.")
        paths = [list(path) for path in raw_paths]
        nonempty = bool(config.get("nonempty", True))
        observed: dict[str, Any] = {}
        missing: list[str] = []
        empty: list[str] = []
        for path in paths:
            key = _reference_path_key(path)
            try:
                value = _json_pointer(payload, path)
                observed[key] = _compact_observed_value(value)
                if nonempty and value in (None, "", [], {}):
                    empty.append(key)
            except Exception:
                missing.append(key)
        passed = not missing and not empty
        return {
            "passed": passed,
            "metric": metric,
            "observed": {"paths": observed, "missing": missing, "empty": empty},
            "expected": [_reference_path_key(path) for path in paths],
            "threshold": "present" if not nonempty else "present_nonempty",
            "metadata": {"artifact": _sandbox_artifact_path(artifact)},
        }

    if metric == "json_numeric_min":
        payload = json.loads(text)
        path = list(config.get("json_path", []))
        minimum = float(config.get("minimum", 0.0))
        observed = _coerce_float(_json_pointer(payload, path))
        return {
            "passed": observed >= minimum,
            "metric": metric,
            "observed": observed,
            "expected": {_reference_path_key(path): f">= {minimum}"},
            "threshold": minimum,
            "metadata": {
                "artifact": _sandbox_artifact_path(artifact),
                "json_path": path,
            },
        }

    if metric == "tsv_schema":
        fieldnames, rows = _tsv_table(text)
        required_columns = [str(column) for column in config.get("required_columns", [])]
        min_rows = int(config.get("min_rows", 1))
        missing_columns = [column for column in required_columns if column not in fieldnames]
        observed = {
            "rows": len(rows),
            "columns": fieldnames,
            "missing_columns": missing_columns,
        }
        passed = len(rows) >= min_rows and not missing_columns
        return {
            "passed": passed,
            "metric": metric,
            "observed": observed,
            "expected": {"min_rows": min_rows, "required_columns": required_columns},
            "threshold": min_rows,
            "metadata": {"artifact": _sandbox_artifact_path(artifact)},
        }

    raise ValueError(f"Unsupported deterministic execution metric: {metric}")


async def _deterministic_execution_judgement(
    leaf: Mapping[str, Any],
    *,
    paper_id: str,
) -> LeafJudgement | None:
    """Grade execution leaves by parsing declared artifacts before any LLM judge."""

    if str(leaf.get("category", "")) != "execution":
        return None

    reference = load_execution_reference(paper_id)
    if not reference:
        return None

    leaf_id = str(leaf["id"])
    strict = bool(reference.get("strict_execution", False))
    leaves = reference.get("leaves", {})
    if not isinstance(leaves, Mapping):
        raise ValueError("execution_reference.json field `leaves` must be an object.")

    config = leaves.get(leaf_id)
    if not config:
        if not strict:
            return None
        return _deterministic_category_zero(
            leaf,
            category_key="execution",
            reason=f"deterministic_execution_reference_missing: no artifact check for {leaf_id}",
            metadata={
                "deterministic_execution_reference_missing": True,
                "strict_execution": True,
            },
        )
    if not isinstance(config, Mapping):
        return _deterministic_category_zero(
            leaf,
            category_key="execution",
            reason=f"deterministic_execution_reference_invalid: check for {leaf_id} is not an object",
            metadata={"deterministic_execution_reference_invalid": True},
        )

    status = str(config.get("status", "ready")).strip().lower()
    if config.get("enabled") is False or status in {
        "pending",
        "pending_benchmark_author_fill_in",
        "todo",
        "disabled",
    }:
        return _deterministic_category_zero(
            leaf,
            category_key="execution",
            reason=f"deterministic_execution_reference_pending: check for {leaf_id} is {status}",
            metadata={
                "deterministic_execution_reference_missing": True,
                "reference_status": status,
            },
        )

    result = await _safe_execution_check(config, paper_id=paper_id)
    return _deterministic_category_passfail(
        leaf,
        category_key="execution",
        metric=str(result["metric"]),
        observed=result["observed"],
        expected=result["expected"],
        passed=bool(result["passed"]),
        threshold=result.get("threshold"),
        metadata=dict(result.get("metadata") or {}),
    )


def _normalize_pattern_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value]
    raise TypeError("Pattern fields must be strings or lists of strings.")


async def _read_source_candidates(
    candidates: Iterable[str],
) -> tuple[str, list[str], list[str], dict[str, str]]:
    chunks: list[str] = []
    read_paths: list[str] = []
    missing_paths: list[str] = []
    source_texts: dict[str, str] = {}
    for candidate in candidates:
        path = str(candidate)
        try:
            text = await _read_sandbox_file(path)
        except Exception:
            missing_paths.append(_sandbox_artifact_path(path))
            continue
        read_paths.append(_sandbox_artifact_path(path))
        source_texts[path] = text
        chunks.append(f"\n--- {path} ---\n{text}\n")
    return "\n".join(chunks), read_paths, missing_paths, source_texts


def _ast_call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _ast_call_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Call):
        return _ast_call_name(node.func)
    if isinstance(node, ast.Subscript):
        return _ast_call_name(node.value)
    return None


def _python_ast_calls(source_texts: Mapping[str, str]) -> tuple[set[str], dict[str, str]]:
    calls: set[str] = set()
    parse_errors: dict[str, str] = {}
    for path, source in source_texts.items():
        if not path.endswith(".py"):
            continue
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            parse_errors[path] = f"{exc.__class__.__name__}: {exc}"
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                call_name = _ast_call_name(node.func)
                if call_name:
                    calls.add(call_name)
    return calls, parse_errors


def _match_literals(source: str, literals: Iterable[str], *, case_insensitive: bool) -> list[str]:
    haystack = source.lower() if case_insensitive else source
    matches: list[str] = []
    for literal in literals:
        needle = literal.lower() if case_insensitive else literal
        if needle in haystack:
            matches.append(literal)
            continue
        flipped = _flip_quote_style(needle)
        if flipped is not None and flipped in haystack:
            matches.append(literal)
    return matches


def _flip_quote_style(text: str) -> str | None:
    """Return text with double-quotes swapped to single-quotes, or vice versa.

    Used by `_match_literals` so that source-pattern checks tolerate Python kwarg
    quoting differences such as ``coord_type="grid"`` versus
    ``coord_type='grid'``. Returns ``None`` when the input contains both quote
    characters or neither, so unrelated literals are not silently rewritten.
    """

    has_double = '"' in text
    has_single = "'" in text
    if has_double and not has_single:
        return text.replace('"', "'")
    if has_single and not has_double:
        return text.replace("'", '"')
    return None


def _match_regexes(source: str, patterns: Iterable[str], *, case_insensitive: bool) -> list[str]:
    flags = re.MULTILINE | (re.IGNORECASE if case_insensitive else 0)
    matches: list[str] = []
    for pattern in patterns:
        if re.search(pattern, source, flags):
            matches.append(pattern)
    return matches


async def _deterministic_code_development_judgement(
    leaf: Mapping[str, Any],
    *,
    paper_id: str,
) -> LeafJudgement | None:
    """Grade selected code-development leaves with declared source-pattern checks."""

    if str(leaf.get("category", "")) != "code_development":
        return None

    reference = load_code_development_reference(paper_id)
    if not reference:
        return None

    leaf_id = str(leaf["id"])
    strict = bool(reference.get("strict_code_development", False))
    leaves = reference.get("leaves", {})
    if not isinstance(leaves, Mapping):
        raise ValueError("code_development_reference.json field `leaves` must be an object.")

    config = leaves.get(leaf_id)
    if not config:
        if not strict:
            return None
        return _deterministic_category_zero(
            leaf,
            category_key="code_development",
            reason=f"deterministic_code_reference_missing: no source check for {leaf_id}",
            metadata={
                "deterministic_code_development_reference_missing": True,
                "strict_code_development": True,
            },
        )
    if not isinstance(config, Mapping):
        return _deterministic_category_zero(
            leaf,
            category_key="code_development",
            reason=f"deterministic_code_reference_invalid: check for {leaf_id} is not an object",
            metadata={"deterministic_code_development_reference_invalid": True},
        )

    metric = str(config.get("metric", "source_patterns")).strip()
    if metric != "source_patterns":
        return _deterministic_category_zero(
            leaf,
            category_key="code_development",
            reason=f"deterministic_code_metric_unsupported: {metric}",
            metadata={"deterministic_code_development_metric_unsupported": True},
        )

    default_sources = reference.get(
        "source_candidates",
        [
            "/workspace/submission/main_analysis.py",
            "/workspace/submission/squidpy_spatial_workflow.py",
            "/workspace/submission/run.sh",
        ],
    )
    source_candidates = config.get("source_candidates", default_sources)
    if not isinstance(source_candidates, list) or not source_candidates:
        raise TypeError("source_candidates must be a non-empty list.")

    source, read_paths, missing_paths, source_texts = await _read_source_candidates(
        str(path) for path in source_candidates
    )
    if not read_paths:
        return _deterministic_category_zero(
            leaf,
            category_key="code_development",
            reason=f"deterministic_code_source_missing: no configured source files were readable for {leaf_id}",
            metadata={
                "deterministic_code_development_source_missing": True,
                "source_candidates": [str(path) for path in source_candidates],
                "missing_sources": missing_paths,
            },
        )

    case_insensitive = bool(config.get("case_insensitive", False))
    all_literals = _normalize_pattern_list(config.get("all_literals"))
    any_literals = _normalize_pattern_list(config.get("any_literals"))
    forbidden_literals = _normalize_pattern_list(config.get("forbidden_literals"))
    all_regex = _normalize_pattern_list(config.get("all_regex"))
    any_regex = _normalize_pattern_list(config.get("any_regex"))
    forbidden_regex = _normalize_pattern_list(config.get("forbidden_regex"))
    all_ast_calls = _normalize_pattern_list(config.get("all_ast_calls"))
    any_ast_calls = _normalize_pattern_list(config.get("any_ast_calls"))
    forbidden_ast_calls = _normalize_pattern_list(config.get("forbidden_ast_calls"))

    ast_calls, ast_parse_errors = _python_ast_calls(source_texts)
    matched_all_literals = _match_literals(
        source,
        all_literals,
        case_insensitive=case_insensitive,
    )
    matched_any_literals = _match_literals(
        source,
        any_literals,
        case_insensitive=case_insensitive,
    )
    matched_forbidden_literals = _match_literals(
        source,
        forbidden_literals,
        case_insensitive=case_insensitive,
    )
    matched_all_regex = _match_regexes(source, all_regex, case_insensitive=case_insensitive)
    matched_any_regex = _match_regexes(source, any_regex, case_insensitive=case_insensitive)
    matched_forbidden_regex = _match_regexes(
        source,
        forbidden_regex,
        case_insensitive=case_insensitive,
    )
    matched_all_ast_calls = [name for name in all_ast_calls if name in ast_calls]
    matched_any_ast_calls = [name for name in any_ast_calls if name in ast_calls]
    matched_forbidden_ast_calls = [name for name in forbidden_ast_calls if name in ast_calls]

    missing_all_literals = [literal for literal in all_literals if literal not in matched_all_literals]
    missing_all_regex = [pattern for pattern in all_regex if pattern not in matched_all_regex]
    missing_all_ast_calls = [name for name in all_ast_calls if name not in matched_all_ast_calls]
    any_literal_pass = not any_literals or bool(matched_any_literals)
    any_regex_pass = not any_regex or bool(matched_any_regex)
    any_ast_pass = not any_ast_calls or bool(matched_any_ast_calls)
    forbidden_pass = (
        not matched_forbidden_literals
        and not matched_forbidden_regex
        and not matched_forbidden_ast_calls
    )
    passed = (
        not missing_all_literals
        and not missing_all_regex
        and not missing_all_ast_calls
        and any_literal_pass
        and any_regex_pass
        and any_ast_pass
        and forbidden_pass
    )

    observed = {
        "matched_all_literals": matched_all_literals,
        "missing_all_literals": missing_all_literals,
        "matched_any_literals": matched_any_literals,
        "matched_all_regex": matched_all_regex,
        "missing_all_regex": missing_all_regex,
        "matched_any_regex": matched_any_regex,
        "matched_all_ast_calls": matched_all_ast_calls,
        "missing_all_ast_calls": missing_all_ast_calls,
        "matched_any_ast_calls": matched_any_ast_calls,
        "matched_forbidden_ast_calls": matched_forbidden_ast_calls,
        "ast_parse_errors": ast_parse_errors,
        "matched_forbidden_literals": matched_forbidden_literals,
        "matched_forbidden_regex": matched_forbidden_regex,
        "source_char_count": len(source),
    }
    expected = {
        "all_literals": all_literals,
        "any_literals": any_literals,
        "all_regex": all_regex,
        "any_regex": any_regex,
        "all_ast_calls": all_ast_calls,
        "any_ast_calls": any_ast_calls,
        "forbidden_literals": forbidden_literals,
        "forbidden_regex": forbidden_regex,
        "forbidden_ast_calls": forbidden_ast_calls,
    }
    starter_assisted = _reference_starter_assisted_active(reference)
    return _deterministic_category_passfail(
        leaf,
        category_key="code_development",
        metric=metric,
        observed=observed,
        expected=expected,
        passed=passed,
        threshold="declared source-pattern contract",
        metadata={
            "source_candidates": [str(path) for path in source_candidates],
            "read_sources": read_paths,
            "missing_sources": missing_paths,
            "reference_starter_assisted": bool(reference.get("starter_assisted", False)),
            "starter_mode": _starter_mode_for_scoring(),
            "starter_assisted": starter_assisted,
            "starter_profile": reference.get("starter_profile") if starter_assisted else None,
            "matched_all_ast_calls": matched_all_ast_calls,
            "missing_all_ast_calls": missing_all_ast_calls,
            "matched_any_ast_calls": matched_any_ast_calls,
            "matched_forbidden_ast_calls": matched_forbidden_ast_calls,
        },
    )


async def _deterministic_leaf_judgement(
    leaf: Mapping[str, Any],
    *,
    paper_id: str,
) -> LeafJudgement | None:
    """Return the first configured deterministic judgement for a rubric leaf."""

    for scorer_fn in (
        _deterministic_result_match_judgement,
        _deterministic_execution_judgement,
        _deterministic_code_development_judgement,
    ):
        judgement = await scorer_fn(leaf, paper_id=paper_id)
        if judgement is not None:
            return judgement
    return None


async def _artifact_presence_precheck(
    submission_dir: str = _PRECHECK_SUBMISSION_DIR,
    output_dir: str = _PRECHECK_OUTPUT_DIR,
    file_cap: int = _PRECHECK_FILE_CAP,
    require_output_artifact: bool = False,
) -> dict[str, Any]:
    """Preflight scan of the sandbox to detect empty-scaffold submissions.

    Returns a dict with ``ok=True`` only when at least one saved workflow
    source under ``submission_dir`` contains non-trivial executable work.
    Python is checked with AST parsing; R, shell launchers, and notebooks
    have lightweight language-aware checks. Output artifact counts are
    recorded as forensic metadata but do not satisfy the source gate on
    their own. For result-match-ready paper tasks, callers may also require
    at least one non-document output artifact so no-output submissions fail
    before judge-mediated scoring.

    Fails open on sandbox exceptions: the agent should not be penalised
    for a Docker hiccup during scoring.
    """

    env = sandbox()
    try:
        source_res = await env.exec(
            [
                "bash",
                "-lc",
                (
                    f"find {submission_dir} -maxdepth 4 -type f "
                    "\\( -name '*.py' -o -iname '*.r' -o -name '*.sh' "
                    "-o -name '*.ipynb' \\) "
                    f"2>/dev/null | head -{file_cap}"
                ),
            ]
        )
        source_files = [p for p in (source_res.stdout or "").splitlines() if p.strip()]
    except Exception as exc:  # pragma: no cover - sandbox is a live dependency
        return {
            "ok": True,
            "reason": f"sandbox unreachable ({type(exc).__name__}: {exc})",
            "fallback": "allow",
            "nontrivial_py_files": 0,
            "nontrivial_py_examples": [],
            "nontrivial_source_files": 0,
            "nontrivial_source_examples": [],
            "output_artifact_count": 0,
            "output_artifact_examples": [],
            "requires_output_artifact": bool(require_output_artifact),
        }

    nontrivial_source = 0
    nontrivial_py = 0
    source_examples: list[str] = []
    py_examples: list[str] = []
    for path in source_files[:file_cap]:
        try:
            src = await env.read_file(path)
        except Exception:
            continue
        if _has_nontrivial_workflow_source(path, src):
            nontrivial_source += 1
            if len(source_examples) < 3:
                source_examples.append(path)
            if Path(path).suffix.lower() == ".py":
                nontrivial_py += 1
                if len(py_examples) < 3:
                    py_examples.append(path)

    try:
        out_res = await env.exec(
            [
                "bash",
                "-lc",
                (
                    f"find {output_dir} -maxdepth 4 -type f "
                    f"! -name 'README*' ! -iname '*.md' 2>/dev/null | head -{file_cap}"
                ),
            ]
        )
        output_files = [p for p in (out_res.stdout or "").splitlines() if p.strip()]
    except Exception:
        output_files = []

    if nontrivial_source <= 0:
        ok = False
        reason = (
            "no non-trivial saved workflow source (.py, .R, .sh, or .ipynb) was produced "
            f"under {submission_dir}"
        )
    elif require_output_artifact and not output_files:
        ok = False
        reason = (
            "no non-document output artifacts were produced under "
            f"{output_dir}; result-match-ready tasks must execute the saved workflow"
        )
    else:
        ok = True
        reason = None
    return {
        "ok": ok,
        "reason": reason,
        "nontrivial_py_files": nontrivial_py,
        "nontrivial_py_examples": py_examples,
        "nontrivial_source_files": nontrivial_source,
        "nontrivial_source_examples": source_examples,
        "output_artifact_count": len(output_files),
        "output_artifact_examples": output_files[:3],
        "requires_output_artifact": bool(require_output_artifact),
    }


def _iter_reality_sources(reality_context: str) -> list[EvidenceSource]:
    """Split scorer reality context into file-list and file-content sources."""

    sources: list[EvidenceSource] = []
    matches = list(_REALITY_SECTION_HEADER_RE.finditer(reality_context))
    file_list_block = reality_context[: matches[0].start()] if matches else reality_context
    prefix = "Submission file list:\n"
    if file_list_block.startswith(prefix):
        for line in file_list_block[len(prefix) :].splitlines():
            path = line.strip()
            if path:
                sources.append(
                    EvidenceSource(
                        source_type="file_list",
                        path=path,
                        matched_text=path,
                    )
                )

    for index, match in enumerate(matches):
        path = match.group("path").strip()
        start = match.end()
        if start < len(reality_context) and reality_context[start] == "\n":
            start += 1
        end = matches[index + 1].start() - 1 if index + 1 < len(matches) else len(reality_context)
        text = reality_context[start:end].rstrip()
        sources.append(
            EvidenceSource(
                source_type="file_content",
                path=path,
                matched_text=text,
            )
        )

    return sources


def _format_file_content_sources(sources: Iterable[EvidenceSource], *, fallback: str) -> str:
    chunks = [
        f"--- {source.path} ---\n{source.matched_text}"
        for source in sources
        if source.source_type == "file_content" and source.path
    ]
    return "\n\n".join(chunks) if chunks else fallback


def _reality_context_for_leaf(leaf: Mapping[str, Any], reality_context: str) -> str:
    """Filter scorer context to the evidence sources eligible for one leaf category."""

    category = str(leaf.get("category", "unknown"))
    content_sources = [
        source
        for source in _iter_reality_sources(reality_context)
        if source.source_type == "file_content" and source.path
    ]

    if category == "code_development":
        eligible = [
            source
            for source in content_sources
            if str(source.path).startswith(_SUBMISSION_PREFIX)
            and not _skip_reality_file_contents(str(source.path))
        ]
        return _format_file_content_sources(
            eligible,
            fallback=f"(no eligible {_PRECHECK_SUBMISSION_DIR} implementation evidence was captured)",
        )

    if category in {"execution", "result_match"}:
        eligible = [
            source
            for source in content_sources
            if str(source.path).startswith(_OUTPUT_PREFIX)
            and not _skip_reality_file_contents(str(source.path))
        ]
        return _format_file_content_sources(
            eligible,
            fallback=f"(no eligible {_PRECHECK_OUTPUT_DIR} artifact evidence was captured)",
        )

    return reality_context


def _quote_variants(evidence_quote: str) -> list[str]:
    quote = evidence_quote.strip()
    if not quote:
        return []
    variants = [quote]
    if len(quote) >= 2 and quote[0] == quote[-1] and quote[0] in {'"', "'", "`"}:
        variants.append(quote[1:-1].strip())
    return [variant for index, variant in enumerate(variants) if variant and variant not in variants[:index]]


def _strip_leading_line_whitespace(text: str) -> str:
    return "\n".join(line.lstrip() for line in text.strip().splitlines())


def _strip_all_whitespace(text: str) -> str:
    compact = re.sub(r"\s+", "", text)
    return re.sub(r",([)\]}])", r"\1", compact)


def _source_contains_quote(source: EvidenceSource, candidate: str) -> bool:
    """Return whether candidate is a defensible quote from one reality source.

    Judges sometimes include the `--- path ---` content-block header in an
    otherwise exact quote, or drop leading indentation from Python snippets.
    Accept those narrow forms while still rejecting bare header/path evidence.
    """

    if candidate in source.matched_text:
        return True

    header = f"--- {source.path} ---" if source.source_type == "file_content" and source.path else ""
    if header and candidate.startswith(header):
        body_candidate = candidate[len(header) :].lstrip("\n")
        if not body_candidate.strip():
            return False
        if body_candidate in source.matched_text:
            return True
        if _strip_leading_line_whitespace(body_candidate) in _strip_leading_line_whitespace(
            source.matched_text
        ):
            return True

    if "\n" in candidate and _strip_leading_line_whitespace(candidate) in _strip_leading_line_whitespace(
        source.matched_text
    ):
        return True

    if (
        source.source_type == "file_content"
        and source.path
        and str(source.path).startswith(_SUBMISSION_PREFIX)
        and len(candidate) >= 40
    ):
        return _strip_all_whitespace(candidate) in _strip_all_whitespace(source.matched_text)

    return False


def _matching_evidence_sources(
    reality_context: str, evidence_quote: str
) -> list[EvidenceSource]:
    """Locate all reality-context sources that contain the quoted evidence verbatim."""

    matches: list[EvidenceSource] = []
    seen: set[tuple[str, str | None, str]] = set()
    for source in _iter_reality_sources(reality_context):
        for candidate in _quote_variants(evidence_quote):
            if _source_contains_quote(source, candidate):
                key = (source.source_type, source.path, candidate)
                if key not in seen:
                    matches.append(
                        EvidenceSource(
                            source_type=source.source_type,
                            path=source.path,
                            matched_text=candidate,
                        )
                    )
                    seen.add(key)
    return matches


def _is_markdown_like(path: str | None) -> bool:
    if not path:
        return False
    return Path(path).suffix.lower() in _MARKDOWN_EXTENSIONS


def _is_readme_like(path: str | None) -> bool:
    if not path:
        return False
    return Path(path).name.lower().startswith("readme")


def _skip_reality_file_contents(path: str) -> bool:
    """Keep scorer reality focused on executable code and measured artifacts."""

    normalized = path.rstrip("/")
    return (
        _is_readme_like(normalized)
        or _is_markdown_like(normalized)
        or normalized == _SUBMISSION_MANIFEST_PATH
    )


def _is_submission_python_source(path: str) -> bool:
    return path.startswith(_SUBMISSION_PREFIX) and Path(path).suffix.lower() == ".py"


def _focused_source_excerpt(contents: str, *, max_chars: int) -> str:
    """Return actual source lines sampled across implementation-relevant regions."""

    if len(contents) <= max_chars:
        return contents

    lines = contents.splitlines()
    if not lines:
        return contents[:max_chars]

    selected_ranges: list[tuple[int, int]] = []

    def add_range(start: int, end: int) -> None:
        bounded_start = max(0, start)
        bounded_end = min(len(lines), end)
        if bounded_start < bounded_end:
            selected_ranges.append((bounded_start, bounded_end))

    prologue_lines = 90 if max_chars >= 5000 else 24
    tail_lines = 90 if max_chars >= 5000 else 24

    add_range(0, prologue_lines)

    lowered_lines = [line.lower() for line in lines]
    for pattern in _SOURCE_FOCUS_PATTERNS:
        lowered_pattern = pattern.lower()
        for line_index, line in enumerate(lowered_lines):
            if lowered_pattern in line:
                add_range(line_index - 4, line_index + 16)
                break

    add_range(len(lines) - tail_lines, len(lines))

    used_lines: set[int] = set()
    chunks: list[str] = []
    total = 0
    last_line: int | None = None
    for start, end in selected_ranges:
        indices = [index for index in range(start, end) if index not in used_lines]
        if not indices:
            continue

        needs_gap = last_line is not None and indices[0] > last_line + 1
        pieces: list[str] = []
        if needs_gap:
            pieces.append("[...source excerpt gap...]")
        pieces.extend(lines[index] for index in indices)
        chunk = "\n".join(pieces)
        addition = ("\n" if chunks else "") + chunk
        if total + len(addition) > max_chars:
            remaining = max_chars - total
            if remaining > 0:
                chunks.append(addition[:remaining].rstrip())
            break

        chunks.append(addition)
        total += len(addition)
        used_lines.update(indices)
        last_line = max(indices)

    excerpt = "".join(chunks).strip()
    if not excerpt:
        return contents[:max_chars]
    marker = "\n[truncated to focused source excerpts]"
    if len(excerpt) + len(marker) <= max_chars:
        return excerpt + marker
    if max_chars > len(marker):
        return excerpt[: max_chars - len(marker)].rstrip() + marker
    return excerpt[:max_chars]


def _looks_like_path_text(text: str) -> bool:
    stripped = text.strip().strip('"').strip("'").strip("`")
    if not stripped or any(ch.isspace() for ch in stripped):
        return False
    if stripped.startswith(f"{_WORKSPACE_ROOT}/"):
        return True
    return "/" in stripped and "." in Path(stripped).name


def _looks_like_benchmark_comparator_metric(text: str) -> bool:
    stripped = text.strip().strip('"').strip("'").strip("`").lower()
    if not stripped:
        return False
    comparator_patterns = (
        r"(?:^|[_\W])rbo(?:$|[_\W])",
        r"(?:^|[_\W])overlap(?:$|[_\W])",
        r"(?:^|[_\W])ari(?:$|[_\W])",
        r"(?:^|[_\W])pearson(?:$|[_\W])",
        r"(?:^|[_\W])spearman(?:$|[_\W])",
        r"(?:^|[_\W])correlation(?:$|[_\W])",
    )
    return any(re.search(pattern, stripped) for pattern in comparator_patterns)


def _is_valid_execution_evidence_source(match: EvidenceSource) -> bool:
    return (
        match.source_type == "file_content"
        and bool(match.path)
        and str(match.path).startswith(_OUTPUT_PREFIX)
        and not _is_readme_like(match.path)
        and not _looks_like_path_text(match.matched_text)
        and not _looks_like_benchmark_comparator_metric(match.matched_text)
    )


def _allowed_evidence_for_leaf(
    leaf: Mapping[str, Any],
    matches: list[EvidenceSource],
) -> bool:
    category = str(leaf.get("category", "unknown"))

    if matches and all(_is_readme_like(match.path) for match in matches if match.path):
        return False

    if category == "code_development":
        return any(
            match.source_type == "file_content"
            and bool(match.path)
            and str(match.path).startswith(_SUBMISSION_PREFIX)
            and not _is_markdown_like(match.path)
            for match in matches
        )

    if category == "execution":
        return any(_is_valid_execution_evidence_source(match) for match in matches)

    if category == "result_match":
        return any(
            match.source_type == "file_content"
            and bool(match.path)
            and str(match.path).startswith(_OUTPUT_PREFIX)
            and not _is_readme_like(match.path)
            for match in matches
        )

    return bool(matches)


def _evidence_policy_failure_reason(
    leaf: Mapping[str, Any],
    matches: list[EvidenceSource],
) -> str:
    category = str(leaf.get("category", "unknown"))
    if not matches:
        return "evidence_quote was not found verbatim in scorer reality context"
    if matches and all(_is_readme_like(match.path) for match in matches if match.path):
        return "README-style prose is not valid passing evidence"
    if category == "code_development":
        return (
            "code_development leaves require non-markdown submission-file content, "
            "not planning prose or README text"
        )
    if category == "execution":
        output_path_matches = [
            match
            for match in matches
            if match.path
            and str(match.path).startswith(_OUTPUT_PREFIX)
            and not _is_readme_like(match.path)
        ]
        if output_path_matches and not any(
            _is_valid_execution_evidence_source(match) for match in output_path_matches
        ):
            return (
                "execution leaves require concrete written outputs or runtime text, "
                "not bare output-file paths or hidden-reference comparison metrics"
            )
        return (
            "execution leaves require a non-README output artifact or output-derived "
            "evidence, not submission-side planning prose"
        )
    if category == "result_match":
        return (
            "result_match leaves require non-README output-file content, not "
            "submission-side claims or code comments"
        )
    return "evidence source did not satisfy leaf policy"


def _enforce_leaf_evidence_policy(
    leaf: Mapping[str, Any],
    judgement: LeafJudgement,
    *,
    reality_context: str,
) -> LeafJudgement:
    """Zero unsupported passing judgements whose evidence lacks valid provenance."""

    if judgement.score != 1:
        return judgement

    matches = _matching_evidence_sources(reality_context, judgement.evidence_quote)
    if _allowed_evidence_for_leaf(leaf, matches):
        metadata = dict(judgement.metadata)
        metadata["evidence_sources"] = [match.to_dict() for match in matches]
        return LeafJudgement(
            leaf_id=judgement.leaf_id,
            expectations=judgement.expectations,
            reality=judgement.reality,
            evidence_quote=judgement.evidence_quote,
            score=judgement.score,
            confidence=judgement.confidence,
            metadata=metadata,
        )

    reason = _evidence_policy_failure_reason(leaf, matches)
    metadata = dict(judgement.metadata)
    metadata.update(
        {
            "evidence_policy_failure": reason,
            "original_score": judgement.score,
            "original_evidence_quote": judgement.evidence_quote,
            "evidence_sources": [match.to_dict() for match in matches],
        }
    )
    return LeafJudgement(
        leaf_id=judgement.leaf_id,
        expectations=judgement.expectations,
        reality=judgement.reality,
        evidence_quote=f"evidence_policy_failed: {reason}",
        score=0,
        confidence=judgement.confidence,
        metadata=metadata,
    )


async def _collect_submission_context(
    max_chars: int = _JUDGE_MAX_SUBMISSION_CHARS,
    per_file_chars: int = _JUDGE_MAX_SUBMISSION_FILE_CHARS,
) -> str:
    """Read a compact summary of the agent's submission artifacts from the sandbox."""

    env = sandbox()
    priority_paths = " ".join(f"'{path}'" for path in _SUBMISSION_CONTEXT_PRIORITY_PATHS)
    chunks: list[str] = []
    try:
        listing = await env.exec(
            [
                "bash",
                "-lc",
                (
                    "( for path in "
                    + priority_paths
                    + "; do [ -f \"$path\" ] && printf '%s\\n' \"$path\"; done; "
                    f"find {_PRECHECK_OUTPUT_DIR} -maxdepth 4 -type f "
                    "! -iname 'README*' ! -iname '*.md' ! -iname '*.markdown' "
                    "! -iname '*.rst' 2>/dev/null; "
                    f"find {_PRECHECK_SUBMISSION_DIR} -maxdepth 4 -type f "
                    "! -iname 'README*' ! -iname '*.md' ! -iname '*.markdown' "
                    "! -iname '*.rst' 2>/dev/null; "
                    f"find {_PRECHECK_OUTPUT_DIR} -maxdepth 4 -type f "
                    "\\( -iname 'README*' -o -iname '*.md' -o -iname '*.markdown' "
                    "-o -iname '*.rst' \\) 2>/dev/null; "
                    f"find {_PRECHECK_SUBMISSION_DIR} -maxdepth 4 -type f "
                    "\\( -iname 'README*' -o -iname '*.md' -o -iname '*.markdown' "
                    "-o -iname '*.rst' \\) 2>/dev/null; "
                    ") | awk '!seen[$0]++' | head -40"
                ),
            ]
        )
        file_list = (listing.stdout or "").strip()
    except Exception as exc:  # pragma: no cover - sandbox is a live dependency
        return f"(sandbox unreachable during scoring: {exc})"

    if not file_list:
        return (
            f"(no submission artifacts were produced in {_PRECHECK_SUBMISSION_DIR} "
            f"or {_PRECHECK_OUTPUT_DIR})"
        )

    chunks.append("Submission file list:\n" + file_list)
    total = len(chunks[0])

    for path in file_list.splitlines():
        path = path.strip()
        if not path:
            continue
        if _skip_reality_file_contents(path):
            continue
        header = f"\n--- {path} ---\n"
        available = max_chars - total - len(header)
        if available <= 0:
            break
        try:
            contents = await env.read_file(path)
        except Exception:
            continue
        if _is_submission_python_source(path):
            snippet_limit = min(available, max(_JUDGE_MAX_SOURCE_FILE_CHARS, per_file_chars, 1))
            snippet = _focused_source_excerpt(contents, max_chars=snippet_limit)
        else:
            snippet_limit = min(available, max(per_file_chars, 1))
            snippet = contents[:snippet_limit]
        if not snippet:
            continue
        if len(contents) > len(snippet):
            marker = "\n[truncated]"
            remaining = available - len(snippet)
            if remaining > 0:
                snippet += marker[:remaining]
        chunks.append(header + snippet)
        total += len(header) + len(snippet)

    return "\n".join(chunks)


def _resolve_paper_id(state: Any) -> str:
    metadata = getattr(state, "metadata", None) or {}
    paper_id = metadata.get("paper_id")
    if paper_id:
        return str(paper_id)
    sample_id = getattr(state, "sample_id", None) or ""
    if isinstance(sample_id, str) and sample_id.endswith("_main"):
        return sample_id[: -len("_main")]
    raise ValueError(
        "Could not resolve paper_id from sample state; expected metadata.paper_id or '<paper>_main' sample id."
    )


async def _judge_leaf(
    judge: Any,
    leaf: dict[str, Any],
    *,
    paper_summary: str,
    reality_context: str,
) -> LeafJudgement:
    base_prompt = format_leaf_judge_prompt(
        leaf,
        paper_summary=paper_summary,
        reality_context=reality_context,
    )
    prompt = base_prompt
    attempts = 0
    last_exc: Exception | None = None
    for _ in range(_JUDGE_PARSE_RETRIES + 1):
        attempts += 1
        try:
            result = await judge.generate(prompt)
            raw = getattr(result, "completion", None) or str(result)
            judgement = parse_leaf_judgement(raw, expected_leaf_id=leaf["id"])
            if judgement.metadata.get("empty_evidence_quote_repaired"):
                raise ValueError("Judge response had an empty evidence_quote.")
            if attempts > 1:
                metadata = dict(judgement.metadata)
                metadata["judge_attempts"] = attempts
                judgement = LeafJudgement(
                    leaf_id=judgement.leaf_id,
                    expectations=judgement.expectations,
                    reality=judgement.reality,
                    evidence_quote=judgement.evidence_quote,
                    score=judgement.score,
                    confidence=judgement.confidence,
                    metadata=metadata,
                )
            return judgement
        except Exception as exc:  # capture judge/model failures as leaf-level 0
            last_exc = exc
            prompt = (
                f"{base_prompt}\n\n"
                f"Previous judge response was invalid: {type(exc).__name__}: {exc}\n"
                "Return only one valid JSON object with a non-empty evidence_quote "
                "copied verbatim from Observed reality. Do not include markdown "
                "fences or commentary."
            )

    return LeafJudgement(
        leaf_id=str(leaf["id"]),
        expectations="",
        reality="",
        evidence_quote=f"judge_error: {type(last_exc).__name__}: {last_exc}",
        score=0,
        metadata={"judge_failure": True, "judge_attempts": attempts},
    )


if _HAS_INSPECT_SCORING:

    @scorer(metrics=[mean(), stderr()])
    def rubric_tree_scorer(
        judge_model: str = _JUDGE_DEFAULT_MODEL,
        *,
        leaf_limit: int | None = None,
    ):
        """Grade each rubric leaf with an LLM judge and aggregate to a weighted score.

        Each leaf is graded independently using the structured judge prompt
        (Expectations → Reality → Evidence Quote → Score). Leaf scores flow
        bottom-up through the rubric tree's existing weighted aggregation.

        Args:
          judge_model: Inspect-style model identifier for the judge.
          leaf_limit: Optional cap on leaves graded per sample. When provided,
            the remaining leaves are scored 0 with an informational evidence
            quote. Mainly useful for cheap smoke runs.
        """

        import os

        async def score(state: "TaskState", target: "Target"):  # type: ignore[name-defined]
            paper_id = _resolve_paper_id(state)
            rubric = load_rubric_payload(paper_id)
            paper_summary = load_paper_summary(paper_id)
            reality = await _collect_submission_context()

            tree = extract_rubric_tree(rubric)
            leaves = collect_leaf_nodes(tree)

            env_cap = os.getenv(_JUDGE_LEAF_LIMIT_ENV)
            cap = leaf_limit if leaf_limit is not None else (int(env_cap) if env_cap else None)

            precheck = await _artifact_presence_precheck(
                require_output_artifact=_result_match_requires_output_artifact(paper_id)
            )
            if not precheck["ok"]:
                # Scaffold-over-substance guard: no non-trivial saved workflow source was
                # produced under the configured submission root.
                # Zero the rubric without billing a single judge call.
                judgements: list[LeafJudgement] = [
                    LeafJudgement(
                        leaf_id=str(leaf["id"]),
                        expectations="",
                        reality="",
                        evidence_quote=f"precheck_failed: {precheck['reason']}",
                        score=0,
                        metadata={
                            "precheck_failed": True,
                            "nontrivial_py_files": precheck.get("nontrivial_py_files", 0),
                            "nontrivial_source_files": precheck.get(
                                "nontrivial_source_files",
                                precheck.get("nontrivial_py_files", 0),
                            ),
                            "output_artifact_count": precheck["output_artifact_count"],
                        },
                    )
                    for leaf in leaves
                ]
            else:
                judge = get_model(judge_model)
                judgements = []
                for index, leaf in enumerate(leaves):
                    if cap is not None and index >= cap:
                        judgements.append(
                            LeafJudgement(
                                leaf_id=str(leaf["id"]),
                                expectations="",
                                reality="",
                                evidence_quote=f"skipped by leaf_limit={cap}",
                                score=0,
                                metadata={"skipped": True},
                            )
                        )
                        continue
                    deterministic_judgement = await _deterministic_leaf_judgement(
                        leaf,
                        paper_id=paper_id,
                    )
                    if deterministic_judgement is not None:
                        judgements.append(deterministic_judgement)
                        continue
                    leaf_reality = _reality_context_for_leaf(leaf, reality)
                    judgements.append(
                        _enforce_leaf_evidence_policy(
                            leaf,
                            await _judge_leaf(
                                judge,
                                leaf,
                                paper_summary=paper_summary,
                                reality_context=leaf_reality,
                            ),
                            reality_context=reality,
                        )
                    )

            leaf_map = leaf_score_map_from_judgements(judgements)
            report = score_rubric_payload(rubric, leaf_map)
            base_score = to_inspect_score(report)

            metadata = dict(base_score.metadata or {})
            metadata.update(
                {
                    "paper_id": paper_id,
                    "judge_model": judge_model,
                    "leaf_limit": cap,
                    "leaves_graded": sum(
                        1
                        for j in judgements
                        if not j.metadata.get("skipped")
                        and not j.metadata.get("precheck_failed")
                    ),
                    "leaves_total": len(leaves),
                    "judge_failures": sum(
                        1 for j in judgements if j.metadata.get("judge_failure")
                    ),
                    "deterministic_result_match_leaves": sum(
                        1
                        for j in judgements
                        if j.metadata.get("deterministic_result_match")
                    ),
                    "deterministic_execution_leaves": sum(
                        1 for j in judgements if j.metadata.get("deterministic_execution")
                    ),
                    "deterministic_code_development_leaves": sum(
                        1
                        for j in judgements
                        if j.metadata.get("deterministic_code_development")
                    ),
                    "deterministic_reference_missing": sum(
                        1
                        for j in judgements
                        if j.metadata.get("deterministic_reference_missing")
                    ),
                    "deterministic_execution_reference_missing": sum(
                        1
                        for j in judgements
                        if j.metadata.get("deterministic_execution_reference_missing")
                    ),
                    "deterministic_code_development_reference_missing": sum(
                        1
                        for j in judgements
                        if j.metadata.get(
                            "deterministic_code_development_reference_missing"
                        )
                    ),
                    "precheck": precheck,
                    "leaf_judgements": [j.to_dict() for j in judgements],
                }
            )
            metadata.update(_score_interpretation_metadata(base_score.value, judgements))
            return InspectScore(
                value=base_score.value,
                explanation=_score_explanation_with_lane(
                    base_score.explanation, metadata
                ),
                metadata=metadata,
            )

        return score

else:  # pragma: no cover - pure-library fallback so imports succeed outside Inspect

    def rubric_tree_scorer(*args: Any, **kwargs: Any):  # type: ignore[no-redef]
        raise RuntimeError(
            "inspect-ai is not installed; rubric_tree_scorer requires the Inspect AI runtime."
        )


__all__ = [
    "InspectScore",
    "NodeScoreReport",
    "RubricScoreReport",
    "_artifact_presence_precheck",
    "_deterministic_code_development_judgement",
    "_deterministic_execution_judgement",
    "_deterministic_leaf_judgement",
    "_deterministic_result_match_judgement",
    "_has_nontrivial_body",
    "_has_nontrivial_workflow_source",
    "leaf_score_map_from_judgements",
    "load_code_development_reference",
    "load_execution_reference",
    "load_paper_summary",
    "load_result_match_reference",
    "load_rubric_payload",
    "rubric_tree_scorer",
    "score_rubric_payload",
    "summarize_score_report",
    "to_inspect_score",
]
