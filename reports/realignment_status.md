# Realignment Status

This note records the repo-local realignment work added after the baseline v1.2 handoff.

## Shipped

- Phase plans now carry readiness-gate metadata with `pilot_ready` / `production_ready` semantics.
- Production plans now request judge self-consistency metadata (`n=3`, minimum confidence `0.6`).
- Hidden-reference readiness is now a first-class check instead of an implicit TODO.
- A second-human-rater gap in `judge_eval/human_grades.json` is now treated as a production blocker.
- GeneLab starter integration smoke now verifies that all four required TSV families are written as machine-readable outputs.
- Squidpy scientific-stack smoke now has a dedicated CI workflow and a smoke requirements file with `numcodecs<0.16`.

## Current Gate Shape

- `inspiration4_multiome`: enablement lane until a reviewer-ready AnnData or MuData object is staged.
- `genelab_benchmark`: pilot-capable, but not production-ready until hidden references and judge-panel credibility gates are complete.
- `squidpy_spatial`: pilot-capable external anchor, with scientific-stack smoke coverage and production gating tied to hidden references plus judge-panel credibility.

## Latest GeneLab Pilot

The April 25, 2026 v21 `genelab_benchmark` pilot validated the first starter-preservation patch: the agent copied the seeded starter, then ran `bash /workspace/submission/run.sh` as the canonical workflow. The run still regressed because, after the starter succeeded, the agent attempted optional sidecar work (`evaluate_models.py`) and rewrote a short `/workspace/output/submission_manifest.json`, which weakened the final evidence trail even though the protected `main_analysis.py` and `run.sh` edits were rejected.

- Log: `logs/2026-04-26T01-46-20-00-00_scireplicbench_hbpprfCRQig8ZSSPhMkiFW.eval`
- Trace: `logs-prod/inspect-trace-genelab-pilot-v21.log.gz`
- Score: `0.08888333333333333`
- Category scores: `code_development=0.20633333333333334`, `execution=0.06666666666666667`, `result_match=0.0`
- Passed leaves: `5 / 55`
- Judge failures: `1`
- Zero-score `no_valid_evidence` responses: `42`
- Sample limit: none
- Precheck: `ok=true`, `nontrivial_py_files=2`, `output_artifact_count=9`

Compared with v20 (`0.15855`), v21 gained `fit_random_forest` and `compare_foundation_to_classical`, but lost six execution/code leaves including `load_feature_matrices`, `bootstrap_ci_written`, `go_nogo_summary_written`, and `geneformer_stage_executes`. The follow-up patch now protects rich GeneLab starter manifests from thin overwrites and strengthens the GeneLab prompt: after the canonical launcher succeeds, agents should inspect the concrete TSV artifacts and avoid alternate drivers unless they are wired into the saved workflow and verified against the full artifact set.

## Remaining Human/Data Inputs

- Fill at least one real paper's `hidden_reference_generation` block with sealed reference values.
- Add a second human rater to the reliability packet so Krippendorff's alpha and CI become meaningful.
- Materialize the reviewer-ready Inspiration4 multimodal object under `papers/inspiration4_multiome/data/cache/`.
