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

The April 25, 2026 v20 `genelab_benchmark` pilot ran successfully after the judge prompt/parser was hardened for zero-score responses with no valid supporting evidence. v20 reran the same patched state with `message_limit=100` after v19 hit the original 60-message cap.

- Log: `logs/2026-04-25T16-40-28-00-00_scireplicbench_5zsyi5gh9Bp7B79VPEdEbF.eval`
- Trace: `logs-prod/inspect-trace-genelab-pilot-v20.log.gz`
- Score: `0.15855`
- Category scores: `code_development=0.253`, `execution=0.28`, `result_match=0.0`
- Passed leaves: `9 / 55`
- Judge failures: `1`
- Zero-score `no_valid_evidence` responses: `40`
- Sample limit: none
- Precheck: `ok=true`, `nontrivial_py_files=4`, `output_artifact_count=9`

Compared with v18, v20 reduced judge failures from `10` to `1`, confirming that the `no_valid_evidence` fallback removes most empty-quote validation failures. The remaining score drop from v18 (`0.22688333333333333`) and v17 (`0.31771666666666665`) is now attributable to agent-output quality rather than sample truncation: v20 recovered `load_feature_matrices`, `bootstrap_ci_written`, and `go_nogo_summary_written`, but lost several execution leaves such as `data_load_executes`, `classical_models_execute`, `preprocessed_matrix_written`, and `cross_mission_matrix_written`. The next local lever is to harden the GeneLab starter/fallback so it consistently executes the packaged workflow and writes the execution-side TSV artifacts before the agent begins optional extensions.

## Remaining Human/Data Inputs

- Fill at least one real paper's `hidden_reference_generation` block with sealed reference values.
- Add a second human rater to the reliability packet so Krippendorff's alpha and CI become meaningful.
- Materialize the reviewer-ready Inspiration4 multimodal object under `papers/inspiration4_multiome/data/cache/`.
