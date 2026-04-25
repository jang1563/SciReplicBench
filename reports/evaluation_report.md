# Evaluation Report

This report tracks SciReplicBench agent runs with rubric-tree scores aggregated from the LLM judge. It is updated from Inspect `.eval` logs as new runs land.

## Current coverage

Two scientific sandboxes have been exercised end-to-end on the `squidpy_spatial` rubric, plus a ladder of evidence-policy probes ranging from deterministic internal fixtures to three-model frontier-agent traces and a first non-mock-judge extension. The smoke sandbox (see [../environments/Dockerfile.smoke](../environments/Dockerfile.smoke)) is a minimal runtime-wiring validator. The production sandbox (see [../environments/Dockerfile](../environments/Dockerfile) + [compose.squidpy_spatial.yaml](../environments/compose.squidpy_spatial.yaml)) ships scanpy 1.10.1 + squidpy 1.6.0 + spatialdata. As of April 21, 2026, the paper-specific `inspiration4_multiome` scientific image also builds cleanly, and `papers/inspiration4_multiome/data/prepare_data.sh` now stages both the public `inspiration4-omics` repository under `papers/inspiration4_multiome/data/raw/` and the public `OSD-570` / `GLDS-562` processed files under `papers/inspiration4_multiome/data/cache/osdr_public/`, with a local manifest at `papers/inspiration4_multiome/data/cache/osdr_public/manifest.tsv`. The remaining blocker for live benchmark runs there is still the benchmark-author AnnData or MuData cache expected under `papers/inspiration4_multiome/data/cache/`, because the public OSDR files are DEG/DAR result tables plus ISA metadata rather than the reviewer-ready multimodal object. `genelab_benchmark` now builds its paper-specific image and stages both the public GitHub repo and the Hugging Face `A*_lomo` feature matrices with Git LFS materialization. Its first seven `gpt-4o-mini` production attempts still score `0.000`, but the failure ladder is now much more specific: wrong-input/schema mistakes, then transient `python()`-only work, then broken `echo "...\\n..."` file writes, then a precheck-passing placeholder submission, then a real index-aligned single-fold AUROC artifact, and finally a stricter no-placeholder rerun that regressed into debug-heavy fold exploration without benchmark outputs. At this point the blocker is no longer public data staging or sample-ID alignment; it is converting multi-fold exploration into benchmark-shaped output artifacts without relying on prompt wording alone.

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
| `VN3Jn8x7` | squidpy_spatial | openai/gpt-4o-mini | **production** | 40 | **failed** (v0.3) | 0 / 65 | **0.000** |
| `TJQKBPfv` | squidpy_spatial | anthropic/claude-haiku-4-5 | **production** | 40 | **failed** (v0.3) | 0 / 65 | **0.000** |
| `WvLKMqep` | squidpy_spatial | anthropic/claude-sonnet-4-6 | **production** | 40 | **failed** (v0.3) | 0 / 65 | **0.000** |
| `UHz9awZj` | evidence_policy_probe | none/none (deterministic solver) | smoke | 4 | **passed** (v0.4) | 6 / 6 | **0.500** |
| `DxjYt2CF` | squidpy_spatial | none/none (deterministic solver) | **production probe** | 4 | **passed** (v0.5) | 130 / 130 | **0.022** |
| `fmbjLZy7` | squidpy_spatial | openai/gpt-4o-mini | **production probe** | 20 | **passed** (v0.6) | 130 / 130 | **0.022** |
| `c8MepEBS` | squidpy_spatial | openai/gpt-4o-mini | **production probe** | 20 | **passed** (v0.9) | 130 / 130 | **0.022** |
| `c2bzKgU9` | squidpy_spatial | openai/gpt-4o-mini | **production probe** | 20 | **passed** (v1.1) | 130 / 130 | **0.022** |
| `YvGhZ3x9` | squidpy_spatial | anthropic/claude-sonnet-4-6 | **production probe** | 20 | **passed** (v1.1) | 130 / 130 | **0.022** |
| `Cr4bjhKb` | squidpy_spatial | openai/gpt-4o-mini | **production probe** | 20 | **passed** (v1.2) | 130 / 130 | **0.022** |
| `PnyxRmso` | squidpy_spatial | anthropic/claude-sonnet-4-6 | **production probe** | 20 | **passed** (v1.2) | 130 / 130 | **0.022** |
| `Q3o5WVk8` | squidpy_spatial | anthropic/claude-haiku-4-5 | **production probe** | 20 | **passed** (v1.2) | 130 / 130 | **0.022** |
| `WRsMysX5` | squidpy_spatial | openai/gpt-4o-mini | **production probe** | 20 | **passed** (v1.2 + live `gpt-4o-mini` judge) | 130 / 130 | **0.042** |
| `D6ti4iFV` | squidpy_spatial | openai/gpt-4o-mini | **production probe** | 20 | **passed** (v1.2 + live `o3-mini` judge) | 130 / 130 | **0.085** |
| `3PgCvjdM` | squidpy_spatial | openai/gpt-4o-mini | **production probe** | 20 | **passed** (v1.2 + calibrated live `o3-mini` judge) | 130 / 130 | **0.022** |
| `TnUTWPrT` | squidpy_spatial | openai/gpt-4o-mini | **production probe** | 20 | **passed** (v1.2 + execution-clarified control, mock judge) | 130 / 130 | **0.022** |
| `mZHU6eGr` | squidpy_spatial | openai/gpt-4o-mini | **production probe** | 20 | **passed** (v1.2 + execution-clarified control + live `o3-mini` judge) | 130 / 130 | **0.043** |
| `f2KkxWjV` | squidpy_spatial | openai/gpt-4o-mini | **production probe** | 20 | **passed** (v1.2 + execution-clarified control + live `o3-mini` judge + post-fix rerun) | 130 / 130 | **0.043** |
| `BmPYCdd9` | genelab_benchmark | openai/gpt-4o-mini | **production** | 60 | **failed** | 0 / 55 | **0.000** |
| `EBqDy3e3` | genelab_benchmark | openai/gpt-4o-mini | **production** | 60 | **failed** | 0 / 55 | **0.000** |
| `NBYyMZFQ` | genelab_benchmark | openai/gpt-4o-mini | **production** | 60 | **failed** | 0 / 55 | **0.000** |
| `QAF72c7N` | genelab_benchmark | openai/gpt-4o-mini | **production** | 60 | **passed** | 55 / 55 | **0.000** |
| `KjSseoSX` | genelab_benchmark | openai/gpt-4o-mini | **production** | 60 | **failed** | 0 / 55 | **0.000** |
| `3L2uDjJE` | genelab_benchmark | openai/gpt-4o-mini | **production** | 60 | **passed** | 55 / 55 | **0.000** |
| `2mqb75xQ` | genelab_benchmark | openai/gpt-4o-mini | **production** | 60 | **passed** | 55 / 55 | **0.000** |

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

