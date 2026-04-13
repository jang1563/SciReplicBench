# Inspiration4 Method Equivalence Matrix

This matrix defines the accepted Python-side substitutes for the original paper's R-heavy workflow. The benchmark grades **computational intent and result recovery**, not literal library identity.

| Original paper tool / step | Role in the published analysis | Accepted Python-side equivalent(s) | What must be preserved for grading |
|---|---|---|---|
| `Seurat` object creation + metadata handling | Central RNA container with cell metadata | `AnnData` in `scanpy` or `MuData` in `muon` | Cell-wise metadata, raw counts or equivalent, and reproducible saved objects |
| `PercentageFeatureSet` + Seurat QC filters | RNA QC metrics and thresholds | `scanpy.pp.calculate_qc_metrics` | Same filter family and near-paper thresholds for genes, counts, and mitochondrial fraction |
| `Signac` chromatin assay QC | ATAC depth, nucleosome signal, TSS enrichment | `muon.atac`, `episcanpy`, or custom ATAC QC code | Explicit ATAC QC metrics with logged thresholds |
| `RunTFIDF` / `RunSVD` / LSI | ATAC latent representation | `muon.atac.pp.tfidf`, `sklearn.decomposition.TruncatedSVD`, `episcanpy` LSI workflows | A valid ATAC latent space used in downstream neighbors/integration |
| `RunHarmony` / Harmony integration | Remove donor/timepoint batch effects while preserving biology | `harmonypy` or `scanpy.external.pp.harmony_integrate` | Documented Harmony-like integration or another explicit batch-correction step with comparable downstream behavior |
| WNN / multimodal neighbor graph | Joint RNA+ATAC representation | `muon` + `MOFA+`, `muon.pp.neighbors` on joint latent embeddings, or `scvi-tools` `MULTIVI` | Joint multimodal structure, not RNA-only clustering masquerading as multiome integration |
| `FindNeighbors` + `FindClusters` | Graph construction and clustering | `scanpy.pp.neighbors` + `scanpy.tl.leiden` | Reproducible graph-based clustering with saved labels |
| `RunUMAP` | Visualization and neighborhood preservation | `scanpy.tl.umap` | A low-dimensional embedding tied to the integrated graph |
| `Azimuth` reference mapping | PBMC cell-type label transfer | `celltypist`, `scANVI`, or marker-scoring plus manual curation | Final labels must map cleanly to the benchmark's nine immune lineages |
| Manual marker validation | Confirm cluster identities | `scanpy.pl.dotplot`, `scanpy.pl.matrixplot`, marker AUC/rank reports | Marker evidence should support assigned lineage names |
| `FindMarkers` (Wilcoxon) | Differential expression per contrast | `scanpy.tl.rank_genes_groups(method=\"wilcoxon\")`, `diffxpy`, or equivalent rank-based test | Same contrast logic and published thresholds `padj < 0.05`, `|log2FC| > 0.25` |
| `fgsea` preranked GSEA | Pathway enrichment for DE signatures | `gseapy.prerank`, `decoupler.run_gsea`, or equivalent preranked enrichment | Ranked-gene enrichment with reproducible gene-set source and adjusted p-values |
| `ssGSEA` | Per-sample or per-cell pathway activity | `gseapy.ssgsea`, `decoupler`, or pseudobulk pathway scoring | Relative pathway activity trends across timepoints or cell types |
| `FindMotifs` on DARs | TF motif enrichment from accessible regions | `pycisTopic`, `gimmemotifs`, HOMER via subprocess, or equivalent motif-enrichment workflow | Ranked motif enrichment tied to DAR sets |
| `chromVAR` deviation scores | Motif activity dynamics over time | `pycisTopic` motif deviation/enrichment proxies or another explicit motif-activity workflow | A numeric motif activity signal that can be compared across timepoints and cell types |
| `GeneActivity` | ATAC-derived gene activity for cross-modal interpretation | promoter/gene-body accessibility summarization in `muon`, `episcanpy`, `pycisTopic`, or custom aggregation | ATAC-derived gene-level signal linked back to RNA interpretation |
| GO / ORA side analysis | Secondary confirmation of pathway findings | `gseapy.enrichr`, `goatools`, `decoupler`, or similar | Open-source enrichment confirming broad pathway directionality |
| `ComplexHeatmap` / volcano / dot plots | Communication of key results | `matplotlib`, `seaborn`, `scanpy.pl`, `plotnine`, `altair` | Figures are optional for code-development credit but required for relevant execution leaves |

## Benchmark policy

- Final labels should normalize to eight ontology-backed benchmark lineages plus the explicit benchmark residual bucket `residual immune cells`.
- Exact tool identity is **not** required unless a rubric leaf explicitly tests an algorithmic class.
- For `code_development`, a clearly documented substitute earns credit if it serves the same analytical purpose.
- For `result_match`, the substitute must recover the hidden-reference outputs within the stated numeric tolerance.
- IPA is excluded; open-source pathway methods are mandatory.
