# Examples

Sanitized snapshots of SciReplicBench runs. Each file is a reduced, path-redacted summary of an Inspect `.eval` log so reviewers can see concrete evidence of the pipeline without needing to rerun it locally.

## Files

| File | What it is |
|---|---|
| [`squidpy_smoke_run.json`](squidpy_smoke_run.json) | End-to-end smoke run on the `squidpy_spatial` rubric against the smoke sandbox. `rubric_tree_scorer` grades all 65 leaves via a `gpt-4o-mini` judge; overall score is 0.000 because the smoke sandbox has no scientific Python stack and the agent cannot produce a real submission. Includes five example leaf judgements with structured evidence quotes. |

## Producing new examples

```bash
python - <<'PY'
import json, subprocess
from pathlib import Path
LOG = "logs-smoke/<run>.eval"
raw = subprocess.check_output(["python", "-m", "inspect_ai", "log", "dump", LOG])
summary = {...}  # redact absolute paths, extract fields of interest
Path("examples/<name>.json").write_text(json.dumps(summary, indent=2))
PY
```

Raw `.eval` files live under `logs-smoke/` (gitignored) and are reproducible by re-running the invocations documented in [`../reports/evaluation_report.md`](../reports/evaluation_report.md).
