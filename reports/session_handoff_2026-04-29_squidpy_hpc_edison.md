# Session Handoff: Squidpy Spatial HPC + Edison Work Trial

Generated: 2026-04-29 21:29 EDT
Repo: `/Users/jak4013/Dropbox/Bioinformatics/Claude/SciReplicBench/scireplicbench`

## User Preferences And Constraints

- Continue in Korean unless the user asks otherwise.
- Be proactive and implement, but keep the user updated briefly.
- Local machine resources are limited.
- Do not run compute-heavy tests/evaluations locally.
- All tests, evals, and scientific compute should run on HPC/Cayuga only.
- It is acceptable to use API keys in `~/.api_keys`, including Anthropic, but be cost-conscious.
- Do not use expensive model runs casually; prefer deterministic inspection and targeted reruns.
- Dirty git worktree contains many existing changes. Do not revert unrelated changes.

## Main User Goal

The user is improving SciReplicBench, focusing on enabling the Squidpy spatial benchmark in a production-grade way:

- deterministic comparators before judge-mediated result scoring
- generated/sealed hidden references
- artifact-schema parsing before snippet-based judging
- fair offline assets for segmentation, ligand-receptor, and interactions
- HPC-only validation because local resources are insufficient

The user also noted that an Edison Scientific final work trial is very similar to this project and wants to reuse the project ideas for that 48-hour assignment.

Edison folder:

`/Users/jak4013/Dropbox/Lab/Post-doc_cmlab/Application/Anthropic/Application_documents/Application_strategy/2026_01_25/Edison_Scientific/Final_Work_Trial`

## Review Findings Being Addressed

1. Result-match was judge-mediated rather than comparator-enforced.
2. Squidpy hidden references were pending, so production claims were not ready.
3. Scoring context truncation could hide valid evidence.
4. Precheck was too Python-centric for broader SciReplicBench.
5. Some Squidpy segmentation/LR/interaction leaves required offline assets not yet staged.

## Current SciReplicBench State

The Squidpy spatial lane has moved from pilot/evidence-policy toward production-style deterministic scoring.

Implemented or staged:

- Deterministic comparators for Squidpy `code_development`, `execution`, and `result_match` references in `src/scireplicbench/scorers.py`.
- Local sandbox/HPC starter-mode behavior in `src/scireplicbench/tasks.py`.
- Starter off mode: `SCIREPLICBENCH_STARTER_MODE=off`.
- Squidpy output contract: `papers/squidpy_spatial/output_contract.md`.
- Generated reference artifacts in `papers/squidpy_spatial/reference_outputs/`:
  - `result_match_reference.json`
  - `execution_reference.json`
  - `code_development_reference.json`
  - `generated/`
- `papers/squidpy_spatial/novel_contrast.json` now says references are generated rather than pending.
- Anthropic cost config: `configs/anthropic_model_costs.json`.
- Cayuga sbatch scripts:
  - `scripts/cayuga_squidpy_eval_local.sbatch`
  - `scripts/cayuga_squidpy_prepare.sbatch`
  - `scripts/cayuga_squidpy_reference.sbatch`
- Squidpy starter/reference assets under `papers/squidpy_spatial/starter/`.
- Offline LR panel: `papers/squidpy_spatial/data/ligrec_interactions.tsv`.
- Status report updated: `reports/realignment_status.md`.

## Important HPC Paths

HPC staged repo:

`/athena/masonlab/scratch/users/jak4013/SciReplicBench_hpc/scireplicbench_20260428_114814`

HPC Python env:

`/athena/masonlab/scratch/users/jak4013/SciReplicBench_hpc/envs/squidpy_spatial_py311/bin/python`

Slurm tools:

- sbatch: `/opt/ohpc/pub/software/slurm/24.05.2/bin/sbatch`
- squeue: `/opt/ohpc/pub/software/slurm/24.05.2/bin/squeue`
- scancel: `/opt/ohpc/pub/software/slurm/24.05.2/bin/scancel`

Use SSH target:

`cayuga-login1`

## HPC Testing Commands

Run tests on HPC only.

Targeted tests used successfully:

```bash
ssh cayuga-login1 'cd /athena/masonlab/scratch/users/jak4013/SciReplicBench_hpc/scireplicbench_20260428_114814 && /athena/masonlab/scratch/users/jak4013/SciReplicBench_hpc/envs/squidpy_spatial_py311/bin/python -m pytest tests/test_tasks.py tests/test_scorer.py'
```

Full suite used successfully:

```bash
ssh cayuga-login1 'cd /athena/masonlab/scratch/users/jak4013/SciReplicBench_hpc/scireplicbench_20260428_114814 && /athena/masonlab/scratch/users/jak4013/SciReplicBench_hpc/envs/squidpy_spatial_py311/bin/python -m pytest'
```

Latest known full suite result:

`186 passed, 20 subtests passed in 42.99s`

Sync selected files to HPC with `rsync` rather than rerunning local compute.

Example:

```bash
rsync -av src/scireplicbench/tasks.py tests/test_tasks.py papers/squidpy_spatial/output_contract.md papers/squidpy_spatial/reference_outputs/code_development_reference.json reports/realignment_status.md cayuga-login1:/athena/masonlab/scratch/users/jak4013/SciReplicBench_hpc/scireplicbench_20260428_114814/
```

Adjust destination paths if syncing nested files; use `rsync -avR` or explicit remote subdirectories when needed.

## Latest Squidpy Evaluation Results

### Starter-Assisted Golden Path

Job: `2832715`

- Score: `1.000`
- Categories: `code_development=1.000`, `execution=1.000`, `result_match=1.000`
- Lane: `starter_assisted`
- Interpretation: validates starter/reference lane only. Not model-performance comparable.

### First Successful Unassisted Run

Job: `2839138`

Configuration:

- `STARTER_MODE=off`
- `MODEL=anthropic/claude-sonnet-4-6`
- `JUDGE_MODEL=anthropic/claude-haiku-4-5`
- `COST_LIMIT=5`
- `MODEL_COST_CONFIG=configs/anthropic_model_costs.json`

Outcome:

- Completed in `17:21`
- Inspect tokens: `1,206,353` total, mostly Anthropic cache reads
- Official score at run time: `0.5319446428571428`
- Official categories:
  - `code_development=0.327`
  - `execution=0.695`
  - `result_match=0.578`
- Official passed leaves:
  - `code_development=7 / 22`
  - `execution=11 / 16`
  - `result_match=16 / 27`
- Precheck: `ok=true`
- Output artifacts: `20`
- Lane: `blank_slate_or_unassisted`
- `production_comparable=true`

Official log:

`logs-hpc/2026-04-29T23-53-54-00-00_scireplicbench_A3kthidFuEWWRwVfdvFhFY.eval`

Manual post-fix rescore on the same frozen artifacts after broadening code-development patterns:

- Manual score: `0.7339946428571429`
- Manual categories:
  - `code_development=1.000`
  - `execution=0.695`
  - `result_match=0.578`
- Manual passed leaves:
  - `code_development=22 / 22`
  - `execution=11 / 16`
  - `result_match=16 / 27`

Interpretation:

The official lower score was partly a benchmark-side fairness issue: code-development checks were too starter-specific. After broadening the deterministic source checks, the remaining failures are mainly output schema/result details.

## Current Remaining Squidpy Failure Areas

From the unassisted run `2839138`, remaining issues concentrate in execution/result artifacts:

- `dataset_manifest.json` should include `cluster_key` and seqFISH `cluster_labels`, not only shapes.
- Graph result-match tables need exact key conventions:
  - neighborhood and interaction matrix: `pair_key=cluster_1|cluster_2`
  - cooccurrence: `pair_key=cluster_1->cluster_2`
  - nhood ranking should omit or demote self-pairs.
- Cooccurrence should use `interval=25`, not arbitrary `np.linspace(...)` radii.
- Ripley output should compute `radius_index` with `groupby("label").cumcount()` rather than global row index.
- `svg_summary.json` should expose `method`, `fdr_column`, `fdr_threshold`, and `significant_gene_count`.
- Visualization/report artifacts should contain deterministic recognition strings:
  - `Top Moran`
  - `Marker localization`
  - `Squidpy spatial reviewer-path report`
  - `spatial_stats_plot.svg`
  - `marker_localization.svg`
