# Evaluation Report

This report tracks SciReplicBench agent runs with rubric-tree scores aggregated from the LLM judge. It is updated from Inspect `.eval` logs as new runs land.

## Current coverage

Two sandboxes have been exercised end-to-end on the `squidpy_spatial` rubric. The smoke sandbox (see [../environments/Dockerfile.smoke](../environments/Dockerfile.smoke)) is a minimal runtime-wiring validator. The production sandbox (see [../environments/Dockerfile](../environments/Dockerfile) + [compose.squidpy_spatial.yaml](../environments/compose.squidpy_spatial.yaml)) ships scanpy 1.10.1 + squidpy 1.6.0 + spatialdata. Paper-specific scientific images for `inspiration4_multiome` and `genelab_benchmark` have not yet been built.

| Run | Paper | Agent | Sandbox | Msg limit | Precheck | Leaves graded | Overall score |
|---|---|---|---|---:|---|---|---:|
| `jqv6qmGg` | squidpy_spatial | openai/gpt-4o-mini | smoke | 25 | n/a (v0.1) | 10 / 65 | 0.000 |
| `VAaLhS7Y` | squidpy_spatial | openai/gpt-4o-mini | smoke | 25 | n/a (v0.1) | 65 / 65 | 0.000 |
| `GaKiuf8G` | squidpy_spatial | openai/gpt-4o-mini | **production** | 40 | n/a (v0.1) | 65 / 65 | **0.028** |
| `Kfjef4zb` | squidpy_spatial | anthropic/claude-haiku-4-5 | **production** | 40 | n/a (v0.1) | 65 / 65 | **0.000** |
| `JeRrV6ju` | squidpy_spatial | anthropic/claude-sonnet-4-6 | **production** | 40 | n/a (v0.1) | 65 / 65 | **0.000** |
| `cEsYJL6i` | squidpy_spatial | openai/gpt-4o-mini | **production** | 40 | **failed** (v0.2) | 0 / 65 | **0.000** |
| `nQGFXNVZ` | squidpy_spatial | anthropic/claude-haiku-4-5 | **production** | 40 | **failed** (v0.2) | 0 / 65 | **0.000** |
| `2EuTNiNq` | squidpy_spatial | anthropic/claude-sonnet-4-6 | **production** | 40 | **failed** (v0.2) | 0 / 65 | **0.000** |

Log paths:

**v0.1 baseline (no precheck):**
- `logs-smoke/2026-04-14T01-22-26-00-00_scireplicbench_jqv6qmGgRHBumGqML6kpGN.eval`
- `logs-smoke/2026-04-14T01-26-14-00-00_scireplicbench_VAaLhS7Yszu66EQxgmYcC8.eval`
- `logs-prod/2026-04-14T02-40-31-00-00_scireplicbench_GaKiuf8GTW7q6BLSMRNC6K.eval`
- `logs-prod/2026-04-14T02-58-39-00-00_scireplicbench_Kfjef4zbDpVAoWmQS7fYDB.eval`
- `logs-prod/2026-04-14T03-05-54-00-00_scireplicbench_JeRrV6juZ4nxSBKtAVuK3w.eval`

**v0.2 with artifact-presence precheck:**
- `logs-prod/2026-04-14T13-25-26-00-00_scireplicbench_cEsYJL6iXwjyaB3RQyTw8x.eval`
- `logs-prod/2026-04-14T13-32-06-00-00_scireplicbench_nQGFXNVZpmuTPa482HsAYa.eval`
- `logs-prod/2026-04-14T13-48-30-00-00_scireplicbench_2EuTNiNqM4nqeVMw5xTiVk.eval`

Sanitized, path-redacted summaries of each run live under [../examples/](../examples/).

## Before vs. after artifact-presence precheck

The single highest-leverage v0.2 fix. Same three agents, same `squidpy_spatial` rubric, same scientific Docker image, same 40-message budget; the only change is `src/scireplicbench/scorers.py` gaining `_artifact_presence_precheck` (commit `6a86372`).

