# GeneLab Benchmark Method Equivalence

GeneLab_benchmark mixes Python ML code with R/Bioconductor-style normalization and pathway-analysis conventions. The benchmark should reward preservation of the **evaluation logic** and the **algorithmic class** of each step rather than force a single language.

| Original project component | Role in the workflow | Accepted equivalent(s) in SciReplicBench | What must be preserved for grading |
|---|---|---|---|
| OSDR / HuggingFace feature-matrix download | Public data access | direct HuggingFace download, cached benchmark matrices, or packaged sample files | identical train/test metadata and sample identities |
| DESeq2 normalization | mission-level count normalization | published normalized matrices, `PyDESeq2`, or another documented size-factor workflow | no train/test leakage and comparable downstream feature scale |
| low-expression filtering | remove uninformative genes | explicit count-based filtering on train folds or use of published filtered matrices | filtering logic must avoid peeking at held-out data |
| top-variance feature selection | reduce dimensionality per fold | train-fold variance filtering in Python or provided benchmark splits | feature selection must be fit on train data only |
| ElasticNet logistic regression | baseline linear classifier | `sklearn.linear_model.LogisticRegression(solver=\"saga\", penalty=\"elasticnet\")` | comparable hyperparameter family and probability outputs |
| Random forest | nonlinear classical baseline | `sklearn.ensemble.RandomForestClassifier` | seeded training and fold-aware evaluation |
| XGBoost | boosted-tree baseline | `xgboost.XGBClassifier` | comparable objective and probability outputs |
| PCA + logistic regression | low-rank baseline | `sklearn.decomposition.PCA` + logistic regression | PCA fit on train folds only |
| LOMO evaluation loop | core generalization test | any implementation that leaves one mission out at a time | mission-wise split integrity is non-negotiable |
| cross-mission transfer matrix | pairwise generalization summary | any loop that evaluates ordered mission pairs | matrix semantics and metric definitions must match |
| cross-tissue transfer | tissue generalization summary | any implementation that preserves the published train/test tissue logic | correct tissue-pair bookkeeping |
| AUROC + bootstrap CI | main performance statistic | `sklearn.metrics.roc_auc_score` plus bootstrap resampling | confidence intervals and resampling definition must be explicit |
| permutation p-value | negative-control significance check | explicit label permutations or cached permutation summaries | same null concept as the benchmark |
| fGSEA | group-level pathway enrichment | `gseapy.prerank`, `decoupler`, or another preranked GSEA implementation | ranked-gene enrichment with signed statistics |
| GSVA | sample-level pathway features | `gseapy.ssgsea`, `decoupler`, or another documented sample-level pathway score | pathway-level representation, not just gene-level reuse |
| ComBat-seq / limma / RUVseq comparisons | batch-correction ablation | benchmark-provided precomputed comparisons, `pycombat` on transformed features, or another explicitly documented transformed-feature ablation | preserve the comparison logic, and do not treat `scanpy.pp.combat` as a count-level drop-in replacement for ComBat-seq |
| SHAP feature importance | model interpretability | `shap` in Python | feature-importance ranking and tissue/model bookkeeping |
| Geneformer fine-tuning | foundation-model baseline | full Geneformer run on a GPU-equipped HPC, cached Geneformer outputs, or a staged lightweight run with documented constraints | model-comparison logic and no silent omission of the foundation-model branch |

## Benchmark policy

- For the reviewer path, using the published processed feature matrices is acceptable and preferred.
- For the default reviewer path, start from `data/huggingface_dataset/A*_lomo/fold_*/train_X.csv` and `test_X.csv`, joined to `data/raw/GeneLab_benchmark/tasks/A*_lomo/fold_*/train_y.csv`, `test_y.csv`, `train_meta.csv`, and `test_meta.csv`.
- Each tissue directory is only a container for `fold_*` subdirectories. Do not assume `train_X.csv`, `test_X.csv`, or `labels.csv` exist at the tissue root.
- In the staged reviewer path, the sample IDs live in the first CSV column. Load `train_X.csv`, `test_X.csv`, `train_y.csv`, and `test_y.csv` with `index_col=0`, use the single numeric column in `train_y.csv` / `test_y.csv` as the binary target, and align all tables by shared sample IDs before fitting.
- Treat `train_meta.csv` and `test_meta.csv` as descriptive mission/tissue metadata, not as substitute feature matrices or target columns for the main classifier.
- Do not collapse the benchmark to one hard-coded demo fold. A minimal passing workflow should iterate real `fold_*` directories and aggregate the folds it actually ran.
- For AUROC, use continuous scores such as `predict_proba` or `decision_function`, not hard class labels from `predict()`.
- Required TSV outputs should contain real machine-readable rows. If a branch is incomplete, emit a structured status table rather than a one-line placeholder sentence.
- The `data/huggingface_dataset/v4/`, `v5/`, and `v6/` evaluation JSON files are reference summaries for comparison, not substitute feature matrices for model fitting.
- For `code_development`, a clear fold-aware implementation of the evaluation logic earns credit even if it substitutes one open-source package for another.
- If `/workspace/submission/run.sh` is required, it should be a launcher for substantive source files under `/workspace/submission`, not the only place where the analysis logic lives.
- For `result_match`, the submission must match the hidden reference outputs within the benchmark's numeric tolerances.
- Any substitute that leaks held-out mission or tissue information should fail regardless of surface similarity.
