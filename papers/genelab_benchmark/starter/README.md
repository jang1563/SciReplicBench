# GeneLab Starter

This starter is a runnable reviewer-path baseline for the cached GeneLab benchmark snapshot. It is designed to be copied into `/workspace/submission`, executed, and then improved rather than used only as a placeholder template.

Use it when you need a concrete starting point for:

- discovering real `A*_lomo/fold_*` directories
- loading `train_X.csv` / `test_X.csv` together with `train_y.csv` / `test_y.csv` and optional `train_meta.csv` / `test_meta.csv`
- aligning feature matrices, labels, and metadata by shared sample IDs
- running several classical baselines and writing machine-readable benchmark outputs
- exporting structured transfer, negative-control, interpretability, and staging artifacts instead of placeholder text

Suggested usage:

1. Copy `starter/main_analysis.py` into `/workspace/submission/main_analysis.py`.
2. Copy `starter/run.sh` into `/workspace/submission/run.sh`.
3. Execute the saved workflow once before making large edits so you can inspect the baseline TSV outputs.
4. Extend or replace model branches as time allows while preserving the fold traversal and required structured outputs.

`starter/genelab_scaffold.py` remains available as a thin helper companion that re-exports the fold-discovery and TSV-writing surface from `starter/main_analysis.py`. `starter/main_analysis.py` is still the direct path because it already runs the baseline and writes the required output files. The baseline screens each fold to a bounded high-variance feature panel before fitting models so the reviewer-path snapshot stays runnable in the sandbox. The launcher also verifies that the expected benchmark artifacts were emitted, caps the primary submission runtime, and will rerun the pristine starter baseline from the staged paper bundle if a rewritten submission drops required outputs.

Useful runtime knobs:

- `GENELAB_MAX_MODEL_FEATURES` controls the variance-screened feature cap used for model fitting.
- `GENELAB_PRIMARY_TIMEOUT_SECONDS` controls how long `run.sh` gives a rewritten primary script before falling back.
- `GENELAB_FALLBACK_TIMEOUT_SECONDS` controls how long the pristine staged starter gets during fallback.