**v0.3 with precheck + per-leaf evidence hardening:**
- `logs-prod/2026-04-16T17-42-16-00-00_scireplicbench_VN3Jn8x7gRLTcsRKUa5p8t.eval`
- `logs-prod/2026-04-16T17-48-43-00-00_scireplicbench_TJQKBPfv3RuruRg9NG8bUi.eval`
- `logs-prod/2026-04-16T17-57-13-00-00_scireplicbench_WvLKMqepBzgn8HXeBeKzVE.eval`

**v0.4 live Inspect evidence-policy probe:**
- `logs-smoke/2026-04-16T23-11-30-00-00_evidence-policy-probe_UHz9awZjitJ9tHHYMru2Zv.eval`

**v0.5 live Squidpy-paper evidence-policy probe:**
- `logs-prod/2026-04-16T23-28-48-00-00_squidpy-evidence-policy-probe_DxjYt2CFdKj2h2mHZwhmEZ.eval`

**v0.6-v0.9 frontier-agent Squidpy evidence-policy probe:**
- `logs-prod/2026-04-16T23-47-32-00-00_squidpy-evidence-policy-agent-probe_JpKPChRb4yHuRTbXHGjWVk.eval` (initial frontier-agent attempt; both samples still precheck-failed because the inherited prompt spent the whole budget on context reads)
- `logs-prod/2026-04-16T23-53-06-00-00_squidpy-evidence-policy-agent-probe_cfnAKdM2v98xwjskEc4xhB.eval` (compact-prompt rerun; fail arm cleared precheck, exposed a remaining execution-evidence loophole, control arm still precheck-failed)
- `logs-prod/2026-04-16T23-56-24-00-00_squidpy-evidence-policy-agent-probe_fmbjLZy7QPeGaMLvNNdJ96.eval` (stabilized final v0.6 result after closing the execution loophole and simplifying the agent tool surface)
- `logs-prod/2026-04-17T00-13-53-00-00_squidpy-evidence-policy-agent-probe_8EDgq5PzDesSkQynF4Xf2X.eval` (v0.7 prompt-hardening attempt; both samples regressed to precheck failure after the agent relied on temporary interpreter/code-generation patterns instead of durable disk writes)
- `logs-prod/2026-04-17T00-16-42-00-00_squidpy-evidence-policy-agent-probe_UpUY8DLXFj7JkeAYsdFEcY.eval` (v0.8 bash-only rerun; control arm recovered, but the fail arm still precheck-failed because malformed `echo` output wrote invalid one-line Python)
- `logs-prod/2026-04-17T00-22-53-00-00_squidpy-evidence-policy-agent-probe_c8MepEBS4k6BpfF3uCHbTp.eval` (final v0.9 rerun after explicit heredoc/no-echo guidance; both arms pass precheck and the fail arm now hits the exact intended policy reasons)

**v1.0-v1.2 cross-model frontier-agent continuation:**
- `logs-prod/2026-04-17T02-52-32-00-00_squidpy-evidence-policy-agent-probe_ZwS5nw37Dbd7YSQvLfyi8a.eval` (v1.0 Sonnet rerun; the control arm recovered, but the fail arm exposed a new execution-evidence loophole where a bare output path could still pass if repeated inside an output-side manifest)
- `logs-prod/2026-04-17T02-58-48-00-00_squidpy-evidence-policy-agent-probe_c2bzKgU9oDEJFCYjiFjRER.eval` (final v1.1 `gpt-4o-mini` rerun after tightening the exact fail-arm result comment)
- `logs-prod/2026-04-17T02-59-33-00-00_squidpy-evidence-policy-agent-probe_YvGhZ3x9xyFBVMuEDDrgBL.eval` (final v1.1 Sonnet rerun after the execution-manifest loophole fix; matches the `gpt-4o-mini` v1.1 behavior exactly)
- `logs-prod/2026-04-17T03-28-23-00-00_squidpy-evidence-policy-agent-probe_TUSBgDp4VArMHBj2euL7C4.eval` (first Haiku cross-model attempt; fail arm stayed clean, but the control arm over-inspected the bundle, ran out of budget for output evidence, and fell to `overall = 0.0135`)
- `logs-prod/2026-04-17T03-34-09-00-00_squidpy-evidence-policy-agent-probe_Cr4bjhKbfMwuajLZTgFJLj.eval` (final v1.2 `gpt-4o-mini` rerun under the tighter "contract is sufficient" guidance)
- `logs-prod/2026-04-17T03-35-30-00-00_squidpy-evidence-policy-agent-probe_PnyxRmsoZQbTp8xhCP9ocT.eval` (final v1.2 Sonnet rerun; unchanged stable fail/control pattern under the new contract)
- `logs-prod/2026-04-17T03-37-09-00-00_squidpy-evidence-policy-agent-probe_Q3o5WVk8z3JCL2U6Mn8Vt8.eval` (final v1.2 Haiku rerun after explicit skip-inspection guidance; now matches `gpt-4o-mini` and Sonnet exactly)

**v1.2 non-mock judge extension:**
- `logs-prod/2026-04-17T15-09-29-00-00_squidpy-evidence-policy-agent-probe_WRsMysX5KPnHyeCitTB4BQ.eval` (first live-judge extension using `openai/gpt-4o-mini` as both authoring model and judge; proves the non-mock runtime path, but under-credits the control sample and emits one parse-level `judge_error`)
- `logs-prod/2026-04-17T15-15-11-00-00_squidpy-evidence-policy-agent-probe_D6ti4iFVYTxyCxYHPtx54p.eval` (stronger live-judge extension using `openai/o3-mini`; preserves all three targeted control leaves, but broadens the control score and no longer lands the exact intended fail-arm policy reasons)
- `logs-prod/2026-04-17T17-08-22-00-00_squidpy-evidence-policy-agent-probe_3PgCvjdMBkdkKby3arErVs.eval` (calibrated `o3-mini` live-judge rerun after exact-leaf guardrails and retry-on-parse were added; collapses the broad overpass set and returns the mean score to the v1.2 mock-baseline level)
- `logs-prod/2026-04-17T17-31-52-00-00_squidpy-evidence-policy-agent-probe_TnUTWPrTLQUM24gGo9j6ya.eval` (execution-clarified mock-baseline rerun; keeps the same three intended control passes, but now the runtime line names `sq.datasets.visium_hne_adata()` explicitly)
- `logs-prod/2026-04-17T17-33-34-00-00_squidpy-evidence-policy-agent-probe_mZHU6eGr7VowxLNyBX8KZJ.eval` (execution-clarified live `o3-mini` follow-up; fail arm stays at 0.000, the intended execution leaf now passes, and the remaining live-judge delta is extra but hand-gradeable leaf credit rather than a missing targeted pass)
- `logs-prod/2026-04-19T00-52-46-00-00_squidpy-evidence-policy-agent-probe_f2KkxWjVwbeyXCd8dZcwsY.eval` (successful post-fix live rerun after OpenAI balance was restored; removes the old `moran_geary_written` over-credit and is now the promoted live successor artifact)

