from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import patch

from scireplicbench import tasks
from scireplicbench.tasks import (
    COMPOSE_FILE,
    COMPOSE_OVERRIDE_ENV,
    ENV_VARIANT_ENV,
    _paper_bundle_file_map,
    _paper_task,
    build_sample_input,
    compose_file_for_paper,
    load_task_records,
    record_to_sample,
)


class TaskConfigTest(unittest.TestCase):
    def test_compose_file_for_known_paper_uses_paper_specific_file(self) -> None:
        compose_file = compose_file_for_paper("squidpy_spatial")
        self.assertEqual(compose_file.name, "compose.squidpy_spatial.yaml")
        self.assertTrue(compose_file.exists())

    def test_compose_file_for_unknown_paper_falls_back_to_default(self) -> None:
        compose_file = compose_file_for_paper("unknown_paper")
        self.assertEqual(compose_file, COMPOSE_FILE)
        self.assertEqual(compose_file, Path(COMPOSE_FILE))

    def test_compose_file_variant_uses_smoke_compose(self) -> None:
        with patch.dict(os.environ, {ENV_VARIANT_ENV: "smoke"}, clear=False):
            compose_file = compose_file_for_paper("squidpy_spatial")
        self.assertEqual(compose_file.name, "compose.smoke.yaml")
        self.assertTrue(compose_file.exists())

    def test_compose_file_override_uses_explicit_path(self) -> None:
        override = "environments/compose.smoke.yaml"
        with patch.dict(os.environ, {COMPOSE_OVERRIDE_ENV: override}, clear=False):
            compose_file = compose_file_for_paper("squidpy_spatial")
        self.assertEqual(compose_file.resolve(), (Path(COMPOSE_FILE).parent / "compose.smoke.yaml").resolve())

    def test_build_sample_input_mentions_workspace_text_file(self) -> None:
        record = load_task_records("genelab_benchmark")[0]
        prompt = build_sample_input(record)
        self.assertIn("workspace_text_file", prompt)
        self.assertIn("/workspace/input/paper_bundle/starter/main_analysis.py", prompt)
        self.assertIn("/workspace/submission", prompt)
        self.assertIn("already seeded under `/workspace/submission`", prompt)
        self.assertIn("Keep the seeded `/workspace/submission/run.sh` launcher intact", prompt)
        self.assertIn("primary-script timeout", prompt)
        self.assertIn("run `bash /workspace/submission/run.sh` as the canonical saved workflow", prompt)
        self.assertIn("may reject attempts to overwrite the seeded GeneLab `run.sh`", prompt)
        self.assertIn("Do not replace the runnable GeneLab baseline", prompt)

    def test_paper_bundle_file_map_excludes_irrelevant_genelab_artifacts(self) -> None:
        file_map = _paper_bundle_file_map("genelab_benchmark")
        self.assertTrue(file_map)
        self.assertFalse(
            any("/.git/" in sandbox_path for sandbox_path in file_map),
            msg="Nested VCS internals should not be staged into the sandbox",
        )
        self.assertFalse(
            any("/__pycache__/" in sandbox_path or sandbox_path.endswith(".pyc") for sandbox_path in file_map),
            msg="Python bytecode caches should not be staged into the sandbox",
        )
        self.assertFalse(
            any("/data/huggingface_dataset/v5/" in sandbox_path for sandbox_path in file_map),
            msg="Historical evaluation bundles should not distract the agent",
        )
        self.assertFalse(
            any("/data/raw/GeneLab_benchmark/evaluation/" in sandbox_path for sandbox_path in file_map),
            msg="Historical raw-repo evaluation outputs should be excluded from the sandbox",
        )
        self.assertFalse(
            any("/data/raw/GeneLab_benchmark/processed/" in sandbox_path for sandbox_path in file_map),
            msg="Historical processed outputs should be excluded from the sandbox",
        )
        self.assertFalse(
            any("/data/raw/GeneLab_benchmark/scripts/" in sandbox_path for sandbox_path in file_map),
            msg="Raw-repo reference scripts should stay out of the reviewer-path sandbox",
        )
        self.assertFalse(
            any("/data/raw/GeneLab_benchmark/tasks/B" in sandbox_path for sandbox_path in file_map),
            msg="Cross-mission raw task directories should not be staged for the reviewer path",
        )
        self.assertFalse(
            any(sandbox_path.endswith("/selected_genes.txt") for sandbox_path in file_map),
            msg="Auxiliary selected-gene manifests should stay out of the sandbox",
        )
        self.assertFalse(
            any(sandbox_path.endswith("/fold_info.json") for sandbox_path in file_map),
            msg="Fold-sidecar JSON files should stay out of the sandbox",
        )
        self.assertFalse(
            any(sandbox_path.endswith("/task_info.json") for sandbox_path in file_map),
            msg="Task-sidecar JSON files should stay out of the sandbox",
        )
        self.assertFalse(
            any("/data/raw/GeneLab_benchmark/tasks/A1_liver_lomo/" in sandbox_path for sandbox_path in file_map),
            msg="Raw labels without staged feature matrices should not distract the reviewer path",
        )
        self.assertFalse(
            any("/data/raw/GeneLab_benchmark/tasks/A3_kidney_lomo/" in sandbox_path for sandbox_path in file_map),
            msg="Raw labels without staged feature matrices should not distract the reviewer path",
        )
        self.assertTrue(
            any(
                sandbox_path.endswith(
                    "/data/raw/GeneLab_benchmark/tasks/A2_gastrocnemius_lomo/fold_RR-1_test/train_y.csv"
                )
                for sandbox_path in file_map
            ),
            msg="Reviewer-path labels matching staged feature matrices should remain staged",
        )

    def test_paper_task_wires_workspace_text_file_tool(self) -> None:
        with (
            patch.object(tasks, "Task", side_effect=lambda **kwargs: kwargs),
            patch.object(tasks, "react", return_value="solver") as react_mock,
            patch.object(tasks, "guarded_bash", return_value="bash_tool"),
            patch.object(tasks, "python", return_value="python_tool"),
            patch.object(tasks, "scratchpad", return_value="scratchpad_tool"),
            patch.object(tasks, "workspace_text_file", return_value="workspace_text_tool"),
            patch.object(tasks, "rubric_tree_scorer", return_value="scorer"),
        ):
            _paper_task("genelab_benchmark")

        self.assertEqual(
            react_mock.call_args.kwargs["tools"],
            ["bash_tool", "python_tool", "scratchpad_tool", "workspace_text_tool"],
        )

    def test_record_to_sample_seeds_genelab_submission_from_starter(self) -> None:
        record = load_task_records("genelab_benchmark")[0]
        sample = record_to_sample(record)
        self.assertIn("cp -R /workspace/input/paper_bundle/starter/. /workspace/submission/", sample.setup)
        self.assertIn("chmod 0555 /workspace/submission/run.sh || true", sample.setup)