| Agent | v0.1 score | v0.2 score | v0.1 wall-clock | v0.2 wall-clock | Judge calls v0.1 → v0.2 |
|---|---:|---:|---|---|---|
| openai/gpt-4o-mini | **0.028** | **0.000** | 5 m 32 s | 1 m 47 s | 65 → 0 |
| anthropic/claude-haiku-4-5 | 0.000 | 0.000 | 4 m 34 s | 2 m 32 s | 65 → 0 |
| anthropic/claude-sonnet-4-6 | 0.000 | 0.000 | 4 m 07 s | 1 m 42 s | 65 → 0 |

Findings:

1. **The capability-inverting ordering flip is eliminated.** All three agents now converge at 0.000, matching what they actually accomplished in 40 messages (none produced executable analysis code).
2. **gpt-4o-mini's v0.1 0.028 was a judge-lenience artifact.** Both passing leaves were graded on README text; the precheck verifies that no Python file under `/workspace/submission` had a non-trivial function or module body and zeros every leaf without billing the judge.
3. **The judge is skipped entirely** when the precheck fails. v0.2 reruns issued zero leaf-grading API calls, dropping wall-clock by 50–70 % and judge token spend to zero on these scaffolding-failure runs.
4. **Haiku and Sonnet remain at 0.000** — same numeric result as v0.1, but for a stronger reason: the precheck honestly reports they wrote no scaffold, instead of the judge handing out 65 zeros after reading their import-debugging output.

## What the scores mean

- **Smoke runs (0.000):** The smoke sandbox has no scientific Python stack. The agent cannot produce a runnable replication; the judge correctly grades every leaf 0 with evidence-quote `(no submission artifacts were produced in /workspace/submission or /workspace/output)`. A non-zero score on smoke would be a bug.
- **Production runs vary by agent behaviour, not capability:**
  - **`gpt-4o-mini` → 0.028.** Reads the paper bundle, runs `prepare_data.sh` (self-corrects a missing `numcodecs` with in-container `pip install`), creates `/workspace/submission` with a README plus empty `.py` stubs. 2 of 65 leaves pass on README-based evidence.
  - **`claude-haiku-4-5` → 0.000.** Tries to `import squidpy` inside the sandbox, hits a zarr v3 API incompatibility, spends the message budget diagnosing it. No README scaffold, so no false-positive surface for the judge.
  - **`claude-sonnet-4-6` → 0.000.** Spends the budget diagnosing a `pkg_resources` import issue. Same shape as Haiku — attempts real work, gets stopped by an environment wrinkle, produces no scaffold for the judge to over-credit.

The v0.1 three-agent delta exposed a judge-lenience mode that flipped model ordering: a weaker agent scored higher by doing less-substantive but more-scaffold-looking work. The v0.2 reruns show that this was a grading artifact rather than a real capability difference: once empty-scaffold submissions are intercepted before leaf grading, all three agents converge honestly at 0.000. This is documented as mode 2 in [failure_taxonomy.md](failure_taxonomy.md) and is the central methodology result of the v0.2 pack.

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

### `Kfjef4zb` — full 65-leaf production, claude-haiku-4-5 agent + gpt-4o-mini judge

- Status: success
- Wall-clock: 274 s
- Tool calls across 40 messages: `bash` × 17, `scratchpad` × 1, `python` × 1
- Overall score: 0.000; all category scores 0.000
- Observed behaviour: attempted to `import squidpy`, hit a zarr v3 API incompatibility (`numcodecs.blosc` attribute lookup), spent the budget diagnosing and working around it. Produced no `/workspace/submission` scaffold, so the judge had no surface for README-lenience to inflate the score.
- Judge failures: 0

### `JeRrV6ju` — full 65-leaf production, claude-sonnet-4-6 agent + gpt-4o-mini judge

- Status: success
- Wall-clock: 247 s
- Tool calls across 40 messages: `bash` × 19, `scratchpad` × 0, `python` × 0
- Overall score: 0.000; all category scores 0.000
- Observed behaviour: spent the budget diagnosing a `pkg_resources` import issue and probing the Python path for the missing module. Same qualitative outcome as Haiku.
- Judge failures: 0

## Run matrix snapshot (filled as pilots land)

