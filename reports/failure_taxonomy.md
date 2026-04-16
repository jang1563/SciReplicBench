# Failure Taxonomy

This document names the concrete failure modes observed while running SciReplicBench agents. It is intentionally written from measured runs, not hypothetical scenarios, so each mode is traceable back to a log artifact. Current coverage is still narrow (smoke sandbox plus one three-agent production matrix on `squidpy_spatial`) and will broaden as the matrix fills out.

## Observed modes

### 1. Empty-artifact false-floor grading

- **What it is:** The agent runs to completion or hits `message_limit` without writing any file under `/workspace/submission` or `/workspace/output`. The rubric scorer correctly grades every leaf 0 with evidence-quote `(no submission artifacts were produced in /workspace/submission or /workspace/output)`.
- **Where seen:** `logs-smoke/2026-04-14T01-22-26-00-00_scireplicbench_jqv6qmGgRHBumGqML6kpGN.eval`, `logs-smoke/2026-04-14T01-26-14-00-00_scireplicbench_VAaLhS7Yszu66EQxgmYcC8.eval`.
- **Why it matters for the benchmark:** This is the *correct* behavior for the smoke sandbox (no scientific tools, no data), but the same code path would silently floor real runs if a paper's `prepare_data.sh` failed to stage files or if the agent misunderstood the output contract.
- **Expected mitigation once Phase 4a data is available:** promote a `result_match` leaf per paper to "Any artifact under /workspace/submission" so the mode is visible as a hard failure rather than a graded 0.

### 2. README-only false positives in the judge (flips model ordering) — FIXED in v0.2

- **What it is:** The agent creates `/workspace/submission/README.md` describing the *intended* workflow and `touch`es empty `.py` files named after each analysis stage. The judge, shown only these artifacts plus the rubric, grades some leaves as passing based on the README's natural-language description of what the code would do.
- **Where seen — and why it matters:** Three same-setup runs with different agents on the `squidpy_spatial` scientific sandbox, judged by the same `gpt-4o-mini`:
  - `gpt-4o-mini` agent: **0.028** (2/65 passing). Produced a README + empty stubs.
  - `claude-haiku-4-5` agent: **0.000** (0/65 passing). Tried to `import squidpy`, hit a zarr v3 incompatibility, spent the budget diagnosing. No README scaffold.
  - `claude-sonnet-4-6` agent: **0.000** (0/65 passing). Spent the budget diagnosing a `pkg_resources` import issue. No README scaffold.

  The weaker agent scored higher than both Claude models — not because it did better work, but because its *less-ambitious scaffold* was more legible to a lenient judge. The Claude models' attempts at real execution produced no files the judge could latch onto.

- **Passing-leaf evidence trail (gpt-4o-mini run):** `squidpy_spatial/code_development/image_features_segmentation/compute_segmentation_features` and `squidpy_spatial/execution/datasets_and_containers/visium_dataset_executes`. Both passing evidence quotes start with "This README provides instructions on running the Squidpy spatial omics workflow..."

- **Why it matters for the benchmark:** The judge's scoring behaviour is currently sensitive to submission *shape* in a way that can flip the ordering between agents of different actual capability. Without mitigation, a SciReplicBench score is a noisy proxy for real replication skill.
- **Mitigation shipped in v0.2:** option (d) — artifact-presence precheck. `src/scireplicbench/scorers.py` now invokes `_artifact_presence_precheck` before any LLM judge call. The precheck AST-scans submission `.py` files for non-trivial function or module bodies and rejects empty stubs (`pass`-only, docstring-only, `raise NotImplementedError`). When the gate fails, every leaf is auto-zeroed with a structured `precheck_failed` evidence quote and the judge is never invoked.
- **Empirical evidence the fix works:** rerunning the same three production agents with v0.2 active gave the following before / after scores:
  - `gpt-4o-mini`: **0.028 → 0.000** (the ordering flip is gone)
  - `claude-haiku-4-5`: 0.000 → 0.000
  - `claude-sonnet-4-6`: 0.000 → 0.000
  - All three runs hit `precheck.ok=False` (no `.py` file with a non-trivial body, no non-doc output artifact). The judge was skipped entirely on each rerun. Wall-clock dropped 50–70 % per sample because the 65-leaf grading loop never ran.
