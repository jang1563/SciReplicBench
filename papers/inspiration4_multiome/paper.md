# Inspiration4 Single-Cell Multi-Ome

## Scope

This benchmark paper package targets the processed PBMC single-nucleus multi-ome analysis from Kim, Tierney, Overbey et al. *Nature Communications* (2024), DOI `10.1038/s41467-024-49211-2`. The benchmark is framed as **computational reproducibility of published findings**, not raw-to-final replication. The paper's original workflow is primarily R/Seurat/Signac based; SciReplicBench evaluates a defensible **Python/scanpy-style equivalent** that starts from preprocessed multimodal matrices rather than raw FASTQ files.

The agent is therefore expected to:

- load a curated multimodal object containing RNA and ATAC modalities,
- reproduce the main PBMC quality-control, integration, clustering, annotation, and differential analysis logic,
- recover the paper's core biological findings in a tool-agnostic but quantitatively comparable way, and
- save structured outputs that can be re-run in a fresh reproducer container.

The benchmark explicitly excludes raw Cell Ranger processing, BCR/TCR repertoire analysis, BayesPrism deconvolution, microbiome integration, and Ingenuity Pathway Analysis (IPA). These are either too compute-heavy, too domain-specific for the v1 artifact, or depend on commercial software. Open alternatives such as GSEA/ORA are required in place of IPA.

## Data Model

The reference paper profiled PBMC single-nucleus gene expression and chromatin accessibility across the four Inspiration4 crew members at six longitudinal timepoints: `L-92`, `L-44`, `L-3`, `R+1`, `R+45`, and `R+82`. After filtering, the study reports **151,411 nuclei** across a combined multi-omic analysis. For benchmark purposes, the label space is defined as **eight ontology-backed immune lineages plus one explicit residual bucket**:

- CD4 T cells
- CD8 T cells
- T cells, unspecified
- B cells
- NK cells
- CD14 monocytes
- CD16 monocytes
- dendritic cells
- residual immune cells

The first eight labels should normalize cleanly to Cell Ontology-compatible names or descendants. `residual immune cells` is an explicit benchmark bucket for low-confidence, mixed, or rare immune cells and is intentionally not forced into a fake ontology label.

For benchmark purposes, the input should be a preprocessed `AnnData` or `MuData` representation containing:

- raw or minimally processed RNA counts,
- ATAC peak accessibility or a derived latent representation,
- per-cell metadata for crew member, timepoint, and modality availability, and
- enough reference metadata to support hidden-label evaluation for clustering and annotation.

The benchmark should preserve the study's longitudinal structure and multimodal nature even if the execution path uses smaller subsets or cached reference outputs.

## Benchmark-Target Pipeline

### 1. Multimodal loading and quality control

The Python-equivalent pipeline should compute standard RNA and ATAC QC metrics, then apply the paper-aligned filters:

- minimum 200 genes detected per nucleus,
- maximum 4,500 RNA counts or equivalent upper RNA complexity cap,
- maximum 20% mitochondrial reads,
- maximum 100,000 ATAC peak counts,
- maximum nucleosome signal of 2,
- minimum TSS enrichment threshold.

The benchmark should reward exact threshold matching for `result_match` leaves, but allow modest implementation flexibility for `code_development` leaves when the agent applies the same conceptual filter family and documents its threshold choice.

### 2. Batch integration and latent representation

The original analysis used Harmony-assisted integration and a multi-omic workflow adapted from Seurat/Signac. In the Python benchmark, acceptable implementations should:

- normalize RNA,
- select informative features,
- build a joint representation across RNA and ATAC,
- correct for donor/timepoint batch structure without erasing biology, and
- generate PCA/LSI-style latent spaces suitable for graph construction and visualization.

The rubric should focus on the **algorithmic role** of each step rather than force a single library. A WNN-like or MOFA/MultiVI-style joint latent representation is acceptable if it yields comparable downstream clustering and annotation.

### 3. Clustering and cell-type annotation

The paper combined multimodal structure with reference-guided annotation to recover nine immune lineages and verified marker expression for each subpopulation. The benchmark should therefore expect:

- graph construction and Leiden-style clustering,
- UMAP or equivalent low-dimensional visualization,
- reference mapping or marker-based annotation,
- explicit handling of ambiguous clusters,
- ontology-aware normalization of labels to Cell Ontology-compatible names or descendants.

For grading, exact cluster IDs are not important; agreement after label normalization is.

### 4. Differential expression and pathway analysis

The paper compared immediate and later post-flight samples against pre-flight baselines, using `padj < 0.05` and `|log2FC| > 0.25` for DEGs and DARs. In the benchmark, the main target contrasts are the longitudinal post-flight comparisons within PBMCs and key immune cell classes. The expected Python path is:

- run differential expression per relevant cell type or pooled PBMCs,
- produce ranked gene lists,
- run open pathway analysis such as preranked GSEA or over-representation analysis,
- summarize the "spaceflight signature" pathways highlighted in the paper.

Core pathway findings to recover include oxidative phosphorylation, UV response, immune-function programs, and TCF21-related signals. These are benchmark anchors for `result_match`, but the implementation may use `gseapy`, `decoupler`, or another open-source equivalent.

For Phase 2 scorer implementation, the benchmark should use a single primary pathway-evaluation context by default: pooled PBMC `R+1` versus pooled pre-flight (`L-92`, `L-44`, `L-3`) unless a rubric leaf explicitly specifies a cell-type-specific contrast.

### 5. Chromatin accessibility and regulatory interpretation

The original work uses Signac/chromVAR-style ATAC analysis to identify differentially accessible regions, enriched TF motifs, and motif activity changes over time. The benchmark version should retain the same analytical intent:

- identify DARs for immediate and recovery timepoints,
- quantify motif enrichment or motif deviation activity,
- derive promoter/gene-activity summaries where needed,
- compare chromatin-derived regulatory signals to RNA-derived findings.

Important reference signals include the R+1 enrichment of motifs such as `SPIB`, `SPI1`, `CEBPD`, `SPIC`, `EHF`, `CEBPA`, `ELF3`, `IKZF1`, `EWSR1-FLI1`, `FOSL2`, and `KLF4`, followed by recovery over later timepoints. The paper also links TCF21- and FOXP3-related regulatory activity to the spaceflight response, which makes those especially useful for held-out evaluation leaves.

## Key Benchmark Findings To Target

The rubric and hidden references should center on findings that are both biologically meaningful and operationally gradable:

- the filtered dataset remains close to 151,411 nuclei,
- overall major cell proportions remain broadly stable across time,
- immediate post-flight (`R+1`) perturbation is stronger than later recovery timepoints,
- a pan-cellular "spaceflight signature" is enriched for oxidative phosphorylation, mitochondrial metabolism, UV response, immune pathways, and TCF21-related programs,
- FOXP3 target activity increases in T-cell compartments after flight,
- MHC class I expression shows long-term suppression,
- chromatin accessibility changes are strongest at `R+1` and recover over time.

These findings should be judged mostly through numeric comparators or hidden-reference overlap metrics rather than image inspection alone.

## Benchmark Boundaries

To keep the artifact public, portable, and reviewer-runnable, the following are **out of scope** for the v1 benchmark:

- raw Cell Ranger / Cell Ranger ARC processing,
- V(D)J mutation and repertoire analysis,
- cfRNA deconvolution with BayesPrism,
- microbiome association analyses,
- IPA-specific outputs,
- cross-species GeneLab meta-analysis as a required execution path.

Those components can still appear in `paper.md` as biological context, but they should not be required for a passing benchmark submission.
