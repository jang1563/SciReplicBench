"""Rubric-tree scoring helpers."""

from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

from .judge import LeafJudgement, format_leaf_judge_prompt, parse_leaf_judgement
from .rubric_utils import collect_leaf_ids, collect_leaf_nodes, extract_rubric_tree, validate_rubric_payload

PROJECT_ROOT = Path(__file__).resolve().parents[2]
_JUDGE_MAX_SUBMISSION_CHARS = 36000
_JUDGE_MAX_SUBMISSION_FILE_CHARS = 2600
_JUDGE_MAX_SOURCE_FILE_CHARS = 18000
_JUDGE_MAX_PAPER_CHARS = 3000
_JUDGE_DEFAULT_MODEL = "openai/gpt-4o-mini"
_JUDGE_LEAF_LIMIT_ENV = "SCIREPLICBENCH_JUDGE_LEAF_LIMIT"
_JUDGE_PARSE_RETRIES = 2
_PRECHECK_SUBMISSION_DIR = "/workspace/submission"
_PRECHECK_OUTPUT_DIR = "/workspace/output"
_PRECHECK_FILE_CAP = 20
_REALITY_SECTION_HEADER_RE = re.compile(r"^--- (?P<path>.+?) ---$", re.MULTILINE)
_MARKDOWN_EXTENSIONS = {".md", ".markdown", ".rst"}
_SUBMISSION_CONTEXT_PRIORITY_PATHS = (
    "/workspace/output/agent/lomo/summary.tsv",
    "/workspace/output/agent/lomo/split_manifest.tsv",
    "/workspace/output/agent/lomo/preprocessed_features.tsv",
    "/workspace/output/agent/transfer/cross_tissue.tsv",
    "/workspace/output/agent/negative_controls/summary.tsv",
    "/workspace/output/agent/interpretability/top_features.tsv",
    "/workspace/output/agent/go_nogo/summary.tsv",
    "/workspace/output/agent/foundation/geneformer_staging.tsv",
    "/workspace/output/submission_manifest.json",
    "/workspace/submission/main_analysis.py",
    "/workspace/submission/genelab_scaffold.py",
    "/workspace/submission/run.sh",
    "/workspace/submission/README.md",
)
_GENELAB_CONTEXT_ANCHOR_PATHS = (
    "/workspace/output/agent/lomo/summary.tsv",
    "/workspace/output/submission_manifest.json",
    "/workspace/submission/main_analysis.py",
)
_GENELAB_CANONICAL_SOURCE_PATHS = {
    "/workspace/submission/main_analysis.py",
    "/workspace/submission/genelab_scaffold.py",
}
_GENELAB_UNHOOKED_SIDECAR_NAMES = {
    "run_benchmark.py",
    "evaluate_models.py",
    "model_analysis.py",
    "model_evaluation.py",
    "evaluate_lomo.py",
    "evaluation_helpers.py",
    "gene_lab_helpers.py",
}
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


try:  # pragma: no cover - optional Inspect-only integration
    from inspect_ai.model import get_model
    from inspect_ai.scorer import Target, mean, scorer, stderr
    from inspect_ai.solver import TaskState
    from inspect_ai.util import sandbox

    _HAS_INSPECT_SCORING = True
except ModuleNotFoundError:  # pragma: no cover - local fallback
    _HAS_INSPECT_SCORING = False


async def _artifact_presence_precheck(
    submission_dir: str = _PRECHECK_SUBMISSION_DIR,
    output_dir: str = _PRECHECK_OUTPUT_DIR,
    file_cap: int = _PRECHECK_FILE_CAP,
) -> dict[str, Any]:
    """Preflight scan of the sandbox to detect empty-scaffold submissions.

    Returns a dict with ``ok=True`` only when at least one Python file
    under ``submission_dir`` contains a non-trivial function body or
    module-level statement. Output artifact counts are recorded as
    forensic metadata but do not satisfy the gate on their own -- an
    agent that only downloaded data or produced READMEs has not done
    anything a grader would call "replication."

    Fails open on sandbox exceptions: the agent should not be penalised
    for a Docker hiccup during scoring.
    """

    env = sandbox()
    try:
        py_res = await env.exec(
            [
                "bash",
                "-lc",
                (
                    f"find {submission_dir} -maxdepth 4 -type f -name '*.py' "
                    f"2>/dev/null | head -{file_cap}"
                ),
            ]
        )
        py_files = [p for p in (py_res.stdout or "").splitlines() if p.strip()]
    except Exception as exc:  # pragma: no cover - sandbox is a live dependency
        return {
            "ok": True,
            "reason": f"sandbox unreachable ({type(exc).__name__}: {exc})",
            "fallback": "allow",
            "nontrivial_py_files": 0,
            "nontrivial_py_examples": [],
            "output_artifact_count": 0,
            "output_artifact_examples": [],
        }

    nontrivial = 0
    examples: list[str] = []
    for path in py_files[:file_cap]:
        try:
            src = await env.read_file(path)
        except Exception:
            continue
        if _has_nontrivial_body(src):
            nontrivial += 1
            if len(examples) < 3:
                examples.append(path)

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

    ok = nontrivial > 0
    reason = (
        None
        if ok
        else (
            "no Python file with a non-trivial function or module body was produced "
            f"under {submission_dir}"
        )
    )
    return {
        "ok": ok,
        "reason": reason,
        "nontrivial_py_files": nontrivial,
        "nontrivial_py_examples": examples,
        "output_artifact_count": len(output_files),
        "output_artifact_examples": output_files[:3],
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
            if str(source.path).startswith("/workspace/submission/")
            and not _skip_reality_file_contents(str(source.path))
        ]
        return _format_file_content_sources(
            eligible,
            fallback="(no eligible /workspace/submission implementation evidence was captured)",
        )

    if category in {"execution", "result_match"}:
        eligible = [
            source
            for source in content_sources
            if str(source.path).startswith("/workspace/output/")
            and not _skip_reality_file_contents(str(source.path))
        ]
        return _format_file_content_sources(
            eligible,
            fallback="(no eligible /workspace/output artifact evidence was captured)",
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


def _strip_trailing_quote_punctuation(text: str) -> str:
    return "\n".join(line.rstrip().rstrip(";") for line in text.strip().splitlines())


def _normalize_inline_whitespace(text: str) -> str:
    return "\n".join(" ".join(line.split()) for line in text.strip().splitlines())


def _source_contains_quote(source: EvidenceSource, candidate: str) -> bool:
    """Return whether candidate is a defensible quote from one reality source.

    Judges sometimes include the `--- path ---` content-block header in an
    otherwise exact quote, drop leading indentation from Python snippets, or
    normalize TSV spacing. Accept those narrow forms while still rejecting bare
    header/path evidence.
    """

    if candidate in source.matched_text:
        return True

    if _normalize_inline_whitespace(candidate) in _normalize_inline_whitespace(
        source.matched_text
    ):
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
        and str(source.path).startswith("/workspace/submission/")
        and len(candidate) >= 40
    ):
        normalized_candidate = _strip_trailing_quote_punctuation(candidate)
        normalized_source = _strip_trailing_quote_punctuation(source.matched_text)
        return _strip_all_whitespace(normalized_candidate) in _strip_all_whitespace(
            normalized_source
        )

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
        or normalized == "/workspace/output/submission_manifest.json"
    )


