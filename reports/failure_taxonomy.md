# Failure Taxonomy

## Goal

Document the dominant ways agents fail on SciReplicBench once pilot or production runs exist. Target at least 4 named modes with concrete examples.

## Template

### 1. Environment Setup Drift

- Definition: the agent cannot establish a runnable environment or silently depends on unstaged state.
- Evidence examples: missing package installs, incorrect paths, irreproducible temp files.
- Typical affected papers: pending
- Mitigations: pending

### 2. Evaluation Leakage Or Split Violations

- Definition: the agent leaks information across benchmark splits or violates the reviewer path.
- Evidence examples: train/test contamination, mission leakage, direct reuse of authored repository outputs.
- Typical affected papers: pending
- Mitigations: pending

### 3. Result-Match Near Misses

- Definition: the workflow runs, but ranked outputs or metrics fall short of the rubric thresholds.
- Evidence examples: wrong top genes, poor overlap@k, weak ARI/NMI, inaccurate pathway ranks.
- Typical affected papers: pending
- Mitigations: pending

### 4. Unsupported Tool Substitution

- Definition: the agent chooses a tool or algorithm family that is not method-equivalent enough for the rubric.
- Evidence examples: count-agnostic batch correction where count-aware modeling was required.
- Typical affected papers: pending
- Mitigations: pending

### 5. Judge-Evidence Mismatch

- Definition: the scoring evidence is present, but the judge or output formatting makes it hard to score reliably.
- Evidence examples: missing evidence quote, ambiguous log files, non-machine-readable outputs.
- Typical affected papers: pending
- Mitigations: pending
