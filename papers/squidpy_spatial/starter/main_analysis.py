#!/usr/bin/env python3
"""Runnable Squidpy reviewer-path starter for the offline benchmark cache."""

from __future__ import annotations

import csv
import html
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from squidpy_spatial_workflow import generate_references  # noqa: E402

SPATIAL_STATS_PLOT_RELATIVE = "visualizations/spatial_stats_plot.svg"
MARKER_LOCALIZATION_RELATIVE = "visualizations/marker_localization.svg"
REPORT_RELATIVE = "visualizations/report.html"


def _workspace_root() -> Path:
    return Path(os.environ.get("SCIREPLICBENCH_WORKSPACE_ROOT", "/workspace")).resolve()


def _json_dump(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n")


def _read_tsv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return [
            {str(key): str(value) for key, value in row.items() if key is not None}
            for row in csv.DictReader(handle, delimiter="\t")
        ]


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _write_svg_barplot(
    rows: list[dict[str, str]],
    path: Path,
    *,
    title: str,
    label_column: str,
    value_column: str,
    max_bars: int = 12,
) -> None:
    selected = rows[:max_bars]
    values = [_safe_float(row.get(value_column)) for row in selected]
    max_value = max([abs(value) for value in values] + [1.0])
    width = 960
    row_height = 34
    top = 78
    left = 230
    plot_width = 620
    height = top + row_height * max(len(selected), 1) + 44
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<rect width=\"100%\" height=\"100%\" fill=\"#fbf7ef\"/>",
        f'<text x="40" y="44" font-family="Georgia, serif" font-size="26" fill="#1d2b21">{html.escape(title)}</text>',
        '<text x="40" y="66" font-family="Menlo, monospace" font-size="12" fill="#536257">Benchmark-pinned Squidpy artifact</text>',
    ]
    for index, (row, value) in enumerate(zip(selected, values)):
        y = top + index * row_height
        label = html.escape(str(row.get(label_column, ""))[:28])
        bar_width = max(2, int((abs(value) / max_value) * plot_width))
        parts.extend(
            [
                f'<text x="40" y="{y + 18}" font-family="Menlo, monospace" font-size="13" fill="#263128">{label}</text>',
                f'<rect x="{left}" y="{y}" width="{bar_width}" height="22" rx="4" fill="#2f6f4e"/>',
                f'<text x="{left + bar_width + 10}" y="{y + 16}" font-family="Menlo, monospace" font-size="12" fill="#263128">{value:.4g}</text>',
            ]
        )
    parts.append("</svg>")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(parts) + "\n")


def _write_marker_localization_svg(rows: list[dict[str, str]], path: Path) -> None:
    best_by_gene: dict[str, dict[str, str]] = {}
    for row in rows:
        gene = str(row.get("gene", ""))
        if not gene:
            continue
        current = best_by_gene.get(gene)
        if current is None or _safe_float(row.get("mean_expression")) > _safe_float(
            current.get("mean_expression")
        ):
            best_by_gene[gene] = row
    selected = sorted(best_by_gene.values(), key=lambda row: str(row.get("gene", "")))
    _write_svg_barplot(
        selected,
        path,
        title="Marker localization summary",
        label_column="localization_key",
        value_column="mean_expression",
        max_bars=12,
    )