- **After-fix log IDs:** `logs-prod/2026-04-14T13-25-26-..._cEsYJL6i...eval` (gpt-4o-mini), `..._13-32-06-..._nQGFXNVZ...eval` (Haiku), `..._13-48-30-..._2EuTNiNq...eval` (Sonnet). Sanitized snapshots in `examples/`.
- **What this does NOT fix:** options (a), (b), and (c) above remain useful future work for richer agents that DO produce non-trivial code but get over-credited on prose explanations of what the code "would" do. v0.2's task-level gate addresses the empty-scaffold pattern; per-leaf code-vs-prose gating is v0.3 scope.

### 3. Empty-scaffold submission shape — FIXED in v0.2 (same mitigation as mode 2)

- **What it is:** The agent's output is structurally plausible — it produces a directory tree and filenames matching the rubric — but the files are empty or stub-only. In the production run the agent ran `touch /workspace/submission/scripts/load_datasets.py` and several sibling files, then stopped.
- **Where seen:** Same `GaKiuf8G` prod log. 12 bash calls over 40 messages; 0 python calls; no executable analysis ever ran inside the sandbox.
- **Why it matters:** This is the precursor to mode 2. A benchmark that only grades file structure will reward empty scaffolding.
- **What v0.2 solved:** `_artifact_presence_precheck` now blocks this exact stub-only pattern before any leaf grading, so empty scaffold directories no longer earn structure points or README-mediated false positives.
- **What remains for v0.3:** Once an agent writes some real code, the scorer still needs per-leaf evidence rules that distinguish executable implementation from descriptive prose. For `code_development` and `execution` leaves, that means requiring non-README code snippets, command invocations, or runtime output rather than accepting a plausible file tree alone.

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

### 6. Sandbox environment wrinkles defeat real execution attempts

- **What it is:** The scientific image resolves deps at build time via `uv`, but two modern packages in the Squidpy stack have version frictions at *import time* that only surface when the agent actually tries to use them:
  - `zarr` v3 changes the API that `numcodecs.blosc` expects. An agent importing `squidpy → spatialdata → xarray → zarr` may hit a `cbuffer` attribute lookup that v3 no longer exposes the same way. Haiku's 40-message run is dominated by diagnosing this.
  - `pkg_resources` was deprecated and is no longer always importable in Python 3.11 slim; some squidpy-adjacent code paths still try to import it. Sonnet spent its budget probing the Python path for a missing `pkg_resources`.
- **Where seen:** `logs-prod/2026-04-14T02-58-39-00-00_scireplicbench_Kfjef4zbDpVAoWmQS7fYDB.eval` (zarr v3), `logs-prod/2026-04-14T03-05-54-00-00_scireplicbench_JeRrV6juZ4nxSBKtAVuK3w.eval` (pkg_resources).
- **Why it matters:** The benchmark cannot separate "agent is bad at Squidpy" from "agent was defeated by a Docker-side environment wrinkle." Fixing the environment is a prerequisite to drawing strong capability claims from the score.
- **Mitigation:** pin `zarr==2.18.3` and `numcodecs<0.16` in `requirements.squidpy_spatial.txt` (already done for zarr; numcodecs pin is pending), pre-install `setuptools` so `pkg_resources` is importable without a shim, and add a container-health smoke that runs `python -c "import squidpy; import scanpy; import spatialdata"` as part of the build.

## Anticipated but not yet observed

Modes the design expects but that no log evidence yet supports:

- **Judge parse failure.** `rubric_tree_scorer` degrades gracefully (score 0, evidence `judge_error: ...`) but we have not yet caught the judge in the act. The instrumentation (`leaves_graded`, `judge_failures`) is already recorded in metadata so a future run with a weaker judge or a malformed leaf will expose this naturally.
- **Method-equivalence drift.** e.g., agent uses `scanpy.pp.combat` where the rubric expects `ComBat-seq` on counts. Will only show up once a stronger agent produces real analyses.
- **Self-grading-bias artifact.** If the Squidpy-anchored judge grades the authored papers leniently, we expect a systematic gap between Squidpy and authored-paper judge-human agreement; waiting on `judge_eval/human_grades.json` to populate.
- **Evaluation leakage across benchmark splits.** For `genelab_benchmark` specifically, an agent could accidentally leak mission-level information across LOMO folds. The rubric flags this, but no production run has executed it yet.

This file is a living document: expand each entry with its real signal as more runs land.
