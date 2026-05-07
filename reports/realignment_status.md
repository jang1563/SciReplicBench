# Realignment Status

This note records the repo-local realignment work added after the baseline v1.2 handoff.

## Shipped

- Phase plans now carry readiness-gate metadata with `pilot_ready` / `production_ready` semantics.
- Production plans now request judge self-consistency metadata (`n=3`, minimum confidence `0.6`).
- Hidden-reference readiness is now a first-class check instead of an implicit TODO.
- A second-human-rater gap in `judge_eval/human_grades.json` is now treated as a production blocker.
- GeneLab starter integration smoke now verifies that all four required TSV families are written as machine-readable outputs.
- Squidpy scientific-stack smoke now has a dedicated CI workflow, exact `numcodecs==0.15.1` / `setuptools==80.8.0` pins, and a Cayuga cache/load/analysis smoke path.

## Current Gate Shape

- `inspiration4_multiome`: enablement lane until a reviewer-ready AnnData or MuData object is staged.
- `genelab_benchmark`: pilot-capable, but not production-ready until hidden references and judge-panel credibility gates are complete.
- `squidpy_spatial`: external-anchor lane with generated hidden/reference artifacts, deterministic result-match comparators, scientific-stack smoke coverage, and remaining production gating tied to repeated unassisted runs plus judge-panel credibility for any qualitative fallback leaves.

## Latest GeneLab Pilot

The April 26, 2026 v25 `genelab_benchmark` pilot validates the canonical-source hardening path. The agent first attempted to replace `main_analysis.py`, `run.sh`, and the structured manifest with thinner files; the tool guards blocked all three and steered it back to the seeded workflow. The final submission kept only the canonical `genelab_scaffold.py` and `main_analysis.py`, produced the expected nine output artifacts, and recovered execution evidence that earlier pilots left invisible to the judge.

- Log: `logs/2026-04-26T04-08-51-00-00_scireplicbench_j5nuaXbQta4PV9jUcEsWQX.eval`
- Trace: `logs-prod/inspect-trace-genelab-pilot-v25.log.gz`
- Score: `0.21738333333333332`
- Category scores: `code_development=0.20800000000000002`, `execution=0.5783333333333333`, `result_match=0.0`
- Passed leaves: `12 / 55`
- Judge failures: `0`
- Zero-score `no_valid_evidence` responses: `34`
- Sample limit: none
- Precheck: `ok=true`, `nontrivial_py_files=2`, `output_artifact_count=9`

Compared with v22 (`0.16561666666666666`), v25 removes the unhooked sidecar source and increases total score by improving execution recognition for split manifests, AUROC tables, bootstrap CIs, permutation results, cross-mission/tissue transfer outputs, and go/no-go summaries. v23 confirmed that sidecar prevention alone kept the submission focused but starved the judge of source evidence (`0.05075`); v24 recovered source-focused code leaves (`0.1193`) but exposed overly strict judge handling of fallback code, example alternatives, and header-plus-row output evidence. The current local lever is to convert the remaining `no_valid_evidence` zeroes into grounded code/result matches without weakening the protected starter workflow.

## Latest Squidpy HPC Validation

The April 29, 2026 Cayuga run `2832715` validates the Squidpy spatial starter/reference lane end to end. The first full HPC attempt (`2832679`) scored `0.000` because the agent spent its 12-message budget reading files and produced no output artifacts, triggering the result-match precheck. After increasing the message budget and making the task prompt tell the agent to run `bash /workspace/submission/run.sh` first, run `2832715` completed in 11:39 and produced the full required artifact tree.

- Log: `logs-hpc/2026-04-29T17-41-27-00-00_scireplicbench_WPxMVVLjkVtj2UZuoyoXos.eval`
- Raw score: `1.000`
- Category scores: `code_development=1.000`, `execution=1.000`, `result_match=1.000`
- Deterministic leaves: `code_development=22`, `execution=16`, `result_match=27`
- Precheck: `ok=true`, `nontrivial_py_files=2`, `nontrivial_source_files=3`, `output_artifact_count=20`
- Evaluation lane: `starter_assisted`
- Score interpretation: the raw `1.000` is a golden-path/starter validation score, not a blank-slate model-performance estimate.
- New metadata: starter-assisted scores now expose `raw_reproducibility_score=1.0`, `model_performance_score=None`, `model_performance_score_available=false`, and `production_comparable=false`.
- Regression tests: Cayuga full suite passed after the metadata/negative-control hardening (`184 passed, 20 subtests passed`).

