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
- **v0.3 follow-up reruns:** April 16, 2026 reruns at `logs-prod/2026-04-16T17-42-16-..._VN3Jn8x7...eval` (gpt-4o-mini), `..._17-48-43-..._TJQKBPfv...eval` (Haiku), and `..._17-57-13-..._WvLKMqep...eval` (Sonnet) landed in the same benchmark-visible state: `precheck.ok=False`, `leaves_graded=0`, `overall=0.000`. That confirms the public `squidpy_spatial` matrix is still stopped by the task-level gate before any richer leaf-level policy can matter.
- **Archived replay proof:** replaying the two `GaKiuf8G` passing leaves (`compute_segmentation_features` and `visium_dataset_executes`) against their stored `Observed reality` blocks under the current scorer converts both to `evidence_policy_failed: README-style prose is not valid passing evidence`.
- **v0.4 live Inspect proof:** `logs-smoke/2026-04-16T23-11-30-..._UHz9awZj...eval` runs the internal `evidence_policy_probe` harness through the full Inspect runtime. Its `evidence_policy_probe_prose_fail` sample passes precheck and is then zeroed with three benchmark-visible `evidence_policy_failed` reasons, while the matched control sample scores 1.000.
- **v0.5 real-paper proof:** `logs-prod/2026-04-16T23-28-48-..._DxjYt2CF...eval` runs the same idea against the real `squidpy_spatial` paper bundle, full rubric, and scientific image. The prose-trap sample still zeroes the exact historical false-positive leaf types, and the matched control sample keeps those same leaves as valid passes.
- **v1.2 three-model frontier-agent proof:** `logs-prod/2026-04-17T03-34-09-..._Cr4bjhKb...eval` (`gpt-4o-mini`), `..._03-35-30-..._PnyxRmso...eval` (Sonnet), and `..._03-37-09-..._Q3o5WVk8...eval` (Haiku) move the same idea onto three stabilized frontier-authored traces on the real `squidpy_spatial` paper package. In all three runs, both arms clear precheck; the fail arm lands at 0.000 with the exact intended README/path/result evidence-policy reasons, while the matched control preserves the three targeted leaves at `overall = 0.045`.
- **v1.2 non-mock judge extension:** `logs-prod/2026-04-17T15-09-29-..._WRsMysX5...eval` (`openai/gpt-4o-mini` judge) and `..._15-15-11-..._D6ti4iFV...eval` (`openai/o3-mini` judge) prove that the same frontier-agent probe can now run against live judges. `gpt-4o-mini` keeps the fail arm at 0.000 but under-credits the control arm and emits one parse-level `judge_error`; `o3-mini` preserves all three targeted control leaves but broadens the control score to `overall = 0.170`, which shows the live-judge path works but is not yet calibrated.
- **Calibrated `o3-mini` follow-up:** `logs-prod/2026-04-17T17-08-22-..._3PgCvjdM...eval` adds exact-leaf guardrails to the judge prompt plus one retry for malformed outputs. That rerun collapses the broad overpass set and returns the mean score to the v1.2 mock-baseline level. The remaining mismatch is narrow: the control arm now preserves `compute_image_features`, `compute_segmentation_features`, and `geary_rank_overlap_threshold`, while the intended `visium_dataset_executes` leaf remains 0.
- **Execution-clarified `o3-mini` follow-up:** `logs-prod/2026-04-17T17-33-34-..._mZHU6eGr...eval` sharpens the control-arm runtime evidence so the log names `sq.datasets.visium_hne_adata()` explicitly. Under that tighter control contract, the fail arm stays at 0.000 and the intended execution leaf now passes. The control arm rises to `overall = 0.087` because three additional leaves (`load_visium_dataset`, `compute_image_features`, and `moran_geary_written`) also receive credit.
- **Successful post-fix live successor:** `logs-prod/2026-04-19T00-52-46-..._f2KkxWjV...eval` reruns that same setup after quota recovery under the current scorer. The fail arm still stays at 0.000, the control arm stays at `overall = 0.087`, but the historically disputed `moran_geary_written` pass disappears. The remaining sixth control-arm pass is now `join_image_features_to_adata`, which is tied to the real Squidpy image-feature call rather than a hidden-reference comparison metric.
- **Expanded provisional review panel:** `judge_eval/human_grades.json` still records a 20-leaf, single-rater review panel: 10 leaves from the archived v0.1 false-positive run `GaKiuf8G` and 10 matched leaves from the historical live artifact `mZHU6eGr`. On that panel, `openai/gpt-4o-mini` exact-matches the provisional reviewer on `0.800` of items and `openai/o3-mini` exact-matches on `0.900`.
- **Historical disputed live-judge leaf:** on the older `mZHU6eGr` artifact, the lone provisional disagreement remains `moran_geary_written`. The manual review marks it 0 because `geary_top20_rbo=0.90` is a benchmark-comparison overlap metric, not a raw Moran/Geary output artifact.
- **Current scorer-side mitigation for that historical leaf:** `src/scireplicbench/scorers.py` now rejects hidden-reference comparison metrics such as `*_rbo`, `*_overlap`, and `ARI` as execution evidence for "written output" leaves. Replaying the archived `mZHU6eGr` `moran_geary_written` leaf through `_enforce_leaf_evidence_policy` now deterministically flips it to `evidence_policy_failed`.
- **v1.0 loophole discovered and fixed:** the intermediate Sonnet rerun `..._ZwS5nw37...eval` showed that an `execution` leaf could still pass on a bare output path if that same path reappeared inside an output-side manifest file. `src/scireplicbench/scorers.py` now rejects path-like execution evidence even when it appears in output-file contents.
- **v1.1 Haiku prompt-robustness bug fixed in v1.2:** the first Haiku cross-model attempt `..._03-28-23-..._TUSBgDp4...eval` showed that a smaller frontier model could waste its budget re-inspecting the bundle and data directories even though the probe contract already specified exactly what to write. `src/scireplicbench/probes.py` now states that the contract is sufficient and that bundle inspection should be skipped unless file creation or path discovery is actually blocked.
- **What this still does NOT prove in the fully naturalistic setting:** options (a), (b), and (c) still matter for richer agents on scientific tasks. v1.2 proves the live runtime path on three frontier-authored samples with faithful fail-arm triggering, and the live-judge extension now has one calibrated `o3-mini` candidate, but calibration across real judges and one paper package is still open.

