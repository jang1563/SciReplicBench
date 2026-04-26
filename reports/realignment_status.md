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

The April 26, 2026 v25 `genelab_benchmark` pilot validates the canonical-source hardening path. The agent first attempted to replace `main_analysis.py`, `run.sh`, and the structured manifest with thinner files; the tool guards blocked all three and steered it back to the seeded workflow. The final submission kept only the canonical `genelab_scaffold.py` and `main_analysis.py`, produced the expected nine output artifacts, and recovered execution evidence that earlier pilots left invisible to the judge.

- Log: `logs/2026-04-26T04-08-51-00-00_scireplicbench_j5nuaXbQta4PV9jUcEsWQX.eval`
- Trace: `logs-prod/inspect-trace-genelab-pilot-v25.log.gz`
- Score: `0.21738333333333332`
- Category scores: `code_development=0.20800000000000002`, `execution=0.5783333333333333`, `result_match=0.0`
- Passed leaves: `12 / 55`
- Judge failures: `0`
- Zero-score `no_valid_evidence` responses: `34`
- Sample limit: none
- Precheck: `ok=true`, `nontrivial_py_files=2`, `output_artifact_count=9`

Compared with v22 (`0.16561666666666666`), v25 removes the unhooked sidecar source and increases total score by improving execution recognition for split manifests, AUROC tables, bootstrap CIs, permutation results, cross-mission/tissue transfer outputs, and go/no-go summaries. v23 confirmed that sidecar prevention alone kept the submission focused but starved the judge of source evidence (`0.05075`); v24 recovered source-focused code leaves (`0.1193`) but exposed overly strict judge handling of fallback code, example alternatives, and header-plus-row output evidence. The current local lever is to convert the remaining `no_valid_evidence` zeroes into grounded code/result matches without weakening the protected starter workflow.

## Remaining Human/Data Inputs

- Fill at least one real paper's `hidden_reference_generation` block with sealed reference values.
- Add a second human rater to the reliability packet so Krippendorff's alpha and CI become meaningful.
- Materialize the reviewer-ready Inspiration4 multimodal object under `papers/inspiration4_multiome/data/cache/`.