## Latest Squidpy Unassisted HPC Validation

The April 29, 2026 Cayuga unassisted run `2839138` is the first successful blank-slate Squidpy spatial evaluation with all required artifact families present. It used `STARTER_MODE=off`, `MODEL=anthropic/claude-sonnet-4-6`, `JUDGE_MODEL=anthropic/claude-haiku-4-5`, `COST_LIMIT=5`, and `MODEL_COST_CONFIG=configs/anthropic_model_costs.json`. The run completed in 17:21 and stayed under the configured cost cap while using Anthropic prompt caching (`1,206,353` tokens reported by Inspect, mostly cache reads).

- Log: `logs-hpc/2026-04-29T23-53-54-00-00_scireplicbench_A3kthidFuEWWRwVfdvFhFY.eval`
- Official score at run time: `0.5319446428571428`
- Official category scores: `code_development=0.327`, `execution=0.695`, `result_match=0.578`
- Official passed leaves: `code_development=7 / 22`, `execution=11 / 16`, `result_match=16 / 27`
- Precheck: `ok=true`, `nontrivial_py_files=1`, `nontrivial_source_files=2`, `output_artifact_count=20`
- Evaluation lane: `blank_slate_or_unassisted`
- Model-performance metadata: `model_performance_score=0.5319446428571428`, `production_comparable=true`

Reviewing the artifacts exposed an important benchmark-side fairness issue: the deterministic `code_development_reference.json` was still too starter-specific, requiring variable/helper names such as `path=visium_path`, `_rank_autocorr`, `_write_tsv`, and `_write_visualization_report`. The unassisted code executed the relevant Squidpy APIs but used different variable names and direct pandas/matplotlib/json writers, so code-development was under-credited. After broadening the deterministic source-pattern checks to accept equivalent unassisted implementations, the same frozen `2839138` artifacts manually re-score as:

- Manual post-fix score on the same artifacts: `0.7339946428571429`
- Manual post-fix category scores: `code_development=1.000`, `execution=0.695`, `result_match=0.578`
- Manual post-fix passed leaves: `code_development=22 / 22`, `execution=11 / 16`, `result_match=16 / 27`

The remaining failures are now concentrated in execution/result artifact details rather than missing workflow substance:

- Dataset execution JSON should include `cluster_key` and seqFISH `cluster_labels`, not just shapes.
- Graph result-match tables need benchmark key conventions: nhood and interaction matrix `pair_key=cluster_1|cluster_2`, cooccurrence `pair_key=cluster_1->cluster_2`, and nhood top ranks should omit or demote self-pairs.
- Cooccurrence should use the benchmark-standard `interval=25` rather than arbitrary `np.linspace(...)` radii.
- Ripley output should compute `radius_index` with `groupby("label").cumcount()` instead of a global row index.
- `svg_summary.json` should expose `method`, `fdr_column`, `fdr_threshold`, and `significant_gene_count`.
- Visualization/report artifacts should contain deterministic recognition strings: `Top Moran`, `Marker localization`, `Squidpy spatial reviewer-path report`, `spatial_stats_plot.svg`, and `marker_localization.svg`.
- Image-feature result-match still misses the hidden reference on exact dimensionality, segmentation feature count, image-cluster ARI, and texture ranking; the current prompt now prioritizes bounded completion over perfect image-feature parity.

The public Squidpy output contract and unassisted prompt now document those conventions explicitly, including real `signal.alarm(...)` style timeouts for image-feature calls. Cayuga regression tests passed after these prompt/reference fixes (`186 passed, 20 subtests passed`).

## Squidpy Rubric v2 (Q1+Q2+Q3+Q4 applied 2026-04-30)

After the unassisted run `2839395` produced an interpretable 0.812 score, the rubric itself was reviewed against published scientific-agent benchmarks (PaperBench Starace et al. 2025, MLE-Bench, METR HCAST, BLADE, Pineau ML Reproducibility Checklist v2.0, ScienceAgentBench). Four design changes were applied to address concerns flagged by that review.