**April 21-22, 2026 GeneLab prompt-hardening sequence:**
- `logs-prod/2026-04-21T20-06-00-00-00_scireplicbench_BmPYCdd9VLr2rBYJMsoD2D.eval` (first real `genelab_benchmark` production attempt; still wandered into `v4/evaluation/*.json`, copied scratchpad content into `run.sh`, and failed precheck)
- `logs-prod/2026-04-21T20-47-58-00-00_scireplicbench_EBqDy3e3CazvWNdmfS3Roz.eval` (task-path guidance fix; now starts from `A*_lomo` paths, but keeps the main workflow inside transient `python()` tool calls and still fails precheck)
- `logs-prod/2026-04-21T21-19-53-00-00_scireplicbench_NBYyMZFQxnFgXhq574JLxv.eval` (saved-submission wording fix; writes `benchmark_analysis.py` and `run.sh`, but uses `echo "...\\n..."` for multi-line files, leaving broken one-line outputs and failing precheck)
- `logs-prod/2026-04-21T23-19-58-00-00_scireplicbench_QAF72c7NR4GoXnh37fwfmw.eval` (newline-safe file-writing fix; first GeneLab run to pass precheck and grade all 55 leaves, but it still submits placeholder outputs without executing a meaningful workflow, so all judged leaves score 0)
- `logs-prod/2026-04-21T23-53-16-00-00_scireplicbench_KjSseoSXfrAmYsPrrQJMjv.eval` (execute-before-submit wording fix; regresses to `echo "...\\n..."` file creation during debugging, so it falls back behind the precheck gate again)
- `logs-prod/2026-04-22T06-12-20-00-00_scireplicbench_PwWmiCMEEMchQoJv4x5zky.eval` (first `workspace_text_file` rerun; interrupted by a tool bug when the new file helper rejected `/workspace/input/paper_bundle/paper.md` reads instead of returning a normal tool error)
- `logs-prod/2026-04-22T06-56-22-00-00_scireplicbench_RFEwu74ZsfRSuMdt2mDTmD.eval` (fixed `workspace_text_file` rerun; uses durable reads/writes and passes precheck, but still assumes flat tissue-root files like `labels.csv` and submits only a manifest)
- `logs-prod/2026-04-22T07-34-32-00-00_scireplicbench_8aAZafctZVmMmkuFwKRYnG.eval` (fold-layout guidance rerun; now targets real `fold_*` paths and durable files, but still dies on sample-ID/index misuse inside model fitting)
- `logs-prod/2026-04-22T14-19-06-00-00_scireplicbench_3L2uDjJEF6FyrXXkYsLQ9Z.eval` (index-alignment guidance rerun; loads with `index_col=0`, aligns `X`/`y`, uses real classifiers, writes a real `lomo/summary.tsv`, and emits five output artifacts, but still hard-codes one demo fold and fills the rest of the required outputs with placeholders)
- `logs-prod/2026-04-22T15-34-37-00-00_scireplicbench_2mqb75xQbNCAaqa3p4z4Cs.eval` (no-placeholder / multi-fold guidance rerun; explores real `fold_*` directories and switches to probability-based AUROC, but spends the budget on debug-heavy scripts and exits with only `/workspace/output/submission_manifest.json`)

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

## v0.3 rerun outcome

v0.3 adds leaf-level evidence hardening on top of the v0.2 precheck: passing `code_development` leaves now require verbatim non-README evidence under `/workspace/submission`, and passing `execution` leaves require verbatim non-README evidence under `/workspace/output`. The April 16, 2026 reruns kept the same three agents, same `squidpy_spatial` image, same 40-message budget, and same `gpt-4o-mini` judge.

| Agent | v0.2 score | v0.3 score | v0.2 wall-clock | v0.3 wall-clock | Judge calls v0.2 → v0.3 |
|---|---:|---:|---|---|---|
| openai/gpt-4o-mini | 0.000 | 0.000 | 1 m 47 s | 3 m 09 s | 0 → 0 |
| anthropic/claude-haiku-4-5 | 0.000 | 0.000 | 2 m 32 s | 3 m 27 s | 0 → 0 |
| anthropic/claude-sonnet-4-6 | 0.000 | 0.000 | 1 m 42 s | 3 m 03 s | 0 → 0 |

Findings:

1. **The public `squidpy_spatial` matrix is still precheck-gated.** All three v0.3 reruns ended with `precheck.ok = false`, `leaves_graded = 0`, and no leaf-level judge calls.
2. **The archived v0.1 false positives now collapse under the current scorer.** Replaying the two old `GaKiuf8G` passing leaves against their stored `Observed reality` blocks turns both into `evidence_policy_failed: README-style prose is not valid passing evidence`.
3. **The benchmark-visible live result is unchanged from v0.2.** On the current three-agent / one-paper setup, v0.3 confirms that the honest score is still 0.000 across the board; the incremental v0.3 value is defensive hardening plus an archived false-positive replay, not a new live score delta on these logs.
4. **That Inspect-level precheck-passing trigger is now implemented in v0.4 below.** v0.3 still leaves the public `squidpy_spatial` matrix numerically unchanged, but it set up the evidence-policy path that the new deterministic live probe now exercises.

## v0.4 live Inspect evidence-policy probe

v0.4 adds a deterministic internal harness, `evidence_policy_probe`, whose only job is to drive the shipped scorer through a real Inspect run after precheck success. It runs inside the smoke Docker sandbox, uses a local `mockllm/model` judge, and stages artifacts with a deterministic solver rather than a frontier agent. This is not a new scientific-paper benchmark result; it is a live runtime proof that the benchmark-visible `.eval` path now emits `evidence_policy_failed` exactly where intended.

| Sample | Precheck | Overall | code_development | execution | result_match |
|---|---|---:|---:|---:|---:|
| `evidence_policy_probe_prose_fail` | passed | **0.000** | 0.000 | 0.000 | 0.000 |
| `evidence_policy_probe_control_pass` | passed | **1.000** | 1.000 | 1.000 | 1.000 |

Findings:

1. **This is the first live Inspect-level log where the artifact-presence precheck passes and the scorer emits `evidence_policy_failed`.** The prose-trap sample is zeroed with three distinct reasons: README-style code evidence, bare output-path execution evidence, and a submission-side metric claim.
2. **The v0.3 policy is selective rather than blanket-rejecting.** The control sample uses the same 3-leaf rubric and same judge, but passes cleanly because its quoted evidence comes from `pipeline.py`, `results.log`, and `metrics.txt`.
3. **At the v0.4 stage, the remaining gap shifted from runtime plumbing to paper realism.** Once the internal harness proved the Inspect + sandbox + scorer path, the next step became moving the same proof onto a real paper package rather than stopping at an internal fixture.

