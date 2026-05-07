# Squidpy Spatial Result-Match Threshold Calibration

Each numeric threshold in `result_match_reference.json` is benchmarked against a random-baseline distribution generated from the paper-pinned reference artifact in `reference_outputs/generated/`. The random baseline answers the question: *if a model produced random output of the same shape, what score would it get?* A defensible threshold must lie well above the random baseline.

Random trials per leaf: **200**. Seed: 20260430.

## Numeric thresholds — random-baseline calibrated

| Leaf | Metric | Random mean | Random std | Random p99 | Threshold | z-score | p(random passes) |
|---|---|---|---|---|---|---|---|
| `image_features_segmentation/image_feature_cluster_alignment_ari` | – | 0.000 | 0.002 | 0.005 | **0.250** | 137.76 | 0.000 |
| `image_features_segmentation/texture_feature_rank_overlap` | – | 0.115 | 0.068 | 0.290 | **0.600** | 7.09 | 0.000 |
| `interaction_reporting/ligrec_top_pair_overlap_threshold` | – | 0.001 | 0.007 | 0.025 | **0.600** | 89.25 | 0.000 |
| `interaction_reporting/marker_localization_consistency` | – | 0.031 | 0.276 | 0.650 | **0.600** | 2.06 | 0.025 |
| `spatial_graph_neighbors/centrality_ranking_overlap_threshold` | – | -0.002 | 0.151 | 0.306 | **0.800** | 5.30 | 0.000 |
| `spatial_graph_neighbors/cooccurrence_curve_overlap_threshold` | – | 0.001 | 0.014 | 0.032 | **0.850** | 61.39 | 0.000 |
| `spatial_graph_neighbors/interaction_matrix_overlap_threshold` | – | -0.005 | 0.097 | 0.213 | **0.800** | 8.28 | 0.000 |
| `spatial_graph_neighbors/known_spatial_association_recovered` | – | 0.045 | 0.207 | 1.000 | **1.000** | 4.61 | 0.045 |
| `spatial_graph_neighbors/nhood_enrichment_rank_overlap` | – | 0.061 | 0.057 | 0.259 | **0.650** | 10.32 | 0.000 |
| `spatial_graph_neighbors/positive_neighbor_pair_recovered` | – | 0.045 | 0.088 | 0.202 | **0.200** | 1.76 | 0.215 |
| `spatial_statistics/geary_rank_overlap_threshold` | – | 0.002 | 0.011 | 0.031 | **0.650** | 56.67 | 0.000 |
| `spatial_statistics/ripley_curve_overlap_threshold` | – | 0.003 | 0.043 | 0.088 | **0.900** | 20.98 | 0.000 |
| `spatial_statistics/spatial_localization_pattern_recovered` | – | 0.003 | 0.258 | 0.560 | **0.600** | 2.32 | 0.010 |
| `spatial_statistics/top_moran_genes_overlap_threshold` | – | 0.001 | 0.008 | 0.017 | **0.700** | 84.11 | 0.000 |

**Interpretation guide**:

- `z-score >= 5` and `p(random passes) <= 0.01`: threshold is well-calibrated; reviewer-defensible.
- `z-score 3-5`: defensible but conservative; document or tighten.
- `z-score < 3` or `p(random passes) > 0.05`: threshold not adequately above noise; tighten.

## Analytical (non-random-permutation) thresholds

These thresholds are not amenable to permutation calibration (numeric counts, exact shape matches, categorical matches). They act as gating checks rather than discriminative thresholds. See `scoring_methodology.json` for full details.

- `datasets_and_containers/image_shape_within_tolerance` (json_shape_within_tolerance): These leaves act as gates rather than discriminative checks. Recommend collapsing into one gating leaf per asset.
- `datasets_and_containers/label_vocabulary_matches_reference` (json_set_match): Categorical match or structural sanity; not a numeric threshold.
- `datasets_and_containers/seqfish_shape_within_tolerance` (json_shape_within_tolerance): These leaves act as gates rather than discriminative checks. Recommend collapsing into one gating leaf per asset.
- `datasets_and_containers/visium_shape_within_tolerance` (json_shape_within_tolerance): These leaves act as gates rather than discriminative checks. Recommend collapsing into one gating leaf per asset.
- `image_features_segmentation/image_feature_matrix_dimensionality_band` (tsv_shape_within_tolerance): These leaves act as gates rather than discriminative checks. Recommend collapsing into one gating leaf per asset.
- `image_features_segmentation/image_feature_structure_nondegenerate` (json_cluster_nondegenerate): Categorical match or structural sanity; not a numeric threshold.
- `image_features_segmentation/segmentation_feature_count_band` (json_numeric_within_tolerance): These leaves require the agent to actually compute the right thing; tolerance is for numerical noise, not random guessing.
- `interaction_reporting/ligrec_significant_count_band` (json_numeric_within_tolerance): These leaves require the agent to actually compute the right thing; tolerance is for numerical noise, not random guessing.
- `spatial_graph_neighbors/seqfish_graph_edge_count_band` (json_numeric_within_tolerance): These leaves require the agent to actually compute the right thing; tolerance is for numerical noise, not random guessing.
- `spatial_graph_neighbors/visium_graph_edge_count_band` (json_numeric_within_tolerance): These leaves require the agent to actually compute the right thing; tolerance is for numerical noise, not random guessing.
- `spatial_statistics/svg_fdr_count_within_band` (json_numeric_within_tolerance): These leaves require the agent to actually compute the right thing; tolerance is for numerical noise, not random guessing.

## Comparison with PaperBench

PaperBench (Starace et al., 2025) does not publish per-threshold calibration; its leaves are binary with thresholds set by expert judgment. SciReplicBench publishes random-baseline calibration for all discriminative numeric thresholds, providing a stronger peer-review defense for the chosen cutoffs.