### Q4 — Threshold calibration documented (`papers/squidpy_spatial/scoring_methodology.md`)

`scripts/calibrate_squidpy_thresholds.py` permutes each numeric reference artifact 200 times and reports the random-baseline mean, std, and p(random passes) for every result-match threshold. Results: 11 of 14 numeric thresholds are well-calibrated (z-score >> 5, p_random < 0.01); 3 thresholds were flagged as borderline:

- `positive_neighbor_pair_recovered` (z=1.76, p_random=0.215) — weakest, redundant with `nhood_enrichment_rank_overlap` (z=10.32). Dropped in Q2.
- `marker_localization_consistency` (z=2.06, p_random=0.025) — borderline. Merged with `spatial_localization_pattern_recovered` and threshold tightened to 0.7 in Q2.
- `spatial_localization_pattern_recovered` (z=2.32, p_random=0.010) — borderline. Merged target above with stricter threshold.

PaperBench publishes no per-threshold calibration; this is a stronger peer-review defense than the published comparable.

### Q1 — Trivial leaves collapsed into gating leaves

Six leaves that pass for any correctly-loaded built-in dataset (3 dataset-execute + 3 shape-tolerance) were collapsed into 2 gating leaves. The execution gate uses `all_checks` over `json_paths_present`; the result-match gate uses a new `all_checks` branch in the result-match dispatcher with a small `_evaluate_result_match_subcheck` helper that handles `json_shape_within_tolerance` and `json_numeric_within_tolerance` sub-checks. Net: −4 leaves (6 dropped, 2 added).

### Q2 — Redundant leaves removed

- `plp1_moran_close` removed (subset of `top_moran_genes_overlap_threshold` rank check; `olfm1_moran_close` retained as a value-precision check).
- `positive_neighbor_pair_recovered` and `known_spatial_association_recovered` removed (both overlap@k variants of `nhood_enrichment_rank_overlap` RBO@20).
- `marker_localization_consistency` (Ttr) merged into `spatial_localization_pattern_recovered` (now Olfm1 + Ttr) with stricter Pearson threshold 0.7 (was 0.6).

Net: −4 leaves.

### Q3 — Seeding leaf added (operationalizes Pineau checklist)

`code_development/interaction_reporting/seeded_permutation_pipeline` checks the submission source for either a global seed call (`np.random.seed(N)` / `random.seed(N)`) or a `seed=N` / `random_state=N` keyword on permutation methods. No published agent benchmark previously operationalized seeding as a deterministic-comparator leaf — this is a novel SciReplicBench contribution.

Net: +1 leaf.

### Combined leaf count: 65 → 58

| Category | v1 weight | v1 leaves | v2 leaves | v2 sub-clusters |
|---|---|---|---|---|
| code_development | 0.30 | 22 | 23 | unchanged (seeding leaf added inside `interaction_reporting`) |
| execution | 0.25 | 16 | 14 | datasets sub-cluster collapsed 3→1 |
| result_match | 0.45 | 27 | 21 | datasets 4→2; spatial_graph 8→6; spatial_stats 7→6; interactions 3→2 |
| **Total** | **1.00** | **65** | **58** | |

### Sensitivity check — rescore of run 2839395 under rubric v2

Frozen artifacts from the 2026-04-29 unassisted run `2839395` were rescored under rubric v2 via `scripts/rescore_squidpy_run.py`. Result: overall score **0.806** (v1 was **0.812**). Ranking is stable; rubric structural change has minimal effect.

| Category | v1 score | v2 score | v1 passed leaves | v2 passed leaves |
|---|---|---|---|---|
| code_development | 0.761 | 0.761 | 17 / 22 | 18 / 23 (seeding leaf passes) |
| execution | 0.933 | 0.933 | 15 / 16 | 13 / 14 (gate leaf passes) |
| result_match | 0.779 | 0.765 | 21 / 27 | 15 / 21 |
| overall | 0.812 | 0.806 | 53 / 65 | 46 / 58 |

The result-match per-leaf pass rate dropped from 78% to 71% because Q1 removed mostly-passing trivial leaves; the remaining 6 result-match failures are all in the image-features cluster (`image_feature_*` leaves + `nhood_enrichment_rank_overlap`).

### v2 failed leaves remaining for next iteration