## v0.5 live Squidpy-paper evidence-policy probe

v0.5 takes that next step. It keeps the deterministic solver and local `mockllm/model` judge, but swaps in the real `squidpy_spatial` paper bundle, full 65-leaf rubric, and scientific Docker image from `compose.squidpy_spatial.yaml`. The probe targets the exact historical false-positive leaf types:

- `squidpy_spatial/code_development/image_features_segmentation/compute_segmentation_features`
- `squidpy_spatial/execution/datasets_and_containers/visium_dataset_executes`
- `squidpy_spatial/result_match/spatial_statistics/geary_rank_overlap_threshold`

| Sample | Precheck | Overall | Targeted code leaf | Targeted execution leaf | Targeted result leaf |
|---|---|---:|---:|---:|---:|
| `squidpy_spatial_evidence_probe_prose_fail` | passed | **0.000** | 0 | 0 | 0 |
| `squidpy_spatial_evidence_probe_control_pass` | passed | **0.045** | 1 | 1 | 1 |

Findings:

1. **The evidence policy is now proven on a real paper package, not just an internal harness.** The live `.eval` log uses the actual `squidpy_spatial` rubric and image, and the prose-trap sample still zeroes out once scorer enforcement runs.
2. **The exact historical false-positive leaf types now fail for the right reasons.** The fail sample lands at `README-style prose is not valid passing evidence`, `execution leaves require output evidence with captured content or runtime text, not a bare output-file path`, and `result_match leaves require non-README output-file content, not submission-side claims or code comments`.
3. **The matched control proves this is not overcorrection.** Under the same full 65-leaf Squidpy rubric, the control sample preserves all three targeted leaves as valid passes, yielding `overall = 0.045`.
4. **The remaining gap is now naturalism, not paper coverage.** We have live proof on the real paper package, but it is still a deterministic solver + mock judge harness rather than a frontier agent generating the sample organically.

## v0.9 stabilized frontier-agent Squidpy evidence-policy probe

v0.9 keeps the same real `squidpy_spatial` paper bundle, full 65-leaf rubric, scientific Docker image, frontier `openai/gpt-4o-mini` authoring agent, and local `mockllm/model` judge as v0.6. The difference is probe fidelity. v0.7 and v0.8 showed that once the frontier agent was nudged toward bash-only authoring, the remaining failure mode was malformed multi-line file writes: the agent kept using temporary interpreter sessions or `echo` with escaped newlines, which caused the fail arm to die at precheck before the scorer could evaluate the intended policy trap. v0.9 closes that loop by explicitly steering the agent toward bash heredocs for multi-line files and away from brittle `echo` patterns.

| Sample | Precheck | Overall | Targeted code leaf | Targeted execution leaf | Targeted result leaf |
|---|---|---:|---:|---:|---:|
| `squidpy_spatial_evidence_probe_prose_fail` | passed | **0.000** | 0 | 0 | 0 |
| `squidpy_spatial_evidence_probe_control_pass` | passed | **0.045** | 1 | 1 | 1 |

Findings:

1. **The frontier-agent gap is now closed on a real paper package with exact policy-trigger fidelity.** In the final `c8MepEBS` rerun, both samples clear the v0.2 artifact-presence precheck and all 65 leaves are graded inside the real `squidpy_spatial` runtime.
2. **The matched control still survives the hardened scorer exactly where it should.** The frontier-authored control sample keeps the three targeted Squidpy leaves as valid passes, with evidence in `/workspace/submission/pipeline.py`, `/workspace/output/agent/run.log`, and `/workspace/output/agent/geary_metrics.txt`, yielding `overall = 0.045`.
3. **The prose-trap sample now fails for the exact intended reasons on a frontier-authored trace.** In `c8MepEBS`, the targeted leaves zero as `README-style prose is not valid passing evidence`, `execution leaves require output evidence with captured content or runtime text, not a bare output-file path`, and `result_match leaves require non-README output-file content, not submission-side claims or code comments`.
4. **The v0.7-v0.9 development loop identified the real harness risk: malformed file authoring, not scorer behavior.** v0.7 regressed both samples by letting the agent rely on ephemeral interpreter state, and v0.8 still let the fail arm write malformed one-line Python via `echo`. The final v0.9 heredoc guidance fixed the authoring path without changing the scorer.
5. **The remaining gap is now judge realism and model breadth, not probe correctness.** The live frontier probe is faithful on one real paper, but it still uses a local mock judge and only one authoring model.

## v1.2 three-model frontier-agent Squidpy evidence-policy probe

v1.2 carries the same real `squidpy_spatial` paper bundle, full 65-leaf rubric, scientific Docker image, and local `mockllm/model` judge forward from v1.1, but promotes the authoring side to three stabilized frontier models: `openai/gpt-4o-mini`, `anthropic/claude-sonnet-4-6`, and `anthropic/claude-haiku-4-5`. The key engineering change between v1.1 and v1.2 was prompt robustness for smaller agents. The first Haiku cross-model attempt showed that the probe contract was already sufficient for file authoring, but Haiku still spent budget re-reading the bundle and data directories; the fail arm stayed clean, yet the control arm lost its output evidence and fell to `overall = 0.0135`. `src/scireplicbench/probes.py` now states explicitly that the authoring contract is sufficient and bundle inspection should be skipped unless file creation or path discovery is actually blocked.

| Run | Agent | Fail arm | Control arm | Notes |
|---|---|---:|---:|---|
| `Cr4bjhKb` | openai/gpt-4o-mini | 0.000 | 0.045 | final `gpt-4o-mini` v1.2 rerun |
| `PnyxRmso` | anthropic/claude-sonnet-4-6 | 0.000 | 0.045 | final Sonnet v1.2 rerun |
| `Q3o5WVk8` | anthropic/claude-haiku-4-5 | 0.000 | 0.045 | final Haiku v1.2 rerun |

Findings:

1. **The frontier-agent probe now generalizes cleanly across three authoring models on the same real paper package.** In all three final v1.2 reruns, the fail arm and control arm clear precheck, all 65 leaves are graded, the fail arm lands at `overall = 0.000`, and the control arm lands at `overall = 0.045`.
2. **The targeted leaves are now symmetric across `gpt-4o-mini`, Sonnet, and Haiku.** In all three v1.2 examples, the fail arm zeroes for the same three exact policy reasons and the control arm preserves the same three targeted leaves with evidence in `pipeline.py`, `run.log`, and `geary_metrics.txt`.
3. **The remaining prompt fragility exposed by the first Haiku run is now closed.** The intermediate `TUSBgDp4` run showed that a smaller frontier model could waste its budget on unnecessary bundle inspection even when the authoring contract already specified what to write. The shipped probe now says that the contract is sufficient and that bundle inspection should be skipped unless file creation is blocked.
4. **The remaining gap is now judge realism and paper breadth more than model breadth.** v1.2 is strong evidence that the frontier-agent harness is robust across three current authoring models, but it still uses a local mock judge and one paper.