### 3. Empty-scaffold submission shape — FIXED in v0.2; v1.2 now has a faithful three-model frontier-agent live trigger

- **What it is:** The agent's output is structurally plausible — it produces a directory tree and filenames matching the rubric — but the files are empty or stub-only. In the production run the agent ran `touch /workspace/submission/scripts/load_datasets.py` and several sibling files, then stopped.
- **Where seen:** Same `GaKiuf8G` prod log. 12 bash calls over 40 messages; 0 python calls; no executable analysis ever ran inside the sandbox.
- **Why it matters:** This is the precursor to mode 2. A benchmark that only grades file structure will reward empty scaffolding.
- **What v0.2 solved:** `_artifact_presence_precheck` now blocks this exact stub-only pattern before any leaf grading, so empty scaffold directories no longer earn structure points or README-mediated false positives.
- **What v0.3 shipped:** once an agent clears the task-level precheck, any passing `code_development` leaf must cite verbatim evidence from a non-markdown file under `/workspace/submission`, and any passing `execution` leaf must cite verbatim evidence tied to a non-README artifact under `/workspace/output`. If a pass only cites README-style prose or a quote that does not appear verbatim in scorer reality context, the scorer converts that leaf to `score = 0` with `evidence_policy_failed: ...`.
- **What the April 16, 2026 reruns showed:** `VN3Jn8x7`, `TJQKBPfv`, and `WvLKMqep` all failed the same v0.2 precheck before any leaf grading, so the new v0.3 `evidence_policy_failed` path did not activate on a live benchmark trace.
- **What the archived replay showed:** the exact two v0.1 false-positive passes from `GaKiuf8G` now zero under the current scorer because their only evidence source is `/workspace/submission/README.md`.
- **What v0.4 now proves live:** the deterministic `evidence_policy_probe` harness drives the same pattern through a real Inspect `.eval` log. Its prose-trap sample passes precheck and is then zeroed for README-style code evidence, bare output-path execution evidence, and a submission-side metric claim; the matched control sample survives because its evidence comes from valid code/output files.
- **What v0.5 adds:** the deterministic `squidpy_evidence_policy_probe` moves that same proof onto the real `squidpy_spatial` paper bundle and scientific image. The exact targeted Squidpy leaves now flip the way the benchmark needs them to.
- **What v1.2 adds:** the `squidpy_evidence_policy_agent_probe` now produces three frontier-agent-generated, precheck-passing scientific traces on the same real paper package, and all three fail arms hit the exact README/path trap reasons rather than merely zeroing on verbatim mismatch.
- **What v1.2 also fixed:** the first Haiku cross-model attempt showed a prompt-robustness problem rather than a scorer problem. The authoring contract already contained enough information, but the model still burned budget on unnecessary bundle reads. The shipped v1.2 prompt now says the contract is sufficient and that bundle inspection should be skipped unless writing files is blocked.
- **What remains to measure:** add a second rater to that 20-leaf panel, then repeat the same pattern with at least one more authoring-model family and at least one more scientific paper image.

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

