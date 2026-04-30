#!/usr/bin/env python
"""Calibrate Squidpy result_match thresholds against random baselines.

For each numeric threshold in result_match_reference.json, this script
permutes the paper's frozen reference artifact, recomputes the metric,
and reports the random-baseline distribution. Output is a JSON summary
plus a Markdown report saved to papers/squidpy_spatial/scoring_methodology.md.

Run on Cayuga only:
    /athena/.../envs/squidpy_spatial_py311/bin/python scripts/calibrate_squidpy_thresholds.py
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from statistics import mean, pstdev
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import pearsonr, spearmanr
from sklearn.metrics import adjusted_rand_score

REPO_ROOT = Path(__file__).resolve().parents[1]
PAPER_DIR = REPO_ROOT / "papers" / "squidpy_spatial"
GENERATED_DIR = PAPER_DIR / "reference_outputs" / "generated"
REFERENCE_JSON = PAPER_DIR / "reference_outputs" / "result_match_reference.json"
OUTPUT_JSON = PAPER_DIR / "scoring_methodology.json"
OUTPUT_MD = PAPER_DIR / "scoring_methodology.md"

N_TRIALS = 200
RNG = np.random.default_rng(20260430)


def _rbo(s1: list[str], s2: list[str], p: float = 0.9) -> float:
    """Standard rank-biased overlap (Webber et al. 2010), p=0.9 default."""
    if not s1 or not s2:
        return 0.0
    k = max(len(s1), len(s2))
    overlap = 0
    rbo = 0.0
    seen1: set[str] = set()
    seen2: set[str] = set()
    for d in range(1, k + 1):
        if d <= len(s1):
            seen1.add(s1[d - 1])
        if d <= len(s2):
            seen2.add(s2[d - 1])
        overlap = len(seen1 & seen2)
        rbo += (overlap / d) * (p ** (d - 1))
    return (1 - p) * rbo


def _calibrate_rbo(reference: list[str], top_k: int, threshold: float, *,
                   universe: list[str] | None = None) -> dict[str, Any]:
    """Permute ranked list and compute RBO vs reference top-k."""
    ref_top = list(reference[:top_k])
    pool = universe if universe is not None else list(reference)
    if len(pool) < top_k:
        return {"error": f"universe too small: {len(pool)}"}
    samples: list[float] = []
    for _ in range(N_TRIALS):
        shuffled = list(pool)
        RNG.shuffle(shuffled)
        cand = shuffled[:top_k]
        samples.append(_rbo(ref_top, cand))
    return _summarize(samples, threshold)


def _calibrate_overlap_at_k(reference_top_k: list[str], top_k: int, threshold: float,
                             *, universe: list[str]) -> dict[str, Any]:
    """Random-sample top_k from universe; report overlap fraction with reference top-k."""
    samples: list[float] = []
    expected_set = set(reference_top_k)
    if len(universe) < top_k:
        return {"error": f"universe too small: {len(universe)}"}
    for _ in range(N_TRIALS):
        idx = RNG.choice(len(universe), size=top_k, replace=False)
        cand = {universe[i] for i in idx}
        match = len(cand & expected_set) / max(1, len(expected_set))
        samples.append(min(match, 1.0))
    return _summarize(samples, threshold)


def _calibrate_correlation(values: np.ndarray, threshold: float, *,
                           method: str = "spearman") -> dict[str, Any]:
    """Random-shuffle values along axis 0 and compute self-correlation."""
    samples: list[float] = []
    func = spearmanr if method == "spearman" else pearsonr
    for _ in range(N_TRIALS):
        shuffled = values.copy()
        RNG.shuffle(shuffled)
        try:
            r, _ = func(values, shuffled)
        except Exception:
            r = 0.0
        if math.isnan(r):
            r = 0.0
        samples.append(float(r))
    return _summarize(samples, threshold)


def _calibrate_grouped_curve(df: pd.DataFrame, group_col: str, x_col: str, val_col: str,
                              threshold: float, method: str = "pearson") -> dict[str, Any]:
    """For each group, shuffle the value column then average per-group correlation."""
    samples: list[float] = []
    func = pearsonr if method == "pearson" else spearmanr
    groups = list(df.groupby(group_col))
    if not groups:
        return {"error": "no groups"}
    for _ in range(N_TRIALS):
        group_corrs: list[float] = []
        for _gname, gdf in groups:
            if len(gdf) < 3:
                continue
            ref = gdf.sort_values(x_col)[val_col].to_numpy()
            shuffled = ref.copy()
            RNG.shuffle(shuffled)
            try:
                r, _ = func(ref, shuffled)
            except Exception:
                r = 0.0
            if math.isnan(r):
                r = 0.0
            group_corrs.append(float(r))
        if group_corrs:
            samples.append(float(np.mean(group_corrs)))
    return _summarize(samples, threshold)


def _calibrate_ari(labels: list[Any], threshold: float) -> dict[str, Any]:
    """Random permutation of labels; compute ARI vs original."""
    arr = np.array(labels)
    samples: list[float] = []
    for _ in range(N_TRIALS):
        shuffled = arr.copy()
        RNG.shuffle(shuffled)
        samples.append(float(adjusted_rand_score(arr, shuffled)))
    return _summarize(samples, threshold)


def _summarize(samples: list[float], threshold: float) -> dict[str, Any]:
    if not samples:
        return {"error": "no samples"}
    arr = np.asarray(samples)
    return {
        "n_trials": len(samples),
        "random_mean": float(arr.mean()),
        "random_std": float(arr.std(ddof=0)),
        "random_min": float(arr.min()),
        "random_max": float(arr.max()),
        "random_p99": float(np.percentile(arr, 99)),
        "threshold": float(threshold),
        "z_score": (
            float((threshold - arr.mean()) / arr.std(ddof=0))
            if arr.std(ddof=0) > 0
            else float("inf")
        ),
        "p_random_passes": float((arr >= threshold).mean()),
    }


def _load_tsv(filename: str) -> pd.DataFrame:
    return pd.read_csv(GENERATED_DIR / filename, sep="\t")


def main() -> None:
    ref = json.loads(REFERENCE_JSON.read_text())
    leaves = ref["leaves"]
    results: dict[str, Any] = {}

    # 1. RBO leaves
    rbo_specs = [
        ("squidpy_spatial/result_match/spatial_statistics/top_moran_genes_overlap_threshold",
         "visium_hne_moran_ranked.tsv", "gene"),
        ("squidpy_spatial/result_match/spatial_statistics/geary_rank_overlap_threshold",
         "visium_hne_geary_ranked.tsv", "gene"),
        ("squidpy_spatial/result_match/image_features_segmentation/texture_feature_rank_overlap",
         "visium_hne_image_feature_ranking.tsv", "feature"),
        ("squidpy_spatial/result_match/interaction_reporting/ligrec_top_pair_overlap_threshold",
         "visium_hne_ligrec_ranked.tsv", "interaction_key"),
        ("squidpy_spatial/result_match/spatial_graph_neighbors/nhood_enrichment_rank_overlap",
         "visium_hne_nhood_enrichment_ranked.tsv", "pair_key"),
    ]
    for leaf_id, gen_tsv, col in rbo_specs:
        spec = leaves[leaf_id]
        df = _load_tsv(gen_tsv)
        universe = df[col].astype(str).tolist()
        results[leaf_id] = _calibrate_rbo(
            spec["expected"], spec["top_k"], spec["minimum"], universe=universe
        )

    # 2. overlap_at_k leaves
    for leaf_id in [
        "squidpy_spatial/result_match/spatial_graph_neighbors/positive_neighbor_pair_recovered",
        "squidpy_spatial/result_match/spatial_graph_neighbors/known_spatial_association_recovered",
    ]:
        spec = leaves[leaf_id]
        df = _load_tsv("visium_hne_nhood_enrichment_ranked.tsv")
        universe = df[spec["column"]].astype(str).tolist()
        results[leaf_id] = _calibrate_overlap_at_k(
            spec["expected"], spec["top_k"], spec["minimum"], universe=universe
        )

    # 3. centrality_ranking_overlap (Spearman across 3 columns -> mean)
    centr_spec = leaves[
        "squidpy_spatial/result_match/spatial_graph_neighbors/centrality_ranking_overlap_threshold"
    ]
    df = _load_tsv("visium_hne_centrality_scores.tsv")
    cols = centr_spec["value_columns"]
    samples = []
    for _ in range(N_TRIALS):
        per_col = []
        for c in cols:
            v = df[c].to_numpy()
            shuffled = v.copy()
            RNG.shuffle(shuffled)
            r, _ = spearmanr(v, shuffled)
            if math.isnan(r):
                r = 0.0
            per_col.append(float(r))
        samples.append(float(np.mean(per_col)))
    results[
        "squidpy_spatial/result_match/spatial_graph_neighbors/centrality_ranking_overlap_threshold"
    ] = _summarize(samples, centr_spec["minimum"])

    # 4. interaction_matrix_overlap (Spearman on count column)
    im_spec = leaves[
        "squidpy_spatial/result_match/spatial_graph_neighbors/interaction_matrix_overlap_threshold"
    ]
    df = _load_tsv("visium_hne_interaction_matrix.tsv")
    results[
        "squidpy_spatial/result_match/spatial_graph_neighbors/interaction_matrix_overlap_threshold"
    ] = _calibrate_correlation(
        df[im_spec["value_column"]].to_numpy(), im_spec["minimum"], method="spearman"
    )

    # 5. cooccurrence_curve (grouped Pearson)
    cooc_spec = leaves[
        "squidpy_spatial/result_match/spatial_graph_neighbors/cooccurrence_curve_overlap_threshold"
    ]
    df = _load_tsv("visium_hne_cooccurrence_curves.tsv")
    results[
        "squidpy_spatial/result_match/spatial_graph_neighbors/cooccurrence_curve_overlap_threshold"
    ] = _calibrate_grouped_curve(
        df, cooc_spec["group_column"], cooc_spec["x_column"], cooc_spec["value_column"],
        cooc_spec["minimum"], method="pearson"
    )

    # 6. ripley_curve (grouped Pearson)
    rip_spec = leaves[
        "squidpy_spatial/result_match/spatial_statistics/ripley_curve_overlap_threshold"
    ]
    df = _load_tsv("seqfish_ripley_l_curves.tsv")
    results[
        "squidpy_spatial/result_match/spatial_statistics/ripley_curve_overlap_threshold"
    ] = _calibrate_grouped_curve(
        df, rip_spec["group_column"], rip_spec["x_column"], rip_spec["value_column"],
        rip_spec["minimum"], method="pearson"
    )

    # 7. spatial_localization_pattern + marker_localization_consistency (single-group Pearson)
    for leaf_id in [
        "squidpy_spatial/result_match/spatial_statistics/spatial_localization_pattern_recovered",
        "squidpy_spatial/result_match/interaction_reporting/marker_localization_consistency",
    ]:
        spec = leaves[leaf_id]
        df = _load_tsv("visium_hne_gene_localization.tsv")
        gene = spec["groups"][0]
        sub = df[df[spec["group_column"]] == gene].sort_values(spec["x_column"])
        v = sub[spec["value_column"]].to_numpy()
        if len(v) < 3:
            results[leaf_id] = {"error": "not enough points"}
            continue
        results[leaf_id] = _calibrate_correlation(v, spec["minimum"], method="pearson")

    # 8. image_feature_cluster_alignment (ARI)
    ari_spec = leaves[
        "squidpy_spatial/result_match/image_features_segmentation/image_feature_cluster_alignment_ari"
    ]
    df = _load_tsv("visium_hne_image_feature_clusters.tsv")
    results[
        "squidpy_spatial/result_match/image_features_segmentation/image_feature_cluster_alignment_ari"
    ] = _calibrate_ari(
        df[ari_spec["label_column"]].tolist(), ari_spec["minimum"]
    )

    # 9. olfm1_moran / plp1_moran absolute_tolerance — analytical, not random-permutation
    moran_df = _load_tsv("visium_hne_moran_ranked.tsv")
    moran_pop = moran_df["moran_i"].to_numpy()
    for leaf_id in [
        "squidpy_spatial/result_match/spatial_statistics/olfm1_moran_close",
        "squidpy_spatial/result_match/spatial_statistics/plp1_moran_close",
    ]:
        spec = leaves[leaf_id]
        ref_val = spec["expected"]
        tol = spec["absolute_tolerance"]
        # Random baseline: probability a random gene's Moran I is within tolerance of expected
        within = ((moran_pop >= ref_val - tol) & (moran_pop <= ref_val + tol)).mean()
        results[leaf_id] = {
            "n_trials": len(moran_pop),
            "p_random_passes": float(within),
            "threshold": float(tol),
            "expected_value": float(ref_val),
            "population_mean": float(moran_pop.mean()),
            "population_std": float(moran_pop.std()),
            "population_n": int(len(moran_pop)),
            "note": "p_random_passes = fraction of all genes whose Moran I is within absolute tolerance of expected; lower is better (more discriminative).",
        }

    # 10. Numeric tolerance leaves — analytical
    for leaf_id, spec_key in [
        ("squidpy_spatial/result_match/spatial_graph_neighbors/visium_graph_edge_count_band", None),
        ("squidpy_spatial/result_match/spatial_graph_neighbors/seqfish_graph_edge_count_band", None),
        ("squidpy_spatial/result_match/spatial_statistics/svg_fdr_count_within_band", None),
        ("squidpy_spatial/result_match/image_features_segmentation/segmentation_feature_count_band", None),
        ("squidpy_spatial/result_match/interaction_reporting/ligrec_significant_count_band", None),
    ]:
        spec = leaves[leaf_id]
        results[leaf_id] = {
            "metric": spec["metric"],
            "expected": spec["expected"],
            "tolerance_pct": spec["tolerance_pct"],
            "p_random_passes": "n/a (numeric tolerance — random integer hits within X% only by coincidence; expected count is hidden so cannot be guessed without running pipeline correctly)",
            "calibration_note": "These leaves require the agent to actually compute the right thing; tolerance is for numerical noise, not random guessing.",
        }

    # 11. Shape tolerance leaves — analytical (paper-pinned)
    for leaf_id in [
        "squidpy_spatial/result_match/datasets_and_containers/visium_shape_within_tolerance",
        "squidpy_spatial/result_match/datasets_and_containers/seqfish_shape_within_tolerance",
        "squidpy_spatial/result_match/datasets_and_containers/image_shape_within_tolerance",
        "squidpy_spatial/result_match/image_features_segmentation/image_feature_matrix_dimensionality_band",
    ]:
        spec = leaves[leaf_id]
        results[leaf_id] = {
            "metric": spec["metric"],
            "expected": spec["expected"],
            "tolerance_pct": spec.get("tolerance_pct"),
            "p_random_passes": "n/a (shape match — passes only if agent loaded correct asset)",
            "calibration_note": "These leaves act as gates rather than discriminative checks. Recommend collapsing into one gating leaf per asset.",
        }

    # 12. Set match / nondegenerate / label_vocabulary — analytical
    for leaf_id in [
        "squidpy_spatial/result_match/datasets_and_containers/label_vocabulary_matches_reference",
        "squidpy_spatial/result_match/image_features_segmentation/image_feature_structure_nondegenerate",
    ]:
        spec = leaves[leaf_id]
        results[leaf_id] = {
            "metric": spec["metric"],
            "p_random_passes": "n/a (categorical / structural)",
            "calibration_note": "Categorical match or structural sanity; not a numeric threshold.",
        }

    OUTPUT_JSON.write_text(json.dumps(results, indent=2, sort_keys=True))
    print(f"Wrote {OUTPUT_JSON}")
    _write_markdown(results)
    print(f"Wrote {OUTPUT_MD}")


def _write_markdown(results: dict[str, Any]) -> None:
    lines: list[str] = []
    lines.append("# Squidpy Spatial Result-Match Threshold Calibration")
    lines.append("")
    lines.append(
        "Each numeric threshold in `result_match_reference.json` is benchmarked "
        "against a random-baseline distribution generated from the paper-pinned "
        "reference artifact in `reference_outputs/generated/`. The random "
        "baseline answers the question: *if a model produced random output of the "
        "same shape, what score would it get?* A defensible threshold must lie "
        "well above the random baseline."
    )
    lines.append("")
    lines.append(
        "Random trials per leaf: **{}**. Seed: 20260430.".format(N_TRIALS)
    )
    lines.append("")
    lines.append("## Numeric thresholds — random-baseline calibrated")
    lines.append("")
    lines.append(
        "| Leaf | Metric | Random mean | Random std | Random p99 | Threshold | z-score | p(random passes) |"
    )
    lines.append("|---|---|---|---|---|---|---|---|")
    for leaf_id, r in sorted(results.items()):
        if "random_mean" not in r:
            continue
        short = leaf_id.split("/", 2)[-1]
        z = r["z_score"]
        z_str = f"{z:.2f}" if not math.isinf(z) else "inf"
        lines.append(
            f"| `{short}` | – | {r['random_mean']:.3f} | {r['random_std']:.3f} | "
            f"{r['random_p99']:.3f} | **{r['threshold']:.3f}** | {z_str} | {r['p_random_passes']:.3f} |"
        )
    lines.append("")
    lines.append("**Interpretation guide**:")
    lines.append("")
    lines.append("- `z-score >= 5` and `p(random passes) <= 0.01`: threshold is well-calibrated; reviewer-defensible.")
    lines.append("- `z-score 3-5`: defensible but conservative; document or tighten.")
    lines.append("- `z-score < 3` or `p(random passes) > 0.05`: threshold not adequately above noise; tighten.")
    lines.append("")
    lines.append("## Analytical (non-random-permutation) thresholds")
    lines.append("")
    lines.append("These thresholds are not amenable to permutation calibration "
                 "(numeric counts, exact shape matches, categorical matches). "
                 "They act as gating checks rather than discriminative thresholds. "
                 "See `scoring_methodology.json` for full details.")
    lines.append("")
    for leaf_id, r in sorted(results.items()):
        if "calibration_note" not in r:
            continue
        short = leaf_id.split("/", 2)[-1]
        lines.append(f"- `{short}` ({r.get('metric','-')}): {r['calibration_note']}")
    lines.append("")
    lines.append("## Comparison with PaperBench")
    lines.append("")
    lines.append(
        "PaperBench (Starace et al., 2025) does not publish per-threshold "
        "calibration; its leaves are binary with thresholds set by expert "
        "judgment. SciReplicBench publishes random-baseline calibration for all "
        "discriminative numeric thresholds, providing a stronger peer-review "
        "defense for the chosen cutoffs."
    )
    lines.append("")
    OUTPUT_MD.write_text("\n".join(lines))


if __name__ == "__main__":
    main()
