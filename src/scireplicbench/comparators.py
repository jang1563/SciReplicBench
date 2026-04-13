"""Deterministic comparator helpers for rubric grading."""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from typing import Callable, Iterable, Sequence, TypeVar

T = TypeVar("T")


def _require_equal_length(left: Sequence[object], right: Sequence[object]) -> None:
    if len(left) != len(right):
        raise ValueError("Both inputs must have the same length.")


def _dedupe_preserve_order(
    items: Iterable[T],
    *,
    normalize: Callable[[T], T] | None = None,
) -> list[T]:
    seen: set[T] = set()
    unique: list[T] = []
    for item in items:
        normalized = normalize(item) if normalize else item
        if normalized in seen:
            continue
        seen.add(normalized)
        unique.append(normalized)
    return unique


def normalize_gene_symbol(symbol: str) -> str:
    """Normalize gene symbols for HGNC-style comparisons."""

    cleaned = symbol.strip().upper().replace("_", "-")
    cleaned = re.sub(r"\s*-\s*", "-", cleaned)
    cleaned = re.sub(r"\s+", "", cleaned)
    return cleaned


def normalize_pathway_name(pathway: str) -> str:
    """Normalize pathway names for case- and punctuation-insensitive comparisons."""

    cleaned = pathway.strip().lower()
    cleaned = re.sub(r"[^a-z0-9]+", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def normalize_cell_ontology_label(label: str) -> str:
    """Normalize benchmark cell labels to a canonical local vocabulary.

    This is a lightweight ontology-aware heuristic intended for the benchmark's
    small immune-cell label families. It does not attempt full Cell Ontology graph
    reasoning, but it does collapse common synonyms and formatting variants.
    """

    cleaned = normalize_pathway_name(label)
    cleaned = cleaned.replace(" t lymphocyte", " t cell").replace(
        " t lymphocytes", " t cells"
    )

    if "residual" in cleaned or "other immune" in cleaned or "other cells" in cleaned:
        return "residual immune cells"
    if "cd14" in cleaned and "monocyte" in cleaned:
        return "CD14 monocytes"
    if "cd16" in cleaned and "monocyte" in cleaned:
        return "CD16 monocytes"
    if "dendritic" in cleaned:
        return "dendritic cells"
    if "natural killer" in cleaned or re.search(r"\bnk\b", cleaned):
        return "NK cells"
    if "b cell" in cleaned:
        return "B cells"
    if "cd4" in cleaned and "t cell" in cleaned:
        return "CD4 T cells"
    if "cd8" in cleaned and "t cell" in cleaned:
        return "CD8 T cells"
    if "t cell" in cleaned:
        return "T cells, unspecified"
    return label.strip()


def overlap_at_k(
    predicted: Sequence[str],
    reference: Sequence[str],
    *,
    k: int,
    normalize: Callable[[str], str] | None = None,
) -> float:
    """Compute top-k overlap against a reference ranking."""

    if k <= 0:
        raise ValueError("k must be positive.")

    predicted_unique = _dedupe_preserve_order(predicted, normalize=normalize)
    reference_unique = _dedupe_preserve_order(reference, normalize=normalize)
    if not predicted_unique and not reference_unique:
        return 1.0
    if not reference_unique:
        return 0.0

    reference_top = reference_unique[:k]
    predicted_top = predicted_unique[:k]
    denominator = min(k, len(reference_top))
    if denominator == 0:
        return 1.0
    return len(set(predicted_top) & set(reference_top)) / denominator


def rank_biased_overlap(
    left: Sequence[str],
    right: Sequence[str],
    *,
    p: float = 0.9,
    k: int | None = None,
    normalize: Callable[[str], str] | None = None,
) -> float:
    """Compute extrapolated rank-biased overlap for finite ranked lists."""

    if not 0 < p < 1:
        raise ValueError("p must be between 0 and 1.")

    left_unique = _dedupe_preserve_order(left, normalize=normalize)
    right_unique = _dedupe_preserve_order(right, normalize=normalize)
    if k is not None:
        if k <= 0:
            raise ValueError("k must be positive when provided.")
        left_unique = left_unique[:k]
        right_unique = right_unique[:k]

    if not left_unique and not right_unique:
        return 1.0
    if not left_unique or not right_unique:
        return 0.0

    depth = max(len(left_unique), len(right_unique))
    left_seen: set[str] = set()
    right_seen: set[str] = set()
    cumulative = 0.0
    overlap_fraction = 0.0

    for index in range(1, depth + 1):
        if index <= len(left_unique):
            left_seen.add(left_unique[index - 1])
        if index <= len(right_unique):
            right_seen.add(right_unique[index - 1])
        overlap = len(left_seen & right_seen)
        overlap_fraction = overlap / index
        cumulative += overlap_fraction * (p ** (index - 1))

    return (1 - p) * cumulative + overlap_fraction * (p**depth)


def adjusted_rand_index(labels_true: Sequence[object], labels_pred: Sequence[object]) -> float:
    """Compute the adjusted Rand index without external dependencies."""

    _require_equal_length(labels_true, labels_pred)
    n_items = len(labels_true)
    if n_items < 2:
        return 1.0

    contingency: dict[object, dict[object, int]] = defaultdict(lambda: defaultdict(int))
    row_totals: Counter[object] = Counter()
    col_totals: Counter[object] = Counter()

    for truth, pred in zip(labels_true, labels_pred):
        contingency[truth][pred] += 1
        row_totals[truth] += 1
        col_totals[pred] += 1

    sum_comb_cells = sum(math.comb(count, 2) for row in contingency.values() for count in row.values())
    sum_comb_rows = sum(math.comb(count, 2) for count in row_totals.values())
    sum_comb_cols = sum(math.comb(count, 2) for count in col_totals.values())
    total_pairs = math.comb(n_items, 2)
    if total_pairs == 0:
        return 1.0

    expected_index = (sum_comb_rows * sum_comb_cols) / total_pairs
    max_index = 0.5 * (sum_comb_rows + sum_comb_cols)
    denominator = max_index - expected_index
    if denominator == 0:
        return 1.0
    return (sum_comb_cells - expected_index) / denominator


def normalized_mutual_information(
    labels_true: Sequence[object], labels_pred: Sequence[object]
) -> float:
    """Compute normalized mutual information with arithmetic-mean normalization."""

    _require_equal_length(labels_true, labels_pred)
    n_items = len(labels_true)
    if n_items == 0:
        return 1.0

    contingency: dict[object, dict[object, int]] = defaultdict(lambda: defaultdict(int))
    row_totals: Counter[object] = Counter()
    col_totals: Counter[object] = Counter()

    for truth, pred in zip(labels_true, labels_pred):
        contingency[truth][pred] += 1
        row_totals[truth] += 1
        col_totals[pred] += 1

    mutual_information = 0.0
    for truth, row in contingency.items():
        for pred, count in row.items():
            if count == 0:
                continue
            mutual_information += (count / n_items) * math.log(
                (count * n_items) / (row_totals[truth] * col_totals[pred])
            )

    entropy_true = -sum(
        (count / n_items) * math.log(count / n_items) for count in row_totals.values() if count
    )
    entropy_pred = -sum(
        (count / n_items) * math.log(count / n_items) for count in col_totals.values() if count
    )

    denominator = entropy_true + entropy_pred
    if denominator == 0:
        return 1.0
    return 2 * mutual_information / denominator


def _average_ranks(values: Sequence[float]) -> list[float]:
    indexed = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [0.0] * len(values)
    start = 0
    while start < len(indexed):
        end = start + 1
        while end < len(indexed) and indexed[end][1] == indexed[start][1]:
            end += 1
        average_rank = (start + 1 + end) / 2.0
        for idx in range(start, end):
            ranks[indexed[idx][0]] = average_rank
        start = end
    return ranks


def pearson_correlation(left: Sequence[float], right: Sequence[float]) -> float:
    """Compute Pearson correlation without external dependencies."""

    _require_equal_length(left, right)
    if not left:
        return 1.0

    mean_left = sum(left) / len(left)
    mean_right = sum(right) / len(right)
    centered_left = [value - mean_left for value in left]
    centered_right = [value - mean_right for value in right]

    numerator = sum(x * y for x, y in zip(centered_left, centered_right))
    denominator = math.sqrt(sum(x * x for x in centered_left) * sum(y * y for y in centered_right))
    if denominator == 0:
        return 1.0 if centered_left == centered_right else 0.0
    return numerator / denominator


def spearman_correlation(left: Sequence[float], right: Sequence[float]) -> float:
    """Compute Spearman rank correlation using average ranks for ties."""

    _require_equal_length(left, right)
    if not left:
        return 1.0
    return pearson_correlation(_average_ranks(left), _average_ranks(right))


def kendall_tau_b(left: Sequence[float], right: Sequence[float]) -> float:
    """Compute Kendall's tau-b correlation."""

    _require_equal_length(left, right)
    n_items = len(left)
    if n_items < 2:
        return 1.0

    concordant = 0
    discordant = 0
    ties_left = 0
    ties_right = 0

    for i in range(n_items - 1):
        for j in range(i + 1, n_items):
            delta_left = (left[i] > left[j]) - (left[i] < left[j])
            delta_right = (right[i] > right[j]) - (right[i] < right[j])
            if delta_left == 0 and delta_right == 0:
                continue
            if delta_left == 0:
                ties_left += 1
                continue
            if delta_right == 0:
                ties_right += 1
                continue
            if delta_left == delta_right:
                concordant += 1
            else:
                discordant += 1

    denominator = math.sqrt(
        (concordant + discordant + ties_left) * (concordant + discordant + ties_right)
    )
    if denominator == 0:
        return 1.0
    return (concordant - discordant) / denominator


def mean_absolute_error(left: Sequence[float], right: Sequence[float]) -> float:
    """Compute mean absolute error."""

    _require_equal_length(left, right)
    if not left:
        return 0.0
    return sum(abs(x - y) for x, y in zip(left, right)) / len(left)


def within_percent_tolerance(
    observed: float, expected: float, *, tolerance_pct: float
) -> bool:
    """Check whether an observed value is within a percent tolerance of a reference."""

    if tolerance_pct < 0:
        raise ValueError("tolerance_pct must be non-negative.")
    if expected == 0:
        return abs(observed) <= tolerance_pct / 100.0
    relative_error = abs(observed - expected) / abs(expected)
    return relative_error <= tolerance_pct / 100.0


def sign_concordance(left: Sequence[float], right: Sequence[float]) -> float:
    """Compute the fraction of values with matching signs."""

    _require_equal_length(left, right)
    if not left:
        return 1.0

    def sign(value: float) -> int:
        if value > 0:
            return 1
        if value < 0:
            return -1
        return 0

    matches = sum(1 for x, y in zip(left, right) if sign(x) == sign(y))
    return matches / len(left)


__all__ = [
    "adjusted_rand_index",
    "kendall_tau_b",
    "mean_absolute_error",
    "normalize_cell_ontology_label",
    "normalize_gene_symbol",
    "normalize_pathway_name",
    "normalized_mutual_information",
    "overlap_at_k",
    "pearson_correlation",
    "rank_biased_overlap",
    "sign_concordance",
    "spearman_correlation",
    "within_percent_tolerance",
]