- code_development (5): `attach_spatial_coordinates`, `load_image_container`, `compute_segmentation_features`, `construct_geometry_aware_graph`, `run_ripley`
- execution (1): `segmentation_features_written`
- result_match (6): `nhood_enrichment_rank_overlap`, `image_feature_cluster_alignment_ari`, `image_feature_matrix_dimensionality_band`, `image_feature_structure_nondegenerate`, `segmentation_feature_count_band`, `texture_feature_rank_overlap`

`186 passed in 29.51s` Cayuga regression suite confirms rubric v2 + scorers + tests are coherent.

## Phase B-1 — Comparator Fixes (2026-04-30)

Direct artifact inspection of frozen run `2839395` revealed three comparator-side gaps that explain 6 of the 12 remaining failures. All three are benchmark-side fixes; the agent code is correct but the comparator was too strict.

### Fix 1 — Quote-style insensitive literal matching

`_match_literals` now flips double-quoted patterns to single-quoted (or vice versa) on a second pass when the original literal is not present. The agent submitted `coord_type='grid'`, `mode='L'`, `method='watershed'` (Python single quotes) while the references requested double-quoted variants.

Recovered 4 leaves: `attach_spatial_coordinates`, `construct_geometry_aware_graph`, `run_ripley`, `compute_segmentation_features`.

### Fix 2 — Loosen `load_image_container` reference

The reference required `sq.datasets.visium_hne_image`, but the agent loaded the staged TIFF cache directly via `sq.im.ImageContainer(str(IMAGE_TIFF))` — functionally equivalent. The reference now accepts either AST call (`any_ast_calls`) and only requires the substring `visium_hne_image` (instead of the full namespaced literal).

Recovered 1 leaf: `load_image_container`.

### Fix 3 — `pair_key_canonical` normalizer for symmetric Squidpy pair_keys

Squidpy's neighborhood-enrichment exports list each unordered cluster pair twice (`cluster_1|cluster_2` and `cluster_2|cluster_1`), so the agent's top-20 contained 10 unique pairs each duplicated. The new `pair_key_canonical` normalizer in `_normalizer_for_reference` sorts the two halves alphabetically before computing rank-biased overlap, collapsing the symmetric duplicates so the actual top 5 pairs match the reference exactly. Applied via `"normalize": "pair_key_canonical"` on the `nhood_enrichment_rank_overlap` reference config.

Recovered 1 leaf: `nhood_enrichment_rank_overlap`.

### Frozen run 2839395 rescore after Phase B-1

| Category | rubric v2 only | rubric v2 + B-1 fixes | Δ |
|---|---|---|---|
| code_development | 0.761 (18/23) | **1.000 (23/23)** | +5 leaves recovered |
| execution | 0.933 (13/14) | 0.933 (13/14) | unchanged (real failure) |
| result_match | 0.765 (15/21) | **0.820 (16/21)** | +1 leaf recovered |
| **overall** | **0.806** | **0.902** | **+0.096** |

`189 passed in 7.96s` regression confirms the new tests for quote-flip, `pair_key_canonical` normalizer, and `_normalizer_for_reference` alias resolution.

### Remaining 6 failures concentrated in one fallback path

All 6 remaining failures derive from one runtime event: `sq.im.segment` watershed timed out on the agent's submission, which triggered the agent's fallback path to a placeholder `feature_summary.json` with `n_features=5`, `segmentation_feature_count=0`, all observations in cluster `0`, and feature names `fallback_feature_*`. This single fallback causes:

- `execution/.../segmentation_features_written` (count=0 vs minimum 1)
- `result_match/.../image_feature_matrix_dimensionality_band` (5 columns vs reference 26)
- `result_match/.../segmentation_feature_count_band` (0 vs reference 5)
- `result_match/.../image_feature_cluster_alignment_ari` (single cluster → ARI=0)
- `result_match/.../texture_feature_rank_overlap` (`fallback_feature_*` vs reference `texture_*`)
- `result_match/.../image_feature_structure_nondegenerate` (1 cluster, 100% in cluster 0)

This is a real model-side gap, not a comparator gap. Phase B-2 (prompt strengthening) is the appropriate response: the unassisted prompt should explicitly forbid placeholder fallback when image-feature computation times out and instead instruct the agent to reduce image library size or retry with a smaller crop, mirroring the starter's `signal.alarm(...)` timeout-then-retry pattern.

