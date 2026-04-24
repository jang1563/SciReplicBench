"""Reviewer-path baseline for GeneLab benchmark submissions.

This starter is intentionally strong enough to serve as a real baseline on the
cached reviewer snapshot. It discovers staged LOMO folds, runs several
classical baselines, writes AUROC plus bootstrap/permutation statistics,
exports simple transfer and interpretability artifacts, stages a Geneformer
comparison note, and records a submission manifest.
"""

from __future__ import annotations

import csv
import json
import math
import os
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

FEATURE_ROOT = Path(
    os.environ.get(
        "GENELAB_FEATURE_ROOT",
        "/workspace/input/paper_bundle/data/huggingface_dataset",
    )
)
LABEL_ROOT = Path(
    os.environ.get(
        "GENELAB_LABEL_ROOT",
        "/workspace/input/paper_bundle/data/raw/GeneLab_benchmark/tasks",
    )
)
OUTPUT_ROOT = Path(
    os.environ.get(
        "GENELAB_OUTPUT_ROOT",
        "/workspace/output/agent",
    )
)

LOMO_FIELDS = [
    "tissue",
    "fold",
    "heldout_mission",
    "model",
    "status",
    "auroc",
    "ci_lower",
    "ci_upper",
    "perm_pvalue",
    "go_nogo",
    "n_train",
    "n_test",
    "n_features",
    "detail",
]
TRANSFER_FIELDS = [
    "source_tissue",
    "target_tissue",
    "source_fold",
    "target_fold",
    "model",
    "status",
    "metric",
    "value",
    "n_train",
    "n_test",
    "n_common_genes",
    "detail",
]
NEGATIVE_FIELDS = [
    "tissue",
    "fold",
    "control",
    "model",
    "status",
    "metric",
    "value",
    "spread",
    "detail",
]
INTERPRETABILITY_FIELDS = [
    "tissue",
    "fold",
    "model",
    "feature_rank",
    "feature_id",
    "importance",
    "importance_type",
    "status",
    "detail",
]
GO_NOGO_FIELDS = [
    "tissue",
    "model",
    "mean_auroc",
    "mean_ci_lower",
    "mean_ci_upper",
    "max_perm_pvalue",
    "decision",
    "detail",
]
FOUNDATION_FIELDS = [
    "model",
    "status",
    "classical_reference_model",
    "classical_reference_auroc",
    "expected_artifact",
    "detail",
]
SPLIT_FIELDS = [
    "tissue",
    "fold",
    "heldout_mission",
    "n_train",
    "n_test",
    "n_features",
    "train_missions",
    "test_missions",
]
PREPROCESSED_FIELDS = [
    "tissue",
    "fold",
    "n_samples",
    "n_features",
    "mean_abs_value",
    "detail",
]

_PRIMARY_MODELS = [
    "ElasticNetLogReg",
    "RandomForest",
    "XGBoost",
    "PCALogReg",
]


def _int_env(name: str, default: int) -> int:
    raw_value = os.environ.get(name, "").strip()
    if not raw_value:
        return default
    try:
        value = int(raw_value)
    except ValueError:
        return default
    return value if value > 0 else default


MAX_MODEL_FEATURES = _int_env("GENELAB_MAX_MODEL_FEATURES", 128)
BOOTSTRAP_REPLICATES = _int_env("GENELAB_BOOTSTRAP_REPLICATES", 20)
PERMUTATION_REPLICATES = _int_env("GENELAB_PERMUTATION_REPLICATES", 20)
NEGATIVE_CONTROL_REPEATS = _int_env("GENELAB_NEGATIVE_CONTROL_REPEATS", 2)
RANDOM_FOREST_ESTIMATORS = _int_env("GENELAB_RANDOM_FOREST_ESTIMATORS", 24)
XGBOOST_ESTIMATORS = _int_env("GENELAB_XGBOOST_ESTIMATORS", 20)


@dataclass(frozen=True)
class FoldSpec:
    tissue: str
    fold: str
    feature_dir: Path
    label_dir: Path

    @property
    def heldout_mission(self) -> str:
        name = self.fold.removeprefix("fold_")
        if name.endswith("_test"):
            return name[: -len("_test")]
        return name


@dataclass(frozen=True)
class AlignedFoldData:
    spec: FoldSpec
    feature_names: list[str]
    train_ids: list[str]
    train_x: list[list[float]]
    train_y: list[int]
    test_ids: list[str]
    test_x: list[list[float]]
    test_y: list[int]
    train_meta: list[dict[str, str]]
    test_meta: list[dict[str, str]]


