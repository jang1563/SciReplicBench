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

The April 25, 2026 v18 `genelab_benchmark` pilot ran successfully after Docker Desktop was restarted and scorer evidence quote matching was relaxed for narrow quote-format artifacts.

- Log: `logs/2026-04-25T13-05-03-00-00_scireplicbench_RPUHcHpkvMWpUARB7xJSzN.eval`
- Trace: `logs-prod/inspect-trace-genelab-pilot-v18.log`
- Score: `0.22688333333333333`
- Category scores: `code_development=0.353`, `execution=0.4133333333333334`, `result_match=0.0`
- Passed leaves: `13 / 55`
- Judge failures: `10`
- Precheck: `ok=true`, `nontrivial_py_files=2`, `output_artifact_count=9`

Compared with v17, v18 confirms that the trailing-punctuation quote relaxation can rescue real code evidence, but the run was still lower overall than v17 (`0.31771666666666665`) because several execution and result-match leaves regressed under stochastic judge behavior. The next local lever is judge-output stability for failing result-match leaves and clearer output-side evidence selection for execution leaves; the starter fallback still produced the required machine-readable artifact families.

## Remaining Human/Data Inputs

- Fill at least one real paper's `hidden_reference_generation` block with sealed reference values.
- Add a second human rater to the reliability packet so Krippendorff's alpha and CI become meaningful.
- Materialize the reviewer-ready Inspiration4 multimodal object under `papers/inspiration4_multiome/data/cache/`.