## Phase B-2 — Image-Feature Prompt Hardening + Live Run 2839660 (2026-04-30)

### Prompt and contract changes (`tasks.py`, `output_contract.md`)

The unassisted prompt now explicitly forbids the placeholder fallback pattern observed in run 2839395 and replaces it with a credible recovery path. New constraints:

- Default `features=['histogram', 'summary', 'texture']` (was `['histogram', 'summary']`); the contract notes this single call already produces 20+ real columns and is the floor for a credible submission.
- `feature_summary.json` must report `n_features >= 20` and an honest `feature_families` list of executed families; never list `'fallback'` as a feature family or `'fallback_placeholder'` as a status.
- `feature_clusters.tsv` must have at least 3 distinct `image_cluster` values with no single cluster containing more than 60% of observations; if KMeans collapses, increase `n_clusters` or drop near-constant columns.
- `feature_ranking.tsv` rows must use real executed feature columns (e.g. `texture_ch-0_contrast_dist-1_angle-0.00`); placeholder names like `fallback_feature_0` will fail every image-feature result-match leaf simultaneously.

`output_contract.md` carries the same prohibitions. `test_tasks.py` now asserts each new prompt string appears in the rendered task input.

### Live unassisted run 2839660

Submitted at `2026-04-30T10:15`, completed at `2026-04-30T10:34` (`19:03` elapsed, 14:59 inspect time, well before the 12:00 EDT HPC head-node reboot window). `1,249,018` Anthropic tokens, mostly cache reads (`1,129,148`).

- Log: `logs-hpc/2026-04-30T14-19-43-00-00_scireplicbench_4R8domHZdqPmhwWPkTvmMU.eval`
- Score: **0.896** (`production_comparable=true`, `evaluation_lane=blank_slate_or_unassisted`)
- Category scores: `code_development=0.925` (21/23), `execution=0.933` (13/14), `result_match=0.856` (17/21)
- Failed leaves: 7 (down from 12 in 2839395)

### Score progression — single-paper Squidpy spatial unassisted lane

| Run | Date | Rubric | B-1 | B-2 | Overall | Code | Exec | Result | Failed leaves |
|---|---|---|---|---|---|---|---|---|---|
| 2839138 | 2026-04-29 | v1 (65) | – | – | 0.532 | 0.327 | 0.695 | 0.578 | 31 |
| 2839395 | 2026-04-29 | v1 (65) | – | – | 0.812 | 0.761 | 0.933 | 0.779 | 12 |
| 2839395 rescore | 2026-04-30 | v2 (58) | applied | – | 0.902 | 1.000 | 0.933 | 0.820 | 5 |
| **2839660** | **2026-04-30** | v2 (58) | applied | applied | **0.896** | 0.925 | 0.933 | 0.856 | **7** |

Net gain since first unassisted run: **+0.364** (`0.532 → 0.896`). The 0.006 difference between the frozen-2839395 + B-1 rescore (0.902) and the live 2839660 (0.896) reflects two real shifts in agent behavior under the new B-2 prompt: result_match gained `image_feature_structure_nondegenerate` (cluster diversity recovered, 6 clusters with max 35%) but code_development lost `compute_segmentation_features` (agent skipped `sq.im.segment` entirely instead of attempting + failing) and `generate_spatial_visualizations` (different visualization helper pattern).

### B-2 effect on image-feature pipeline

The placeholder fallback that drove 6 of the 12 failures in 2839395 is now eliminated. Concrete artifact comparison:

| Field | 2839395 | 2839660 |
|---|---|---|
| `n_features` | 5 | 105 |
| `feature_families` | `["fallback"]` | `["histogram", "summary", "texture"]` |
| `status` | `"fallback_placeholder"` | `"completed"` |
| Cluster distribution | 100% in cluster 0 | 6 clusters, max 35%, min 1.2% |
| `image_feature_structure_nondegenerate` | FAIL | **PASS** |

### Remaining 7 failures shift in nature

Image-feature fallback is gone, but new image-feature failures emerge from different causes:

- `image_feature_matrix_dimensionality_band` (105 cols vs reference 26): agent uses `sq.im.calculate_image_features` defaults — texture features expand to many distance/angle combinations. Reference uses constrained `features_kwargs={'texture': {'distances': [1], 'angles': [0.0]}}`. Fix: specify the exact `features_kwargs` in the prompt.
- `texture_feature_rank_overlap`: same parameter mismatch — agent generates `texture_ch-*_dist-*_angle-*` names that don't appear in the reference's constrained ranking.
- `segmentation_feature_count_band` and `execution/segmentation_features_written`: agent skipped `sq.im.segment` entirely (interpreting "no placeholder" as "no attempt"). Fix: rephrase prompt to say "attempt segmentation; if it fails, record `segmentation_feature_count: 0` honestly without writing fake feature columns" — distinguishing skip from attempt-then-fail.
- `image_feature_cluster_alignment_ari`: ARI < 0.25 against reference clusters because feature space differs.
- `compute_segmentation_features` (code): consequence of skipping `sq.im.segment`.
- `generate_spatial_visualizations` (code): different visualization helper pattern; needs comparator review or prompt clarification.

These 4 image-feature result-match leaves form a tight cluster that should be addressed together by pinning `features_kwargs` to match the reference recipe exactly.

## Phase B-3 — Image-Feature Recipe Pinning + Live Run 2840243 (2026-04-30)

Three additional fixes derived from direct artifact inspection of run `2839660`:

### B-3a — Comparator: relax `generate_spatial_visualizations` literal patterns

The reference required the literal `visualizations/spatial_stats_plot.svg`, but agents typically build paths via `OUTPUT_DIR / "visualizations" / "spatial_stats_plot.svg"` (Path concatenation), so the substring with the slash never appears in source. The reference now requires only the basenames `spatial_stats_plot.svg` and `marker_localization.svg` plus any of the existing AST-call alternatives. Comparator-only fix.

### B-3b — Prompt: pin `features_kwargs` to match reference 26-column shape

The hidden reference has exactly 26 image-feature columns from `sq.im.calculate_image_features`. Agents using default kwargs expand texture into many distance/angle combinations, generating ~100+ off-shape columns. The unassisted prompt now contains the exact `features_kwargs` recipe needed:

```python
features_kwargs={
    "histogram": {"channels": [0], "bins": 4},
    "segmentation": {
        "label_layer": "segmented_watershed",
        "props": ["label", "area", "mean_intensity"],
        "channels": [0],
    },
    "summary": {"channels": [0, 1, 2]},
    "texture": {
        "channels": [0],
        "props": ["contrast", "homogeneity"],
        "distances": [1],
        "angles": [0],
    },
}
```

`output_contract.md` carries the same recipe. Verified to produce a 26-column matrix matching the reference.

### B-3c — Prompt: distinguish "skip segmentation" from "attempt-then-fail"

Run 2839660 had `compute_segmentation_features` failing because the agent skipped `sq.im.segment` entirely, interpreting "no placeholder fallback" as "no attempt at segmentation". The new prompt explicitly requires the `sq.im.segment` call to be present in the saved source (so the AST check passes) and reframes the timeout-tolerant guidance: "if segmentation itself raises a TimeoutError, the call still belongs in the saved source and `feature_families` should record what actually executed (e.g. `['histogram', 'summary', 'texture']`); set `segmentation_feature_count: 0` honestly. Do NOT omit the `sq.im.segment` call from the source just because it might fail."

### Live unassisted run 2840243

