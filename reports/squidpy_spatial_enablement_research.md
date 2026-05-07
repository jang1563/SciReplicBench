# Squidpy Spatial Enablement Research

Date: 2026-04-28

## Executive Summary

The historical `squidpy_spatial` failures were runtime-first failures. Agents hit a broken scientific stack before they could produce durable source/output artifacts, then the v0.2+ scorer correctly zeroed the runs at artifact precheck. The repair path is therefore:

1. make the Squidpy stack fail-fast before agent work starts,
2. stage the public Squidpy datasets as offline benchmark cache files,
3. run a small graph/autocorrelation smoke on Cayuga before any paid model run,
4. keep the scorer strict about evidence provenance, and
5. treat production result-match claims as blocked until sealed hidden references exist.

## Source Grounding

- Squidpy's Nature Methods paper positions the framework around spatial graphs, tissue images, image-derived features, spatial statistics, and ligand-receptor style interaction analysis, so the task's broad modality coverage is scientifically aligned with the paper.
- The official Visium H&E tutorial loads `sq.datasets.visium_hne_image()` and `sq.datasets.visium_hne_adata()`, computes image features, neighborhood enrichment, co-occurrence, ligand-receptor analysis, and Moran statistics. It also exposes public anchor values for the top Moran genes.
- The official `spatial_neighbors` API distinguishes `coord_type="grid"` from `coord_type="generic"`, which supports the rubric's geometry-aware graph requirement.
- The official `spatial_autocorr` API computes Moran's I or Geary's C and writes `adata.uns["moranI"]` or `adata.uns["gearyC"]`, supporting ranked TSV/JSON outputs.
- The official `calculate_image_features` API writes an observations-by-features matrix and supports `summary`, `texture`, `histogram`, `segmentation`, and `custom` feature families.
- The zarr/numcodecs compatibility failure is a known upstream issue: zarr 2.x imports `numcodecs.blosc.cbuffer_sizes`, which numcodecs 0.16 removed.

## Runtime Fix

The benchmark now pins the risky packages exactly:

- `numcodecs==0.15.1`
- `zarr==2.18.3`
- `setuptools==80.8.0`

The stack check in `scripts/check_squidpy_scientific_stack.py` now verifies:

- package ceilings for `numcodecs` and `setuptools`,
- importability of `scanpy`, `squidpy`, `spatialdata`, and `zarr`,
- `pkg_resources` importability,
- public `numcodecs.blosc.cbuffer_sizes` and `cbuffer_metainfo` visibility,
- optional offline cache file existence and exact manifest sizes,
- optional offline loading of Visium H&E AnnData, Visium H&E image, and seqFISH,
- optional graph/autocorrelation smoke using Visium grid coordinates and seqFISH generic coordinates.

## HPC Test Protocol

Use Cayuga for heavy checks:

```bash
cd /athena/masonlab/scratch/users/$USER/SciReplicBench_hpc/scireplicbench_<stamp>
/opt/ohpc/pub/software/slurm/24.05.2/bin/sbatch scripts/cayuga_squidpy_prepare.sbatch
```

The prepare job now runs the import smoke before data prep, runs `prepare_data.sh`, then runs:

```bash
python scripts/check_squidpy_scientific_stack.py --check-cache --load-cache --analysis-smoke
```

For an Inspect path smoke without Docker:

```bash
MODEL=mockllm/model JUDGE_MODEL=mockllm/model MESSAGE_LIMIT=12 JUDGE_LEAF_LIMIT=5 \
  /opt/ohpc/pub/software/slurm/24.05.2/bin/sbatch scripts/cayuga_squidpy_eval_local.sbatch
```

The local-sandbox Cayuga lane is an enablement lane, not the final isolation lane. Final benchmark claims should still prefer Docker/Apptainer-style two-sandbox separation when available.

## Metric Audit

The current 30/25/45 category split is directionally right: code and execution prevent "answer-only" submissions, while the 45% result-match block keeps the benchmark scientific rather than merely procedural. The main issue is not the weights; it is whether each result-match leaf has a sealed, reproducible reference and an offline-compatible path.

