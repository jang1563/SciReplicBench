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

The inclusion of one external paper (`squidpy_spatial`) anchors judge reliability against work the author did not co-write; per-paper author relationships and the conflict-of-interest firewall are disclosed in [AUTHORSHIP.md](AUTHORSHIP.md).

An additional internal harness, `evidence_policy_probe`, lives alongside the paper packages as a deterministic v0.4 validation task. It is not part of the three-paper benchmark lineup; its only job is to prove that the shipped scorer emits `evidence_policy_failed` in a real Inspect run once precheck succeeds.

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

```text
scireplicbench/
├── papers/                         # rubric + task definitions per paper
│   ├── inspiration4_multiome/
│   ├── squidpy_spatial/
│   ├── genelab_benchmark/
│   └── evidence_policy_probe/      # internal v0.4 scorer-validation harness
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

Current staging status: `inspiration4_multiome` now builds its scientific image and `papers/inspiration4_multiome/data/prepare_data.sh` stages both the public `inspiration4-omics` repository under `papers/inspiration4_multiome/data/raw/` and the public `OSD-570`/`GLDS-562` processed files under `papers/inspiration4_multiome/data/cache/osdr_public/`. Those public downloads are useful DEG/DAR tables plus ISA metadata, but the benchmark-ready AnnData or MuData cache under `papers/inspiration4_multiome/data/cache/` is still required before a real production eval can run. `genelab_benchmark` now also builds its scientific image, and `papers/genelab_benchmark/data/prepare_data.sh` stages both the public `GeneLab_benchmark` repository and the public Hugging Face `A*_lomo` feature matrices with Git LFS materialization. The latest April 22, 2026 GeneLab reruns also showed that the package is past the old sample-ID/index trap: one run now loads fold data with `index_col=0`, aligns `X`/`y`, and writes a real `lomo/summary.tsv`. The current blocker is narrower and more structural: turning that real-but-toy artifact into benchmark-shaped multi-fold outputs without oscillating back into debug-only scripts. The next improvement there should come from a stronger task scaffold, not more prompt wording alone.

For a fast end-to-end runtime check, you can point tasks at the lightweight smoke sandbox instead of the paper-specific scientific image:

```bash
SCIREPLICBENCH_ENV_VARIANT=smoke python -m inspect_ai eval \
  src/scireplicbench/tasks.py@scireplicbench \
  --model openai/gpt-4o-mini \
  -T paper_id=squidpy_spatial \
  --message-limit 5 \
  --time-limit 600 \
  --working-limit 600
```

For the deterministic v0.4 scorer-validation harness that proves `evidence_policy_failed` on a live Inspect run:

```bash
.venv/bin/python scripts/run_evidence_policy_probe.py
```

For the deterministic v0.5 Squidpy-paper probe that uses the real `squidpy_spatial` bundle and scientific image:

```bash
.venv/bin/python scripts/run_evidence_policy_probe.py --probe squidpy
```

For the v1.2 frontier-agent Squidpy-paper probe that keeps the real paper package but lets `gpt-4o-mini` author the artifacts:

```bash
.venv/bin/python scripts/run_evidence_policy_probe.py --probe squidpy-agent --model openai/gpt-4o-mini
```

For the matching Sonnet v1.2 artifact:

```bash
.venv/bin/python scripts/run_evidence_policy_probe.py --probe squidpy-agent --model anthropic/claude-sonnet-4-6 --artifact-label sonnet
```

For the matching Haiku v1.2 artifact:

```bash
.venv/bin/python scripts/run_evidence_policy_probe.py --probe squidpy-agent --model anthropic/claude-haiku-4-5 --artifact-label haiku
```

For the first live-judge extension of the same probe using `gpt-4o-mini` as the judge:

```bash
.venv/bin/python scripts/run_evidence_policy_probe.py \
  --probe squidpy-agent \
  --model openai/gpt-4o-mini \
  --judge-model openai/gpt-4o-mini \
  --artifact-label judge_gpt4o_mini
```

---

## Phased evaluation

The benchmark is designed for a two-stage evaluation to control cost:

1. **Phase 4a — cheap pilot.** Run the full pipeline end-to-end on small / reasoning-light models (e.g., `gpt-4o-mini`, `claude-haiku`, `deepseek`) to validate rubric grading, Docker behavior, reproducer diffs, and tool use before committing to expensive runs.
2. **Phase 4b — production.** Run the agent lineup decided from the pilot signal (typically `gpt-4o` + `claude-sonnet` with `o3-mini` as reasoning anchor; judge commonly `o3-mini` with `n=3` self-consistency on disagreements) across ≥3 seeds per paper and compile reliability + cost tables.

Skeleton plans for each phase live under `configs/` and `reports/phase4{a,b}_*`.

---

## Framing

SciReplicBench measures **computational reproducibility of published findings** rather than exact bit-level replication. Where the original paper used R/Seurat or another non-Python stack, the rubric targets the Python/scanpy-equivalent workflow and documents acceptable method substitutes in each paper's `method_equivalence.md`. Each paper also includes a `novel_contrast.json` that specifies a held-out contrast or annotation not present in the source paper, as an anti-memorization control for frontier models whose training data likely includes the original tutorials.

v1 is intended as a methodology prototype on three papers, not a general-purpose benchmark; scaling beyond three papers is explicit future work.

---

## License and citation

MIT — see [LICENSE](LICENSE). Citation metadata is provided in [CITATION.cff](CITATION.cff).