Submitted at `2026-04-30T17:46`, completed at `2026-04-30T18:50` (`1:04:00` elapsed, 1:00:41 inspect time, agent's `--time-limit 3600` fired then scoring completed). `1,201,747` Anthropic tokens, mostly cache reads (`1,069,166`).

- Log: `logs-hpc/2026-04-30T21-49-35-00-00_scireplicbench_Hy6bE2t7bytAEJQy7zCm5f.eval`
- Score: **0.935** (`production_comparable=true`, `evaluation_lane=blank_slate_or_unassisted`)
- Category scores: `code_development=1.000` (23/23 — perfect), `execution=0.933` (13/14), `result_match=0.892` (18/21)
- Failed leaves: 4 (down from 7 in 2839660)

### Score progression — full single-paper Squidpy spatial unassisted lane

| Run | Date | Rubric | B-1 | B-2 | B-3 | Overall | Code | Exec | Result | Failed |
|---|---|---|---|---|---|---|---|---|---|---|
| 2839138 | 2026-04-29 | v1 (65) | – | – | – | 0.532 | 0.327 | 0.695 | 0.578 | 31 |
| 2839395 | 2026-04-29 | v1 (65) | – | – | – | 0.812 | 0.761 | 0.933 | 0.779 | 12 |
| 2839395 rescore | 2026-04-30 | v2 (58) | applied | – | – | 0.902 | 1.000 | 0.933 | 0.820 | 5 |
| 2839660 | 2026-04-30 | v2 (58) | applied | applied | – | 0.896 | 0.925 | 0.933 | 0.856 | 7 |
| 2839660 rescore | 2026-04-30 | v2 (58) | applied | applied | B-3a | 0.905 | 0.955 | 0.933 | 0.856 | 6 |
| **2840243** | **2026-04-30** | v2 (58) | applied | applied | applied | **0.935** | **1.000** | 0.933 | 0.892 | **4** |

Net gain since first unassisted run: **+0.403** (`0.532 → 0.935`). Net gain in this session alone: +0.123 (`0.812 → 0.935`). `code_development` is now perfect (23/23) — every deterministic source-pattern leaf is recoverable with current prompt and comparator state.

### Remaining 4 failures all derive from one runtime event

- `execution/image_features_segmentation/segmentation_features_written`
- `result_match/image_features_segmentation/image_feature_matrix_dimensionality_band`
- `result_match/image_features_segmentation/segmentation_feature_count_band`
- `result_match/image_features_segmentation/texture_feature_rank_overlap`

Root cause: the agent now correctly calls `sq.im.segment(..., method='watershed')` per Phase B-3c (so `code_development/compute_segmentation_features` passes), but watershed segmentation itself fails or times out at runtime, so the 5 segmentation-derived feature columns never reach `feature_matrix.tsv`. This produces:

- `segmentation_feature_count: 0` in `feature_summary.json` (fails count and execution leaves)
- `feature_matrix.tsv` with ~21 columns instead of 26 (fails dimensionality band ±10%)
- `feature_ranking.tsv` missing `segmentation_label` and segmentation channel-mean rankings (fails texture/segmentation top-10 RBO)

This is a real environment/model capability limit, not a prompt or comparator gap. Resolution paths for a future Phase B-4:

- Provide a benchmark-pinned watershed parameter recipe in the prompt with a smaller image crop or coarser `geq` so segmentation completes within budget.
- Optionally relax the `image_feature_matrix_dimensionality_band` tolerance from ±10% to ±25% to acknowledge that the 5 segmentation columns are a single failure mode rather than five independent capabilities.
- Consider exposing a starter helper that wraps `sq.im.segment` with safe parameters and surfaces it as an opt-in "image-feature reviewer-path" lane.

## Phase B-4a — Edison-style Severity Caps (2026-04-30)

After cross-referencing Edison Scientific's work-test rubric design, ported the **severity-ordered cap rules** pattern to SciReplicBench's score aggregation. Edison uses cap rules so that a model with one catastrophically broken dimension cannot reach "strong reproduction" via the weighted average alone (e.g., D1=0 caps Core at 2/14 even if every other dimension is full marks).

### Implementation

`SEVERITY_CAP_RULES` in `src/scireplicbench/scorers.py` defines three cap thresholds:

| Trigger | Cap on overall |
|---|---|
| `execution < 0.30` | 0.40 |
| `result_match < 0.30` | 0.50 |
| `result_match < 0.50` | 0.70 |

`_apply_severity_caps` returns the (capped overall, list of triggered rule names). The `RubricScoreReport` now exposes both `overall_score` (post-cap, headline) and `raw_overall_score` (pre-cap, transparent), plus a `severity_caps_applied` tuple of rule names. `summarize_score_report` includes the cap rationale in the explanation when caps fire.

### Effect on previously misleading scores

A hypothetical agent that writes perfect code patterns and produces every required artifact, but every numeric comparator returns 0 (`code=1.0, exec=1.0, result_match=0.0`) used to score `0.55` weighted, suggesting "halfway reproducing." Under B-4a it caps at `0.50` with rule `result_match_below_0_30_caps_overall_at_0_50`, signalling reviewers that the result-match floor was breached. The `raw_overall_score=0.55` is preserved for transparency.

### Effect on the current 2840243 run

Frozen rescore confirms `0.935` is unchanged — all three categories (`code_development=1.000, execution=0.933, result_match=0.892`) are above every cap trigger, so `severity_caps_applied=[]`. The cap is purely defensive against future catastrophic submissions.

`194 passed in 11.90s` Cayuga regression suite (up from 189) confirms five new severity-cap tests integrate cleanly:

- `test_severity_caps_dont_fire_when_categories_healthy`
- `test_severity_caps_fire_when_result_match_catastrophic`
- `test_severity_caps_fire_when_execution_below_threshold`
- `test_severity_caps_use_lowest_when_multiple_fire`
- `test_score_rubric_payload_records_raw_and_capped`

### Remaining Edison-pattern items deferred to future sessions

- **Phase B-4b — D2-style method-fidelity audit**: extract Squidpy paper Methods into a structured per-step spec, add a deterministic-comparator leaf that scores YES/PARTIAL/NO matches per step. Direct fix candidate for the watershed-parameter mismatch driving the remaining 4 segmentation failures.
- **Phase B-4c — paper_spec.json declarative ground truth**: consolidate the existing `output_contract.md`, reference TSVs, and threshold policy into a single versioned JSON spec consumed by both prompts and comparators.
- **Krippendorff alpha paired-judge calibration**: run Sonnet 4.6 + Opus 4.7 on the same image-feature artifacts to produce per-leaf reliability metrics; addresses the long-standing handoff gap "Add a second human rater to the reliability packet" with model-paired evidence rather than waiting on a second human.

## Phase B-4b' Stage 1 — Dimensionality Tolerance Relaxation (2026-04-30)

After diagnosing all 4 remaining failures as a single watershed-segmentation runtime event, the `image_feature_matrix_dimensionality_band` leaf was relaxed from `tolerance_pct=0.0` (exact 26 columns required) to `tolerance_pct=25.0` (columns within 26 ± 25% = [19.5, 32.5]).

**Rationale**: the reference 26-column recipe is `histogram (4) + summary (15) + texture (2) + segmentation (5)`. The 5 segmentation columns are produced by a single `sq.im.segment` watershed call. If watershed fails at runtime, the agent's `histogram + summary + texture` matrix has 21 columns — 80% of the reference shape. Treating the segmentation cluster as one capability rather than five makes 21 columns an acceptable shape-band match while still rejecting placeholder fallbacks (5 columns of `fallback_feature_*`, ~80% off — safely outside the 25% band).

The `require_exact_ids: true` constraint still enforces all 2688 obs_ids exactly, so this is purely a column-count relaxation, not a row-count one. The other three segmentation-derived leaves (`segmentation_features_written`, `segmentation_feature_count_band`, `texture_feature_rank_overlap`) remain strict — they still correctly fail when watershed produces no output, so the relaxation is bounded.

### Frozen rescore 2840243 after Stage 1

| Category | B-4a baseline | B-4b' Stage 1 | Δ |
|---|---|---|---|
| code_development | 1.000 (23/23) | 1.000 (23/23) | unchanged |
| execution | 0.933 (13/14) | 0.933 (13/14) | unchanged |
| result_match | 0.892 (18/21) | **0.928 (19/21)** | +1 leaf |
| overall | 0.935 | **0.951** | **+0.016** |

`194 passed` Cayuga regression confirms the change is non-breaking.

### Stage 2 (deferred decision)

Three failures remain; all require watershed segmentation to actually execute at runtime:

- `execution/segmentation_features_written` (count >= 1)
- `result_match/segmentation_feature_count_band` (count within 5 ± 20%)
- `result_match/texture_feature_rank_overlap` (top-10 RBO including segmentation_label)

A prompt-side intervention (explicit watershed parameter recipe + smaller image crop suggestion to fit segmentation in budget) is the natural next step but requires a live eval to validate (≈$0.5, 15-60 min). Deferred pending budget approval.

## Remaining Human/Data Inputs

- Run a separate unassisted Squidpy submission before comparing model performance across agents.
- Add a second human rater to the reliability packet so Krippendorff's alpha and CI become meaningful.
- Materialize the reviewer-ready Inspiration4 multimodal object under `papers/inspiration4_multiome/data/cache/`.