| Rubric area | Current metric | Verdict | Notes |
| --- | --- | --- | --- |
| Dataset/container loading | shape, image dimensions, label vocabulary | Good | Low ambiguity and tied to the offline manifest. |
| Geometry-aware graphs | edge-count bands, rank/curve overlap | Good with hidden refs | Edge counts are brittle unless graph settings are fixed; rank/curve metrics are better for scientific similarity. |
| Neighborhood/co-occurrence | RBO, positive pair recovery, Pearson curve correlation | Good | Matches the Squidpy tutorial's neighborhood/co-occurrence framing. Requires fixed cluster label normalization. |
| Moran/Geary | public Moran anchors plus hidden Geary rank | Good | Geary is a useful anti-memorization target; Moran public values are sanity anchors, not sufficient alone. |
| Ripley | curve Pearson | Acceptable but fragile | Needs fixed radius grid, fixed cluster label, and explicit statistic family. Otherwise agents can generate incomparable curves. |
| Image features | row alignment, feature-count band, ARI, feature rank overlap | Mixed | Summary/texture/histogram features are well grounded. Segmentation-specific leaves are only fair if a segmentation label layer or benchmark segmentation recipe is staged. |
| Ligand-receptor/interactions | top interaction pair overlap, significant count | Risky offline | Full ligand-receptor analysis may depend on database availability. The rubric should continue allowing a benchmark-approved interaction-matrix equivalent unless an offline LR resource is staged. |
| Visualization/localization | region-wise Pearson, marker consistency | Good as secondary evidence | Should never be screenshot-only; needs numeric region/bin summaries. |

## Recommended Metric Policy

1. Keep `code_development`, `execution`, and `result_match` separate.
2. Keep artifact precheck and evidence-provenance hardening.
3. Do not use hidden-reference comparison metrics as proof that execution outputs were written; the scorer already blocks this pattern.
4. Promote deterministic numeric comparators for result-match leaves once hidden references are sealed.
5. Mark production blocked until `novel_contrast.json` contains sealed reference values and generation metadata.
6. For image segmentation, either stage segmentation labels/recipe or down-weight/rename segmentation leaves to "segmentation-or-morphology proxy" so the task remains offline-fair.
7. For ligand-receptor, either stage the LR database or grade an offline cluster-interaction equivalent rather than requiring internet-dependent resources.

## Immediate Go/No-Go

- Go for Cayuga stack/cache/analysis smoke.
- Go for local unit tests.
- Go for mock Inspect local-sandbox smoke on Cayuga.
- No-go for production scientific claims until hidden references and second-rater judge calibration gates are complete.

## 2026-04-28 Test Results

- Local unit tests: `146 passed, 20 subtests passed in 31.53s`.
- Cayuga stack/cache/analysis smoke: passed on staged repo `scireplicbench_20260428_114814`.
- Cayuga cache sizes verified:
  - `visium_hne_adata.h5ad`: `329316778` bytes.
  - `visium_hne_image.tiff`: `398415836` bytes.
  - `seqfish.h5ad`: `32167384` bytes.
- Cayuga offline loads verified:
  - Visium H&E AnnData shape `(2688, 18078)`.
  - seqFISH AnnData shape `(19416, 351)`.
  - Visium image container loaded.
- Cayuga analysis smoke verified:
  - Visium grid graph edges: `15580`.
  - Geary smoke rows: `25`.
  - seqFISH generic-coordinate subset edges: `3000`.
- Cayuga mock Inspect local-sandbox eval:
  - Slurm job: `2824603`.
  - State: `COMPLETED`.
  - Elapsed: `00:02:48`.
  - MaxRSS: `2508708K`.
  - Eval log: `logs-hpc/2026-04-28T18-38-50-00-00_scireplicbench_9wAQSbvcYZG7mnTBLoh4AQ.eval`.
  - Score: `0.000`, expected for `mockllm/model` because no non-trivial submission/output artifacts were produced.
  - Precheck: `ok=false`, `nontrivial_py_files=0`, `output_artifact_count=0`, confirming the scaffold guard still prevents empty submissions from receiving judge credit.