def _write_visualization_report(
    *,
    output_root: Path,
    visualizations: dict[str, str],
    summary: dict[str, Any],
) -> Path:
    manifest_path = output_root / "dataset_manifest.json"
    feature_summary_path = output_root / "image_features" / "feature_summary.json"
    ligrec_summary_path = output_root / "interactions" / "ligrec_summary.json"
    manifest = json.loads(manifest_path.read_text())
    feature_summary = json.loads(feature_summary_path.read_text())
    ligrec_summary = json.loads(ligrec_summary_path.read_text())
    visium_shape = manifest["datasets"]["visium_hne_adata"]["shape"]
    seqfish_shape = manifest["datasets"]["seqfish"]["shape"]
    graph_metrics = summary.get("graph_metrics", {})
    html_text = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Squidpy spatial reviewer-path report</title>
  <style>
    body {{ margin: 32px; background: #fbf7ef; color: #1d2b21; font-family: Georgia, serif; }}
    code, li {{ font-family: Menlo, monospace; }}
    .grid {{ display: grid; gap: 18px; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); }}
    .card {{ border: 1px solid #d8cdb7; border-radius: 16px; padding: 18px; background: #fffdf8; }}
    img {{ max-width: 100%; border: 1px solid #d8cdb7; border-radius: 12px; background: white; }}
  </style>
</head>
<body>
  <h1>Squidpy spatial reviewer-path report</h1>
  <p>This report is generated from benchmark-pinned offline Squidpy caches and links the graph, spatial-statistics, image-feature, ligand-receptor, and visualization artifacts.</p>
  <div class="grid">
    <section class="card">
      <h2>Datasets</h2>
      <ul>
        <li>Visium H&amp;E shape: <code>{html.escape(str(visium_shape))}</code></li>
        <li>seqFISH shape: <code>{html.escape(str(seqfish_shape))}</code></li>
        <li>Squidpy version: <code>{html.escape(str(summary.get("squidpy_version")))}</code></li>
      </ul>
    </section>
    <section class="card">
      <h2>Execution settings</h2>
      <ul>
        <li>Graph metrics: <code>{html.escape(json.dumps(graph_metrics, sort_keys=True))}</code></li>
        <li>Image features: <code>{html.escape(str(feature_summary.get("n_features")))}</code></li>
        <li>Segmentation features: <code>{html.escape(str(feature_summary.get("segmentation_feature_count")))}</code></li>
        <li>Ligand-receptor input pairs: <code>{html.escape(str(ligrec_summary.get("n_input_pairs")))}</code></li>
      </ul>
    </section>
  </div>
  <h2>Visualizations</h2>
  <figure>
    <img src="{html.escape(visualizations['spatial_stats_plot'])}" alt="Top Moran spatial-statistics plot">
    <figcaption>Top Moran-ranked spatial genes from <code>autocorrelation/moran_ranked.tsv</code>.</figcaption>
  </figure>
  <figure>
    <img src="{html.escape(visualizations['marker_localization'])}" alt="Marker localization plot">
    <figcaption>Marker localization summary from <code>spatial_stats/gene_localization.tsv</code>.</figcaption>
  </figure>
</body>
</html>
"""
    report_path = output_root / REPORT_RELATIVE
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(html_text)
    return report_path


def _write_visualizations(output_root: Path, summary: dict[str, Any]) -> dict[str, str]:
    spatial_plot_path = output_root / SPATIAL_STATS_PLOT_RELATIVE
    marker_plot_path = output_root / MARKER_LOCALIZATION_RELATIVE
    moran_rows = _read_tsv_rows(output_root / "autocorrelation" / "moran_ranked.tsv")
    localization_rows = _read_tsv_rows(output_root / "spatial_stats" / "gene_localization.tsv")
    _write_svg_barplot(
        moran_rows,
        spatial_plot_path,
        title="Top Moran spatial-statistics genes",
        label_column="gene",
        value_column="moran_i",
    )
    _write_marker_localization_svg(localization_rows, marker_plot_path)
    visualizations = {
        "spatial_stats_plot": spatial_plot_path.name,
        "marker_localization": marker_plot_path.name,
    }
    report_path = _write_visualization_report(
        output_root=output_root,
        visualizations=visualizations,
        summary=summary,
    )
    return {
        "spatial_stats_plot": str(spatial_plot_path),
        "marker_localization": str(marker_plot_path),
        "report": str(report_path),
    }


def _copy_generated(generated_dir: Path, output_root: Path) -> dict[str, str]:
    mapping = {
        "visium_hne_nhood_enrichment_ranked.tsv": "neighborhood/nhood_enrichment_ranked.tsv",
        "visium_hne_centrality_scores.tsv": "neighborhood/centrality_scores.tsv",
        "visium_hne_cooccurrence_curves.tsv": "neighborhood/cooccurrence_curves.tsv",
        "visium_hne_interaction_matrix.tsv": "neighborhood/interaction_matrix.tsv",
        "visium_hne_moran_ranked.tsv": "autocorrelation/moran_ranked.tsv",
        "visium_hne_geary_ranked.tsv": "autocorrelation/geary_ranked.tsv",
        "seqfish_ripley_l_curves.tsv": "spatial_stats/ripley_curves.tsv",
        "visium_hne_svg_summary.json": "spatial_stats/svg_summary.json",
        "visium_hne_gene_localization.tsv": "spatial_stats/gene_localization.tsv",
        "visium_hne_image_feature_matrix.tsv": "image_features/feature_matrix.tsv",
        "visium_hne_image_feature_ranking.tsv": "image_features/feature_ranking.tsv",
        "visium_hne_image_feature_clusters.tsv": "image_features/feature_clusters.tsv",
        "visium_hne_image_feature_summary.json": "image_features/feature_summary.json",
        "visium_hne_ligrec_ranked.tsv": "interactions/ligrec_ranked.tsv",
        "visium_hne_ligrec_summary.json": "interactions/ligrec_summary.json",
    }
    copied: dict[str, str] = {}
    for source_name, relative_target in mapping.items():
        source = generated_dir / source_name
        target = output_root / relative_target
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied[source_name] = str(target)
    return copied


def _write_dataset_manifest(
    *,
    source_manifest_path: Path,
    summary: dict[str, Any],
    output_root: Path,
) -> Path:
    manifest = json.loads(source_manifest_path.read_text())
    datasets = manifest.setdefault("datasets", {})
    labels = summary.get("labels", {})

    visium = datasets.setdefault("visium_hne_adata", {})
    visium["cluster_key"] = labels.get("visium_cluster_key", "cluster")
    visium["cluster_labels"] = labels.get("visium_cluster_labels", [])

    seqfish = datasets.setdefault("seqfish", {})
    seqfish["cluster_key"] = labels.get("seqfish_cluster_key", "celltype_mapped_refined")
    seqfish["cluster_labels"] = labels.get("seqfish_cluster_labels", [])

    manifest["starter_profile"] = "squidpy_offline_reviewer_path"
    manifest["source_manifest"] = str(source_manifest_path)
    manifest_path = output_root / "dataset_manifest.json"
    _json_dump(manifest, manifest_path)
    return manifest_path


def _write_submission_manifest(
    *,
    workspace_root: Path,
    paper_bundle: Path,
    output_root: Path,
    generated_dir: Path,
    copied: dict[str, str],
    visualizations: dict[str, str],
    summary: dict[str, Any],
) -> Path:
    manifest_path = workspace_root / "output" / "submission_manifest.json"
    payload = {
        "starter_profile": "squidpy_offline_reviewer_path",
        "command": "bash ${SCIREPLICBENCH_WORKSPACE_ROOT:-/workspace}/submission/run.sh",
        "paper_bundle": str(paper_bundle),
        "output_root": str(output_root),
        "generated_work_dir": str(generated_dir),
        "copied_outputs": copied,
        "visualizations": visualizations,
        "graph_metrics": summary.get("graph_metrics", {}),
        "squidpy_version": summary.get("squidpy_version"),
        "notes": [
            "Outputs were generated from benchmark-pinned offline Squidpy caches.",
            "The workflow uses the Visium cluster labels and custom ligand-receptor panel staged in the paper bundle.",
        ],
    }
    _json_dump(payload, manifest_path)
    return manifest_path


def main() -> int:
    workspace_root = _workspace_root()
    paper_bundle = Path(
        os.environ.get("SQUIDPY_PAPER_BUNDLE_DIR", workspace_root / "input" / "paper_bundle")
    )
    output_root = Path(os.environ.get("SQUIDPY_OUTPUT_ROOT", workspace_root / "output" / "agent"))
    generated_dir = output_root / "_squidpy_generated"
    manifest_path = Path(
        os.environ.get(
            "SQUIDPY_DATASET_MANIFEST",
            paper_bundle / "data" / "dataset_manifest.json",
        )
    )
    interactions_path = Path(
        os.environ.get(
            "SQUIDPY_LIGREC_INTERACTIONS",
            paper_bundle / "data" / "ligrec_interactions.tsv",
        )
    )

    output_root.mkdir(parents=True, exist_ok=True)
    summary = generate_references(
        manifest_path=manifest_path,
        interactions_path=interactions_path,
        out_dir=generated_dir,
        n_jobs=int(os.environ.get("SQUIDPY_N_JOBS", "1")),
        nhood_n_perms=int(os.environ.get("SQUIDPY_NHOOD_N_PERMS", "100")),
        cooccurrence_intervals=int(os.environ.get("SQUIDPY_COOCCURRENCE_INTERVALS", "25")),
        ripley_n_simulations=int(os.environ.get("SQUIDPY_RIPLEY_N_SIMULATIONS", "20")),
        ripley_n_observations=int(os.environ.get("SQUIDPY_RIPLEY_N_OBSERVATIONS", "1000")),
        ripley_n_steps=int(os.environ.get("SQUIDPY_RIPLEY_N_STEPS", "25")),
        ligrec_n_perms=int(os.environ.get("SQUIDPY_LIGREC_N_PERMS", "100")),
    )

    copied = _copy_generated(generated_dir, output_root)
    graph_metrics_path = output_root / "spatial_graph_metrics.json"
    _json_dump(summary.get("graph_metrics", {}), graph_metrics_path)
    dataset_manifest_path = _write_dataset_manifest(
        source_manifest_path=manifest_path,
        summary=summary,
        output_root=output_root,
    )
    visualizations = _write_visualizations(output_root, summary)
    submission_manifest_path = _write_submission_manifest(
        workspace_root=workspace_root,
        paper_bundle=paper_bundle,
        output_root=output_root,
        generated_dir=generated_dir,
        copied=copied,
        visualizations=visualizations,
        summary=summary,
    )

    print(f"[squidpy-starter] wrote {dataset_manifest_path}", flush=True)
    print(f"[squidpy-starter] wrote {graph_metrics_path}", flush=True)
    print(f"[squidpy-starter] wrote {submission_manifest_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