### 7. Live-judge calibration drift on the evidence-policy probe

- **What it is:** Once the stabilized `squidpy_evidence_policy_agent_probe` is switched from `mockllm/model` to a real judge, the scorer/runtime path remains intact, but the judge no longer reproduces the clean three-leaf fail/control split that the deterministic baseline was built to expose.
- **Where seen:** `logs-prod/2026-04-17T15-09-29-00-00_squidpy-evidence-policy-agent-probe_WRsMysX5KPnHyeCitTB4BQ.eval` (`openai/gpt-4o-mini` judge) and `logs-prod/2026-04-17T15-15-11-00-00_squidpy-evidence-policy-agent-probe_D6ti4iFVYTxyCxYHPtx54p.eval` (`openai/o3-mini` judge).
- **Why it matters:** This is now the main blocker between "we can exercise live judges" and "we have a promoted real-judge benchmark result." The probe is supposed to isolate three targeted leaves, so either under-crediting valid control evidence or broadly over-crediting the control sample distorts what the harness is meant to measure.
- **Observed shape with `openai/gpt-4o-mini`:**
  - fail arm stays at `overall = 0.000`
  - control arm reaches only `overall = 0.085`
  - targeted code and execution leaves are under-credited
  - one fail-arm execution leaf becomes `judge_error: ValueError: Judge evidence_quote must be non-empty`
- **Observed shape with `openai/o3-mini`:**
  - fail arm stays at `overall = 0.000`
  - all three targeted control leaves pass
  - control arm broadens to `overall = 0.170`, implying more non-target leaves passed than intended
  - fail-arm code and execution quotes drift to generic submission-code snippets instead of the exact README/path trap reasons
- **Likely mitigation path:** once the reviewer hold is lifted, confirm the provisional 20-leaf panel with a second rater and then decide whether the fresh live successor `f2KkxWjV` should replace `mZHU6eGr` inside that panel. A blinded JSON/CSV packet for the current panel exists under `judge_eval/review_packet_v0_1_false_positive_and_mZHU6eGr_blinded.*`.
- **Current status:** the exact-leaf guardrail prompt plus one retry for malformed outputs removed the largest source of drift on `o3-mini`, and the execution-clarified follow-up removed the earlier missing-targeted-leaf issue. The current scorer already contains a narrow deterministic fix for the one historically disputed execution-statistics pattern, and the fresh live rerun `f2KkxWjV` no longer grants that historical `moran_geary_written` leaf at all. The earlier quota-blocked attempts (`fa5G3aTA` and `g7eC3Ph9`) remain useful only as failure-history artifacts, and `scripts/run_evidence_policy_probe.py` now fails cleanly on that incomplete-log shape instead of cascading into a secondary `_write_example` error.

