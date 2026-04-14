# Failure Taxonomy

This document names the concrete failure modes observed while running SciReplicBench agents. It is intentionally written from measured runs, not hypothetical scenarios, so each mode is traceable back to a log artifact. Current coverage is narrow (smoke sandbox, `squidpy_spatial`, one agent, one seed) and will broaden as the matrix fills out.

## Observed modes

### 1. Empty-artifact false-floor grading

- **What it is:** The agent runs to completion or hits `message_limit` without writing any file under `/workspace/submission` or `/workspace/output`. The rubric scorer correctly grades every leaf 0 with evidence-quote `(no submission artifacts were produced in /workspace/submission or /workspace/output)`.
- **Where seen:** `logs-smoke/2026-04-14T01-22-26-00-00_scireplicbench_jqv6qmGgRHBumGqML6kpGN.eval`, `logs-smoke/2026-04-14T01-26-14-00-00_scireplicbench_VAaLhS7Yszu66EQxgmYcC8.eval`.
- **Why it matters for the benchmark:** This is the *correct* behavior for the smoke sandbox (no scientific tools, no data), but the same code path would silently floor real runs if a paper's `prepare_data.sh` failed to stage files or if the agent misunderstood the output contract.
- **Expected mitigation once Phase 4a data is available:** promote a `result_match` leaf per paper to "Any artifact under /workspace/submission" so the mode is visible as a hard failure rather than a graded 0.

### 2. Tool-call absorption into the scratchpad

- **What it is:** Given the scratchpad + bash + python tool surface, gpt-4o-mini spent 8 of 11 tool calls on `scratchpad` within a 25-message budget and only 3 on `bash`. No `python` call fired.
- **Where seen:** Both smoke runs above; `tool_call counts: {'scratchpad': 8, 'bash': 3}`.
- **Why it matters:** If agents consistently burn message budget on scratchpad bookkeeping, the practical ceiling on what they can *do* with bash/python per sample collapses well below the nominal 25-message cap. This risk is visible even in the smallest smoke run.
- **Open question:** is this specific to gpt-4o-mini at `message_limit=25`, or does it persist at higher limits and with stronger models? Phase 4a will answer this by repeating with Haiku 4.5 and DeepSeek V3 at the same budget.

### 3. Short-budget early termination

- **What it is:** At `message_limit=5` the agent's first bash call arrives as the fifth message and never gets a result returned inside the conversation; the run ends "successful" with no tool output ever shown to the agent.
- **Where seen:** `logs-smoke/2026-04-13T22-08-01-00-00_scireplicbench_MdTkRUJL7QnyWbrPaoQdvr.eval`, the pre-scorer plumbing run.
- **Why it matters:** Benchmark operators should treat `message_limit < 10` as smoke-only. Phase 4a is already scheduled at ≥ 25 messages and Phase 4b at 60+.

## Anticipated but not yet observed

Modes the design expects but that no log evidence yet supports:

- **Judge parse failure.** `rubric_tree_scorer` degrades gracefully (score 0, evidence `judge_error: ...`) but we have not yet caught the judge in the act. The instrumentation (`leaves_graded`, `judge_failures`) is already recorded in metadata so a future run with a weaker judge or a malformed leaf will expose this naturally.
- **Method-equivalence drift.** e.g., agent uses `scanpy.pp.combat` where the rubric expects `ComBat-seq` on counts. Will only show up once a real scientific image exercises the rubric.
- **Self-grading-bias artifact.** If the Squidpy-anchored judge grades the authored papers leniently, we expect a systematic gap between Squidpy and authored-paper judge-human agreement; waiting on `judge_eval/human_grades.json` to populate.
- **Evaluation leakage across benchmark splits.** For `genelab_benchmark` specifically, an agent could accidentally leak mission-level information across LOMO folds. The rubric flags this, but no production run has executed it yet.

This file is a living document: expand each entry with its real signal as more runs land.
