# Evaluation Report

This report tracks SciReplicBench agent runs with rubric-tree scores aggregated from the LLM judge. It is updated from Inspect `.eval` logs as new runs land.

## Current coverage

Two sandboxes have been exercised end-to-end on the `squidpy_spatial` rubric. The smoke sandbox (see [../environments/Dockerfile.smoke](../environments/Dockerfile.smoke)) is a minimal runtime-wiring validator. The production sandbox (see [../environments/Dockerfile](../environments/Dockerfile) + [compose.squidpy_spatial.yaml](../environments/compose.squidpy_spatial.yaml)) ships scanpy 1.10.1 + squidpy 1.6.0 + spatialdata. Paper-specific scientific images for `inspiration4_multiome` and `genelab_benchmark` have not yet been built.

| Run | Paper | Agent | Sandbox | Msg limit | Leaves graded | Overall score |
|---|---|---|---|---:|---|---:|
| `jqv6qmGg` | squidpy_spatial | openai/gpt-4o-mini | smoke | 25 | 10 / 65 | 0.000 |
| `VAaLhS7Y` | squidpy_spatial | openai/gpt-4o-mini | smoke | 25 | 65 / 65 | 0.000 |
| `GaKiuf8G` | squidpy_spatial | openai/gpt-4o-mini | **production** | 40 | 65 / 65 | **0.028** |

Log paths:

- `logs-smoke/2026-04-14T01-22-26-00-00_scireplicbench_jqv6qmGgRHBumGqML6kpGN.eval`
- `logs-smoke/2026-04-14T01-26-14-00-00_scireplicbench_VAaLhS7Yszu66EQxgmYcC8.eval`
- `logs-prod/2026-04-14T02-40-31-00-00_scireplicbench_GaKiuf8GTW7q6BLSMRNC6K.eval`

Sanitized, path-redacted summaries of each run live under [../examples/](../examples/).

## What the scores mean

- **Smoke runs (0.000):** The smoke sandbox has no scientific Python stack. The agent cannot produce a runnable replication; the judge correctly grades every leaf 0 with evidence-quote `(no submission artifacts were produced in /workspace/submission or /workspace/output)`. A non-zero score on smoke would be a bug.
- **Production run (0.028):** The agent successfully reads the paper bundle, runs `prepare_data.sh` (self-correcting a missing `numcodecs` with in-container `pip install`), and creates `/workspace/submission` with a README plus empty `.py` stubs — but never writes executable Squidpy analysis code within 40 messages. 2 of 65 leaves pass, both on README-based evidence; see [failure_taxonomy.md](failure_taxonomy.md) for the judge-lenience discussion.

## Per-run detail

### `jqv6qmGg` — 10-leaf smoke, gpt-4o-mini agent + judge

- Status: success
- Wall-clock: 75 s
- Agent tool calls across 25 messages: `scratchpad` × 8, `bash` × 3
- Judge: `openai/gpt-4o-mini`, `SCIREPLICBENCH_JUDGE_LEAF_LIMIT=10`
- Category scores: `code_development=0.000`, `execution=0.000`, `result_match=0.000`
- Judge failures: 0

### `VAaLhS7Y` — full 65-leaf smoke, gpt-4o-mini agent + judge

- Status: success
- Wall-clock: 215 s
- Judge: `openai/gpt-4o-mini`, no leaf cap (graded every leaf)
- Category scores: all 0.000
- Judge failures: 0

### `GaKiuf8G` — full 65-leaf production, gpt-4o-mini agent + judge

- Status: success
- Sandbox: real squidpy/scanpy image (Dockerfile + requirements.squidpy_spatial.txt)
- Wall-clock: 332 s (5 min 32 s)
- Tool calls across 40 messages: `bash` × 12, `scratchpad` × 7, `python` × 0
- Judge: `openai/gpt-4o-mini`, no leaf cap
- Overall score: 0.0285; category scores: `code_development=0.045`, `execution=0.060`, `result_match=0.000`
- Leaves passing: 2 / 65 (both judge-lenience cases on README text)
- Judge failures: 0

## Run matrix snapshot (filled as pilots land)

| Phase | Agents | Judge | Papers | Seeds | Runs | Mean score | Mean cost (USD) |
|---|---|---|---:|---:|---:|---:|---:|
| Dev smoke | gpt-4o-mini | gpt-4o-mini | 1 | 1 | 2 | 0.000 | ~$0.015 |
| Dev production | gpt-4o-mini | gpt-4o-mini | 1 | 1 | 1 | 0.028 | ~$0.035 |
| 4a pilot | pending | pending | — | — | 0 | pending | pending |
| 4b production | pending | pending | — | — | 0 | pending | pending |

## Per-paper results

| Paper | Agent | Sandbox | Runs | Mean overall | code_development | execution | result_match |
|---|---|---|---:|---:|---:|---:|---:|
| inspiration4_multiome | — | — | 0 | pending | pending | pending | pending |
| squidpy_spatial | gpt-4o-mini | smoke | 2 | 0.000 | 0.000 | 0.000 | 0.000 |
| squidpy_spatial | gpt-4o-mini | production | 1 | 0.028 | 0.045 | 0.060 | 0.000 |
| genelab_benchmark | — | — | 0 | pending | pending | pending | pending |

## Known limitations (v0.1)

1. **One production paper exercised.** Only `squidpy_spatial` has been run on a real scientific image; `inspiration4_multiome` and `genelab_benchmark` images are defined but unbuilt.
2. **Single model.** `gpt-4o-mini` is the only agent observed so far; Phase 4a additionally targets `claude-haiku-4-5` and `deepseek-v3`, and Phase 4b targets `gpt-4o` and `claude-sonnet-4-6`.
3. **Single seed.** No variance estimate yet. Phase 4b calls for ≥ 3 seeds.
4. **No self-consistency retry.** The n=3 self-consistency wrapper for disagreement-flagged leaves is implemented in `src/scireplicbench/judge.py` but not yet invoked by `rubric_tree_scorer`.
5. **Judge lenience on README text.** The production run surfaced a real failure mode where README-style descriptions can be graded as evidence of behaviour. Documented in [failure_taxonomy.md](failure_taxonomy.md); mitigation options (tighter judge prompt, artifact-existence prechecks) are open work.

## Next milestones

Ordered by priority for a credible artifact:

1. Build scientific images for `inspiration4_multiome` and `genelab_benchmark` and run the same gpt-4o-mini pass on each.
2. Add a second cheap agent (Haiku 4.5 or DeepSeek V3) to get cross-model signal without materially increasing cost.
3. Harden the judge prompt against README-only evidence (quote a line of executable code or a command invocation, not just a description).
4. Populate [judge_reliability.md](judge_reliability.md) by hand-grading ≥ 20 leaves from the production run and computing Krippendorff's α.