## v1.2 non-mock judge extension

The next step after stabilizing the three-model mock-judge harness was to keep the same real `squidpy_spatial` paper bundle, the same `gpt-4o-mini` authoring trace, and the same scorer, but replace the local `mockllm/model` judge with real OpenAI judges. `scripts/run_evidence_policy_probe.py` and the probe task constructors now accept a `--judge-model` override, so the live-judge path uses the shipped scorer and prompt rather than a special-case harness. Two judge models were exercised: `openai/gpt-4o-mini` as a cheap live-judge sanity check and `openai/o3-mini` as the production-style reasoning anchor already named in the repo's phase-4 plans.

| Run | Judge | Fail arm | Control arm | Notes |
|---|---|---:|---:|---|
| `WRsMysX5` | openai/gpt-4o-mini | 0.000 | 0.085 | proves the live-judge path works, but under-credits valid code/execution evidence and emits one parse-level `judge_error` |
| `D6ti4iFV` | openai/o3-mini | 0.000 | 0.170 | preserves all three targeted control leaves, but broadens the control score and drifts away from the exact intended fail-arm policy reasons |
| `3PgCvjdM` | openai/o3-mini (calibrated prompt) | 0.000 | 0.043 | collapses the broad result-match drift and lands three control passes, but still swaps the intended execution leaf for `compute_image_features` |
| `mZHU6eGr` | openai/o3-mini (execution-clarified control) | 0.000 | 0.087 | keeps the intended execution leaf once the control run-log names `sq.datasets.visium_hne_adata()` directly; extra credit now comes from three additional, plausibly defensible leaves |
| `f2KkxWjV` | openai/o3-mini (post-fix execution-clarified rerun) | 0.000 | 0.087 | preserves the intended execution leaf and removes the old `moran_geary_written` over-credit; the remaining extra pass is `join_image_features_to_adata`, which is a code-side interpretation of the Squidpy call rather than a hidden-reference metric artifact |

Findings:

1. **The non-mock judge path is now operational.** Both live-judge reruns clear precheck, grade all 65 leaves per sample, and write sanitized artifacts without any scorer-side mocking.
2. **`gpt-4o-mini` is too brittle to serve as the promoted live judge for this probe.** In `WRsMysX5`, the fail arm stays at 0.000, but the control arm only reaches `overall = 0.085`, the code and execution targeted leaves are under-credited, and one fail-arm leaf becomes `judge_error: ValueError: Judge evidence_quote must be non-empty.`
3. **`o3-mini` becomes a plausible live-judge candidate once the prompt is calibrated.** The first `o3-mini` attempt in `D6ti4iFV` over-passed eleven control leaves and inflated the control arm to `overall = 0.170`. After exact-leaf guardrails were added to the judge prompt and malformed outputs got one retry, the calibrated rerun `3PgCvjdM` drops back to `overall = 0.043`, essentially matching the v1.2 mock-baseline mean.
4. **The old execution mismatch was probe ambiguity more than a structural live-judge blind spot.** In `3PgCvjdM`, the live judge preserved `compute_image_features` instead of the intended `visium_dataset_executes` leaf. After the control run-log was sharpened to name `sq.datasets.visium_hne_adata()` explicitly, both `mZHU6eGr` and the fresh successor `f2KkxWjV` preserve the intended execution leaf while keeping the fail arm at 0.000.
5. **The historically disputed over-credit is gone on the fresh live successor.** The provisional review panel still covers 20 leaves total on `GaKiuf8G` and `mZHU6eGr`, where `openai/gpt-4o-mini` matches the provisional reviewer on `0.800` of items and `openai/o3-mini` on `0.900`, and where the lone historical disagreement is `moran_geary_written`. The current scorer rejects that execution-evidence pattern deterministically on archived replay, and the fresh post-fix live rerun `f2KkxWjV` no longer grants that leaf at all. Its remaining sixth pass is `join_image_features_to_adata`, which is tied to the real Squidpy image-feature call rather than a hidden-reference overlap metric. Formal human review of that successor artifact is still on hold, but the clearly invalid historical pass is no longer present.

## What the scores mean

- **Smoke runs (0.000):** The smoke sandbox has no scientific Python stack. The agent cannot produce a runnable replication; the judge correctly grades every leaf 0 with evidence-quote `(no submission artifacts were produced in /workspace/submission or /workspace/output)`. A non-zero score on smoke would be a bug.
- **Production runs vary by agent behaviour, not capability:**
  - **`gpt-4o-mini` → 0.028.** Reads the paper bundle, runs `prepare_data.sh` (self-corrects a missing `numcodecs` with in-container `pip install`), creates `/workspace/submission` with a README plus empty `.py` stubs. 2 of 65 leaves pass on README-based evidence.
  - **`claude-haiku-4-5` → 0.000.** Tries to `import squidpy` inside the sandbox, hits a zarr v3 API incompatibility, spends the message budget diagnosing it. No README scaffold, so no false-positive surface for the judge.
  - **`claude-sonnet-4-6` → 0.000.** Spends the budget diagnosing a `pkg_resources` import issue. Same shape as Haiku — attempts real work, gets stopped by an environment wrinkle, produces no scaffold for the judge to over-credit.

The v0.1 three-agent delta exposed a judge-lenience mode that flipped model ordering: a weaker agent scored higher by doing less-substantive but more-scaffold-looking work. The v0.2 reruns show that this was a grading artifact rather than a real capability difference: once empty-scaffold submissions are intercepted before leaf grading, all three agents converge honestly at 0.000. The April 16, 2026 v0.3 reruns confirm that the public `squidpy_spatial` matrix still stops at that earlier gate, the v0.4 deterministic probe proves the live Inspect scorer path, the v0.5 Squidpy-paper probe proves the same behavior on the real paper bundle and rubric, and v1.2 extends that proof to three frontier-agent-generated precheck-passing traces that now land the exact intended policy reasons symmetrically. The new live-judge extension proves the same runtime path can now be exercised against real judges, but it also shows that judge calibration remains open. This is documented as modes 2, 3, and 7 in [failure_taxonomy.md](failure_taxonomy.md).

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

### `VN3Jn8x7`, `TJQKBPfv`, `WvLKMqep` — v0.3 production reruns

