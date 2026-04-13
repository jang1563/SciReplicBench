# SciReplicBench

An [Inspect AI](https://inspect.aisi.org.uk/) benchmark for evaluating whether LLM agents can reproduce computational-biology results from published papers, following the decomposition methodology of [PaperBench](https://arxiv.org/abs/2504.01848).

Agents operate inside a Docker sandbox, write and execute code, install packages, and produce outputs. Submissions are graded against hierarchical rubric trees by an LLM judge with structured evidence-quote outputs, path-based leaf identifiers, category weight floors, and a fresh-container reproduction pass.

---

## Paper lineup (v1)

| Paper | Modality | Notes |
|---|---|---|
| `inspiration4_multiome` | single-cell scRNA + scATAC + VDJ multimodal integration | Kim/Overbey et al. *Nat Commun* 2024 ([doi](https://doi.org/10.1038/s41467-024-49211-2)). Rubric targets the Python/scanpy-equivalent pipeline. |
| `squidpy_spatial` | spatial statistics + image analysis | Palla et al. *Nat Methods* 2022 ([doi](https://doi.org/10.1038/s41592-021-01358-2)). External third-party anchor; datasets via `squidpy.datasets`. |
| `genelab_benchmark` | bulk RNA-seq + classical ML + Geneformer foundation model | Leave-one-mission-out cross-validation benchmark on NASA spaceflight transcriptomics. |

The inclusion of one external paper (`squidpy_spatial`) anchors judge reliability against work the author did not co-write; author relationships for the other two papers are disclosed in each paper's `paper.md`.

---

## Design highlights

- **Inspect AI task scaffold** with a ReAct agent and a minimal tool surface: `bash()`, `python()`, and a sandbox-backed `scratchpad()` for multi-turn planning.
- **Two-service Docker Compose runtime** (`agent` + `reproducer`) for fresh-container replays of submitted `reproduce.sh`, mitigating reward-hacking via contaminated state.
- **Path-based rubric leaf IDs** with category weight floors (`result_match ≥ 40%`, `execution ≥ 20%`, `code_development ≤ 40%`) and bottom-up weighted aggregation.
- **Structured judge** with ordered JSON output (Expectations → Reality → Evidence Quote → Score), `n=3` self-consistency on disagreement-flagged leaves, and a one-time cached paper summary shared across leaf calls.
- **Numeric-first comparators**: ARI / NMI for clusters, RBO / overlap@k for DEGs, fixed padj thresholds, and ontology-aware lookups (Cell Ontology, HGNC, GO) where applicable.
- **Judge reliability scaffold** built for Krippendorff's α with bootstrap CIs on paired human grades, plus a held-out calibration panel for a conflict-of-interest firewall.

---

## Repository layout

```
scireplicbench/
├── papers/                         # rubric + task definitions per paper
│   ├── inspiration4_multiome/
│   ├── squidpy_spatial/
│   └── genelab_benchmark/
├── src/scireplicbench/             # Inspect task, scorers, judge, comparators, reproducer
├── environments/                   # Dockerfile + per-paper Compose files
├── configs/                        # pilot / production run plans, runtime.env.example
├── judge_eval/                     # human grades, holdout calibration, reliability runner
├── scripts/                        # plan rendering, readiness check, report rendering
├── reports/                        # evaluation, reliability, cost, failure taxonomy, postmortem
└── tests/                          # pytest suite
```

---

## Quickstart

```bash
# Clone and install
git clone <this-repo-url>
cd scireplicbench
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Configure API keys (copy template, then edit in place)
cp configs/runtime.env.example configs/runtime.env

# Verify the runtime is ready
python scripts/check_runtime_readiness.py

# Generate a Phase-4 run plan (pilot or production)
python scripts/render_phase4_plan.py

# Run the test suite
pytest
```

Running the benchmark itself requires Docker, an Inspect-compatible model provider configured in `configs/runtime.env`, and per-paper data staged via each paper's `papers/<paper>/data/prepare_data.sh`.

---

## Phased evaluation

The benchmark is designed for a two-stage evaluation to control cost:

1. **Phase 4a — cheap pilot.** Run the full pipeline end-to-end on small / reasoning-light models (e.g., `gpt-4o-mini`, `claude-haiku`, `deepseek`) to validate rubric grading, Docker behavior, reproducer diffs, and tool use before committing to expensive runs.
2. **Phase 4b — production.** Run the agent lineup decided from the pilot signal (typically `gpt-4o` + `claude-sonnet` with `o3-mini` as reasoning anchor; judge commonly `o3-mini` with `n=3` self-consistency on disagreements) across ≥3 seeds per paper and compile reliability + cost tables.

Skeleton plans for each phase live under `configs/` and `reports/phase4{a,b}_*`.

---

## Framing

SciReplicBench measures **computational reproducibility of published findings** — not exact bit-level replication. Where the original paper used R/Seurat or another non-Python stack, the rubric targets the Python/scanpy-equivalent workflow and documents acceptable method substitutes in each paper's `method_equivalence.md`. Each paper also includes a `novel_contrast.json` that specifies a held-out contrast or annotation not present in the source paper, as an anti-memorization control for frontier models whose training data likely includes the original tutorials.

v1 is intended as a methodology prototype on three papers, not a general-purpose benchmark; scaling beyond three papers is explicit future work.

---

## License

MIT — see [LICENSE](LICENSE).
