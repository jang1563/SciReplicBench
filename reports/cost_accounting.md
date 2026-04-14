# Cost Accounting

All costs below are measured from Inspect `.eval` log `stats.model_usage` using the public OpenAI `gpt-4o-mini` price list as of 2026-04 (input $0.15 / M, cached input $0.075 / M, output $0.60 / M). Exact per-run cost is small enough that rounding error dominates and numbers are shown to four decimals.

## Summary (smoke sandbox, squidpy_spatial)

| Phase | Agent | Judge | Leaves graded | Input (K) | Cache-read (K) | Output (K) | Est. cost (USD) | Wall-clock |
|---|---|---|---:|---:|---:|---:|---:|---|
| Dev / pipeline proof | openai/gpt-4o-mini | openai/gpt-4o-mini | 10 / 65 | 15.05 | 46.08 | 1.94 | ~$0.0094 | 75 s |
| Dev / full-leaf | openai/gpt-4o-mini | openai/gpt-4o-mini | 65 / 65 | 72.85 | 50.05 | 7.49 | ~$0.0196 | 215 s |

Both numbers include the agent's rollout **and** the judge's 10 or 65 per-leaf calls in the same total, because Inspect shares a single `stats.model_usage` channel across both.

## Derived unit economics

- Per-leaf judge cost (delta from the 10-leaf → 65-leaf run, agent effort held roughly constant): roughly **$0.0002 / leaf** with `gpt-4o-mini` on a context dominated by the paper summary + submission bundle (most of the extra tokens were cache-read). A full 65-leaf grading of a single sample costs roughly **$0.013 / sample** at this scale.
- Per-sample all-in at the smoke scale: **<$0.02**. This is the right order of magnitude to iterate on rubric wording and judge prompting without worrying about budget.

## Extrapolation (not yet measured)

Using the observed per-sample cost as a floor:

- Phase 4a pilot (three papers × three cheap agents × one seed ≈ nine runs) projects to **$0.10–$0.50** depending on how much the scientific image changes prompt volume.
- Phase 4b production (two-to-three agents × three papers × ≥ 3 seeds ≈ 18–27 runs) projects to **$5–$30** if the judge model stays at `gpt-4o-mini` or `o3-mini`; scaling up to `gpt-4o` as judge pushes this toward $100+.

Actual numbers will replace these estimates as real runs land.

## Methodology notes

- `rubric_tree_scorer` aggregates *every* leaf into a single Inspect `Score` per sample; there is no per-leaf judge call fan-out that escapes `stats.model_usage` accounting.
- `SCIREPLICBENCH_JUDGE_LEAF_LIMIT` caps the number of leaves graded per sample. Skipped leaves are recorded with `score=0` and evidence-quote `skipped by leaf_limit=<n>`; they consume no judge tokens.
- Cached prompt reads are billed at the lower rate and explain why the 65-leaf run's input cost scaled sub-linearly with the 10-leaf run.
- This table does not yet account for container build time (which is a compute-minutes / electricity concern, not an API spend concern). Docker build for the smoke sandbox is ~1 min; paper-specific scientific images will be ~15–30 min each on first build and are amortized across all runs against that paper.
