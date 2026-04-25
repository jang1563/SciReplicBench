# Examples

Sanitized snapshots of SciReplicBench runs. Each file is a reduced, path-redacted summary of an Inspect `.eval` log so reviewers can see concrete evidence of the pipeline without needing to rerun it locally.

## Files

| File | What it is |
|---|---|
| [`squidpy_smoke_run.json`](squidpy_smoke_run.json) | End-to-end smoke run on the `squidpy_spatial` rubric against the smoke sandbox. `rubric_tree_scorer` grades all 65 leaves via a `gpt-4o-mini` judge; overall score is 0.000 because the smoke sandbox has no scientific Python stack and the agent cannot produce a real submission. Includes five example leaf judgements with structured evidence quotes. |
| [`squidpy_production_run.json`](squidpy_production_run.json) | End-to-end production run on the `squidpy_spatial` rubric against the real scientific image (scanpy 1.10.1 + squidpy 1.6.0). Same `gpt-4o-mini` agent + judge, 40-message budget. Overall score 0.028 with 2/65 leaves passing; includes the two passing leaves (both judge-lenience cases grading README text) and three representative failing leaves to show the scorer's evidence-quote trail. |
| [`squidpy_production_run_haiku.json`](squidpy_production_run_haiku.json) | Same benchmark as above but with `anthropic/claude-haiku-4-5` as the agent and `gpt-4o-mini` as the judge. Overall score 0.000; agent spent its budget trying to import Squidpy and hit a zarr v3 API incompatibility inside the sandbox. No README scaffold was produced, so there was no false-positive surface for the judge to grade. |
| [`squidpy_production_run_sonnet.json`](squidpy_production_run_sonnet.json) | Same benchmark with `anthropic/claude-sonnet-4-6` as the agent and `gpt-4o-mini` as the judge. Overall score 0.000; agent spent its budget diagnosing a `pkg_resources` import issue. The three-model delta (gpt-4o-mini 0.028 > Claude Haiku/Sonnet 0.000) is a direct, reproducible illustration of judge-lenience on scaffold-shaped submissions — see [../reports/failure_taxonomy.md](../reports/failure_taxonomy.md) mode 2. |
| [`squidpy_production_run_v0_2_gpt4o_mini.json`](squidpy_production_run_v0_2_gpt4o_mini.json) | v0.2 rerun of the `gpt-4o-mini` production sample with the artifact-presence precheck active. The precheck fails, `leaves_graded` drops to 0, and the judge is skipped entirely; this is the after-fix counterpart to `squidpy_production_run.json`. |
| [`squidpy_production_run_v0_2_haiku.json`](squidpy_production_run_v0_2_haiku.json) | v0.2 rerun of the `claude-haiku-4-5` production sample. Same paper, image, and budget as the v0.1 example, but now the summary includes top-level `precheck` metadata showing why leaf grading was bypassed. |
| [`squidpy_production_run_v0_2_sonnet.json`](squidpy_production_run_v0_2_sonnet.json) | v0.2 rerun of the `claude-sonnet-4-6` production sample. Use this alongside the v0.1 Sonnet example to see the difference between "judge read the submission and returned 65 zeros" and "precheck failed before judge invocation." |
| [`squidpy_production_run_v0_3_gpt4o_mini.json`](squidpy_production_run_v0_3_gpt4o_mini.json) | April 16, 2026 v0.3 rerun of the `gpt-4o-mini` production sample after per-leaf evidence hardening shipped. This live run still fails the task-level precheck, so the new `evidence_policy_failed` path never activates. |
| [`squidpy_production_run_v0_3_haiku.json`](squidpy_production_run_v0_3_haiku.json) | April 16, 2026 v0.3 rerun of the `claude-haiku-4-5` production sample. Same paper, image, and budget as the v0.2 example; the benchmark-visible outcome remains `leaves_graded = 0` because the precheck still fires first. |
| [`squidpy_production_run_v0_3_sonnet.json`](squidpy_production_run_v0_3_sonnet.json) | April 16, 2026 v0.3 rerun of the `claude-sonnet-4-6` production sample. Useful as evidence that the v0.3 scorer/judge hardening shipped, but not yet as proof of live leaf-level policy activation. |
| [`evidence_policy_probe_v0_4.json`](evidence_policy_probe_v0_4.json) | April 16, 2026 v0.4 live Inspect probe. This deterministic internal harness runs two samples through the real smoke-sandbox task/scorer path: one precheck-passing prose trap that is zeroed with `evidence_policy_failed`, and one matched control that scores 1.000. |
| [`squidpy_evidence_policy_probe_v0_5.json`](squidpy_evidence_policy_probe_v0_5.json) | April 16, 2026 v0.5 live Squidpy-paper probe. Uses the real `squidpy_spatial` paper bundle, full 65-leaf rubric, and scientific Docker image, but with a deterministic solver plus local mock judge, to prove the exact historical false-positive leaf types now flip the right way once precheck succeeds. |
| [`squidpy_evidence_policy_agent_probe_v0_6.json`](squidpy_evidence_policy_agent_probe_v0_6.json) | April 16, 2026 v0.6 live frontier-agent Squidpy-paper probe. Uses the same real `squidpy_spatial` paper bundle and scientific image as v0.5, but replaces the deterministic solver with a frontier `gpt-4o-mini` agent while keeping the local mock judge deterministic. |
| [`squidpy_evidence_policy_agent_probe_v0_9.json`](squidpy_evidence_policy_agent_probe_v0_9.json) | April 17, 2026 v0.9 stabilized frontier-agent Squidpy-paper probe. Same real `squidpy_spatial` package as v0.6, but with heredoc-oriented authoring guidance that makes both arms clear precheck and makes the fail arm trigger the exact intended README/path/result evidence-policy reasons. |
| [`squidpy_evidence_policy_agent_probe_v1_1.json`](squidpy_evidence_policy_agent_probe_v1_1.json) | April 17, 2026 v1.1 cross-model frontier-agent Squidpy-paper probe for `gpt-4o-mini`. Tightens the probe contract further and includes the execution-manifest loophole fix that was surfaced during the v1.0 Sonnet generalization pass. |
| [`squidpy_evidence_policy_agent_probe_v1_1_sonnet.json`](squidpy_evidence_policy_agent_probe_v1_1_sonnet.json) | April 17, 2026 v1.1 cross-model frontier-agent Squidpy-paper probe for `claude-sonnet-4-6`. It matches the `gpt-4o-mini` v1.1 behavior exactly: fail arm at 0.000 with the same three policy reasons, control arm at 0.045 with the same three surviving leaves. |
| [`squidpy_evidence_policy_agent_probe_v1_2.json`](squidpy_evidence_policy_agent_probe_v1_2.json) | April 17, 2026 v1.2 three-model frontier-agent Squidpy-paper probe for `gpt-4o-mini`. This is the promoted successor to v1.1 and uses the stronger "contract is sufficient; skip bundle inspection unless blocked" guidance. |
| [`squidpy_evidence_policy_agent_probe_v1_2_sonnet.json`](squidpy_evidence_policy_agent_probe_v1_2_sonnet.json) | April 17, 2026 v1.2 three-model frontier-agent Squidpy-paper probe for `claude-sonnet-4-6`. It preserves the same clean fail/control split as v1.1 under the tighter contract. |
| [`squidpy_evidence_policy_agent_probe_v1_2_haiku.json`](squidpy_evidence_policy_agent_probe_v1_2_haiku.json) | April 17, 2026 v1.2 three-model frontier-agent Squidpy-paper probe for `claude-haiku-4-5`. It is the first stabilized Haiku run where both arms pass precheck and match the exact intended fail/control pattern. |
| [`squidpy_evidence_policy_agent_probe_v1_2_judge_gpt4o_mini.json`](squidpy_evidence_policy_agent_probe_v1_2_judge_gpt4o_mini.json) | April 17, 2026 live-judge extension of the v1.2 probe using `openai/gpt-4o-mini` as the judge. Useful mainly as a negative result: it proves the non-mock path works, but under-credits the control arm and emits one parse-level `judge_error`. |
| [`squidpy_evidence_policy_agent_probe_v1_2_judge_o3_mini.json`](squidpy_evidence_policy_agent_probe_v1_2_judge_o3_mini.json) | April 17, 2026 live-judge extension of the v1.2 probe using `openai/o3-mini` as the judge. It preserves all three targeted control leaves, but broadens the control score beyond the intended three-leaf envelope, so it is evidence of judge-calibration drift rather than a promoted replacement for the mock baseline. |
| [`squidpy_evidence_policy_agent_probe_v1_2_judge_o3_mini_calibrated.json`](squidpy_evidence_policy_agent_probe_v1_2_judge_o3_mini_calibrated.json) | April 17, 2026 calibrated `openai/o3-mini` live-judge rerun after exact-leaf prompt guardrails and one retry for malformed judge outputs were added. This collapses the broad overpass set and brings the mean score back to the v1.2 mock-baseline level. |
| [`squidpy_evidence_policy_agent_probe_v1_2_execution_clarified.json`](squidpy_evidence_policy_agent_probe_v1_2_execution_clarified.json) | April 17, 2026 mock-judge rerun of the v1.2 probe with sharper control-arm execution evidence. The control run-log now names `sq.datasets.visium_hne_adata()` explicitly, but the intended three-leaf baseline stays unchanged at `overall = 0.045`. |
| [`squidpy_evidence_policy_agent_probe_v1_2_judge_o3_mini_execution_clarified.json`](squidpy_evidence_policy_agent_probe_v1_2_judge_o3_mini_execution_clarified.json) | April 17, 2026 calibrated live-judge follow-up on the execution-clarified control contract. The intended execution leaf now passes under `openai/o3-mini`; the remaining delta is three extra control-arm leaves that appear hand-gradeable rather than broad drift. |
| [`squidpy_evidence_policy_agent_probe_v1_2_judge_o3_mini_execution_clarified_output_guardrail_balance_restored.json`](squidpy_evidence_policy_agent_probe_v1_2_judge_o3_mini_execution_clarified_output_guardrail_balance_restored.json) | April 18, 2026 successful post-fix live rerun after OpenAI balance was restored. It keeps the intended execution leaf, preserves the same overall control score, and removes the old `moran_geary_written` over-credit from the live successor artifact. |

