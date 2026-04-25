from __future__ import annotations

import json
import unittest

from scireplicbench.probes import (
    PROBE_CODE_QUOTE,
    PROBE_CONTROL_SAMPLE_ID,
    PROBE_EXECUTION_QUOTE,
    PROBE_FAIL_SAMPLE_ID,
    PROBE_README_QUOTE,
    PROBE_RESULT_QUOTE,
    PROBE_SMOKE_COMPOSE,
    SQUIDPY_AGENT_PROBE_DEFAULT_MODEL,
    SQUIDPY_EXECUTION_INVALID_QUOTE,
    SQUIDPY_EXECUTION_VALID_QUOTE,
    SQUIDPY_PROBE_COMPOSE,
    SQUIDPY_PROBE_CONTROL_SAMPLE_ID,
    SQUIDPY_PROBE_FAIL_SAMPLE_ID,
    SQUIDPY_RESULT_QUOTE,
    SQUIDPY_SEGMENTATION_CODE_QUOTE,
    SQUIDPY_SEGMENTATION_README_QUOTE,
    SQUIDPY_TARGET_LEAF_IDS,
    _probe_case,
    _squidpy_agent_probe_dataset,
    _squidpy_agent_probe_input,
    _squidpy_segmentation_readme_variants,
    _squidpy_probe_case,
    evidence_policy_probe,
    mock_probe_judge_completion,
    mock_squidpy_probe_judge_completion,
    squidpy_evidence_policy_agent_probe,
    squidpy_evidence_policy_probe,
)


class ProbeArtifactsTest(unittest.TestCase):
    def test_probe_fail_case_has_nontrivial_code_and_empty_output(self) -> None:
        case = _probe_case(PROBE_FAIL_SAMPLE_ID)
        self.assertIn("/workspace/submission/pipeline.py", case.artifact_map)
        self.assertIn("def stage_only_pipeline", case.artifact_map["/workspace/submission/pipeline.py"])
        self.assertIn(PROBE_RESULT_QUOTE, case.artifact_map["/workspace/submission/pipeline.py"])
        self.assertEqual(case.artifact_map["/workspace/output/agent/results.txt"], "")

    def test_probe_control_case_has_valid_output_evidence(self) -> None:
        case = _probe_case(PROBE_CONTROL_SAMPLE_ID)
        self.assertIn(PROBE_CODE_QUOTE, case.artifact_map["/workspace/submission/pipeline.py"])
        self.assertIn(PROBE_EXECUTION_QUOTE, case.artifact_map["/workspace/output/agent/results.log"])
        self.assertIn(PROBE_RESULT_QUOTE, case.artifact_map["/workspace/output/agent/metrics.txt"])

    def test_squidpy_probe_fail_case_has_real_paper_artifacts(self) -> None:
        case = _squidpy_probe_case(SQUIDPY_PROBE_FAIL_SAMPLE_ID)
        self.assertIn(SQUIDPY_SEGMENTATION_README_QUOTE, case.artifact_map["/workspace/submission/README.md"])
        self.assertIn("def stage_visium_probe", case.artifact_map["/workspace/submission/pipeline.py"])
        self.assertIn(SQUIDPY_RESULT_QUOTE, case.artifact_map["/workspace/submission/pipeline.py"])
        self.assertEqual(case.artifact_map[SQUIDPY_EXECUTION_INVALID_QUOTE], "")

    def test_squidpy_probe_control_case_has_valid_target_evidence(self) -> None:
        case = _squidpy_probe_case(SQUIDPY_PROBE_CONTROL_SAMPLE_ID)
        self.assertIn(SQUIDPY_SEGMENTATION_CODE_QUOTE, case.artifact_map["/workspace/submission/pipeline.py"])
        self.assertIn("sq.datasets.visium_hne_adata()", case.artifact_map["/workspace/output/agent/run.log"])
        self.assertIn(SQUIDPY_EXECUTION_VALID_QUOTE, case.artifact_map["/workspace/output/agent/run.log"])
        self.assertIn(SQUIDPY_RESULT_QUOTE, case.artifact_map["/workspace/output/agent/geary_metrics.txt"])

    def test_squidpy_agent_probe_input_includes_exact_contract_markers(self) -> None:
        fail_prompt = _squidpy_agent_probe_input(SQUIDPY_PROBE_FAIL_SAMPLE_ID)
        self.assertIn(SQUIDPY_SEGMENTATION_README_QUOTE, fail_prompt)
        self.assertIn("byte-for-byte", fail_prompt)
        self.assertIn("cat <<'EOF' > /workspace/submission/pipeline.py", fail_prompt)
        self.assertIn("Do not use `echo` with escaped `\\n` sequences", fail_prompt)
        self.assertIn("overrides the broader paper-bundle outputs", fail_prompt)
        self.assertIn("roughly 60 lines or fewer", fail_prompt)
        self.assertIn("exact standalone comment line `# geary_top20_rbo=0.90`", fail_prompt)
        self.assertIn("do not add spaces around the equals sign", fail_prompt)
        self.assertIn("skip bundle or data-directory reads unless file creation itself is blocked", fail_prompt)
        self.assertIn("run one bash verification command", fail_prompt)
        self.assertIn("shows the required files exist on disk", fail_prompt)
        self.assertIn(SQUIDPY_RESULT_QUOTE, fail_prompt)

        control_prompt = _squidpy_agent_probe_input(SQUIDPY_PROBE_CONTROL_SAMPLE_ID)
        self.assertIn(SQUIDPY_SEGMENTATION_CODE_QUOTE, control_prompt)
        self.assertIn("sq.datasets.visium_hne_adata()", control_prompt)
        self.assertIn(SQUIDPY_EXECUTION_VALID_QUOTE, control_prompt)
        self.assertIn("cat <<'EOF' > /workspace/submission/pipeline.py", control_prompt)
        self.assertIn("Do not repeat the exact run-log line", control_prompt)
        self.assertIn("run one bash verification command", control_prompt)
        self.assertIn("/workspace/output/agent/geary_metrics.txt", control_prompt)
        self.assertIn("rewrite the file and verify again", control_prompt)

    def test_squidpy_segmentation_readme_variants_include_single_quote_form(self) -> None:
        variants = _squidpy_segmentation_readme_variants()
        self.assertIn(SQUIDPY_SEGMENTATION_README_QUOTE, variants)
        self.assertIn(
            SQUIDPY_SEGMENTATION_README_QUOTE.replace(
                'features="segmentation"', "features='segmentation'"
            ),
            variants,
        )