def _is_submission_python_source(path: str) -> bool:
    return path.startswith("/workspace/submission/") and Path(path).suffix.lower() == ".py"


def _skip_unhooked_genelab_sidecar_contents(path: str, file_paths: set[str]) -> bool:
    if path in _GENELAB_CANONICAL_SOURCE_PATHS:
        return False
    if not _is_submission_python_source(path):
        return False
    if Path(path).name not in _GENELAB_UNHOOKED_SIDECAR_NAMES:
        return False
    return all(anchor in file_paths for anchor in _GENELAB_CONTEXT_ANCHOR_PATHS)


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
    if stripped.startswith("/workspace/"):
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
        and str(match.path).startswith("/workspace/output/")
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
            and str(match.path).startswith("/workspace/submission/")
            and not _is_markdown_like(match.path)
            for match in matches
        )

    if category == "execution":
        return any(_is_valid_execution_evidence_source(match) for match in matches)

    if category == "result_match":
        return any(
            match.source_type == "file_content"
            and bool(match.path)
            and str(match.path).startswith("/workspace/output/")
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
            and str(match.path).startswith("/workspace/output/")
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
                    "find /workspace/output -maxdepth 4 -type f "
                    "! -iname 'README*' ! -iname '*.md' ! -iname '*.markdown' "
                    "! -iname '*.rst' 2>/dev/null; "
                    "find /workspace/submission -maxdepth 4 -type f "
                    "! -iname 'README*' ! -iname '*.md' ! -iname '*.markdown' "
                    "! -iname '*.rst' 2>/dev/null; "
                    "find /workspace/output -maxdepth 4 -type f "
                    "\\( -iname 'README*' -o -iname '*.md' -o -iname '*.markdown' "
                    "-o -iname '*.rst' \\) 2>/dev/null; "
                    "find /workspace/submission -maxdepth 4 -type f "
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
        return "(no submission artifacts were produced in /workspace/submission or /workspace/output)"

    file_paths = {path.strip() for path in file_list.splitlines() if path.strip()}
    chunks.append("Submission file list:\n" + file_list)
    total = len(chunks[0])

    for path in file_list.splitlines():
        path = path.strip()
        if not path:
            continue
        if _skip_unhooked_genelab_sidecar_contents(path, file_paths):
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
                "Return only one valid JSON object. For score 1, evidence_quote must "
                "be copied verbatim from Observed reality. For score 0, use a "
                "verbatim supporting quote when possible, or set evidence_quote to "
                "exactly no_valid_evidence when no valid supporting evidence exists. "
                "Do not include markdown fences or commentary."
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

            precheck = await _artifact_presence_precheck()
            if not precheck["ok"]:
                # Scaffold-over-substance guard: no non-trivial Python file was produced
                # under /workspace/submission, so no leaf can claim executable backing.
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
                            "nontrivial_py_files": precheck["nontrivial_py_files"],
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
                    "precheck": precheck,
                    "leaf_judgements": [j.to_dict() for j in judgements],
                }
            )
            return InspectScore(
                value=base_score.value,
                explanation=base_score.explanation,
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
    "_has_nontrivial_body",
    "leaf_score_map_from_judgements",
    "load_paper_summary",
    "load_rubric_payload",
    "rubric_tree_scorer",
    "score_rubric_payload",
    "summarize_score_report",
    "to_inspect_score",
]