The three `*_v0_2_*.json` files intentionally keep the same paper and production setup as the v0.1 examples so reviewers can compare before vs. after. Each v0.2 summary includes a top-level `precheck` object plus `leaves_graded = 0`, which means the artifact-presence gate fired and the LLM judge was never called.

The three `*_v0_3_*.json` files record the April 16, 2026 reruns after per-leaf evidence hardening was added on top of the v0.2 precheck. On this exact `squidpy_spatial` matrix they remain numerically identical to v0.2 because all three agents still stop at `precheck.ok = false`, so the leaf-level evidence policy is present but not exercised.

[`evidence_policy_probe_v0_4.json`](evidence_policy_probe_v0_4.json) closes that specific runtime gap. It comes from a deterministic internal `evidence_policy_probe` task with a local `mockllm/model` judge, so it proves the benchmark-visible Inspect path rather than public-model capability. The probe is intentionally paired: the prose-trap sample passes precheck and then hard-fails on three evidence-policy reasons, while the control sample passes all three leaves with valid code/output evidence.

[`squidpy_evidence_policy_probe_v0_5.json`](squidpy_evidence_policy_probe_v0_5.json) takes the next step onto the real paper package. It keeps the deterministic harness structure, but swaps in the actual `squidpy_spatial` rubric and scientific image. The summary intentionally shows only the three targeted Squidpy leaves that matter for this probe, while also recording that all 65 leaves were graded per sample.