class ProbeJudgeTest(unittest.TestCase):
    def test_mock_probe_judge_returns_prose_fail_payload(self) -> None:
        prompt = (
            "Leaf metadata:\n"
            "- leaf_id: evidence_policy_probe/code_development/implements_pipeline\n\n"
            "Observed reality:\n"
            f"{PROBE_README_QUOTE}\n"
        )
        payload = json.loads(mock_probe_judge_completion(prompt))
        self.assertEqual(payload["leaf_id"], "evidence_policy_probe/code_development/implements_pipeline")
        self.assertEqual(payload["evidence_quote"], PROBE_README_QUOTE)
        self.assertEqual(payload["score"], 1)

    def test_mock_probe_judge_returns_control_payload(self) -> None:
        prompt = (
            "Leaf metadata:\n"
            "- leaf_id: evidence_policy_probe/execution/runtime_completed\n\n"
            "Observed reality:\n"
            f"{PROBE_CODE_QUOTE}\n"
        )
        payload = json.loads(mock_probe_judge_completion(prompt))
        self.assertEqual(payload["leaf_id"], "evidence_policy_probe/execution/runtime_completed")
        self.assertEqual(payload["evidence_quote"], PROBE_EXECUTION_QUOTE)
        self.assertEqual(payload["score"], 1)

    def test_mock_squidpy_probe_judge_returns_targeted_pass_payload(self) -> None:
        prompt = (
            "Leaf metadata:\n"
            f"- leaf_id: {SQUIDPY_TARGET_LEAF_IDS[0]}\n\n"
            "Observed reality:\n"
            f"{SQUIDPY_SEGMENTATION_README_QUOTE}\n"
        )
        payload = json.loads(mock_squidpy_probe_judge_completion(prompt))
        self.assertEqual(payload["leaf_id"], SQUIDPY_TARGET_LEAF_IDS[0])
        self.assertEqual(payload["evidence_quote"], SQUIDPY_SEGMENTATION_README_QUOTE)
        self.assertEqual(payload["score"], 1)

    def test_mock_squidpy_probe_judge_accepts_single_quote_readme_variant(self) -> None:
        single_quote_variant = SQUIDPY_SEGMENTATION_README_QUOTE.replace(
            'features="segmentation"', "features='segmentation'"
        )
        prompt = (
            "Leaf metadata:\n"
            f"- leaf_id: {SQUIDPY_TARGET_LEAF_IDS[0]}\n\n"
            "Observed reality:\n"
            f"{single_quote_variant}\n"
        )
        payload = json.loads(mock_squidpy_probe_judge_completion(prompt))
        self.assertEqual(payload["leaf_id"], SQUIDPY_TARGET_LEAF_IDS[0])
        self.assertEqual(payload["evidence_quote"], single_quote_variant)
        self.assertEqual(payload["score"], 1)

    def test_mock_squidpy_probe_judge_returns_default_fail_for_non_target_leaf(self) -> None:
        prompt = (
            "Leaf metadata:\n"
            "- leaf_id: squidpy_spatial/code_development/datasets_and_containers/load_visium_dataset\n\n"
            "Observed reality:\n"
            "/workspace/submission/pipeline.py\n"
        )
        payload = json.loads(mock_squidpy_probe_judge_completion(prompt))
        self.assertEqual(payload["score"], 0)
        self.assertEqual(payload["evidence_quote"], "/workspace/submission/pipeline.py")


