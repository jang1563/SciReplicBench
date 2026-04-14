# Failure Taxonomy

This document names the concrete failure modes observed while running SciReplicBench agents. It is intentionally written from measured runs, not hypothetical scenarios, so each mode is traceable back to a log artifact. Current coverage is narrow (smoke sandbox, `squidpy_spatial`, one agent, one seed) and will broaden as the matrix fills out.

## Observed modes

### 1. Empty-artifact false-floor grading

- **What it is:** The agent runs to completion or hits `message_limit` without writing any file under `/workspace/submission` or `/workspace/output`. The rubric scorer correctly grades every leaf 0 with evidence-quote `(no submission artifacts were produced in /workspace/submission or /workspace/output)`.
- **Where seen:** `logs-smoke/2026-04-14T01-22-26-00-00_scireplicbench_jqv6qmGgRHBumGqML6kpGN.eval`, `logs-smoke/2026-04-14T01-26-14-00-00_scireplicbench_VAaLhS7Yszu66EQxgmYcC8.eval`.
- **Why it matters for the benchmark:** This is the *correct* behavior for the smoke sandbox (no scientific tools, no data), but the same code path would silently floor real runs if a paper's `prepare_data.sh` failed to stage files or if the agent misunderstood the output contract.
- **Expected mitigation once Phase 4a data is available:** promote a `result_match` leaf per paper to "Any artifact under /workspace/submission" so the mode is visible as a hard failure rather than a graded 0.

### 2. README-only false positives in the judge

- **What it is:** The agent creates `/workspace/submission/README.md` describing the *intended* workflow and `touch`es empty `.py` files named after each analysis stage. The judge, shown only these artifacts plus the rubric, grades some leaves as passing based on the README's natural-language description of what the code would do.
- **Where seen:** `logs-prod/2026-04-14T02-40-31-00-00_scireplicbench_GaKiuf8GTW7q6BLSMRNC6K.eval`. Two leaves passed: `squidpy_spatial/code_development/image_features_segmentation/compute_segmentation_features` and `squidpy_spatial/execution/datasets_and_containers/visium_dataset_executes`. Both passing evidence quotes start with "This README provides instructions on running the Squidpy spatial omics workflow..."
- **Why it matters:** Judge lenience on README text inflates scores for agents that planned but did not execute. A 2/65 pass rate is small, but at scale this could mask the difference between "agent wrote code that runs" and "agent wrote a convincing README."
- **Mitigation options (not yet implemented):** (a) have the judge require the evidence quote to come from a non-README file, (b) add a precheck that a leaf's `code_development` rating requires a non-empty Python source file referencing the relevant function, (c) tighten the judge prompt's `expectations` section to distinguish "describes" from "implements".

### 3. Empty-scaffold submission shape

- **What it is:** The agent's output is structurally plausible — it produces a directory tree and filenames matching the rubric — but the files are empty or stub-only. In the production run the agent ran `touch /workspace/submission/scripts/load_datasets.py` and several sibling files, then stopped.
- **Where seen:** Same `GaKiuf8G` prod log. 12 bash calls over 40 messages; 0 python calls; no executable analysis ever ran inside the sandbox.
- **Why it matters:** This is the precursor to mode 2. A benchmark that only grades file structure will reward empty scaffolding.
- **Mitigation:** At least one `execution` leaf per paper should require the judge to find a line of STDOUT or a file-mtime that could only come from running the code. A stricter form of the "evidence_quote must cite a command or output" rule.

### 4. Tool-call absorption into the scratchpad

- **What it is:** Given the scratchpad + bash + python tool surface, gpt-4o-mini spent 8 of 11 tool calls on `scratchpad` within a 25-message budget and only 3 on `bash`. No `python` call fired.
- **Where seen:** Both smoke runs above; `tool_call counts: {'scratchpad': 8, 'bash': 3}`.
- **Why it matters:** If agents consistently burn message budget on scratchpad bookkeeping, the practical ceiling on what they can *do* with bash/python per sample collapses well below the nominal 25-message cap. This risk is visible even in the smallest smoke run.
- **Partial update from the production run:** at `message_limit=40` on the real scientific image, the ratio inverted (`bash` × 12, `scratchpad` × 7, `python` × 0). Raising the budget moves tool-call share toward shell, but the agent *still* never reached for `python`, which is the tool needed to actually run scanpy/squidpy.
- **Open question:** is this specific to gpt-4o-mini, or does it persist with stronger models? Phase 4a will answer by repeating with Haiku 4.5 and DeepSeek V3 at the same budget.

### 5. Short-budget early termination

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