[`squidpy_evidence_policy_agent_probe_v0_6.json`](squidpy_evidence_policy_agent_probe_v0_6.json) is the first frontier-agent-authored real-paper trace that clears precheck end-to-end. It proves the runtime path, but its fail arm still lands two targeted leaves on verbatim-mismatch rather than the cleaner README/path policy reasons from the deterministic harness.

[`squidpy_evidence_policy_agent_probe_v0_9.json`](squidpy_evidence_policy_agent_probe_v0_9.json) is the stabilized successor. In the April 17, 2026 rerun, both samples pass precheck; the fail arm lands at `overall = 0.000` with the exact three intended evidence-policy reasons, while the matched control preserves the same three targeted leaves and lands at `overall = 0.045`. As with v0.5 and v0.6, the summary intentionally shows only the three targeted Squidpy leaves while recording that all 65 leaves were graded per sample.

[`squidpy_evidence_policy_agent_probe_v1_1.json`](squidpy_evidence_policy_agent_probe_v1_1.json) and [`squidpy_evidence_policy_agent_probe_v1_1_sonnet.json`](squidpy_evidence_policy_agent_probe_v1_1_sonnet.json) extended that proof across two frontier authoring models. The intermediate v1.0 Sonnet rerun exposed a real scorer loophole where a bare output path could still pass if it reappeared inside an output-side manifest; v1.1 closed that loophole and landed the same fail/control pattern for both `gpt-4o-mini` and Sonnet.

