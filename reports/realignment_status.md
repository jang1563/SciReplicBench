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

The April 25, 2026 v22 `genelab_benchmark` pilot validates the starter-manifest protection and GeneLab prompt reinforcement. Like v21, the agent copied the seeded starter and ran `bash /workspace/submission/run.sh` as the canonical workflow. Unlike v21, it left the structured starter manifest in place and recovered several execution/code leaves, though it still created an unhooked `model_analysis.py` sidecar after the canonical workflow had already succeeded.

- Log: `logs/2026-04-26T02-23-40-00-00_scireplicbench_CpmQAN8de73bw6e7FfYT5j.eval`
- Trace: `logs-prod/inspect-trace-genelab-pilot-v22.log.gz`
- Score: `0.16561666666666666`
- Category scores: `code_development=0.267`, `execution=0.21666666666666667`, `result_match=0.045`
- Passed leaves: `9 / 55`
- Judge failures: `2`
- Zero-score `no_valid_evidence` responses: `37`
- Sample limit: none
- Precheck: `ok=true`, `nontrivial_py_files=3`, `output_artifact_count=9`

Compared with v21 (`0.08888333333333333`), v22 recovered `fit_xgboost`, `implement_negative_controls`, `classical_models_execute`, `bootstrap_ci_written`, and `negative_control_near_chance`, while losing only `compare_foundation_to_classical`. Compared with v20 (`0.15855`), v22 is slightly higher overall and adds `fit_random_forest`, `fit_xgboost`, `implement_negative_controls`, `classical_models_execute`, and `negative_control_near_chance`, but still loses `load_feature_matrices`, `attach_mission_tissue_labels`, `compute_bootstrap_and_permutation_metrics`, `go_nogo_summary_written`, and `geneformer_stage_executes`. The next local lever is to prevent or de-prioritize unhooked post-success sidecars so scorer context stays focused on the canonical starter source and measured artifacts.

## Remaining Human/Data Inputs

- Fill at least one real paper's `hidden_reference_generation` block with sealed reference values.
- Add a second human rater to the reliability packet so Krippendorff's alpha and CI become meaningful.
- Materialize the reviewer-ready Inspiration4 multimodal object under `papers/inspiration4_multiome/data/cache/`.
