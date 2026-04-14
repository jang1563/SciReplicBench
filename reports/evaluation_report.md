# Evaluation Report

This report tracks SciReplicBench agent runs with rubric-tree scores aggregated from the LLM judge. It is updated from Inspect `.eval` logs as new runs land.

## Current coverage

Only the smoke sandbox has been exercised end-to-end. The smoke sandbox is a minimal Python 3.11 container with bash and no scientific libraries, included as a runtime-wiring validator (see [../environments/Dockerfile.smoke](../environments/Dockerfile.smoke)). Paper-specific scientific images (`compose.<paper_id>.yaml`) have not yet been built for production evaluation runs.

| Run | Paper | Agent | Sandbox | Msg limit | Leaves graded | Overall score |
|---|---|---|---|---:|---|---:|
| `jqv6qmGg` | squidpy_spatial | openai/gpt-4o-mini | smoke | 25 | 10 / 65 | 0.000 |
| `VAaLhS7Y` | squidpy_spatial | openai/gpt-4o-mini | smoke | 25 | 65 / 65 | 0.000 |

Log paths:

- `logs-smoke/2026-04-14T01-22-26-00-00_scireplicbench_jqv6qmGgRHBumGqML6kpGN.eval`
- `logs-smoke/2026-04-14T01-26-14-00-00_scireplicbench_VAaLhS7Yszu66EQxgmYcC8.eval`

## What the 0.000 score means

The smoke sandbox has neither Squidpy nor any scientific Python stack installed, so the agent cannot produce a runnable replication. The judge correctly grades every leaf 0 with evidence-quote `(no submission artifacts were produced in /workspace/submission or /workspace/output)`. The 0.000 score is therefore the *expected* outcome and is evidence that the rubric is not trivially satisfiable from empty output. A non-zero score on the smoke sandbox would be a bug.

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

## Run matrix snapshot (filled as pilots land)

| Phase | Agents | Judge | Papers | Seeds | Runs | Mean score | Mean cost (USD) |
|---|---|---|---:|---:|---:|---:|---:|
| Dev smoke | gpt-4o-mini | gpt-4o-mini | 1 | 1 | 2 | 0.000 | ~$0.015 |
| 4a pilot | pending | pending | — | — | 0 | pending | pending |
| 4b production | pending | pending | — | — | 0 | pending | pending |

## Per-paper results

| Paper | Agent | Runs | Mean overall | code_development | execution | result_match |
|---|---|---:|---:|---:|---:|---:|
| inspiration4_multiome | — | 0 | pending | pending | pending | pending |
| squidpy_spatial | gpt-4o-mini (smoke) | 2 | 0.000 | 0.000 | 0.000 | 0.000 |
| genelab_benchmark | — | 0 | pending | pending | pending | pending |

## Known limitations (v0.1)

1. **Smoke sandbox only.** Paper-specific compose files (`compose.squidpy_spatial.yaml`, `compose.inspiration4_multiome.yaml`, `compose.genelab_benchmark.yaml`) are defined but not yet built; production runs against scientific images are the next milestone.
2. **Single model exercised.** `gpt-4o-mini` is the only agent observed so far; Phase 4a additionally targets `claude-haiku-4-5` and `deepseek-v3`, and Phase 4b targets `gpt-4o` and `claude-sonnet-4-6`.
3. **One paper exercised.** Only `squidpy_spatial` has been run; `inspiration4_multiome` and `genelab_benchmark` runs are pending.
4. **Single seed.** No variance estimate yet. Phase 4b calls for ≥ 3 seeds.
5. **No self-consistency retry.** The n=3 self-consistency wrapper for disagreement-flagged leaves is implemented in `src/scireplicbench/judge.py` but is not yet invoked by `rubric_tree_scorer`.

## Next milestones

Ordered by priority for a credible artifact:

1. Build `compose.squidpy_spatial.yaml` and rerun both 10-leaf and full-leaf passes on the real image. Expect a non-zero score because the agent can then actually run Squidpy.
2. Extend the run matrix to `inspiration4_multiome` and `genelab_benchmark` on their respective images.
3. Add a second cheap agent (Haiku 4.5 or DeepSeek V3) to get cross-model signal without materially increasing cost.
4. Populate [judge_reliability.md](judge_reliability.md) by hand-grading ≥ 20 leaves and computing Krippendorff's α.