| Run | Agent | Wall-clock | Tool calls | Outcome |
|---|---|---|---|---|
| `VN3Jn8x7` | openai/gpt-4o-mini | 189 s | `scratchpad` × 9, `bash` × 10, `python` × 0 | `precheck.ok = false`, `leaves_graded = 0` |
| `TJQKBPfv` | anthropic/claude-haiku-4-5 | 207 s | `scratchpad` × 1, `bash` × 18, `python` × 0 | `precheck.ok = false`, `leaves_graded = 0` |
| `WvLKMqep` | anthropic/claude-sonnet-4-6 | 183 s | `scratchpad` × 0, `bash` × 19, `python` × 0 | `precheck.ok = false`, `leaves_graded = 0` |

All three share the same precheck reason: `no Python file with a non-trivial function or module body was produced under /workspace/submission`. That means the v0.3 leaf-evidence policy did not activate on any live sample in this rerun batch.

### Archived `GaKiuf8G` replay under the v0.3 evidence policy

Using the stored v0.1 leaf judgements plus their archived judge prompts from `logs-prod/2026-04-14T02-40-31-00-00_scireplicbench_GaKiuf8GTW7q6BLSMRNC6K.eval`, the two original passing leaves now hard-fail under the current scorer:

| Leaf | v0.1 outcome | v0.3 replay outcome |
|---|---|---|
| `squidpy_spatial/code_development/image_features_segmentation/compute_segmentation_features` | pass on README quote | `evidence_policy_failed: README-style prose is not valid passing evidence` |
| `squidpy_spatial/execution/datasets_and_containers/visium_dataset_executes` | pass on README quote | `evidence_policy_failed: README-style prose is not valid passing evidence` |

This is the first direct proof that the new v0.3 leaf-evidence layer removes the exact false positives that inflated `GaKiuf8G` in v0.1.

### `UHz9awZj` — v0.4 live Inspect evidence-policy probe

- Status: success
- Sandbox: smoke Docker image via `environments/compose.smoke.yaml`
- Wall-clock: 41 s
- Eval shape: 2 deterministic samples, no frontier agent model (`none/none`), local `mockllm/model` judge
- Mean overall score across the two samples: 0.500
- `evidence_policy_probe_prose_fail`: precheck passes, but every leaf is zeroed with `evidence_policy_failed`
- `evidence_policy_probe_control_pass`: precheck passes and all three leaves score 1.000
- Purpose: benchmark-runtime validation harness for the shipped v0.3/v0.4 evidence policy, not a scientific capability measurement

### `DxjYt2CF` — v0.5 live Squidpy-paper evidence-policy probe

- Status: success
- Sandbox: real `compose.squidpy_spatial.yaml` scientific image
- Wall-clock: 47 s
- Eval shape: 2 deterministic samples, no frontier agent model (`none/none`), local `mockllm/model` judge
- Mean overall score across the two samples: 0.022
- `squidpy_spatial_evidence_probe_prose_fail`: precheck passes, but the three targeted Squidpy leaves zero out as `evidence_policy_failed`
- `squidpy_spatial_evidence_probe_control_pass`: the same three targeted Squidpy leaves survive, yielding `overall = 0.045`
- Purpose: real-paper validation harness for the shipped evidence policy, still deterministic rather than an organic frontier-agent trace

### `c8MepEBS` — v0.9 live frontier-agent Squidpy evidence-policy probe

- Status: success
- Sandbox: real `compose.squidpy_spatial.yaml` scientific image
- Wall-clock: 66 s
- Eval shape: 2 frontier-agent-authored samples (`openai/gpt-4o-mini`), local `mockllm/model` judge
- Mean overall score across the two samples: 0.022
- `squidpy_spatial_evidence_probe_prose_fail`: precheck passes and all three targeted leaves zero out for the exact intended reasons: README-style code evidence, bare output-path execution evidence, and a submission-side metric claim
- `squidpy_spatial_evidence_probe_control_pass`: precheck passes and the same three targeted Squidpy leaves survive, yielding `overall = 0.045`
- Purpose: stabilized frontier-agent-generated real-paper validation harness for the shipped evidence policy

### `Cr4bjhKb`, `PnyxRmso`, and `Q3o5WVk8` — v1.2 three-model frontier-agent Squidpy evidence-policy probe

- Status: success
- Sandbox: real `compose.squidpy_spatial.yaml` scientific image
- Wall-clock: 41 s (`gpt-4o-mini`), 66 s (Sonnet), and 38 s (Haiku)
- Eval shape: 2 frontier-agent-authored samples per run, local `mockllm/model` judge
- Mean overall score across the two samples: 0.022 in all three runs
- `squidpy_spatial_evidence_probe_prose_fail`: precheck passes and all three targeted leaves zero out with the same three intended policy reasons in all three models
- `squidpy_spatial_evidence_probe_control_pass`: precheck passes and the same three targeted Squidpy leaves survive in all three models, yielding `overall = 0.045`
- Purpose: first three-model frontier-agent real-paper validation harness for the shipped evidence policy

### `WRsMysX5` and `D6ti4iFV` — v1.2 non-mock judge extension

- Status: success
- Sandbox: real `compose.squidpy_spatial.yaml` scientific image
- Wall-clock: 4 m 12 s (`openai/gpt-4o-mini` judge) and 7 m 27 s (`openai/o3-mini` judge)
- Eval shape: 2 frontier-agent-authored samples per run, live OpenAI judge models
- Mean overall score across the two samples: 0.042 (`gpt-4o-mini` judge) and 0.085 (`o3-mini` judge)
- `WRsMysX5`: fail arm stays at `overall = 0.000`, but the control arm reaches only `0.085`; the targeted result leaf passes while the targeted code and execution leaves are under-credited
- `D6ti4iFV`: fail arm stays at `overall = 0.000`, and the targeted control code/execution/result leaves all pass, but the control arm broadens to `overall = 0.170`
- Purpose: first real-judge extension of the stabilized Squidpy frontier-agent probe; shows the scorer path works without mocking and surfaces judge-calibration gaps

### `3PgCvjdM` — calibrated `o3-mini` live-judge extension

- Status: success
- Sandbox: real `compose.squidpy_spatial.yaml` scientific image
- Wall-clock: 10 m 24 s
- Eval shape: 2 frontier-agent-authored samples, live `openai/o3-mini` judge under the calibrated exact-leaf prompt
- Mean overall score across the two samples: 0.022
- `squidpy_spatial_evidence_probe_prose_fail`: precheck passes and all leaves stay at 0
- `squidpy_spatial_evidence_probe_control_pass`: precheck passes and exactly three leaves survive, yielding `overall = 0.043`
- Surviving control leaves: `compute_image_features`, `compute_segmentation_features`, and `geary_rank_overlap_threshold`
- Purpose: calibrated live-judge candidate that removes the broad result-match drift from `D6ti4iFV` and nearly matches the deterministic v1.2 baseline