[`squidpy_evidence_policy_agent_probe_v1_2.json`](squidpy_evidence_policy_agent_probe_v1_2.json), [`squidpy_evidence_policy_agent_probe_v1_2_sonnet.json`](squidpy_evidence_policy_agent_probe_v1_2_sonnet.json), and [`squidpy_evidence_policy_agent_probe_v1_2_haiku.json`](squidpy_evidence_policy_agent_probe_v1_2_haiku.json) are the promoted three-model successor. The first Haiku cross-model attempt showed a prompt-robustness issue rather than a scorer issue: Haiku kept burning budget on unnecessary bundle inspection and lost the control arm's output evidence. v1.2 makes the authoring contract explicitly sufficient and tells the model to skip bundle or data-directory reads unless file creation is actually blocked, which brings all three models onto the same clean fail/control pattern.

[`squidpy_evidence_policy_agent_probe_v1_2_judge_gpt4o_mini.json`](squidpy_evidence_policy_agent_probe_v1_2_judge_gpt4o_mini.json) and [`squidpy_evidence_policy_agent_probe_v1_2_judge_o3_mini.json`](squidpy_evidence_policy_agent_probe_v1_2_judge_o3_mini.json) are the first non-mock-judge extensions of that stabilized harness. They matter because they prove the same probe can run end-to-end without mocking the judge, but they are not promoted replacements for the mock baseline yet. `gpt-4o-mini` under-credits the control sample and produces a parse-level failure; `o3-mini` preserves the three targeted control leaves but over-expands the control score, which makes judge calibration the next project bottleneck.

[`squidpy_evidence_policy_agent_probe_v1_2_judge_o3_mini_calibrated.json`](squidpy_evidence_policy_agent_probe_v1_2_judge_o3_mini_calibrated.json) is the first calibrated live-judge candidate that gets back to the v1.2 baseline mean. It removed the broad overpass set, but it still under-credited the intended execution leaf.

[`squidpy_evidence_policy_agent_probe_v1_2_execution_clarified.json`](squidpy_evidence_policy_agent_probe_v1_2_execution_clarified.json) and [`squidpy_evidence_policy_agent_probe_v1_2_judge_o3_mini_execution_clarified.json`](squidpy_evidence_policy_agent_probe_v1_2_judge_o3_mini_execution_clarified.json) are the follow-up pair that sharpens that specific control-arm ambiguity. The mock rerun proves the contract change does not disturb the intended three-leaf baseline. The first live `o3-mini` rerun then preserves the intended execution leaf too, while additionally crediting `load_visium_dataset`, `compute_image_features`, and `moran_geary_written`.