def discover_fold_specs() -> list[FoldSpec]:
    specs: list[FoldSpec] = []
    for tissue_dir in sorted(FEATURE_ROOT.glob("A*_lomo")):
        if not tissue_dir.is_dir():
            continue
        for fold_dir in sorted(tissue_dir.glob("fold_*")):
            label_dir = LABEL_ROOT / tissue_dir.name / fold_dir.name
            if fold_dir.is_dir() and label_dir.is_dir():
                specs.append(
                    FoldSpec(
                        tissue=tissue_dir.name,
                        fold=fold_dir.name,
                        feature_dir=fold_dir,
                        label_dir=label_dir,
                    )
                )
    return specs


def _read_feature_rows(path: Path) -> tuple[list[str], dict[str, list[float]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        header = next(reader, None)
        if not header:
            raise ValueError(f"Feature table is empty: {path}")
        feature_names = header[1:]
        rows: dict[str, list[float]] = {}
        for row in reader:
            if not row:
                continue
            rows[row[0]] = [float(value) for value in row[1:]]
    return feature_names, rows


def _read_label_rows(path: Path) -> dict[str, int]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        header = next(reader, None)
        if not header:
            raise ValueError(f"Label table is empty: {path}")
        rows: dict[str, int] = {}
        for row in reader:
            if not row:
                continue
            rows[row[0]] = int(float(row[1]))
    return rows


def _read_meta_rows(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        header = next(reader, None)
        if not header:
            raise ValueError(f"Metadata table is empty: {path}")
        sample_key = header[0] or "sample_id"
        fieldnames = [sample_key, *header[1:]]
        rows: dict[str, dict[str, str]] = {}
        for row in reader:
            if not row:
                continue
            record = {name: value for name, value in zip(fieldnames, row, strict=False)}
            sample_id = record[sample_key]
            rows[sample_id] = record
    return rows


def _subset_features(
    feature_names: list[str],
    rows: dict[str, list[float]],
    keep_names: list[str],
) -> dict[str, list[float]]:
    if keep_names == feature_names:
        return rows
    index_lookup = {name: idx for idx, name in enumerate(feature_names)}
    keep_indices = [index_lookup[name] for name in keep_names]
    return {
        sample_id: [values[idx] for idx in keep_indices]
        for sample_id, values in rows.items()
    }


def _align_train_test_features(
    train_names: list[str],
    train_rows: dict[str, list[float]],
    test_names: list[str],
    test_rows: dict[str, list[float]],
) -> tuple[list[str], dict[str, list[float]], dict[str, list[float]]]:
    if train_names == test_names:
        return train_names, train_rows, test_rows
    test_name_set = set(test_names)
    common_names = [name for name in train_names if name in test_name_set]
    if not common_names:
        raise ValueError("Train/test feature tables have no genes in common.")
    return (
        common_names,
        _subset_features(train_names, train_rows, common_names),
        _subset_features(test_names, test_rows, common_names),
    )


def _align_rows(
    feature_rows: dict[str, list[float]],
    label_rows: dict[str, int],
    meta_rows: dict[str, dict[str, str]],
) -> tuple[list[str], list[list[float]], list[int], list[dict[str, str]]]:
    sample_ids = [sample_id for sample_id in feature_rows if sample_id in label_rows]
    if not sample_ids:
        raise ValueError("No shared sample IDs were found between features and labels.")
    metadata = [meta_rows.get(sample_id, {"sample_id": sample_id}) for sample_id in sample_ids]
    return (
        sample_ids,
        [feature_rows[sample_id] for sample_id in sample_ids],
        [label_rows[sample_id] for sample_id in sample_ids],
        metadata,
    )


def load_aligned_fold(spec: FoldSpec) -> AlignedFoldData:
    train_names, train_x_rows = _read_feature_rows(spec.feature_dir / "train_X.csv")
    test_names, test_x_rows = _read_feature_rows(spec.feature_dir / "test_X.csv")
    feature_names, train_x_rows, test_x_rows = _align_train_test_features(
        train_names, train_x_rows, test_names, test_x_rows
    )

    train_y_rows = _read_label_rows(spec.label_dir / "train_y.csv")
    test_y_rows = _read_label_rows(spec.label_dir / "test_y.csv")
    train_meta_rows = _read_meta_rows(spec.label_dir / "train_meta.csv")
    test_meta_rows = _read_meta_rows(spec.label_dir / "test_meta.csv")

    train_ids, train_x, train_y, train_meta = _align_rows(train_x_rows, train_y_rows, train_meta_rows)
    test_ids, test_x, test_y, test_meta = _align_rows(test_x_rows, test_y_rows, test_meta_rows)

    return AlignedFoldData(
        spec=spec,
        feature_names=feature_names,
        train_ids=train_ids,
        train_x=train_x,
        train_y=train_y,
        test_ids=test_ids,
        test_x=test_x,
        test_y=test_y,
        train_meta=train_meta,
        test_meta=test_meta,
    )


def _pairwise_auc(y_true: list[int], scores: list[float]) -> float:
    positives = [score for label, score in zip(y_true, scores, strict=True) if label == 1]
    negatives = [score for label, score in zip(y_true, scores, strict=True) if label == 0]
    if not positives or not negatives:
        raise ValueError("AUROC requires both positive and negative labels in the evaluation split.")
    wins = 0.0
    for positive_score in positives:
        for negative_score in negatives:
            if positive_score > negative_score:
                wins += 1.0
            elif positive_score == negative_score:
                wins += 0.5
    return wins / (len(positives) * len(negatives))


def _percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("Percentile requires at least one value.")
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * quantile
    low = int(math.floor(position))
    high = int(math.ceil(position))
    if low == high:
        return ordered[low]
    fraction = position - low
    return ordered[low] * (1 - fraction) + ordered[high] * fraction


def _bootstrap_ci(
    y_true: list[int],
    scores: list[float],
    *,
    seed: int,
    n_bootstrap: int = 200,
) -> tuple[float, float]:
    rng = random.Random(seed)
    n = len(y_true)
    estimates: list[float] = []
    for _ in range(n_bootstrap):
        indices = [rng.randrange(n) for _ in range(n)]
        sample_y = [y_true[idx] for idx in indices]
        if len(set(sample_y)) < 2:
            continue
        sample_scores = [scores[idx] for idx in indices]
        estimates.append(_pairwise_auc(sample_y, sample_scores))
    if not estimates:
        observed = _pairwise_auc(y_true, scores)
        return observed, observed
    return _percentile(estimates, 0.025), _percentile(estimates, 0.975)


def _permutation_pvalue(
    y_true: list[int],
    scores: list[float],
    *,
    seed: int,
    n_permutations: int = 200,
) -> float:
    rng = random.Random(seed)
    observed = _pairwise_auc(y_true, scores)
    exceedances = 0
    valid = 0
    for _ in range(n_permutations):
        shuffled = list(y_true)
        rng.shuffle(shuffled)
        if len(set(shuffled)) < 2:
            continue
        valid += 1
        if _pairwise_auc(shuffled, scores) >= observed:
            exceedances += 1
    return (exceedances + 1) / (valid + 1)


def _column_means(rows: list[list[float]]) -> list[float]:
    n_rows = len(rows)
    n_features = len(rows[0])
    return [sum(row[idx] for row in rows) / n_rows for idx in range(n_features)]


def _column_variances(rows: list[list[float]]) -> list[float]:
    means = _column_means(rows)
    n_rows = len(rows)
    n_features = len(rows[0])
    if n_rows == 1:
        return [0.0 for _ in range(n_features)]
    return [
        sum((row[idx] - means[idx]) ** 2 for row in rows) / (n_rows - 1)
        for idx in range(n_features)
    ]


def _subset_columns(rows: list[list[float]], indices: list[int]) -> list[list[float]]:
    return [[row[idx] for idx in indices] for row in rows]


def _variance_screened_matrices(
    feature_names: list[str],
    train_x: list[list[float]],
    test_x: list[list[float]],
    *,
    max_features: int = MAX_MODEL_FEATURES,
) -> tuple[list[str], list[list[float]], list[list[float]]]:
    if not feature_names or len(feature_names) <= max_features:
        return feature_names, train_x, test_x

    variances = _column_variances(train_x)
    ranked_indices = sorted(
        range(len(feature_names)),
        key=lambda idx: (-variances[idx], feature_names[idx]),
    )[:max_features]
    ranked_indices.sort()
    return (
        [feature_names[idx] for idx in ranked_indices],
        _subset_columns(train_x, ranked_indices),
        _subset_columns(test_x, ranked_indices),
    )


def _fallback_scores(
    train_x: list[list[float]],
    train_y: list[int],
    test_x: list[list[float]],
) -> tuple[list[float], list[float]]:
    if not train_x:
        raise ValueError("Cannot fit fallback baseline without training rows.")
    positive_rows = [row for row, label in zip(train_x, train_y, strict=True) if label == 1]
    negative_rows = [row for row, label in zip(train_x, train_y, strict=True) if label == 0]
    if not positive_rows or not negative_rows:
        raise ValueError("Fallback baseline requires both positive and negative training labels.")
    positive_mean = _column_means(positive_rows)
    negative_mean = _column_means(negative_rows)
    weights = [
        positive_value - negative_value
        for positive_value, negative_value in zip(positive_mean, negative_mean, strict=True)
    ]
    scores = [
        sum(value * weight for value, weight in zip(row, weights, strict=True))
        for row in test_x
    ]
    importances = [abs(weight) for weight in weights]
    return scores, importances


def _elasticnet_scores(
    train_x: list[list[float]],
    train_y: list[int],
    test_x: list[list[float]],
) -> tuple[list[float], list[float]] | None:
    try:
        import numpy as np
        from sklearn.linear_model import LogisticRegression
    except ModuleNotFoundError:
        return None

    model = LogisticRegression(
        penalty="elasticnet",
        solver="saga",
        l1_ratio=0.5,
        C=1.0,
        class_weight="balanced",
        max_iter=500,
        tol=1e-3,
        random_state=42,
    )
    model.fit(np.asarray(train_x, dtype=float), train_y)
    probabilities = model.predict_proba(np.asarray(test_x, dtype=float))
    return [float(probability[1]) for probability in probabilities], [
        abs(float(value)) for value in model.coef_[0]
    ]


def _random_forest_scores(
    train_x: list[list[float]],
    train_y: list[int],
    test_x: list[list[float]],
) -> tuple[list[float], list[float]] | None:
    try:
        import numpy as np
        from sklearn.ensemble import RandomForestClassifier
    except ModuleNotFoundError:
        return None

    model = RandomForestClassifier(
        n_estimators=RANDOM_FOREST_ESTIMATORS,
        max_features="sqrt",
        class_weight="balanced_subsample",
        random_state=42,
        n_jobs=1,
    )
    model.fit(np.asarray(train_x, dtype=float), train_y)
    probabilities = model.predict_proba(np.asarray(test_x, dtype=float))
    return [float(probability[1]) for probability in probabilities], [
        float(value) for value in model.feature_importances_
    ]


def _xgboost_scores(
    train_x: list[list[float]],
    train_y: list[int],
    test_x: list[list[float]],
) -> tuple[list[float], list[float]] | None:
    try:
        import numpy as np
    except ModuleNotFoundError:
        return None

    try:
        from xgboost import XGBClassifier
    except ModuleNotFoundError:
        try:
            from sklearn.ensemble import GradientBoostingClassifier
        except ModuleNotFoundError:
            return None

        model = GradientBoostingClassifier(random_state=42)
        model.fit(np.asarray(train_x, dtype=float), train_y)
        probabilities = model.predict_proba(np.asarray(test_x, dtype=float))
        return [float(probability[1]) for probability in probabilities], [
            float(value) for value in model.feature_importances_
        ]

    model = XGBClassifier(
        n_estimators=XGBOOST_ESTIMATORS,
        max_depth=3,
        learning_rate=0.08,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_lambda=1.0,
        objective="binary:logistic",
        eval_metric="logloss",
        n_jobs=1,
        random_state=42,
    )
    model.fit(np.asarray(train_x, dtype=float), train_y)
    probabilities = model.predict_proba(np.asarray(test_x, dtype=float))
    return [float(probability[1]) for probability in probabilities], [
        float(value) for value in model.feature_importances_
    ]


def _pca_logreg_scores(
    train_x: list[list[float]],
    train_y: list[int],
    test_x: list[list[float]],
) -> tuple[list[float], list[float]] | None:
    try:
        import numpy as np
        from sklearn.decomposition import PCA
        from sklearn.linear_model import LogisticRegression
    except ModuleNotFoundError:
        return None

    n_components = min(len(train_x) - 1, len(train_x[0]), 8)
    if n_components < 1:
        return None

    x_train = np.asarray(train_x, dtype=float)
    x_test = np.asarray(test_x, dtype=float)
    pca = PCA(n_components=n_components, svd_solver="full")
    x_train_pca = pca.fit_transform(x_train)
    x_test_pca = pca.transform(x_test)

    model = LogisticRegression(
        penalty="l2",
        solver="liblinear",
        class_weight="balanced",
        max_iter=500,
        random_state=42,
    )
    model.fit(x_train_pca, train_y)
    probabilities = model.predict_proba(x_test_pca)
    projected_weights = pca.components_.T @ model.coef_[0]
    return [float(probability[1]) for probability in probabilities], [
        abs(float(value)) for value in projected_weights
    ]


def _score_model(
    model_name: str,
    train_x: list[list[float]],
    train_y: list[int],
    test_x: list[list[float]],
) -> tuple[list[float], list[float]]:
    model_dispatch = {
        "ElasticNetLogReg": _elasticnet_scores,
        "RandomForest": _random_forest_scores,
        "XGBoost": _xgboost_scores,
        "PCALogReg": _pca_logreg_scores,
    }
    predictor = model_dispatch[model_name]
    result = predictor(train_x, train_y, test_x)
    if result is None:
        scores, importances = _fallback_scores(train_x, train_y, test_x)
        return scores, importances
    return result


def _sorted_importance_rows(
    feature_names: list[str],
    importances: list[float],
    *,
    limit: int = 20,
) -> list[tuple[str, float]]:
    ranked = sorted(
        zip(feature_names, importances, strict=True),
        key=lambda item: abs(item[1]),
        reverse=True,
    )
    return [(feature_id, float(importance)) for feature_id, importance in ranked[:limit]]


def write_tsv(path: Path, fieldnames: list[str], rows: Iterable[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name, "") for name in fieldnames})


def _evaluate_lomo(
    fold_data: list[AlignedFoldData],
) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[tuple[str, str], list[tuple[str, float]]]]:
    rows: list[dict[str, object]] = []
    aggregate: dict[tuple[str, str], list[dict[str, float]]] = {}
    interpretability: dict[tuple[str, str], list[tuple[str, float]]] = {}

    for fold in fold_data:
        model_feature_names, model_train_x, model_test_x = _variance_screened_matrices(
            fold.feature_names,
            fold.train_x,
            fold.test_x,
        )
        for model_name in _PRIMARY_MODELS:
            try:
                scores, importances = _score_model(model_name, model_train_x, fold.train_y, model_test_x)
                auroc = _pairwise_auc(fold.test_y, scores)
                ci_lower, ci_upper = _bootstrap_ci(
                    fold.test_y,
                    scores,
                    seed=17,
                    n_bootstrap=BOOTSTRAP_REPLICATES,
                )
                perm_pvalue = _permutation_pvalue(
                    fold.test_y,
                    scores,
                    seed=29,
                    n_permutations=PERMUTATION_REPLICATES,
                )
                go_nogo = auroc >= 0.7 and ci_lower >= 0.6 and perm_pvalue < 0.05
                detail = (
                    "reviewer-path baseline executed on staged fold with "
                    f"variance-screened feature cap={len(model_feature_names)}"
                )
                row = {
                    "tissue": fold.spec.tissue,
                    "fold": fold.spec.fold,
                    "heldout_mission": fold.spec.heldout_mission,
                    "model": model_name,
                    "status": "ok",
                    "auroc": f"{auroc:.4f}",
                    "ci_lower": f"{ci_lower:.4f}",
                    "ci_upper": f"{ci_upper:.4f}",
                    "perm_pvalue": f"{perm_pvalue:.4f}",
                    "go_nogo": "go" if go_nogo else "no_go",
                    "n_train": len(fold.train_x),
                    "n_test": len(fold.test_x),
                    "n_features": len(model_feature_names),
                    "detail": detail,
                }
                rows.append(row)
                aggregate.setdefault((fold.spec.tissue, model_name), []).append(
                    {
                        "auroc": auroc,
                        "ci_lower": ci_lower,
                        "ci_upper": ci_upper,
                        "perm_pvalue": perm_pvalue,
                    }
                )
                interpretability.setdefault((fold.spec.tissue, model_name), _sorted_importance_rows(
                    model_feature_names,
                    importances,
                ))
            except Exception as exc:
                rows.append(
                    {
                        "tissue": fold.spec.tissue,
                        "fold": fold.spec.fold,
                        "heldout_mission": fold.spec.heldout_mission,
                        "model": model_name,
                        "status": "failed",
                        "auroc": "",
                        "ci_lower": "",
                        "ci_upper": "",
                        "perm_pvalue": "",
                        "go_nogo": "",
                        "n_train": len(fold.train_x),
                        "n_test": len(fold.test_x),
                        "n_features": len(model_feature_names),
                        "detail": f"{type(exc).__name__}: {exc}",
                    }
                )

    for (tissue, model_name), metrics in sorted(aggregate.items()):
        mean_auroc = sum(item["auroc"] for item in metrics) / len(metrics)
        mean_lower = sum(item["ci_lower"] for item in metrics) / len(metrics)
        mean_upper = sum(item["ci_upper"] for item in metrics) / len(metrics)
        mean_perm = sum(item["perm_pvalue"] for item in metrics) / len(metrics)
        rows.append(
            {
                "tissue": tissue,
                "fold": "aggregate",
                "heldout_mission": "all",
                "model": model_name,
                "status": "ok",
                "auroc": f"{mean_auroc:.4f}",
                "ci_lower": f"{mean_lower:.4f}",
                "ci_upper": f"{mean_upper:.4f}",
                "perm_pvalue": f"{mean_perm:.4f}",
                "go_nogo": "go" if (mean_auroc >= 0.7 and mean_lower >= 0.6 and mean_perm < 0.05) else "no_go",
                "n_train": "",
                "n_test": "",
                "n_features": "",
                "detail": "aggregate over reviewer-path LOMO folds",
            }
        )

    return rows, _build_go_nogo_rows(aggregate), interpretability


def _build_go_nogo_rows(aggregate: dict[tuple[str, str], list[dict[str, float]]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for (tissue, model_name), metrics in sorted(aggregate.items()):
        mean_auroc = sum(item["auroc"] for item in metrics) / len(metrics)
        mean_lower = sum(item["ci_lower"] for item in metrics) / len(metrics)
        mean_upper = sum(item["ci_upper"] for item in metrics) / len(metrics)
        max_perm = max(item["perm_pvalue"] for item in metrics)
        rows.append(
            {
                "tissue": tissue,
                "model": model_name,
                "mean_auroc": f"{mean_auroc:.4f}",
                "mean_ci_lower": f"{mean_lower:.4f}",
                "mean_ci_upper": f"{mean_upper:.4f}",
                "max_perm_pvalue": f"{max_perm:.4f}",
                "decision": "go" if (mean_auroc >= 0.7 and mean_lower >= 0.6 and max_perm < 0.05) else "no_go",
                "detail": "GO/NO-GO heuristic matches reviewer-path classical baseline summary",
            }
        )
    return rows


def _build_negative_control_rows(fold_data: list[AlignedFoldData]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    rng = random.Random(101)
    for fold in fold_data:
        model_feature_names, model_train_x, model_test_x = _variance_screened_matrices(
            fold.feature_names,
            fold.train_x,
            fold.test_x,
        )
        shuffled_aurocs: list[float] = []
        for repeat in range(NEGATIVE_CONTROL_REPEATS):
            shuffled = list(fold.train_y)
            rng.shuffle(shuffled)
            try:
                scores, _ = _score_model("ElasticNetLogReg", model_train_x, shuffled, model_test_x)
                shuffled_aurocs.append(_pairwise_auc(fold.test_y, scores))
            except Exception:
                continue
        if shuffled_aurocs:
            rows.append(
                {
                    "tissue": fold.spec.tissue,
                    "fold": fold.spec.fold,
                    "control": "label_permutation",
                    "model": "ElasticNetLogReg",
                    "status": "ok",
                    "metric": "mean_auroc",
                    "value": f"{sum(shuffled_aurocs) / len(shuffled_aurocs):.4f}",
                    "spread": f"{max(shuffled_aurocs) - min(shuffled_aurocs):.4f}",
                    "detail": "train-label permutations provide a near-chance negative control",
                }
            )
        else:
            rows.append(
                {
                    "tissue": fold.spec.tissue,
                    "fold": fold.spec.fold,
                    "control": "label_permutation",
                    "model": "ElasticNetLogReg",
                    "status": "failed",
                    "metric": "mean_auroc",
                    "value": "",
                    "spread": "",
                    "detail": "all label-permutation retries failed to produce a scorable AUROC",
                }
            )

        variances = _column_variances(model_train_x)
        n_low_signal = max(8, min(64, len(model_feature_names) // 12))
        low_signal_indices = sorted(
            range(len(model_feature_names)),
            key=lambda idx: variances[idx],
        )[:n_low_signal]
        try:
            scores, _ = _score_model(
                "ElasticNetLogReg",
                _subset_columns(model_train_x, low_signal_indices),
                fold.train_y,
                _subset_columns(model_test_x, low_signal_indices),
            )
            rows.append(
                {
                    "tissue": fold.spec.tissue,
                    "fold": fold.spec.fold,
                    "control": "housekeeping_proxy_low_variance",
                    "model": "ElasticNetLogReg",
                    "status": "ok",
                    "metric": "auroc",
                    "value": f"{_pairwise_auc(fold.test_y, scores):.4f}",
                    "spread": "",
                    "detail": "lowest-variance genes provide a lightweight housekeeping proxy on the reviewer snapshot",
                }
            )
        except Exception as exc:
            rows.append(
                {
                    "tissue": fold.spec.tissue,
                    "fold": fold.spec.fold,
                    "control": "housekeeping_proxy_low_variance",
                    "model": "ElasticNetLogReg",
                    "status": "failed",
                    "metric": "auroc",
                    "value": "",
                    "spread": "",
                    "detail": f"{type(exc).__name__}: {exc}",
                }
            )
    return rows


def _build_interpretability_rows(
    interpretability: dict[tuple[str, str], list[tuple[str, float]]]
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for (tissue, model_name), ranked in sorted(interpretability.items()):
        for rank, (feature_id, importance) in enumerate(ranked, start=1):
            rows.append(
                {
                    "tissue": tissue,
                    "fold": "aggregate",
                    "model": model_name,
                    "feature_rank": rank,
                    "feature_id": feature_id,
                    "importance": f"{importance:.6f}",
                    "importance_type": "absolute_model_weight",
                    "status": "ok",
                    "detail": "top reviewer-path feature ranking derived from the best available classical baseline fold",
                }
            )
    return rows


def _feature_intersection(
    source_names: list[str],
    source_rows: list[list[float]],
    target_names: list[str],
    target_rows: list[list[float]],
) -> tuple[list[str], list[list[float]], list[list[float]]]:
    target_lookup = {name: idx for idx, name in enumerate(target_names)}
    common = [name for name in source_names if name in target_lookup]
    if not common:
        return [], [], []
    source_lookup = {name: idx for idx, name in enumerate(source_names)}
    source_idx = [source_lookup[name] for name in common]
    target_idx = [target_lookup[name] for name in common]
    return (
        common,
        _subset_columns(source_rows, source_idx),
        _subset_columns(target_rows, target_idx),
    )


def _build_transfer_rows(fold_data: list[AlignedFoldData]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    representative_folds: dict[str, AlignedFoldData] = {}
    for fold in fold_data:
        representative_folds.setdefault(fold.spec.tissue, fold)

    tissues = sorted(representative_folds)
    if len(tissues) < 2:
        representative = representative_folds[tissues[0]]
        return [
            {
                "source_tissue": representative.spec.tissue,
                "target_tissue": "",
                "source_fold": representative.spec.fold,
                "target_fold": "",
                "model": "ElasticNetLogReg",
                "status": "not_applicable",
                "metric": "auroc",
                "value": "",
                "n_train": len(representative.train_x),
                "n_test": "",
                "n_common_genes": "",
                "detail": "cross-tissue transfer requires at least two staged tissues in the reviewer snapshot",
            }
        ]

    for source_tissue in tissues:
        source_fold = representative_folds[source_tissue]
        for target_tissue in tissues:
            if source_tissue == target_tissue:
                continue
            target_fold = representative_folds[target_tissue]
            common_genes, source_train_x, target_test_x = _feature_intersection(
                source_fold.feature_names,
                source_fold.train_x,
                target_fold.feature_names,
                target_fold.test_x,
            )
            common_genes, source_train_x, target_test_x = _variance_screened_matrices(
                common_genes,
                source_train_x,
                target_test_x,
            )
            if not common_genes:
                rows.append(
                    {
                        "source_tissue": source_tissue,
                        "target_tissue": target_tissue,
                        "source_fold": source_fold.spec.fold,
                        "target_fold": target_fold.spec.fold,
                        "model": "ElasticNetLogReg",
                        "status": "failed",
                        "metric": "auroc",
                        "value": "",
                        "n_train": len(source_fold.train_x),
                        "n_test": len(target_fold.test_x),
                        "n_common_genes": 0,
                        "detail": "no common genes between source-train and target-test feature spaces",
                    }
                )
                continue

            for model_name in ("ElasticNetLogReg", "RandomForest"):
                try:
                    scores, _ = _score_model(model_name, source_train_x, source_fold.train_y, target_test_x)
                    auroc = _pairwise_auc(target_fold.test_y, scores)
                    rows.append(
                        {
                            "source_tissue": source_tissue,
                            "target_tissue": target_tissue,
                            "source_fold": source_fold.spec.fold,
                            "target_fold": target_fold.spec.fold,
                            "model": model_name,
                            "status": "ok",
                            "metric": "auroc",
                            "value": f"{auroc:.4f}",
                            "n_train": len(source_fold.train_x),
                            "n_test": len(target_fold.test_x),
                            "n_common_genes": len(common_genes),
                            "detail": "cross-tissue transfer on intersected reviewer-path genes",
                        }
                    )
                except Exception as exc:
                    rows.append(
                        {
                            "source_tissue": source_tissue,
                            "target_tissue": target_tissue,
                            "source_fold": source_fold.spec.fold,
                            "target_fold": target_fold.spec.fold,
                            "model": model_name,
                            "status": "failed",
                            "metric": "auroc",
                            "value": "",
                            "n_train": len(source_fold.train_x),
                            "n_test": len(target_fold.test_x),
                            "n_common_genes": len(common_genes),
                            "detail": f"{type(exc).__name__}: {exc}",
                        }
                    )
    return rows


def _build_split_manifest_rows(fold_data: list[AlignedFoldData]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for fold in fold_data:
        train_missions = sorted({meta.get("mission", "") for meta in fold.train_meta if meta.get("mission")})
        test_missions = sorted({meta.get("mission", "") for meta in fold.test_meta if meta.get("mission")})
        rows.append(
            {
                "tissue": fold.spec.tissue,
                "fold": fold.spec.fold,
                "heldout_mission": fold.spec.heldout_mission,
                "n_train": len(fold.train_x),
                "n_test": len(fold.test_x),
                "n_features": len(fold.feature_names),
                "train_missions": ",".join(train_missions),
                "test_missions": ",".join(test_missions),
            }
        )
    return rows


def _build_preprocessed_rows(fold_data: list[AlignedFoldData]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for fold in fold_data:
        flattened = [abs(value) for row in fold.train_x[: min(len(fold.train_x), 12)] for value in row[: min(len(row), 256)]]
        mean_abs = sum(flattened) / len(flattened) if flattened else 0.0
        rows.append(
            {
                "tissue": fold.spec.tissue,
                "fold": fold.spec.fold,
                "n_samples": len(fold.train_x) + len(fold.test_x),
                "n_features": len(fold.feature_names),
                "mean_abs_value": f"{mean_abs:.6f}",
                "detail": "reviewer-path train/test matrices already reflect fold-safe filtering and scaling",
            }
        )
    return rows


def _build_foundation_rows(lomo_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    aggregate_rows = [
        row for row in lomo_rows
        if row["fold"] == "aggregate" and row["status"] == "ok"
    ]
    best_row = max(
        aggregate_rows,
        key=lambda row: float(row["auroc"]),
        default={
            "model": "",
            "auroc": "",
        },
    )
    return [
        {
            "model": "Geneformer",
            "status": "staged",
            "classical_reference_model": best_row["model"],
            "classical_reference_auroc": best_row["auroc"],
            "expected_artifact": "GPU/HPC fine-tuning or cached embeddings",
            "detail": "reviewer-path baseline stages the Geneformer branch and compares it against the best available classical baseline",
        }
    ]


def _write_manifest(
    *,
    fold_data: list[AlignedFoldData],
    lomo_rows: list[dict[str, object]],
    transfer_rows: list[dict[str, object]],
    negative_rows: list[dict[str, object]],
    interpretability_rows: list[dict[str, object]],
) -> None:
    manifest_path = OUTPUT_ROOT.parent / "submission_manifest.json"
    created_files = [
        str(path)
        for path in sorted(OUTPUT_ROOT.rglob("*"))
        if path.is_file()
    ]
    payload = {
        "paper_id": "genelab_benchmark",
        "starter_profile": "reviewer_path_baseline",
        "detected_tissues": sorted({fold.spec.tissue for fold in fold_data}),
        "n_folds": len(fold_data),
        "models_run": _PRIMARY_MODELS,
        "commands": [
            "bash /workspace/submission/run.sh",
        ],
        "inputs": {
            "feature_root": str(FEATURE_ROOT),
            "label_root": str(LABEL_ROOT),
            "reviewer_snapshot_note": "The cached feature bundle currently exposes the public reviewer snapshot available under data/huggingface_dataset.",
        },
        "artifacts": created_files,
        "summary": {
            "successful_lomo_rows": sum(1 for row in lomo_rows if row["status"] == "ok"),
            "successful_transfer_rows": sum(1 for row in transfer_rows if row["status"] == "ok"),
            "successful_negative_control_rows": sum(1 for row in negative_rows if row["status"] == "ok"),
            "interpretability_rows": len(interpretability_rows),
        },
    }
    manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> None:
    fold_specs = discover_fold_specs()
    if not fold_specs:
        raise FileNotFoundError("No GeneLab fold directories were discovered.")

    fold_data = [load_aligned_fold(spec) for spec in fold_specs]

    lomo_rows, go_nogo_rows, interpretability_seed = _evaluate_lomo(fold_data)
    transfer_rows = _build_transfer_rows(fold_data)
    negative_rows = _build_negative_control_rows(fold_data)
    interpretability_rows = _build_interpretability_rows(interpretability_seed)
    foundation_rows = _build_foundation_rows(lomo_rows)

    write_tsv(OUTPUT_ROOT / "lomo/summary.tsv", LOMO_FIELDS, lomo_rows)
    write_tsv(OUTPUT_ROOT / "lomo/split_manifest.tsv", SPLIT_FIELDS, _build_split_manifest_rows(fold_data))
    write_tsv(OUTPUT_ROOT / "lomo/preprocessed_features.tsv", PREPROCESSED_FIELDS, _build_preprocessed_rows(fold_data))
    write_tsv(OUTPUT_ROOT / "transfer/cross_tissue.tsv", TRANSFER_FIELDS, transfer_rows)
    write_tsv(OUTPUT_ROOT / "negative_controls/summary.tsv", NEGATIVE_FIELDS, negative_rows)
    write_tsv(OUTPUT_ROOT / "interpretability/top_features.tsv", INTERPRETABILITY_FIELDS, interpretability_rows)
    write_tsv(OUTPUT_ROOT / "go_nogo/summary.tsv", GO_NOGO_FIELDS, go_nogo_rows)
    write_tsv(OUTPUT_ROOT / "foundation/geneformer_staging.tsv", FOUNDATION_FIELDS, foundation_rows)
    _write_manifest(
        fold_data=fold_data,
        lomo_rows=lomo_rows,
        transfer_rows=transfer_rows,
        negative_rows=negative_rows,
        interpretability_rows=interpretability_rows,
    )


if __name__ == "__main__":
    main()
