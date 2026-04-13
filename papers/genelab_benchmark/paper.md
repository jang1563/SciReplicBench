# GeneLab Benchmark: Multi-Tissue Spaceflight Transcriptomics

## Scope

This package targets the public `GeneLab_benchmark` project, which is a benchmark-of-models rather than a single wet-lab paper. In SciReplicBench it serves as the **authored scaling demonstration**: the benchmark already has structured tasks, public code, and public feature matrices, so it is the most natural place to show that the SciReplicBench framework can expand beyond exploratory omics pipelines into standardized evaluation workloads.

The benchmark should therefore focus on **computational reproducibility of the evaluation workflow**, not on rebuilding every raw-data processing step from scratch. The agent is expected to:

- obtain the public feature matrices and metadata from HuggingFace or cached files,
- reproduce the core classical ML baselines and cross-validation logic,
- reproduce mission-transfer and tissue-transfer summaries,
- run or appropriately stage a foundation-model comparison,
- generate tables, metrics, and negative-control outputs that match the benchmark's headline conclusions.

The package should remain public and reviewer-runnable. That means the default reviewer path should use precomputed feature matrices, while more expensive raw-download or Geneformer runs remain optional extensions.

## Data Model

The research summary defines the benchmark scale as:

- **6 tissues**
- **17 ISS missions**
- **24 verified OSD studies**
- **~450 samples**
- binary **Flight vs Ground** labels
- more than **25 evaluation tasks** across multiple categories

The benchmark uses NASA OSDR-derived mouse bulk RNA-seq data, but for SciReplicBench the main execution path should rely on the published feature matrices and metadata distributed through HuggingFace. This keeps the task portable and makes the benchmark more about scientific ML reasoning than about downloading large archives.

## Benchmark-Target Pipeline

### 1. Data acquisition and preprocessing

The first stage is to load the benchmark-ready feature matrices, metadata tables, and split definitions. The original project applies DESeq2-based normalization, log transformation, low-expression filtering, and variance filtering. In SciReplicBench, the benchmark should accept either:

- direct use of the published normalized matrices, or
- a documented reproduction of the normalization/filtering workflow that yields comparable downstream performance.

The critical point is that the agent preserves the train/test boundaries and does not leak information across missions or tissues.

### 2. Category A: Spaceflight detection with LOMO validation

The most central benchmark task is **leave-one-mission-out (LOMO)** classification of Flight versus Ground status within each tissue. The task package should expect the agent to:

- implement the LOMO loop correctly,
- fit the classical baselines highlighted in the benchmark,
- compute AUROC with bootstrap confidence intervals,
- apply the published Go/No-Go criteria.

This is the cleanest place to test whether an agent can handle careful evaluation logic instead of just fitting a single classifier once.

### 3. Category B and C: Transfer learning across missions and tissues

The benchmark becomes more interesting when the train/test split changes meaning:

- **cross-mission transfer** asks whether a model trained on mission `i` generalizes to mission `j`,
- **cross-tissue transfer** asks whether signal learned in one tissue carries over to another,
- pathway-level representations can compete with gene-level features for these tasks.

SciReplicBench should preserve this logic because it is what distinguishes GeneLab_benchmark from a generic transcriptomics classifier.

### 4. Classical baselines

The published baseline family includes:

- elastic-net logistic regression,
- random forest,
- XGBoost,
- PCA plus logistic regression.

These are the foundation of the benchmark and should account for a large fraction of the rubric. The agent should not receive full credit for reproducing only one baseline. At minimum, the workflow should show that it can fit multiple baseline families and compare them under the same split definitions.

### 5. Foundation model evaluation

Geneformer is the most compute-intensive part of the benchmark. Serious Geneformer fine-tuning should happen on a GPU-equipped HPC (A40/A100 or equivalent) in a pre-configured Python 3.11 environment with `torch`, `transformers`, and the Geneformer package. SciReplicBench therefore separates:

- the **portable reviewer path**, where the task can succeed without long GPU training,
- the **full authored path**, where Geneformer is run on A40/A100 hardware and compared to classical baselines.

This is an important benchmark-design distinction. The rubric should reward correct staging, data preparation, and comparison logic even if a lightweight run uses cached embeddings or a shortened training schedule.

### 6. Pathways, negative controls, and interpretability

The benchmark also includes pathway analysis, negative controls, and interpretability:

- preranked fGSEA / GSVA-style summaries,
- confounder prediction,
- permutation tests and housekeeping baselines,
- SHAP feature importance,
- conservation analysis against external consensus signatures.

These are useful because they move the task beyond pure classification accuracy. An agent that only reports AUROC but misses the negative controls or interpretability layer should not be able to score highly.

## Key Benchmark Findings To Target

The rubric should emphasize the most benchmark-defining, portable findings:

- LOMO Flight-versus-Ground evaluation runs correctly across tissues,
- AUROC, bootstrap confidence intervals, and permutation p-values are computed correctly,
- multiple classical baselines are compared under identical splits,
- negative controls stay near chance performance,
- cross-mission and cross-tissue transfer results are summarized as matrices or structured tables,
- pathway-level analyses and SHAP-style explanations are exported in inspectable formats,
- Geneformer, when staged or run, is compared explicitly against the classical baselines rather than presented in isolation.

## Benchmark Boundaries

To keep v1 practical and reviewer-runnable, the package should avoid several traps:

- no requirement to re-download and reprocess every raw FASTQ in the default path,
- no hard dependency on GPU for the minimal success path,
- no credit for leaking information across train/test missions,
- no single-number leaderboard framing without confidence intervals or negative controls,
- no result-match grading on screenshots alone.

Paper 3 is where SciReplicBench shows it can handle a **benchmark artifact inside a benchmark artifact**. That only works if the rubric emphasizes experimental design, leakage control, and statistical reporting rather than letting the task collapse into \"fit one model and print AUROC\".
