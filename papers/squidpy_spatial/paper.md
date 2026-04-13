# Squidpy: A Scalable Framework for Spatial Omics Analysis

## Scope

This benchmark package targets Palla et al. *Nature Methods* (2022), DOI `10.1038/s41592-021-01358-2`, which presents **Squidpy** as a Python-native framework for spatial omics analysis. Unlike the authored papers in this benchmark suite, Squidpy serves as the **external third-party anchor**: it provides a conflict-of-interest firewall, a modern scverse-native codebase, and a spatial-analysis modality that is orthogonal to both the Inspiration4 multi-ome paper and the GeneLab benchmark.

SciReplicBench should not ask agents to re-implement Squidpy internals. Instead, the task is to **reproduce the analytical workflow demonstrated by the paper** using the official Squidpy library and its public built-in datasets. The benchmark therefore measures whether an agent can:

- load the correct built-in datasets and attached tissue images,
- construct the correct spatial graphs for grid-like and generic-coordinate data,
- compute the core neighborhood, centrality, co-occurrence, autocorrelation, and Ripley statistics highlighted by the paper,
- extract image-derived features and relate them back to transcriptomic structure,
- produce structured outputs that can be re-run in the fresh reproducer container.

The benchmark is framed as **computational reproducibility of a published spatial-omics analysis toolkit**, not a software-engineering reimplementation challenge.

## Benchmark Datasets

To keep the external anchor fully public and reviewer-runnable, the benchmark should use Squidpy's official demo datasets rather than hidden local data. The most useful combinations are:

- `sq.datasets.visium_hne_adata()` plus `sq.datasets.visium_hne_image()`
- `sq.datasets.seqfish()`
- one additional small built-in dataset for a cell-level graph task if needed, such as `sq.datasets.imc()` or `sq.datasets.slideseqv2()`

These datasets give the benchmark both major coordinate regimes that Squidpy is designed for:

- **grid-like spot data** for Visium,
- **generic spatial coordinates** for single-cell imaging or in situ assays.

The Visium H&E mouse-brain example is especially useful because it includes a high-resolution histology image and preannotated clusters. The docs expose several concrete reference values for it, including a dataset shape of **2688 observations × 18,078 genes** and a tissue image shape of **11,757 × 11,291 pixels**. The seqFISH demo adds a cell-level generic-coordinate dataset with **19,416 observations × 351 genes**, which is a good substrate for neighborhood statistics and co-occurrence analyses.

For grading, these shape- and size-based checks should be tied to a **benchmark-pinned dataset manifest** created during data-prep, not to whichever Squidpy version happens to be installed in an unconstrained environment. The benchmark can cite the public tutorial values as anchors, but the scorer should compare against the pinned manifest distributed with the benchmark.

## Benchmark-Target Pipeline

### 1. Dataset loading and spatial containers

The agent should correctly load one or more official Squidpy datasets, preserve the `obsm["spatial"]` coordinates, retain preannotated cluster or cell-type labels where provided, and attach image data through `squidpy.im.ImageContainer` when relevant. The benchmark should give credit for explicit handling of both spot-based and generic-coordinate data, because the paper emphasizes technology-agnostic infrastructure rather than a single assay.

### 2. Spatial graph construction

The first analytical step is to build a spatial-neighbor graph from the coordinates. The paper and docs emphasize that neighborhood definition depends on assay geometry:

- grid-aware graphs for Visium-like data,
- generic-coordinate or Delaunay-based graphs for cell-level data.

The benchmark should therefore reward correct graph construction choices and penalize analyses that ignore the geometry of the dataset.

### 3. Neighborhood enrichment, interaction, and co-occurrence

Squidpy's graph layer is built around cell-type or cluster relationships in space. Benchmark agents should compute:

- **neighborhood enrichment** z-scores,
- **interaction matrices** or equivalent cluster-contact summaries,
- **centrality scores** for cluster positions in the spatial graph,
- **co-occurrence probabilities** across increasing spatial radii.

These outputs test whether the agent understands the difference between adjacency on the graph and broader distance-dependent spatial association.

### 4. Spatial statistics

The toolkit paper also highlights spatial statistics that operate on genes or cluster point patterns. The benchmark should therefore include:

- **Moran's I** and/or **Geary's C** for spatially variable genes,
- **Ripley's statistics** for clustered-versus-dispersed point patterns,
- ranked outputs and multiple-testing correction where appropriate.

The official Squidpy tutorials provide useful anchors for hidden-reference grading. For example, in the Visium H&E tutorial, top Moran genes include `Olfm1`, `Plp1`, `Itpka`, and `Snap25`, and the displayed Moran's I values for `Olfm1` and `Plp1` are approximately `0.763` and `0.748`, respectively. Those are strong candidates for numeric result-match leaves.

### 5. Image features and segmentation

One of the main reasons Squidpy makes a good external anchor is that it combines transcriptomics with image analysis. The benchmark should therefore expect the agent to:

- load the histology image,
- compute one or more image-feature families such as summary, texture, or segmentation features,
- join those features back to observations,
- compare image-derived clusters or summaries with transcriptomic clusters.

This is the most distinctive part of the Squidpy paper relative to the rest of the benchmark suite. It should be preserved even if the benchmark uses small built-in images rather than very large custom slides.

### 6. Ligand-receptor and visualization outputs

The paper positions Squidpy as an extensible interface layer that can wrap downstream analyses such as ligand-receptor inference. In the benchmark, this should remain a visible but not dominant component. The agent should generate at least one interaction-style output and produce the standard spatial visualizations needed to inspect whether the analysis behaved sensibly.

## Key Benchmark Findings To Target

The external-anchor rubric should focus on outputs that are specific enough to be meaningful but not so brittle that the benchmark degenerates into screenshot matching:

- correct built-in dataset selection and loading,
- geometry-aware spatial-neighbor graph construction,
- recovery of known neighborhood enrichment patterns on the benchmark dataset,
- recovery of top spatially variable genes on Visium H&E,
- sensible Ripley and co-occurrence patterns for structured cell-type annotations,
- image-feature outputs that are informative but not identical to transcriptomic clustering,
- one interaction-style analysis that writes a ranked result table.

These outputs are especially attractive for grading because they can be evaluated with numeric comparators such as overlap@k, rank-biased overlap, ARI, NMI, or value tolerances on known statistics.

## Benchmark Boundaries

The v1 benchmark should intentionally avoid several tempting but distracting expansions:

- no reimplementation of Squidpy internals,
- no napari/interactive GUI requirements,
- no massive custom spatial datasets outside the official built-ins,
- no dependence on GPUs,
- no image-only grading without a structured numeric summary.

The point of Paper 2 is to test whether an agent can navigate a public, modern, third-party spatial-omics workflow with graph statistics and image analysis. It should feel like a real external methods-paper reproduction task, not a generic Scanpy exercise with a spatial plot bolted on.