- Image-feature result-match still misses exact dimensionality, segmentation feature count, image-cluster ARI, and texture-rank overlap. Current prompt prioritizes bounded completion over perfect image parity.

## Prompt/Contract Refinements Already Added

Updated in `papers/squidpy_spatial/output_contract.md` and `src/scireplicbench/tasks.py`:

- exact dataset schema with cluster keys and labels
- exact graph table `pair_key` conventions
- cooccurrence `interval=25`
- Ripley flattening with per-label `radius_index`
- `svg_summary.json` keys
- visualization/report recognition strings
- image-feature timeout guidance using real `signal.alarm(...)`
- LR bounded first pass with `n_perms=10`, optional `n_perms=100` after all artifacts exist
- LR `interaction_key = f"{source}|{target}|{cluster_1}->{cluster_2}"`

Updated tests:

- `tests/test_tasks.py` asserts prompt strings.
- `tests/test_scorer.py` covers deterministic comparator behavior.

## Suggested Next SciReplicBench Step

Do not immediately start another expensive unassisted model run unless the user wants validation of the latest prompt refinements.

Recommended next sequence:

1. Inspect current diffs in `src/scireplicbench/tasks.py`, `src/scireplicbench/scorers.py`, `papers/squidpy_spatial/output_contract.md`, and reference JSONs.
2. Ensure all staged reference files are included intentionally and no unrelated dirty files are changed.
3. If running validation, sync only changed files to HPC.
4. Run targeted HPC tests.
5. Run full HPC tests.
6. Only then consider one cost-capped unassisted Squidpy eval.

Cost-capped eval command template:

```bash
ssh cayuga-login1 'cd /athena/masonlab/scratch/users/jak4013/SciReplicBench_hpc/scireplicbench_20260428_114814 && env STARTER_MODE=off SKIP_INSTALL=1 MODEL=anthropic/claude-sonnet-4-6 JUDGE_MODEL=anthropic/claude-haiku-4-5 JUDGE_LEAF_LIMIT= MESSAGE_LIMIT=70 TIME_LIMIT=3600 WORKING_LIMIT=3600 COST_LIMIT=5 MODEL_COST_CONFIG=configs/anthropic_model_costs.json /opt/ohpc/pub/software/slurm/24.05.2/bin/sbatch --time=02:00:00 scripts/cayuga_squidpy_eval_local.sbatch'
```

Check active jobs:

```bash
ssh cayuga-login1 '/opt/ohpc/pub/software/slurm/24.05.2/bin/squeue -u jak4013 | grep srb-squidpy || true'
```

## Dirty Git Worktree Warning

Current `git status --short` shows many modified files and untracked files. Some predate this session.

Important rule for next session:

- Do not run destructive git commands.
- Do not revert unrelated changes.
- If unexpected user edits appear in files being touched, stop and ask.

Relevant current/new files include:

- `configs/anthropic_model_costs.json`
- `papers/squidpy_spatial/output_contract.md`
- `papers/squidpy_spatial/reference_outputs/code_development_reference.json`
- `papers/squidpy_spatial/reference_outputs/execution_reference.json`
- `papers/squidpy_spatial/reference_outputs/result_match_reference.json`
- `papers/squidpy_spatial/reference_outputs/generated/`
- `papers/squidpy_spatial/starter/`
- `reports/realignment_status.md`
- `reports/squidpy_spatial_enablement_research.md`
- `scripts/cayuga_squidpy_eval_local.sbatch`
- `scripts/cayuga_squidpy_prepare.sbatch`
- `scripts/cayuga_squidpy_reference.sbatch`
- `scripts/generate_squidpy_reference_outputs.py`
- `src/scireplicbench/scorers.py`
- `src/scireplicbench/tasks.py`
- `tests/test_scorer.py`
- `tests/test_tasks.py`
- `tests/test_squidpy_stack_check.py`
- `tests/test_squidpy_starter.py`

`TEMP_PATCH_TEST.txt` is untracked and likely unrelated; do not touch unless the user asks.

## Edison Scientific Work Trial State

The real assignment asks:

1. Use Edison Analysis to reproduce one subfigure from a recent publication.
2. Turn that reproduction task into a benchmark and write an LLM-grader rubric.
3. Prepare a 20-minute presentation.

Chosen target:

- Paper: Marconato, Palla, Yamauchi et al., `SpatialData: an open and universal data framework for spatial omics`, Nature Methods.
- Target: Fig. 2e left scatter.
- Source URL: https://www.nature.com/articles/s41592-024-02212-x
- Official reproducibility repository mentioned by the paper: https://github.com/scverse/spatialdata-notebooks/tree/main/notebooks/paper_reproducibility

Why this target:

- recent
- public
- spatial-omics/scverse ecosystem
- compact enough for a 48-hour work trial
- benchmarkable through notebook + figure + per-gene table
- aligned with SciReplicBench's artifact-contract philosophy

Edison files created/updated:

- `Edison_Work_Trial_Response_Draft_SpatialData.md`
- `Edison_Analysis_Prompt_SpatialData_Fig2e.md`
- `Edison_Analysis_Prompt_SpatialData_Fig2e_v2.md`
- `Edison_Benchmark_Artifact_Contract_SpatialData.md`
- `Edison_48h_Execution_Runbook_SpatialData.md`
- `Edison_Presentation_Outline_SpatialData.md`
- `Edison_Presentation_Speaker_Notes_SpatialData.md`
- `STATUS.md`

Edison folder path:

`/Users/jak4013/Dropbox/Lab/Post-doc_cmlab/Application/Anthropic/Application_documents/Application_strategy/2026_01_25/Edison_Scientific/Final_Work_Trial`

## Edison Next Step

The immediate action is to run Edison Analysis with:

`Edison_Analysis_Prompt_SpatialData_Fig2e_v2.md`

Then download/collect:

- report
- notebook
- figure
- table

After outputs are available:

1. Update `Edison_Work_Trial_Response_Draft_SpatialData.md` with actual result/caveats.
2. Fill slide 4/result snapshot in `Edison_Presentation_Speaker_Notes_SpatialData.md`.
3. Keep the benchmark-design answer centered on:
   - public output contract
   - deterministic artifact checks first
   - LLM qualitative judgment second
   - failure taxonomy as training signal

## Strong Edison Positioning

Use this sentence if a new session needs the thesis quickly:

> A scientific-agent benchmark should not ask whether the output looks impressive; it should ask whether the output exposes enough structured evidence for another scientist to verify the claim.

## Sources Used For Edison Target

- Nature Methods SpatialData paper: https://www.nature.com/articles/s41592-024-02212-x
- PubMed page: https://pubmed.ncbi.nlm.nih.gov/38509327/
- PMC full text: https://pmc.ncbi.nlm.nih.gov/articles/PMC11725494/
- scverse SpatialData notebooks: https://github.com/scverse/spatialdata-notebooks/tree/main/notebooks/paper_reproducibility

Key paper facts verified online:

- Fig. 2e left is a scatter plot of per-gene agreement metrics.
- x-axis: aggregated gene expression correlation between Xenium replicates.
- y-axis: correlation between Xenium and Visium.
- points: 313 genes present in both Xenium and Visium.
- color: log expression in Xenium replicate 1.
- paper reports median Pearson R values of about 0.62 for Xenium replicate concordance and 0.48 for Xenium-Visium counts.

## Paste-Into-Next-Session Prompt

Use this to continue cleanly:

```text
We are continuing SciReplicBench Squidpy spatial work. Use Korean. Local resources are limited, so do not run tests/evals/compute locally; use HPC/Cayuga only. Start by reading reports/session_handoff_2026-04-29_squidpy_hpc_edison.md and reports/realignment_status.md. Do not revert unrelated dirty worktree changes. Main goals: continue hardening deterministic Squidpy result_match/execution/code_development comparators and output contract; validate only on HPC; also support Edison Scientific work trial using the SpatialData Fig. 2e benchmark package in /Users/jak4013/Dropbox/Lab/Post-doc_cmlab/Application/Anthropic/Application_documents/Application_strategy/2026_01_25/Edison_Scientific/Final_Work_Trial.
```