### `TnUTWPrT`, `mZHU6eGr`, and `f2KkxWjV` — execution-clarified follow-up

- Status: success
- Sandbox: real `compose.squidpy_spatial.yaml` scientific image
- Wall-clock: 30 s for the mock rerun and 8 m 38 s for the live `openai/o3-mini` rerun
- Eval shape: 2 frontier-agent-authored samples per run on the same real `squidpy_spatial` paper bundle
- `TnUTWPrT`: the control arm still lands exactly the intended three leaves at `overall = 0.045`, but the runtime line now names `sq.datasets.visium_hne_adata()` explicitly
- `mZHU6eGr`: the fail arm stays at `overall = 0.000`, and the control arm rises to `overall = 0.087`
- `f2KkxWjV`: the fail arm stays at `overall = 0.000`, and the control arm lands at `overall = 0.087` again after the post-fix rerun completes successfully under the current scorer
- Surviving control leaves in `mZHU6eGr`: `load_visium_dataset`, `compute_image_features`, `compute_segmentation_features`, `visium_dataset_executes`, `moran_geary_written`, and `geary_rank_overlap_threshold`
- Surviving control leaves in `f2KkxWjV`: `load_visium_dataset`, `compute_image_features`, `compute_segmentation_features`, `join_image_features_to_adata`, `visium_dataset_executes`, and `geary_rank_overlap_threshold`
- The fresh live successor still has six passing control-arm leaves, but the historically disputed `moran_geary_written` leaf is gone
- The provisional review panel has now been widened to 20 leaves total by pairing those six live-pass examples plus four matched live fails with 10 archived `GaKiuf8G` examples
- Current provisional exact-match rates in [judge_reliability.md](judge_reliability.md): `openai/gpt-4o-mini = 0.800`, `openai/o3-mini = 0.900`
- Second-rater workflow: blinded review exports now exist at `judge_eval/review_packet_v0_1_false_positive_and_mZHU6eGr_blinded.json` and `judge_eval/review_packet_v0_1_false_positive_and_mZHU6eGr_blinded.csv`, so a real second reviewer can score the same 20 leaves without seeing the provisional labels or judge model.
- The only current disagreement on `mZHU6eGr` is `moran_geary_written`, which the manual review marks 0 because the output file contains `geary_top20_rbo=0.90` rather than a raw Moran/Geary result artifact or ranked table
- Current scorer state: execution leaves now reject hidden-reference comparison metrics such as `*_rbo` as proof that an analysis output was written; archived replay of the disputed `mZHU6eGr` leaf now flips to `evidence_policy_failed`
- Quota recovery status: two post-fix live attempts failed on quota (`fa5G3aTA` and `g7eC3Ph9`), but the April 19, 2026 restored-balance rerun `f2KkxWjV` completed successfully in 7 m 11 s and is now the promoted live successor artifact.
- Krippendorff's alpha is intentionally reported as N/A until a second human rater is added
- Purpose: show that the prior `visium_dataset_executes` miss was caused by underspecified control evidence; the remaining live-judge gap is now interpretable extra credit rather than missing intended credit

## Run matrix snapshot (filled as pilots land)

| Phase | Agents | Judge | Papers | Seeds | Runs | Mean score | Notes |
|---|---|---|---:|---:|---:|---:|---|
| Dev smoke (v0.1) | gpt-4o-mini | gpt-4o-mini | 1 | 1 | 2 | 0.000 | smoke sandbox: no scientific stack |
| Dev production (v0.1) | gpt-4o-mini / haiku-4-5 / sonnet-4-6 | gpt-4o-mini | 1 | 1 | 3 | 0.009 (mean) | gpt-4o-mini=0.028, haiku=0.000, sonnet=0.000; ordering flip observed |
| Dev production (v0.2) | gpt-4o-mini / haiku-4-5 / sonnet-4-6 | gpt-4o-mini | 1 | 1 | 3 | **0.000** | precheck active; all three converge honestly at 0; judge skipped |
| Dev production (v0.3) | gpt-4o-mini / haiku-4-5 / sonnet-4-6 | gpt-4o-mini | 1 | 1 | 3 | **0.000** | v0.3 hardening shipped, but all three still fail the same task-level precheck before judge |
| Validation harness (v0.4) | deterministic solver | mockllm/model | 1 internal probe | 1 | 1 | **0.500** | first live Inspect proof that precheck-passing prose gets zeroed while valid evidence survives |
| Validation harness (v0.5) | deterministic solver | mockllm/model | 1 Squidpy paper probe | 1 | 1 | **0.022** | first real-paper proof that the targeted Squidpy false-positive leaf types now flip correctly |
| Validation harness (v0.9) | gpt-4o-mini frontier agent | mockllm/model | 1 Squidpy paper probe | 1 | 1 | **0.022** | stabilized single-model real-paper trace; both arms pass precheck and the fail arm hits the exact three intended policy reasons |
| Validation harness (v1.2) | gpt-4o-mini + claude-sonnet-4-6 + claude-haiku-4-5 frontier agents | mockllm/model | 1 Squidpy paper probe | 1 | 3 | **0.022** | three-model real-paper trace; the first Haiku cross-model attempt exposed a prompt-robustness budget loss, and v1.2 closes it by making the authoring contract explicitly sufficient |
| Validation harness (v1.2 live judge) | gpt-4o-mini frontier agent | openai/gpt-4o-mini | 1 Squidpy paper probe | 1 | 1 | **0.042** | first non-mock judge extension; proves the live-judge path, but under-credits the control sample and emits one parse-level judge error |
| Validation harness (v1.2 live judge) | gpt-4o-mini frontier agent | openai/o3-mini | 1 Squidpy paper probe | 1 | 1 | **0.085** | stronger live judge; preserves the three targeted control leaves, but broadens the control score beyond the intended three-leaf envelope |
| Validation harness (v1.2 live judge, calibrated) | gpt-4o-mini frontier agent | openai/o3-mini | 1 Squidpy paper probe | 1 | 1 | **0.022** | calibrated live judge; removes the broad overpass set and returns to the v1.2 baseline mean, with one residual execution-vs-code mismatch |
| 4a pilot | pending | pending | — | — | 0 | pending | will cover 3 papers + deepseek |
| 4b production | pending | pending | — | — | 0 | pending | ≥ 3 seeds, two-container reproducer |

## Per-paper results

