# Squidpy Spatial Starter

This starter is a runnable reviewer-path baseline for the offline Squidpy spatial benchmark cache. It is copied into `/workspace/submission` during task setup and should be executed before replacing any analysis code.

## Files

- `run.sh` launches `main_analysis.py`, verifies the required output artifact families, applies a timeout, and falls back to the pristine staged starter when a rewritten primary script drops required outputs.
- `main_analysis.py` loads the benchmark-pinned Visium H&E, Visium image, seqFISH, and ligand-receptor resources from `/workspace/input/paper_bundle/data`, then writes SVG/HTML visualization artifacts under `/workspace/output/agent/visualizations`.
- `squidpy_spatial_workflow.py` contains the public Squidpy workflow used by the starter to compute graph, autocorrelation, image-feature, spatial-pattern, and ligand-receptor outputs.

## Expected Use

1. Run `bash /workspace/submission/run.sh`.
2. Inspect files under `/workspace/output/agent`.
3. If you improve the analysis, keep `run.sh` intact and preserve the output filenames and schemas.

For HPC/local-sandbox runs, `SCIREPLICBENCH_WORKSPACE_ROOT` can replace `/workspace`.
