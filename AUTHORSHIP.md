# Authorship and Conflict-of-Interest Disclosure

SciReplicBench evaluates agents against rubrics the benchmark author either co-wrote, sole-authored, or had no involvement in. This page makes those relationships explicit so that reviewers can reason about grading bias.

## Per-paper disclosure

| Paper | Relationship to benchmark author (JangKeun Kim) |
|---|---|
| `inspiration4_multiome` — Kim/Overbey et al. *Nat Commun* 2024 ([doi](https://doi.org/10.1038/s41467-024-49211-2)) | **First author.** The rubric reflects direct familiarity with the published pipeline; the benchmark author controls both the source paper and the grading criteria. |
| `squidpy_spatial` — Palla et al. *Nat Methods* 2022 ([doi](https://doi.org/10.1038/s41592-021-01358-2)) | **No authorship.** Included deliberately as an external third-party anchor: neither the paper nor the rubric target is work the benchmark author contributed to. |
| `genelab_benchmark` — this repository's companion benchmark on NASA spaceflight RNA-seq | **Sole author.** The rubric encodes the benchmark's own evaluation logic and Go/No-Go criteria. |

## How the benchmark mitigates self-grading bias

1. **External anchor (`squidpy_spatial`).** One of the three papers is chosen specifically to be out-of-scope for the author's contributions. Any judge reliability metric reported on this paper is a direct estimate of grader behaviour free of self-grading incentive.
2. **Holdout calibration panel.** `judge_eval/holdout_calibration.json` reserves a set of leaves for calibrating the LLM judge against externally graded examples. These leaves are drawn primarily from `squidpy_spatial` and from `novel_contrast.json` entries designed as anti-memorization controls.
3. **Structured judge output.** Each leaf grade requires an `Expectations → Reality → Evidence Quote → Score` chain (see `src/scireplicbench/judge.py`). The mandatory evidence quote forces the judge to cite a specific line from the submission, which prevents score-first rationalization even on familiar material.
4. **Category weight floors.** `result_match` leaves must account for at least 40% of each paper's rubric weight, `execution` at least 20%, and `code_development` at most 40%. This prevents an agent from passing by getting many trivially graded setup leaves while failing the load-bearing quantitative checks.
5. **Numeric-first comparators.** Where possible, grading is reduced to ARI / NMI for clustering, RBO / overlap@k for ranked-gene lists, and fixed padj thresholds (see `src/scireplicbench/comparators.py`). This removes the subjective axis of grading on the leaves most vulnerable to author-familiarity bias.

## Reviewer-checkable claims

A reviewer who wants to independently verify the firewall can:

- Inspect `papers/squidpy_spatial/rubric.json` and confirm that none of the grading notes reference unpublished work of the benchmark author.
- Run the test suite (`pytest`) to confirm rubric structure, category floors, and judge prompt shape.
- Read `judge_eval/holdout_calibration.json` and confirm the held-out panel spans the external paper.
- Read `papers/<paper>/novel_contrast.json` for each authored paper and confirm the held-out contrast is unpublished.

## Version

This disclosure applies to SciReplicBench v0.1.0. Later versions should maintain or strengthen — not weaken — this firewall.