| Phase | Agents | Judge | Papers | Seeds | Runs | Mean score | Notes |
|---|---|---|---:|---:|---:|---:|---|
| Dev smoke (v0.1) | gpt-4o-mini | gpt-4o-mini | 1 | 1 | 2 | 0.000 | smoke sandbox: no scientific stack |
| Dev production (v0.1) | gpt-4o-mini / haiku-4-5 / sonnet-4-6 | gpt-4o-mini | 1 | 1 | 3 | 0.009 (mean) | gpt-4o-mini=0.028, haiku=0.000, sonnet=0.000; ordering flip observed |
| Dev production (v0.2) | gpt-4o-mini / haiku-4-5 / sonnet-4-6 | gpt-4o-mini | 1 | 1 | 3 | **0.000** | precheck active; all three converge honestly at 0; judge skipped |
| 4a pilot | pending | pending | — | — | 0 | pending | will cover 3 papers + deepseek |
| 4b production | pending | pending | — | — | 0 | pending | ≥ 3 seeds, two-container reproducer |

## Per-paper results

| Paper | Agent | Sandbox | Runs | Mean overall | code_development | execution | result_match |
|---|---|---|---:|---:|---:|---:|---:|
| inspiration4_multiome | — | — | 0 | pending | pending | pending | pending |
| squidpy_spatial | gpt-4o-mini | smoke | 2 | 0.000 | 0.000 | 0.000 | 0.000 |
| squidpy_spatial | gpt-4o-mini | production (v0.1) | 1 | 0.028 | 0.045 | 0.060 | 0.000 |
| squidpy_spatial | claude-haiku-4-5 | production (v0.1) | 1 | 0.000 | 0.000 | 0.000 | 0.000 |
| squidpy_spatial | claude-sonnet-4-6 | production (v0.1) | 1 | 0.000 | 0.000 | 0.000 | 0.000 |
| squidpy_spatial | gpt-4o-mini | production (v0.2 + precheck) | 1 | 0.000 | 0.000 | 0.000 | 0.000 |
| squidpy_spatial | claude-haiku-4-5 | production (v0.2 + precheck) | 1 | 0.000 | 0.000 | 0.000 | 0.000 |
| squidpy_spatial | claude-sonnet-4-6 | production (v0.2 + precheck) | 1 | 0.000 | 0.000 | 0.000 | 0.000 |
| genelab_benchmark | — | — | 0 | pending | pending | pending | pending |

## Known limitations (current v0.2 state)

1. **One production paper exercised.** Only `squidpy_spatial` has been run on a real scientific image; `inspiration4_multiome` and `genelab_benchmark` images are defined but unbuilt.
2. **Limited model matrix.** `gpt-4o-mini`, `claude-haiku-4-5`, and `claude-sonnet-4-6` have one production run each on `squidpy_spatial`; `deepseek-v3` and any higher-cost production lineup are still pending.
3. **Single seed.** No variance estimate yet. Phase 4b calls for ≥ 3 seeds.
4. **No self-consistency retry.** The n=3 self-consistency wrapper for disagreement-flagged leaves is implemented in `src/scireplicbench/judge.py` but not yet invoked by `rubric_tree_scorer`.
5. **Per-leaf prose-vs-code guardrails remain open.** v0.2 fixed the empty-scaffold / README-only ordering flip with a task-level precheck, but richer submissions can still be over-credited if descriptive prose is treated as implementation evidence. The next hardening pass should require non-README code, command, or runtime-output evidence at the leaf level.

## Next milestones

Ordered by priority for a credible artifact:

1. Harden the scorer/judge against prose-over-code over-crediting on `squidpy_spatial`, then rerun the existing three-agent production matrix to measure what v0.2 still misses.
2. Build scientific images for `inspiration4_multiome` and `genelab_benchmark` and run the same `gpt-4o-mini` pass on each.
3. Add `deepseek-v3` to the cheap-model matrix and decide whether a higher-cost `gpt-4o` / `claude-sonnet` production pass is still warranted.
4. Populate [judge_reliability.md](judge_reliability.md) by hand-grading ≥ 20 leaves from both a v0.1 false-positive case and a v0.2 precheck-failed case, then compute Krippendorff's α.
