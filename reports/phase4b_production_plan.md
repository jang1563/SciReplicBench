# Run Plan

| Phase | Paper | Gate | Lane | Agent | Judge | Seed | Cost Limit |
|---|---|---|---|---|---|---:|---:|
| phase4b_production | inspiration4_multiome | blocked | enablement | gpt-4o | o3-mini | 1 | 6.00 |
| phase4b_production | inspiration4_multiome | blocked | enablement | gpt-4o | o3-mini | 2 | 6.00 |
| phase4b_production | inspiration4_multiome | blocked | enablement | gpt-4o | o3-mini | 3 | 6.00 |
| phase4b_production | inspiration4_multiome | blocked | enablement | claude-sonnet-4-6 | o3-mini | 1 | 6.00 |
| phase4b_production | inspiration4_multiome | blocked | enablement | claude-sonnet-4-6 | o3-mini | 2 | 6.00 |
| phase4b_production | inspiration4_multiome | blocked | enablement | claude-sonnet-4-6 | o3-mini | 3 | 6.00 |
| phase4b_production | squidpy_spatial | blocked | evaluation | gpt-4o | o3-mini | 1 | 6.00 |
| phase4b_production | squidpy_spatial | blocked | evaluation | gpt-4o | o3-mini | 2 | 6.00 |
| phase4b_production | squidpy_spatial | blocked | evaluation | gpt-4o | o3-mini | 3 | 6.00 |
| phase4b_production | squidpy_spatial | blocked | evaluation | claude-sonnet-4-6 | o3-mini | 1 | 6.00 |
| phase4b_production | squidpy_spatial | blocked | evaluation | claude-sonnet-4-6 | o3-mini | 2 | 6.00 |
| phase4b_production | squidpy_spatial | blocked | evaluation | claude-sonnet-4-6 | o3-mini | 3 | 6.00 |
| phase4b_production | genelab_benchmark | blocked | evaluation | gpt-4o | o3-mini | 1 | 6.00 |
| phase4b_production | genelab_benchmark | blocked | evaluation | gpt-4o | o3-mini | 2 | 6.00 |
| phase4b_production | genelab_benchmark | blocked | evaluation | gpt-4o | o3-mini | 3 | 6.00 |
| phase4b_production | genelab_benchmark | blocked | evaluation | claude-sonnet-4-6 | o3-mini | 1 | 6.00 |
| phase4b_production | genelab_benchmark | blocked | evaluation | claude-sonnet-4-6 | o3-mini | 2 | 6.00 |
| phase4b_production | genelab_benchmark | blocked | evaluation | claude-sonnet-4-6 | o3-mini | 3 | 6.00 |

## Blocking Reasons

| Phase | Paper | Lane | Reasons |
|---|---|---|---|
| phase4b_production | inspiration4_multiome | enablement | judge reliability panel still has only one human rater per item<br>hidden reference is still pending benchmark-author fill-in<br>code_development_reference.json is missing<br>execution_reference.json is missing<br>result_match_reference.json is missing<br>benchmark-ready AnnData or MuData object is not staged under papers/inspiration4_multiome/data/cache |
| phase4b_production | squidpy_spatial | evaluation | judge reliability panel still has only one human rater per item |
| phase4b_production | genelab_benchmark | evaluation | judge reliability panel still has only one human rater per item<br>hidden reference is still pending benchmark-author fill-in<br>code_development_reference.json is missing<br>execution_reference.json is missing<br>result_match_reference.json is missing |