### 8. GeneLab prompt-hardening oscillation: toy executed artifact vs. debug-only scaffold

- **What it is:** Once the GeneLab package stopped failing on path layout, newline corruption, and sample-ID alignment, the same model began oscillating between two different nonzero-effort but still benchmark-insufficient behaviors:
  - a real executed artifact that proves the model can load one fold correctly and write a real AUROC table, but still hard-codes a single demo fold and fills the rest of the required outputs with placeholders;
  - a stricter no-placeholder rerun that discovers the real `fold_*` directories and uses probability-based AUROC, but burns the whole budget on exploratory scripts and exits with only a manifest.
- **Where seen:** `logs-prod/2026-04-22T14-19-06-00-00_scireplicbench_3L2uDjJEF6FyrXXkYsLQ9Z.eval` and `logs-prod/2026-04-22T15-34-37-00-00_scireplicbench_2mqb75xQbNCAaqa3p4z4Cs.eval`.
- **Why it matters:** This is a more mature failure mode than the earlier GeneLab misses. The agent is no longer blocked by public data, Docker image setup, or CSV-index confusion. It can now write saved Python, align `X`/`y`, and run real classifiers. The remaining problem is that the benchmark contract still relies too much on prompt interpretation instead of giving the agent a scaffold that naturally produces benchmark-shaped outputs.
- **Observed shape in `3L2uDjJE`:**
  - `precheck.ok = true`
  - `leaves_graded = 55`
  - `output_artifact_count = 5`
  - non-trivial submission file: `/workspace/submission/analysis.py`
  - real `lomo/summary.tsv` written with AUROC rows
  - but `transfer/cross_tissue.tsv`, `negative_controls/summary.tsv`, and `interpretability/top_features.tsv` are still placeholder text files
  - workflow remains hard-coded to one example fold (`A2_gastrocnemius_lomo/fold_RR-1_test`)
- **Observed shape in `2mqb75xQ`:**
  - `precheck.ok = true`
  - `leaves_graded = 55`
  - `output_artifact_count = 1` (`/workspace/output/submission_manifest.json` only)
  - non-trivial submission files: `/workspace/submission/check_folds.py`, `check_labels_metadata.py`, `load_and_process.py`
  - code now uses `predict_proba` and iterates `A*_lomo/fold_*`
  - but `run.sh` still only launches exploration code and never writes the required benchmark TSV outputs
- **Likely mitigation path:** move from prompt-hardening to scaffold-hardening. For this paper specifically, the next leverage point is a task-side starter that:
  - discovers available folds,
  - defines canonical TSV schemas for `lomo`, `cross_tissue`, `negative_controls`, and `interpretability`,
  - writes honest status rows when a branch is partial,
  - and makes it easier to extend one working fold into a benchmark-shaped multi-fold artifact without spending the whole message budget on repo archaeology.

## Anticipated but not yet observed

Modes the design expects but that no log evidence yet supports:

- **Method-equivalence drift.** e.g., agent uses `scanpy.pp.combat` where the rubric expects `ComBat-seq` on counts. Will only show up once a stronger agent produces real analyses.
- **Self-grading-bias artifact.** If the Squidpy-anchored judge grades the authored papers leniently, we expect a systematic gap between Squidpy and authored-paper judge-human agreement. The file `judge_eval/human_grades.json` now contains a provisional 20-leaf panel spanning both the archived false-positive case and the stable live-judge case, and blinded second-rater exports now exist under `judge_eval/review_packet_v0_1_false_positive_and_mZHU6eGr_blinded.json` and `.csv`, but that second human panel still needs to be filled before the bias can be quantified robustly.
- **Evaluation leakage across benchmark splits.** For `genelab_benchmark` specifically, an agent could accidentally leak mission-level information across LOMO folds. The latest April 22 runs now read real `fold_*` directories and one (`3L2uDjJE`) executes a single fold correctly, but we still do not have a promotable multi-fold LOMO artifact whose split integrity can be judged confidently.

This file is a living document: expand each entry with its real signal as more runs land.
