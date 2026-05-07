#!/usr/bin/env python3
"""Generate sealed Squidpy result-match references from pinned offline inputs."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.feature_selection import f_classif
from sklearn.preprocessing import StandardScaler


@dataclass(frozen=True)
class AutocorrReference:
    mode: str
    statistic_column: str
    ranked_path: Path
    top_genes: list[str]


@dataclass(frozen=True)
class ImageReference:
    feature_matrix_path: Path
    feature_clusters_path: Path
    feature_ranking_path: Path
    feature_summary_path: Path
    n_observations: int
    n_features: int
    segmentation_feature_count: int
    cluster_counts: dict[str, int]
    top_features: list[str]


@dataclass(frozen=True)
class LigrecReference:
    ranked_path: Path
    summary_path: Path
    top_interactions: list[str]
    significant_count: int


@dataclass(frozen=True)
class GraphReference:
    label_vocabulary_path: Path
    nhood_ranked_path: Path
    centrality_path: Path
    cooccurrence_path: Path
    interaction_matrix_path: Path
    visium_cluster_labels: list[str]
    seqfish_cluster_labels: list[str]
    top_nhood_pairs: list[str]
    known_spatial_pair: str


@dataclass(frozen=True)
class SpatialPatternReference:
    ripley_path: Path
    svg_summary_path: Path
    localization_path: Path
    svg_fdr_count: int
    ripley_labels: list[str]
    localization_genes: list[str]


def _load_manifest(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError(f"Manifest must be a JSON object: {path}")
    return payload


def _dataset_path(manifest: dict[str, Any], manifest_path: Path, name: str) -> Path:
    datasets = manifest.get("datasets")
    if not isinstance(datasets, dict) or name not in datasets:
        raise KeyError(f"Dataset {name!r} is missing from {manifest_path}.")
    record = datasets[name]
    if not isinstance(record, dict) or "path" not in record:
        raise KeyError(f"Dataset {name!r} record lacks a relative path.")
    return manifest_path.parent / str(record["path"])


def _autocorr_stat_column(frame: pd.DataFrame, mode: str) -> str:
    candidates = ("C", "gearyC") if mode == "geary" else ("I", "moranI")
    for candidate in candidates:
        if candidate in frame.columns:
            return candidate
    raise KeyError(f"Could not find {mode} statistic column in {list(frame.columns)}")


def _rank_autocorr(frame: pd.DataFrame, *, mode: str) -> tuple[pd.DataFrame, str]:
    stat_col = _autocorr_stat_column(frame, mode)
    ranked = frame.copy()
    ranked.index = ranked.index.map(str)
    ranked.insert(0, "gene", ranked.index)
    ranked = ranked.reset_index(drop=True)

    ascending = mode == "geary"
    ranked = ranked.sort_values([stat_col, "gene"], ascending=[ascending, True]).reset_index(
        drop=True
    )
    ranked.insert(0, "rank", range(1, len(ranked) + 1))

    normalized_stat_col = f"{mode}_{stat_col.lower()}"
    if normalized_stat_col != stat_col:
        ranked = ranked.rename(columns={stat_col: normalized_stat_col})
        stat_col = normalized_stat_col
    return ranked, stat_col


def _write_tsv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, sep="\t", index=False, float_format="%.10g")


def _cluster_labels(adata: Any, cluster_key: str) -> list[str]:
    labels = adata.obs[cluster_key]
    if hasattr(labels, "cat"):
        return [str(label) for label in labels.cat.categories]
    return sorted(str(label) for label in pd.Series(labels).dropna().unique())


def _pair_key(left: str, right: str, *, directed: bool = False) -> str:
    if directed:
        return f"{left}->{right}"
    first, second = sorted([str(left), str(right)])
    return f"{first}|{second}"


def _matrix_long_frame(
    matrix: np.ndarray,
    labels: list[str],
    *,
    value_column: str,
    directed: bool = False,
    include_diagonal: bool = True,
) -> pd.DataFrame:
    values = np.asarray(matrix, dtype=float)
    rows: list[dict[str, Any]] = []
    for i, left in enumerate(labels):
        for j, right in enumerate(labels):
            if not directed and j < i:
                continue
            if not include_diagonal and i == j:
                continue
            rows.append(
                {
                    "cluster_1": left,
                    "cluster_2": right,
                    "pair_key": _pair_key(left, right, directed=directed),
                    value_column: float(values[i, j]),
                }
            )
    return pd.DataFrame(rows)


def _read_interactions(path: Path, *, genes: set[str]) -> pd.DataFrame:
    frame = pd.read_csv(path, sep="\t")
    required = {"source", "target"}
    if not required.issubset(frame.columns):
        raise ValueError(f"{path} must contain source and target columns.")
    frame = frame.copy()
    frame["source"] = frame["source"].astype(str)
    frame["target"] = frame["target"].astype(str)
    present = frame["source"].isin(genes) & frame["target"].isin(genes)
    filtered = frame.loc[present, ["source", "target"]].reset_index(drop=True)
    if filtered.empty:
        raise ValueError("No custom ligand-receptor pairs are present in the AnnData var_names.")
    return filtered


def _gene_value(frame: pd.DataFrame, *, gene: str, value_column: str) -> float | None:
    normalized = frame["gene"].astype(str).str.upper()
    hits = frame.loc[normalized == gene.upper(), value_column]
    if hits.empty:
        return None
    return float(hits.iloc[0])


def _generate_autocorr_reference(
    adata: Any,
    *,
    mode: str,
    out_dir: Path,
    n_jobs: int,
) -> AutocorrReference:
    import squidpy as sq

    frame = sq.gr.spatial_autocorr(
        adata,
        mode=mode,
        genes=None,
        n_perms=None,
        n_jobs=n_jobs,
        copy=True,
        show_progress_bar=True,
    )
    if frame is None:
        frame = adata.uns["gearyC" if mode == "geary" else "moranI"]
    ranked, stat_col = _rank_autocorr(frame, mode=mode)
    path = out_dir / f"visium_hne_{mode}_ranked.tsv"
    _write_tsv(ranked, path)
    return AutocorrReference(
        mode=mode,
        statistic_column=stat_col,
        ranked_path=path,
        top_genes=ranked["gene"].astype(str).head(20).tolist(),
    )


def _generate_graph_reference(
    visium: Any,
    seqfish: Any,
    *,
    out_dir: Path,
    n_jobs: int,
    nhood_n_perms: int,
    cooccurrence_intervals: int,
) -> GraphReference:
    import squidpy as sq

    visium_key = "cluster"
    seqfish_key = "celltype_mapped_refined"
    visium_labels = _cluster_labels(visium, visium_key)
    seqfish_labels = _cluster_labels(seqfish, seqfish_key)

    label_payload = {
        "datasets": {
            "visium_hne_adata": {
                "cluster_key": visium_key,
                "cluster_labels": visium_labels,
            },
            "seqfish": {
                "cluster_key": seqfish_key,
                "cluster_labels": seqfish_labels,
            },
        }
    }
    label_vocabulary_path = out_dir / "squidpy_label_vocabulary.json"
    label_vocabulary_path.write_text(json.dumps(label_payload, indent=2) + "\n")

    print("[squidpy-ref] computing Visium neighborhood enrichment", flush=True)
    nhood_zscore, nhood_count = sq.gr.nhood_enrichment(
        visium,
        cluster_key=visium_key,
        n_perms=nhood_n_perms,
        seed=1,
        copy=True,
        n_jobs=n_jobs,
        show_progress_bar=True,
    )
    nhood_frame = _matrix_long_frame(
        np.nan_to_num(nhood_zscore, nan=0.0, posinf=1e9, neginf=-1e9),
        visium_labels,
        value_column="zscore",
        directed=False,
        include_diagonal=False,
    )
    count_frame = _matrix_long_frame(
        nhood_count,
        visium_labels,
        value_column="count",
        directed=False,
        include_diagonal=False,
    )[["pair_key", "count"]]
    nhood_frame = nhood_frame.merge(count_frame, on="pair_key", how="left")
    nhood_frame = nhood_frame.sort_values(
        ["zscore", "pair_key"],
        ascending=[False, True],
    ).reset_index(drop=True)
    nhood_frame.insert(0, "rank", range(1, len(nhood_frame) + 1))
    nhood_ranked_path = out_dir / "visium_hne_nhood_enrichment_ranked.tsv"
    _write_tsv(nhood_frame, nhood_ranked_path)

    print("[squidpy-ref] computing Visium centrality scores", flush=True)
    centrality = sq.gr.centrality_scores(
        visium,
        cluster_key=visium_key,
        copy=True,
        n_jobs=n_jobs,
        show_progress_bar=True,
    )
    if centrality is None:
        raise RuntimeError("centrality_scores returned None with copy=True.")
    centrality = centrality.copy()
    centrality.insert(0, "cluster", centrality.index.astype(str))
    centrality_path = out_dir / "visium_hne_centrality_scores.tsv"
    _write_tsv(centrality.reset_index(drop=True), centrality_path)

    print("[squidpy-ref] computing Visium interaction matrix", flush=True)
    interaction = sq.gr.interaction_matrix(
        visium,
        cluster_key=visium_key,
        normalized=False,
        copy=True,
    )
    if interaction is None:
        raise RuntimeError("interaction_matrix returned None with copy=True.")
    interaction_frame = _matrix_long_frame(
        interaction,
        visium_labels,
        value_column="count",
        directed=False,
        include_diagonal=True,
    )
    interaction_matrix_path = out_dir / "visium_hne_interaction_matrix.tsv"
    _write_tsv(interaction_frame, interaction_matrix_path)

    print("[squidpy-ref] computing Visium co-occurrence curves", flush=True)
    cooccurrence, intervals = sq.gr.co_occurrence(
        visium,
        cluster_key=visium_key,
        interval=cooccurrence_intervals,
        copy=True,
        n_jobs=n_jobs,
        show_progress_bar=True,
    )
    cooccurrence_rows: list[dict[str, Any]] = []
    for i, left in enumerate(visium_labels):
        for j, right in enumerate(visium_labels):
            pair_key = _pair_key(left, right, directed=True)
            for radius_index, value in enumerate(cooccurrence[i, j, :]):
                cooccurrence_rows.append(
                    {
                        "cluster_1": left,
                        "cluster_2": right,
                        "pair_key": pair_key,
                        "radius_index": radius_index,
                        "radius_start": float(intervals[radius_index]),
                        "radius_end": float(intervals[radius_index + 1]),
                        "cooccurrence": float(value),
                    }
                )
    cooccurrence_path = out_dir / "visium_hne_cooccurrence_curves.tsv"
    _write_tsv(pd.DataFrame(cooccurrence_rows), cooccurrence_path)

    return GraphReference(
        label_vocabulary_path=label_vocabulary_path,
        nhood_ranked_path=nhood_ranked_path,
        centrality_path=centrality_path,
        cooccurrence_path=cooccurrence_path,
        interaction_matrix_path=interaction_matrix_path,
        visium_cluster_labels=visium_labels,
        seqfish_cluster_labels=seqfish_labels,
        top_nhood_pairs=nhood_frame["pair_key"].astype(str).head(20).tolist(),
        known_spatial_pair=str(nhood_frame["pair_key"].iloc[0]),
    )


def _gene_expression_vector(adata: Any, gene: str) -> np.ndarray:
    if gene not in adata.var_names:
        raise KeyError(f"Gene {gene!r} is missing from AnnData.var_names.")
    values = adata[:, [gene]].X
    if hasattr(values, "toarray"):
        values = values.toarray()
    return np.asarray(values, dtype=float).reshape(-1)


def _generate_spatial_pattern_reference(
    visium: Any,
    seqfish: Any,
    *,
    moran_frame: pd.DataFrame,
    out_dir: Path,
    ripley_n_simulations: int,
    ripley_n_observations: int,
    ripley_n_steps: int,
) -> SpatialPatternReference:
    import squidpy as sq

    print("[squidpy-ref] computing seqFISH Ripley L curves", flush=True)
    seqfish_key = "celltype_mapped_refined"
    ripley = sq.gr.ripley(
        seqfish,
        cluster_key=seqfish_key,
        mode="L",
        n_simulations=ripley_n_simulations,
        n_observations=ripley_n_observations,
        n_steps=ripley_n_steps,
        seed=1,
        copy=True,
    )
    ripley_frame = ripley["L_stat"].copy()
    ripley_frame = ripley_frame.rename(
        columns={
            "bins": "radius",
            seqfish_key: "label",
            "stats": "ripley_l",
        }
    )
    ripley_frame["label"] = ripley_frame["label"].astype(str)
    ripley_frame = ripley_frame.sort_values(["label", "radius"]).reset_index(drop=True)
    ripley_frame["radius_index"] = ripley_frame.groupby("label").cumcount()
    ripley_path = out_dir / "seqfish_ripley_l_curves.tsv"
    _write_tsv(ripley_frame[["label", "radius_index", "radius", "ripley_l"]], ripley_path)

    fdr_column = "pval_norm_fdr_bh"
    svg_fdr_count = int((pd.to_numeric(moran_frame[fdr_column], errors="coerce") <= 0.05).sum())
    svg_summary = {
        "method": "sq.gr.spatial_autocorr(mode='moran', corr_method='fdr_bh')",
        "fdr_column": fdr_column,
        "fdr_threshold": 0.05,
        "significant_gene_count": svg_fdr_count,
    }
    svg_summary_path = out_dir / "visium_hne_svg_summary.json"
    svg_summary_path.write_text(json.dumps(svg_summary, indent=2) + "\n")

    localization_genes = ["Olfm1", "Ttr", "Nrgn", "Plp1"]
    visium_key = "cluster"
    cluster_labels = _cluster_labels(visium, visium_key)
    localization_rows: list[dict[str, Any]] = []
    clusters = visium.obs[visium_key].astype(str).to_numpy()
    for gene in localization_genes:
        expression = _gene_expression_vector(visium, gene)
        for cluster in cluster_labels:
            mask = clusters == cluster
            mean_expression = float(expression[mask].mean()) if mask.any() else 0.0
            localization_rows.append(
                {
                    "gene": gene,
                    "cluster": cluster,
                    "localization_key": f"{gene}|{cluster}",
                    "mean_expression": mean_expression,
                }
            )
    localization_path = out_dir / "visium_hne_gene_localization.tsv"
    _write_tsv(pd.DataFrame(localization_rows), localization_path)

    return SpatialPatternReference(
        ripley_path=ripley_path,
        svg_summary_path=svg_summary_path,
        localization_path=localization_path,
        svg_fdr_count=svg_fdr_count,
        ripley_labels=_cluster_labels(seqfish, seqfish_key),
        localization_genes=localization_genes,
    )


def _generate_image_reference(
    adata: Any,
    image: Any,
    *,
    out_dir: Path,
    n_jobs: int,
) -> ImageReference:
    import squidpy as sq

    print("[squidpy-ref] segmenting Visium H&E image with watershed", flush=True)
    sq.im.segment(
        image,
        layer="image",
        method="watershed",
        channel=0,
        layer_added="segmented_watershed",
        copy=False,
    )

    features_kwargs = {
        "histogram": {"channels": [0], "bins": 4},
        "segmentation": {
            "label_layer": "segmented_watershed",
            "props": ["label", "area", "mean_intensity"],
            "channels": [0],
        },
        "summary": {"channels": [0, 1, 2]},
        "texture": {
            "channels": [0],
            "props": ["contrast", "homogeneity"],
            "distances": [1],
            "angles": [0],
        },
    }

    print("[squidpy-ref] calculating image features for all Visium spots", flush=True)
    features = sq.im.calculate_image_features(
        adata,
        image,
        layer="image",
        features=["histogram", "segmentation", "summary", "texture"],
        features_kwargs=features_kwargs,
        copy=True,
        n_jobs=n_jobs,
        show_progress_bar=True,
    )
    if features is None:
        raise RuntimeError("calculate_image_features returned None with copy=True.")
    features.index = features.index.astype(str)
    features = features.sort_index()

    feature_matrix = features.copy()
    feature_matrix.insert(0, "obs_id", feature_matrix.index)
    feature_matrix_path = out_dir / "visium_hne_image_feature_matrix.tsv"
    _write_tsv(feature_matrix, feature_matrix_path)

    numeric = features.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    scaled = StandardScaler().fit_transform(numeric)
    clusters = KMeans(n_clusters=5, random_state=0, n_init=10).fit_predict(scaled)
    cluster_series = pd.Series([f"image_cluster_{value}" for value in clusters], index=features.index)
    cluster_counts = {
        str(key): int(value)
        for key, value in cluster_series.value_counts().sort_index().items()
    }
    clusters_frame = pd.DataFrame(
        {"obs_id": cluster_series.index, "image_cluster": cluster_series.values}
    )
    feature_clusters_path = out_dir / "visium_hne_image_feature_clusters.tsv"
    _write_tsv(clusters_frame, feature_clusters_path)

    labels = adata.obs.loc[features.index, "cluster"].astype(str)
    f_values, p_values = f_classif(numeric, labels)
    ranking = pd.DataFrame(
        {
            "feature": numeric.columns.astype(str),
            "f_statistic": f_values,
            "p_value": p_values,
        }
    ).replace([np.inf, -np.inf], np.nan)
    ranking["f_statistic"] = ranking["f_statistic"].fillna(0.0)
    ranking["p_value"] = ranking["p_value"].fillna(1.0)
    ranking = ranking.sort_values(
        ["f_statistic", "feature"],
        ascending=[False, True],
    ).reset_index(drop=True)
    ranking.insert(0, "rank", range(1, len(ranking) + 1))
    feature_ranking_path = out_dir / "visium_hne_image_feature_ranking.tsv"
    _write_tsv(ranking, feature_ranking_path)

    segmentation_feature_count = sum(
        1 for column in features.columns if str(column).startswith("segmentation_")
    )
    feature_summary = {
        "n_observations": int(features.shape[0]),
        "n_features": int(features.shape[1]),
        "segmentation_feature_count": int(segmentation_feature_count),
        "cluster_counts": cluster_counts,
        "top10_features_by_cluster_f": ranking["feature"].astype(str).head(10).tolist(),
        "recipe": {
            "features": ["histogram", "segmentation", "summary", "texture"],
            "segmentation": "sq.im.segment(..., method='watershed', channel=0)",
            "spot_scale": 1.0,
            "kmeans_clusters": 5,
            "kmeans_random_state": 0,
        },
    }
    feature_summary_path = out_dir / "visium_hne_image_feature_summary.json"
    feature_summary_path.write_text(json.dumps(feature_summary, indent=2) + "\n")

    return ImageReference(
        feature_matrix_path=feature_matrix_path,
        feature_clusters_path=feature_clusters_path,
        feature_ranking_path=feature_ranking_path,
        feature_summary_path=feature_summary_path,
        n_observations=int(features.shape[0]),
        n_features=int(features.shape[1]),
        segmentation_feature_count=int(segmentation_feature_count),
        cluster_counts=cluster_counts,
        top_features=ranking["feature"].astype(str).head(10).tolist(),
    )


def _flatten_ligrec_result(result: Mapping[str, pd.DataFrame]) -> pd.DataFrame:
    means = result["means"]
    pvalues = result["pvalues"]
    mean_rows = means.stack(["cluster_1", "cluster_2"]).reset_index()
    mean_rows.columns = ["source", "target", "cluster_1", "cluster_2", "mean"]
    pvalue_rows = pvalues.stack(["cluster_1", "cluster_2"]).reset_index()
    pvalue_rows.columns = ["source", "target", "cluster_1", "cluster_2", "pvalue"]
    merged = mean_rows.merge(
        pvalue_rows,
        on=["source", "target", "cluster_1", "cluster_2"],
        how="left",
    )
    merged["source"] = merged["source"].astype(str)
    merged["target"] = merged["target"].astype(str)
    merged["interaction_key"] = (
        merged["source"]
        + "|"
        + merged["target"]
        + "|"
        + merged["cluster_1"].astype(str)
        + "->"
        + merged["cluster_2"].astype(str)
    )
    merged["pvalue"] = pd.to_numeric(merged["pvalue"], errors="coerce")
    merged["mean"] = pd.to_numeric(merged["mean"], errors="coerce").fillna(0.0)
    merged = merged.sort_values(
        ["mean", "interaction_key"],
        ascending=[False, True],
    ).reset_index(drop=True)
    merged.insert(0, "rank", range(1, len(merged) + 1))
    return merged


def _generate_ligrec_reference(
    adata: Any,
    *,
    interactions_path: Path,
    out_dir: Path,
    n_jobs: int,
    n_perms: int,
) -> LigrecReference:
    import squidpy as sq

    interactions = _read_interactions(interactions_path, genes=set(map(str, adata.var_names)))
    print(
        f"[squidpy-ref] running custom ligrec for {len(interactions)} public pairs",
        flush=True,
    )
    result = sq.gr.ligrec(
        adata,
        cluster_key="cluster",
        interactions=interactions,
        threshold=0.01,
        n_perms=n_perms,
        seed=1,
        copy=True,
        use_raw=False,
        n_jobs=n_jobs,
    )
    ranked = _flatten_ligrec_result(result)
    ranked_path = out_dir / "visium_hne_ligrec_ranked.tsv"
    _write_tsv(ranked, ranked_path)

    significant = ranked["pvalue"].notna() & (ranked["pvalue"] <= 0.05)
    summary = {
        "cluster_key": "cluster",
        "custom_interactions": str(interactions_path),
        "n_input_pairs": int(len(interactions)),
        "n_perms": int(n_perms),
        "significant_count_p_le_0_05": int(significant.sum()),
        "rank_metric": "mean descending",
    }
    summary_path = out_dir / "visium_hne_ligrec_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n")
    return LigrecReference(
        ranked_path=ranked_path,
        summary_path=summary_path,
        top_interactions=ranked["interaction_key"].astype(str).head(20).tolist(),
        significant_count=int(significant.sum()),
    )


def generate_references(
    *,
    manifest_path: Path,
    interactions_path: Path,
    out_dir: Path,
    n_jobs: int,
    nhood_n_perms: int,
    cooccurrence_intervals: int,
    ripley_n_simulations: int,
    ripley_n_observations: int,
    ripley_n_steps: int,
    ligrec_n_perms: int,
) -> dict[str, Any]:
    import squidpy as sq

    manifest = _load_manifest(manifest_path)
    visium_path = _dataset_path(manifest, manifest_path, "visium_hne_adata")
    seqfish_path = _dataset_path(manifest, manifest_path, "seqfish")

    print(f"[squidpy-ref] loading Visium AnnData: {visium_path}", flush=True)
    visium = sq.datasets.visium_hne_adata(path=visium_path)
    print(f"[squidpy-ref] loading seqFISH AnnData: {seqfish_path}", flush=True)
    seqfish = sq.datasets.seqfish(path=seqfish_path)
    print("[squidpy-ref] loading Visium H&E image", flush=True)
    image = sq.datasets.visium_hne_image(
        path=_dataset_path(manifest, manifest_path, "visium_hne_image")
    )

    print("[squidpy-ref] computing Visium spatial graph", flush=True)
    sq.gr.spatial_neighbors(visium, coord_type="grid", n_neighs=6, n_rings=1)
    visium_edges = int(visium.obsp["spatial_connectivities"].nnz)

    print("[squidpy-ref] computing seqFISH spatial graph", flush=True)
    sq.gr.spatial_neighbors(seqfish, coord_type="generic", n_neighs=6)
    seqfish_edges = int(seqfish.obsp["spatial_connectivities"].nnz)

    print("[squidpy-ref] computing Moran reference", flush=True)
    moran = _generate_autocorr_reference(
        visium,
        mode="moran",
        out_dir=out_dir,
        n_jobs=n_jobs,
    )
    moran_frame = pd.read_csv(moran.ranked_path, sep="\t")

    print("[squidpy-ref] computing Geary reference", flush=True)
    geary = _generate_autocorr_reference(
        visium,
        mode="geary",
        out_dir=out_dir,
        n_jobs=n_jobs,
    )

    graph_reference = _generate_graph_reference(
        visium,
        seqfish,
        out_dir=out_dir,
        n_jobs=n_jobs,
        nhood_n_perms=nhood_n_perms,
        cooccurrence_intervals=cooccurrence_intervals,
    )

    spatial_pattern_reference = _generate_spatial_pattern_reference(
        visium,
        seqfish,
        moran_frame=moran_frame,
        out_dir=out_dir,
        ripley_n_simulations=ripley_n_simulations,
        ripley_n_observations=ripley_n_observations,
        ripley_n_steps=ripley_n_steps,
    )

    image_reference = _generate_image_reference(
        visium,
        image,
        out_dir=out_dir,
        n_jobs=n_jobs,
    )

    ligrec_reference = _generate_ligrec_reference(
        visium,
        interactions_path=interactions_path,
        out_dir=out_dir,
        n_jobs=n_jobs,
        n_perms=ligrec_n_perms,
    )

    summary = {
        "schema_version": 1,
        "generator": "scripts/generate_squidpy_reference_outputs.py",
        "squidpy_version": sq.__version__,
        "manifest": str(manifest_path),
        "graph_metrics": {
            "visium": {
                "spatial_neighbors": {
                    "coord_type": "grid",
                    "n_neighs": 6,
                    "n_rings": 1,
                    "edges": visium_edges,
                }
            },
            "seqfish": {
                "spatial_neighbors": {
                    "coord_type": "generic",
                    "n_neighs": 6,
                    "edges": seqfish_edges,
                }
            },
        },
        "gene_selection": {
            "attr": "X",
            "genes_argument": None,
            "squidpy_default": "Use adata.var['highly_variable'] when present.",
            "highly_variable_count": int(visium.var["highly_variable"].sum())
            if "highly_variable" in visium.var
            else None,
        },
        "labels": {
            "vocabulary_json": graph_reference.label_vocabulary_path.name,
            "visium_cluster_key": "cluster",
            "visium_cluster_labels": graph_reference.visium_cluster_labels,
            "seqfish_cluster_key": "celltype_mapped_refined",
            "seqfish_cluster_labels": graph_reference.seqfish_cluster_labels,
        },
        "neighborhood": {
            "nhood_ranked_tsv": graph_reference.nhood_ranked_path.name,
            "centrality_tsv": graph_reference.centrality_path.name,
            "cooccurrence_tsv": graph_reference.cooccurrence_path.name,
            "interaction_matrix_tsv": graph_reference.interaction_matrix_path.name,
            "nhood_n_perms": int(nhood_n_perms),
            "cooccurrence_intervals": int(cooccurrence_intervals),
            "top20_nhood_pairs": graph_reference.top_nhood_pairs,
            "known_spatial_pair": graph_reference.known_spatial_pair,
        },
        "autocorrelation": {
            "moran": {
                "ranked_tsv": moran.ranked_path.name,
                "ranking_direction": "descending",
                "statistic_column": moran.statistic_column,
                "top20_genes": moran.top_genes,
                "olfm1": _gene_value(
                    moran_frame,
                    gene="Olfm1",
                    value_column=moran.statistic_column,
                ),
                "plp1": _gene_value(
                    moran_frame,
                    gene="Plp1",
                    value_column=moran.statistic_column,
                ),
            },
            "geary": {
                "ranked_tsv": geary.ranked_path.name,
                "ranking_direction": "ascending",
                "statistic_column": geary.statistic_column,
                "top20_genes": geary.top_genes,
            },
        },
        "spatial_patterns": {
            "ripley_tsv": spatial_pattern_reference.ripley_path.name,
            "svg_summary_json": spatial_pattern_reference.svg_summary_path.name,
            "localization_tsv": spatial_pattern_reference.localization_path.name,
            "ripley_mode": "L",
            "ripley_n_simulations": int(ripley_n_simulations),
            "ripley_n_observations": int(ripley_n_observations),
            "ripley_n_steps": int(ripley_n_steps),
            "ripley_labels": spatial_pattern_reference.ripley_labels,
            "svg_fdr_count": spatial_pattern_reference.svg_fdr_count,
            "localization_genes": spatial_pattern_reference.localization_genes,
        },
        "image_features": {
            "feature_matrix_tsv": image_reference.feature_matrix_path.name,
            "feature_clusters_tsv": image_reference.feature_clusters_path.name,
            "feature_ranking_tsv": image_reference.feature_ranking_path.name,
            "feature_summary_json": image_reference.feature_summary_path.name,
            "n_observations": image_reference.n_observations,
            "n_features": image_reference.n_features,
            "segmentation_feature_count": image_reference.segmentation_feature_count,
            "cluster_counts": image_reference.cluster_counts,
            "top10_features_by_cluster_f": image_reference.top_features,
            "recipe": {
                "features": ["histogram", "segmentation", "summary", "texture"],
                "segmentation": "sq.im.segment(..., method='watershed', channel=0)",
                "spot_scale": 1.0,
                "kmeans_clusters": 5,
                "kmeans_random_state": 0,
            },
        },
        "ligrec": {
            "ranked_tsv": ligrec_reference.ranked_path.name,
            "summary_json": ligrec_reference.summary_path.name,
            "custom_interactions": str(interactions_path),
            "top20_interactions": ligrec_reference.top_interactions,
            "significant_count_p_le_0_05": ligrec_reference.significant_count,
        },
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    summary_path = out_dir / "squidpy_spatial_reference_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n")
    print(f"[squidpy-ref] wrote {summary_path}", flush=True)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("papers/squidpy_spatial/data/dataset_manifest.json"),
        help="Benchmark-pinned Squidpy dataset manifest.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("papers/squidpy_spatial/reference_outputs/generated"),
        help="Sealed scorer-only reference output directory.",
    )
    parser.add_argument("--n-jobs", type=int, default=1)
    parser.add_argument("--nhood-n-perms", type=int, default=100)
    parser.add_argument("--cooccurrence-intervals", type=int, default=25)
    parser.add_argument("--ripley-n-simulations", type=int, default=20)
    parser.add_argument("--ripley-n-observations", type=int, default=1000)
    parser.add_argument("--ripley-n-steps", type=int, default=25)
    parser.add_argument(
        "--interactions",
        type=Path,
        default=Path("papers/squidpy_spatial/data/ligrec_interactions.tsv"),
        help="Public custom ligand-receptor panel with source and target columns.",
    )
    parser.add_argument("--ligrec-n-perms", type=int, default=100)
    args = parser.parse_args()

    generate_references(
        manifest_path=args.manifest,
        interactions_path=args.interactions,
        out_dir=args.out_dir,
        n_jobs=args.n_jobs,
        nhood_n_perms=args.nhood_n_perms,
        cooccurrence_intervals=args.cooccurrence_intervals,
        ripley_n_simulations=args.ripley_n_simulations,
        ripley_n_observations=args.ripley_n_observations,
        ripley_n_steps=args.ripley_n_steps,
        ligrec_n_perms=args.ligrec_n_perms,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
