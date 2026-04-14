# Cost Accounting

All costs below are measured from Inspect `.eval` log `stats.model_usage` using the public OpenAI `gpt-4o-mini` price list as of 2026-04 (input $0.15 / M, cached input $0.075 / M, output $0.60 / M). Exact per-run cost is small enough that rounding error dominates and numbers are shown to four decimals.

## Summary (squidpy_spatial)

| Phase | Sandbox | Agent | Judge | Leaves | Agent tokens (in/cache/out) | Judge tokens (in/out) | Est. cost (USD) | Wall-clock |
|---|---|---|---|---:|---|---|---:|---|
| Dev / pipeline proof | smoke | gpt-4o-mini | gpt-4o-mini | 10 | 15K / 46K / 1.9K (shared) | (shared) | ~$0.0094 | 75 s |
| Dev / full-leaf | smoke | gpt-4o-mini | gpt-4o-mini | 65 | 73K / 50K / 7.5K (shared) | (shared) | ~$0.0196 | 215 s |
| Dev / production | production | gpt-4o-mini | gpt-4o-mini | 65 | 96K / 119K / 10.5K (shared) | (shared) | ~$0.0295 | 332 s |
| Dev / production | production | claude-haiku-4-5 | gpt-4o-mini | 65 | 6.7K / 130K / 1.7K | 56K / 6.8K | ~$0.15 | 274 s |
| Dev / production | production | claude-sonnet-4-6 | gpt-4o-mini | 65 | 1.8K / 178K / 1.7K | 56K / 6.8K | ~$0.58 | 247 s |

When the agent and judge are the same OpenAI model, Inspect reports their combined tokens in one row and separating them requires counting leaf calls by hand. When the agent is Anthropic and the judge is OpenAI, each provider's totals are tracked independently and the judge column is populated directly.

## Derived unit economics

- **gpt-4o-mini end-to-end:** ~$0.03 / sample. 65 judge leaves on a real production submission cost essentially the same as the agent itself, thanks to prompt caching.
- **Claude Haiku 4.5 as agent (with gpt-4o-mini judge):** ~$0.15 / sample. About 5× more expensive than gpt-4o-mini end-to-end, driven by Haiku input pricing even though the judge side is unchanged.
- **Claude Sonnet 4.6 as agent (with gpt-4o-mini judge):** ~$0.58 / sample. ~20× gpt-4o-mini end-to-end and ~4× Haiku. The jump is almost entirely Sonnet's output + cache-write pricing at the strong-model tier.
- **Judge cost is stable across agents:** the judge used ~56K input + 6.8K output tokens in both Claude runs, mirroring the structure of the paper bundle + rubric + per-leaf prompting. This is the floor you pay to grade one sample with a gpt-4o-mini judge on the 65-leaf squidpy rubric: ~$0.012 regardless of which agent produced the submission.
- Per-sample all-in remains **<$1** for any agent in the currently tested lineup, which is the right order of magnitude to iterate on rubric wording and judge prompting without worrying about budget.

## Extrapolation (not yet measured)

Using the observed per-sample cost as a floor:

- Phase 4a pilot (three papers × three cheap agents × one seed ≈ nine runs) projects to **$0.10–$0.50** depending on how much the scientific image changes prompt volume.
- Phase 4b production (two-to-three agents × three papers × ≥ 3 seeds ≈ 18–27 runs) projects to **$5–$30** if the judge model stays at `gpt-4o-mini` or `o3-mini`; scaling up to `gpt-4o` as judge pushes this toward $100+.

Actual numbers will replace these estimates as real runs land.

## Methodology notes

- `rubric_tree_scorer` aggregates *every* leaf into a single Inspect `Score` per sample; there is no per-leaf judge call fan-out that escapes `stats.model_usage` accounting.
- `SCIREPLICBENCH_JUDGE_LEAF_LIMIT` caps the number of leaves graded per sample. Skipped leaves are recorded with `score=0` and evidence-quote `skipped by leaf_limit=<n>`; they consume no judge tokens.
- Cached prompt reads are billed at the lower rate and explain why the 65-leaf run's input cost scaled sub-linearly with the 10-leaf run.
- This table does not yet account for container build time (which is a compute-minutes / electricity concern, not an API spend concern). The smoke sandbox built in ~1 min; the `squidpy_spatial` scientific image (scanpy + squidpy + spatialdata via `uv`) built in ~21 min on first build and is amortized across all subsequent runs against that paper.