class ProbeTaskTest(unittest.TestCase):
    def test_evidence_policy_probe_task_uses_smoke_sandbox(self) -> None:
        task = evidence_policy_probe()
        sample_ids = [sample.id for sample in task.dataset]
        self.assertEqual(sample_ids, [PROBE_FAIL_SAMPLE_ID, PROBE_CONTROL_SAMPLE_ID])
        self.assertEqual(getattr(task.sandbox, "type", None), "docker")
        self.assertEqual(getattr(task.sandbox, "config", None), str(PROBE_SMOKE_COMPOSE))
        self.assertEqual(task.message_limit, 4)
        self.assertEqual(task.time_limit, 300)
        self.assertEqual(task.working_limit, 300)

        scorer = task.scorer
        self.assertIsInstance(scorer, list)
        self.assertEqual(len(scorer), 1)
        self.assertEqual(getattr(scorer[0], "__name__", ""), "score")

    def test_squidpy_evidence_policy_probe_task_uses_real_paper_bundle(self) -> None:
        task = squidpy_evidence_policy_probe()
        sample_ids = [sample.id for sample in task.dataset]
        self.assertEqual(sample_ids, [SQUIDPY_PROBE_FAIL_SAMPLE_ID, SQUIDPY_PROBE_CONTROL_SAMPLE_ID])
        self.assertEqual(getattr(task.sandbox, "type", None), "docker")
        self.assertEqual(getattr(task.sandbox, "config", None), str(SQUIDPY_PROBE_COMPOSE))
        self.assertEqual(task.message_limit, 4)
        self.assertEqual(task.time_limit, 600)
        self.assertEqual(task.working_limit, 600)
        for sample in task.dataset:
            self.assertEqual((sample.metadata or {}).get("paper_id"), "squidpy_spatial")

    def test_squidpy_agent_probe_dataset_appends_authoring_contract(self) -> None:
        dataset = _squidpy_agent_probe_dataset()
        self.assertEqual([sample.id for sample in dataset], [SQUIDPY_PROBE_FAIL_SAMPLE_ID, SQUIDPY_PROBE_CONTROL_SAMPLE_ID])
        self.assertIn("Probe authoring contract", dataset[0].input)
        self.assertIn("do not spend more than one turn on context gathering", dataset[0].input)
        self.assertIn("Skip bundle inspection unless file creation or path discovery is actually blocked", dataset[0].input)
        self.assertIn("copy it byte-for-byte", dataset[0].input)
        self.assertIn("overrides the broader paper-bundle outputs", dataset[0].input)
        self.assertIn("prefer a bash heredoc", dataset[0].input)
        self.assertIn("Keep authored files compact", dataset[0].input)
        self.assertIn("Only files written to disk count", dataset[0].input)
        self.assertIn("run a final bash verification step", dataset[0].input)
        self.assertIn(SQUIDPY_SEGMENTATION_README_QUOTE, dataset[0].input)
        self.assertIn(SQUIDPY_SEGMENTATION_CODE_QUOTE, dataset[1].input)

    def test_squidpy_agent_probe_task_uses_react_solver_and_real_image(self) -> None:
        task = squidpy_evidence_policy_agent_probe()
        self.assertEqual(getattr(task.sandbox, "type", None), "docker")
        self.assertEqual(getattr(task.sandbox, "config", None), str(SQUIDPY_PROBE_COMPOSE))
        self.assertEqual(task.message_limit, 20)
        self.assertEqual(task.time_limit, 900)
        self.assertEqual(task.working_limit, 900)
        self.assertEqual(SQUIDPY_AGENT_PROBE_DEFAULT_MODEL, "openai/gpt-4o-mini")

    def test_squidpy_agent_probe_task_accepts_custom_judge_model(self) -> None:
        task = squidpy_evidence_policy_agent_probe(judge_model="openai/gpt-4o-mini")
        self.assertEqual(getattr(task.sandbox, "type", None), "docker")
        self.assertEqual(getattr(task.sandbox, "config", None), str(SQUIDPY_PROBE_COMPOSE))
        self.assertEqual(task.message_limit, 20)
        self.assertEqual(task.time_limit, 900)
        self.assertEqual(task.working_limit, 900)