[`squidpy_evidence_policy_agent_probe_v1_2_judge_o3_mini_execution_clarified_output_guardrail_balance_restored.json`](squidpy_evidence_policy_agent_probe_v1_2_judge_o3_mini_execution_clarified_output_guardrail_balance_restored.json) is the successful post-fix live successor after the quota-blocked retries. It keeps the intended execution leaf, still lands at `overall = 0.087`, but no longer credits `moran_geary_written`. The remaining sixth pass is `join_image_features_to_adata`, which is a cleaner code-side interpretation of the Squidpy call than the old hidden-reference-metric over-credit.

## Producing new examples

```bash
python - <<'PY'
import json, subprocess
from pathlib import Path
LOG = "logs-prod/<run>.eval"  # or logs-smoke/<run>.eval
raw = subprocess.check_output(["python", "-m", "inspect_ai", "log", "dump", LOG])
summary = {...}  # redact absolute paths, extract fields of interest
Path("examples/<name>.json").write_text(json.dumps(summary, indent=2))
PY
```

Raw `.eval` files live under `logs-smoke/` and `logs-prod/` (both gitignored) and are reproducible by re-running the invocations documented in [`../reports/evaluation_report.md`](../reports/evaluation_report.md).

The v0.4 probe example is reproduced directly by:

```bash
.venv/bin/python scripts/run_evidence_policy_probe.py
```

The v0.5 Squidpy-paper probe is reproduced directly by:

```bash
.venv/bin/python scripts/run_evidence_policy_probe.py --probe squidpy
```

The v1.2 frontier-agent Squidpy-paper probe for `gpt-4o-mini` is reproduced directly by:

```bash
.venv/bin/python scripts/run_evidence_policy_probe.py --probe squidpy-agent --model openai/gpt-4o-mini
```

The matching Sonnet v1.2 artifact is reproduced directly by:

```bash
.venv/bin/python scripts/run_evidence_policy_probe.py --probe squidpy-agent --model anthropic/claude-sonnet-4-6 --artifact-label sonnet
```

The matching Haiku v1.2 artifact is reproduced directly by:

```bash
.venv/bin/python scripts/run_evidence_policy_probe.py --probe squidpy-agent --model anthropic/claude-haiku-4-5 --artifact-label haiku
```

The live-judge extension with `openai/gpt-4o-mini` as the judge is reproduced by:

```bash
.venv/bin/python scripts/run_evidence_policy_probe.py --probe squidpy-agent --model openai/gpt-4o-mini --judge-model openai/gpt-4o-mini --artifact-label judge_gpt4o_mini
```

The stronger live-judge extension with `openai/o3-mini` is reproduced by:

```bash
.venv/bin/python scripts/run_evidence_policy_probe.py --probe squidpy-agent --model openai/gpt-4o-mini --judge-model openai/o3-mini --artifact-label judge_o3_mini
```

The calibrated `openai/o3-mini` live-judge rerun is reproduced by:

```bash
.venv/bin/python scripts/run_evidence_policy_probe.py --probe squidpy-agent --model openai/gpt-4o-mini --judge-model openai/o3-mini --artifact-label judge_o3_mini_calibrated
```

The execution-clarified mock follow-up is reproduced by:

```bash
.venv/bin/python scripts/run_evidence_policy_probe.py --probe squidpy-agent --model openai/gpt-4o-mini --artifact-label execution_clarified
```

The execution-clarified live `o3-mini` follow-up is reproduced by:

```bash
.venv/bin/python scripts/run_evidence_policy_probe.py --probe squidpy-agent --model openai/gpt-4o-mini --judge-model openai/o3-mini --artifact-label judge_o3_mini_execution_clarified
```