| Paper | Agent | Sandbox | Runs | Mean overall | code_development | execution | result_match |
|---|---|---|---:|---:|---:|---:|---:|
| inspiration4_multiome | — | scientific image built; benchmark-ready data pending | 0 | pending | pending | pending | pending |
| squidpy_spatial | gpt-4o-mini | smoke | 2 | 0.000 | 0.000 | 0.000 | 0.000 |
| squidpy_spatial | gpt-4o-mini | production (v0.1) | 1 | 0.028 | 0.045 | 0.060 | 0.000 |
| squidpy_spatial | claude-haiku-4-5 | production (v0.1) | 1 | 0.000 | 0.000 | 0.000 | 0.000 |
| squidpy_spatial | claude-sonnet-4-6 | production (v0.1) | 1 | 0.000 | 0.000 | 0.000 | 0.000 |
| squidpy_spatial | gpt-4o-mini | production (v0.2 + precheck) | 1 | 0.000 | 0.000 | 0.000 | 0.000 |
| squidpy_spatial | claude-haiku-4-5 | production (v0.2 + precheck) | 1 | 0.000 | 0.000 | 0.000 | 0.000 |
| squidpy_spatial | claude-sonnet-4-6 | production (v0.2 + precheck) | 1 | 0.000 | 0.000 | 0.000 | 0.000 |
| squidpy_spatial | gpt-4o-mini | production (v0.3 + leaf evidence hardening) | 1 | 0.000 | 0.000 | 0.000 | 0.000 |
| squidpy_spatial | claude-haiku-4-5 | production (v0.3 + leaf evidence hardening) | 1 | 0.000 | 0.000 | 0.000 | 0.000 |
| squidpy_spatial | claude-sonnet-4-6 | production (v0.3 + leaf evidence hardening) | 1 | 0.000 | 0.000 | 0.000 | 0.000 |
| squidpy_spatial | deterministic solver | production probe (v0.5 real-paper evidence harness) | 1 eval / 2 samples | 0.022 | 0.022 | 0.030 | 0.018 |
| squidpy_spatial | gpt-4o-mini frontier agent | production probe (v0.9 live frontier-agent harness) | 1 eval / 2 samples | 0.022 | 0.022 | 0.030 | 0.018 |
| squidpy_spatial | gpt-4o-mini frontier agent | production probe (v1.2 three-model harness) | 1 eval / 2 samples | 0.022 | 0.022 | 0.030 | 0.018 |
| squidpy_spatial | claude-sonnet-4-6 frontier agent | production probe (v1.2 three-model harness) | 1 eval / 2 samples | 0.022 | 0.022 | 0.030 | 0.018 |
| squidpy_spatial | claude-haiku-4-5 frontier agent | production probe (v1.2 three-model harness) | 1 eval / 2 samples | 0.022 | 0.022 | 0.030 | 0.018 |
| squidpy_spatial | gpt-4o-mini frontier agent | production probe (v1.2 live judge `gpt-4o-mini`) | 1 eval / 2 samples | 0.042 | 0.000 | 0.000 | 0.095 |
| squidpy_spatial | gpt-4o-mini frontier agent | production probe (v1.2 live judge `o3-mini`) | 1 eval / 2 samples | 0.085 | 0.068 | 0.088 | 0.095 |
| squidpy_spatial | gpt-4o-mini frontier agent | production probe (v1.2 live judge `o3-mini`, calibrated) | 1 eval / 2 samples | 0.022 | 0.045 | 0.000 | 0.036 |
| evidence_policy_probe | deterministic solver | smoke (v0.4 live probe) | 1 | 0.500 | 0.500 | 0.500 | 0.500 |
| genelab_benchmark | gpt-4o-mini | production (first seven prompt-hardening attempts) | 7 | 0.000 | 0.000 | 0.000 | 0.000 |

## Known limitations (current v1.2 state)

1. **Only one paper has a meaningful production artifact so far.** `squidpy_spatial` remains the only paper with a completed production result that yields a stable benchmark story. `inspiration4_multiome` is now one step closer: its image builds, the public upstream analysis repository is staged locally, and the public `OSD-570` processed RNA/ATAC outputs plus ISA metadata are cached locally. The benchmark-ready AnnData or MuData reviewer object is still missing, so a real production eval is still blocked. `genelab_benchmark` is no longer blocked on image build, public data staging, durable file writing, or sample-ID alignment, but the latest April 22, 2026 reruns show an oscillation between a real but toy executed artifact (`3L2uDjJE`) and a stricter debug-heavy no-output artifact (`2mqb75xQ`). The current limiter there is task scaffold quality, not raw prompt wording.
2. **Limited model matrix.** `gpt-4o-mini`, `claude-haiku-4-5`, and `claude-sonnet-4-6` have one production run each on `squidpy_spatial`, and the stabilized frontier-agent evidence-policy probe now covers the same three authoring models; `deepseek-v3` and higher-cost production lineups are still pending.
3. **Single seed.** No variance estimate yet. Phase 4b calls for ≥ 3 seeds.
4. **No self-consistency retry.** The n=3 self-consistency wrapper for disagreement-flagged leaves is implemented in `src/scireplicbench/judge.py` but not yet invoked by `rubric_tree_scorer`.
5. **The frontier-agent probe is now faithful across three authoring models on one paper, and the live-judge gap is now narrow and localized.** The stabilized v1.2 runs still provide the canonical deterministic baseline. The execution-clarified `o3-mini` rerun preserves the intended execution leaf and eliminates the broad overpass set; the widened provisional review panel now puts `openai/o3-mini` at `0.900` exact-match on the sampled live-judge cases, and the current scorer has a narrow deterministic fix for the lone disputed `moran_geary_written` pattern. Fresh replacement live reruns were prepared with stronger on-disk verification instructions, but the April 17 and April 18, 2026 post-fix attempts both aborted on `429 insufficient_quota` before any scorer-complete result was produced, so the historical artifact is still the source of truth. The probe runner now also fails cleanly on that incomplete-log shape instead of cascading into `_write_example`.

## Next milestones

Ordered by priority for a credible artifact:

1. Add a second human rater to the 20-leaf provisional panel in [judge_reliability.md](judge_reliability.md), using `judge_eval/review_packet_v0_1_false_positive_and_mZHU6eGr_blinded.json` or `.csv` so the reviewer sees the same examples without the provisional labels.
2. Fold the fresh live successor `f2KkxWjV` into the human-review panel once the reviewer hold is lifted, so the reliability view no longer stops at the historical `mZHU6eGr` artifact.
3. Finish benchmark-author data staging for `inspiration4_multiome` by materializing or receiving the reviewer-ready AnnData or MuData object, then run the first `gpt-4o-mini` production pass there.
4. For `genelab_benchmark`, stop relying on prompt wording alone and tighten the task scaffold itself: add a benchmark-shaped starter around fold discovery, output writers, and partial-status TSV emission so the agent stops oscillating between placeholder outputs and debug-only scripts.
5. Add `deepseek-v3` to the cheap-model matrix and decide whether a higher-cost `gpt-4o` / `claude-sonnet` production pass is still warranted.
