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
    STARTER_MODE_ENV,
    _SANDBOX_TYPE_ENV,
    _paper_bundle_file_map,
    _paper_task,
    build_sample_input,
    compose_file_for_paper,
    load_task_records,
    record_to_sample,
)
from scireplicbench.workspace import WORKSPACE_ROOT_ENV


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
        self.assertIn("inspect the concrete generated artifacts", prompt)
        self.assertIn("Do not add an alternate GeneLab driver", prompt)
        self.assertIn("may reject unhooked post-success sidecars", prompt)
        self.assertIn("once that structured manifest exists, leave it intact", prompt)

    def test_squidpy_prompt_names_offline_dataset_cache(self) -> None:
        record = load_task_records("squidpy_spatial")[0]
        prompt = build_sample_input(record)
        self.assertIn("/workspace/input/paper_bundle/data/dataset_manifest.json", prompt)
        self.assertIn("/workspace/input/paper_bundle/data/cache/squidpy_builtin/visium_hne_adata.h5ad", prompt)
        self.assertIn("/workspace/input/paper_bundle/data/cache/squidpy_builtin/visium_hne_image.tiff", prompt)
        self.assertIn("/workspace/input/paper_bundle/data/cache/squidpy_builtin/seqfish.h5ad", prompt)
        self.assertIn("/workspace/input/paper_bundle/data/ligrec_interactions.tsv", prompt)
        self.assertIn("/workspace/output/agent/neighborhood/nhood_enrichment_ranked.tsv", prompt)
        self.assertIn("/workspace/output/agent/neighborhood/centrality_scores.tsv", prompt)
        self.assertIn("/workspace/output/agent/spatial_stats/ripley_curves.tsv", prompt)
        self.assertIn("cluster_labels", prompt)
        self.assertIn("segmentation_feature_count", prompt)
        self.assertIn("cluster_counts", prompt)
        self.assertIn("The sandbox has no network", prompt)
        self.assertIn("/workspace/input/paper_bundle/output_contract.md", prompt)
        self.assertIn("/workspace/input/paper_bundle/starter/main_analysis.py", prompt)
        self.assertIn("already seeded under `/workspace/submission`", prompt)
        self.assertIn("first substantive tool action should be `bash /workspace/submission/run.sh`", prompt)
        self.assertIn("run `bash /workspace/submission/run.sh` as the canonical saved workflow", prompt)
        self.assertIn("inspect `/workspace/output/agent/dataset_manifest.json`", prompt)
        self.assertIn("may reject attempts to overwrite the seeded Squidpy", prompt)
        self.assertIn("result-match-ready Squidpy submission with no non-document output artifacts", prompt)

    def test_squidpy_prepare_script_writes_bundle_cache_paths(self) -> None:
        script = (
            tasks.PROJECT_ROOT
            / "papers"
            / "squidpy_spatial"
            / "data"
            / "prepare_data.sh"
        ).read_text()
        self.assertIn("cache/squidpy_builtin", script)
        self.assertIn('sq.datasets.visium_hne_adata(path=paths["visium_hne_adata"])', script)
        self.assertIn('sq.datasets.visium_hne_image(path=paths["visium_hne_image"])', script)
        self.assertIn('sq.datasets.seqfish(path=paths["seqfish"])', script)
        self.assertIn('"workspace_path"', script)

    def test_squidpy_image_feature_recipe_stays_aligned_across_surfaces(self) -> None:
        with patch.dict(os.environ, {STARTER_MODE_ENV: "off"}, clear=False):
            prompt = build_sample_input(load_task_records("squidpy_spatial")[0])
        paper_dir = tasks.PROJECT_ROOT / "papers" / "squidpy_spatial"
        shared_snippets = [
            'layer_added="segmented_watershed"',
            'features=["histogram", "segmentation", "summary", "texture"]',
            '"histogram": {"channels": [0], "bins": 4}',
            '"label_layer": "segmented_watershed"',
            '"props": ["label", "area", "mean_intensity"]',
            '"summary": {"channels": [0, 1, 2]}',
            '"props": ["contrast", "homogeneity"]',
            '"distances": [1]',
            '"angles": [0]',
        ]
        surfaces = {
            "output_contract": (paper_dir / "output_contract.md").read_text(),
            "starter": (paper_dir / "starter" / "squidpy_spatial_workflow.py").read_text(),
            "reference_generator": (
                tasks.PROJECT_ROOT / "scripts" / "generate_squidpy_reference_outputs.py"
            ).read_text(),
        }
        for surface_name, surface_text in surfaces.items():
            with self.subTest(surface=surface_name):
                for snippet in shared_snippets:
                    self.assertIn(snippet, surface_text)

        prompt_snippets = [
            "sq.im.segment(image, layer='image', method='watershed', channel=0, layer_added='segmented_watershed', copy=False)",
            "features=['histogram', 'segmentation', 'summary', 'texture']",
            "'histogram': {'channels': [0], 'bins': 4}",
            "'segmentation': {'label_layer': 'segmented_watershed', 'props': ['label', 'area', 'mean_intensity'], 'channels': [0]}",
            "'summary': {'channels': [0, 1, 2]}",
            "'texture': {'channels': [0], 'props': ['contrast', 'homogeneity'], 'distances': [1], 'angles': [0]}",
        ]
        for snippet in prompt_snippets:
            self.assertIn(snippet, prompt)

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
        expected_label = (
            tasks.PROJECT_ROOT
            / "papers"
            / "genelab_benchmark"
            / "data"
            / "raw"
            / "GeneLab_benchmark"
            / "tasks"
            / "A2_gastrocnemius_lomo"
            / "fold_RR-1_test"
            / "train_y.csv"
        )
        if expected_label.exists():
            self.assertTrue(
                any(
                    sandbox_path.endswith(
                        "/data/raw/GeneLab_benchmark/tasks/A2_gastrocnemius_lomo/fold_RR-1_test/train_y.csv"
                    )
                    for sandbox_path in file_map
                ),
                msg="Reviewer-path labels matching staged feature matrices should remain staged",
            )

    def test_paper_bundle_file_map_excludes_hidden_reference_outputs(self) -> None:
        file_map = _paper_bundle_file_map("squidpy_spatial")
        self.assertTrue(file_map)
        self.assertTrue(
            any(sandbox_path.endswith("/data/ligrec_interactions.tsv") for sandbox_path in file_map),
            msg="The public custom ligand-receptor panel should be staged for offline Squidpy scoring",
        )
        self.assertTrue(
            any(sandbox_path.endswith("/starter/main_analysis.py") for sandbox_path in file_map),
            msg="The runnable Squidpy starter should be staged into the paper bundle",
        )
        self.assertFalse(
            any("/reference_outputs/" in sandbox_path for sandbox_path in file_map),
            msg="Hidden scorer references must not be staged into the agent sandbox",
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

    def test_local_sandbox_uses_unprefixed_custom_workspace_paths(self) -> None:
        root = "/tmp/scireplicbench_hpc_workspace"
        with patch.dict(
            os.environ,
            {_SANDBOX_TYPE_ENV: "local", WORKSPACE_ROOT_ENV: root},
            clear=False,
        ):
            sample = record_to_sample(load_task_records("squidpy_spatial")[0])

        file_map = sample.files or {}
        self.assertTrue(file_map)
        self.assertFalse(any(path.startswith("agent:") for path in file_map))
        self.assertFalse(any(path.startswith("reproducer:") for path in file_map))
        self.assertTrue(
            any(
                path == f"{root}/input/paper_bundle/data/ligrec_interactions.tsv"
                for path in file_map
            )
        )
        self.assertIn(f"mkdir -p {root}/input/paper_bundle", sample.setup)
        self.assertIn(f"{root}/input/paper_bundle/data/dataset_manifest.json", sample.input)
        self.assertIn(f"{root}/output/agent", sample.input)

    def test_paper_task_can_select_local_sandbox_backend(self) -> None:
        with (
            patch.dict(os.environ, {_SANDBOX_TYPE_ENV: "local"}, clear=False),
            patch.object(tasks, "Task", side_effect=lambda **kwargs: kwargs),
            patch.object(tasks, "react", return_value="solver"),
            patch.object(tasks, "guarded_bash", return_value="bash_tool"),
            patch.object(tasks, "python", return_value="python_tool"),
            patch.object(tasks, "scratchpad", return_value="scratchpad_tool"),
            patch.object(tasks, "workspace_text_file", return_value="workspace_text_tool"),
            patch.object(tasks, "rubric_tree_scorer", return_value="scorer"),
        ):
            task_payload = _paper_task("squidpy_spatial")

        self.assertEqual(task_payload["sandbox"], "local")

    def test_record_to_sample_seeds_genelab_submission_from_starter(self) -> None:
        record = load_task_records("genelab_benchmark")[0]
        sample = record_to_sample(record)
        self.assertIn("cp -R /workspace/input/paper_bundle/starter/. /workspace/submission/", sample.setup)
        self.assertIn("chmod 0555 /workspace/submission/run.sh || true", sample.setup)

    def test_record_to_sample_seeds_squidpy_submission_from_starter(self) -> None:
        record = load_task_records("squidpy_spatial")[0]
        sample = record_to_sample(record)
        self.assertIn("cp -R /workspace/input/paper_bundle/starter/. /workspace/submission/", sample.setup)
        self.assertIn("/workspace/input/paper_bundle/starter/run.sh", sample.input)

    def test_unassisted_starter_mode_does_not_stage_or_seed_starter(self) -> None:
        with patch.dict(os.environ, {STARTER_MODE_ENV: "off"}, clear=False):
            record = load_task_records("squidpy_spatial")[0]
            sample = record_to_sample(record)
            file_map = _paper_bundle_file_map("squidpy_spatial")

        self.assertEqual(sample.metadata["starter_mode"], "off")
        self.assertNotIn("cp -R /workspace/input/paper_bundle/starter/.", sample.setup)
        self.assertIn("mkdir -p /workspace/output/agent/neighborhood", sample.setup)
        self.assertIn("mkdir -p /workspace/output/agent/autocorrelation", sample.setup)
        self.assertIn("mkdir -p /workspace/output/agent/visualizations", sample.setup)
        self.assertNotIn("/workspace/input/paper_bundle/starter/run.sh", sample.input)
        self.assertNotIn("already seeded under `/workspace/submission`", sample.input)
        self.assertNotIn("first substantive tool action should be `bash /workspace/submission/run.sh`", sample.input)
        self.assertIn("intentionally unassisted", sample.input)
        self.assertIn("Create your own saved workflow", sample.input)
        self.assertIn("Read `/workspace/input/paper_bundle/output_contract.md`", sample.input)
        self.assertIn("sq.gr.spatial_neighbors", sample.input)
        self.assertIn("adata.obs['cluster']", sample.input)
        self.assertIn("adata.obs['celltype_mapped_refined']", sample.input)
        self.assertIn("Do not use nonexistent helper namespaces", sample.input)
        self.assertIn("do not pass `cluster_key` to it", sample.input)
        self.assertIn("Use `cluster_key=...`, not `key=...`", sample.input)
        self.assertIn("pass the base key `connectivity_key='spatial'`", sample.input)
        self.assertIn("returns `(zscore, count)`", sample.input)
        self.assertIn("do not use `np.column_stack`", sample.input)
        self.assertIn("sq.gr.spatial_autocorr(..., mode='moran'", sample.input)
        self.assertIn("sq.gr.ripley(seqfish, cluster_key='celltype_mapped_refined'", sample.input)
        self.assertIn("sq.im.calculate_image_features(adata, image", sample.input)
        self.assertIn("attempt watershed segmentation FIRST", sample.input)
        self.assertIn("Do not let image feature extraction block final scoring", sample.input)
        self.assertIn("signal.alarm", sample.input)
        self.assertIn("checking elapsed time after `sq.im.segment` returns is not enough", sample.input)
        self.assertIn("features=['histogram', 'segmentation', 'summary', 'texture']", sample.input)
        self.assertIn("sq.gr.ligrec(..., cluster_key='cluster'", sample.input)
        self.assertIn("n_perms=10", sample.input)
        self.assertIn("only rerun with `n_perms=100`", sample.input)
        self.assertIn("including `visualizations/report.html`", sample.input)
        self.assertIn("normally write into `adata.uns`", sample.input)
        self.assertIn("using the required nested schema", sample.input)
        self.assertIn("'cluster_key': 'cluster'", sample.input)
        self.assertIn("'cluster_key': 'celltype_mapped_refined'", sample.input)
        self.assertIn("Generate `spatial_graph_metrics.json` with nested graph keys", sample.input)
        self.assertIn("flat payloads such as", sample.input)
        self.assertIn("nhood and interaction matrix `pair_key` should be `cluster_1|cluster_2`", sample.input)
        self.assertIn("cooccurrence `pair_key` should be `cluster_1->cluster_2`", sample.input)
        self.assertIn("interval=25", sample.input)
        self.assertIn("groupby('label').cumcount()", sample.input)
        self.assertIn("significant_gene_count", sample.input)
        self.assertIn("create every required subdirectory", sample.input)
        self.assertIn("Write durable cheap artifacts first", sample.input)
        self.assertIn("bounded image features", sample.input)
        self.assertIn("submission manifest, and finally ligand-receptor tables", sample.input)
        self.assertIn("Do not postpone `dataset_manifest.json`", sample.input)
        self.assertIn("Write `spatial_graph_metrics.json` immediately", sample.input)
        self.assertIn("Use stable TSV schemas", sample.input)
        self.assertIn("Do not let ligand-receptor permutations block final scoring", sample.input)
        self.assertIn("spatial_stats_plot.svg` should contain `<svg` and `Top Moran`", sample.input)
        self.assertIn("Squidpy spatial reviewer-path report", sample.input)
        self.assertIn("sort the executed custom-panel interaction table by mean descending", sample.input)
        self.assertIn("source|target|cluster_1->cluster_2", sample.input)
        self.assertIn("Treat `n_perms=100` as optional refinement", sample.input)
        self.assertIn("Do not leave placeholder sections", sample.input)
        self.assertIn("attempt watershed segmentation FIRST", sample.input)
        self.assertIn("Skipping `sq.im.segment` entirely will fail", sample.input)
        self.assertIn("'histogram': {'channels': [0], 'bins': 4}", sample.input)
        self.assertIn("'segmentation': {'label_layer': 'segmented_watershed'", sample.input)
        self.assertIn("'texture': {'channels': [0], 'props': ['contrast', 'homogeneity']", sample.input)
        self.assertIn("`feature_families: ['fallback']`", sample.input)
        self.assertIn("`n_features >= 20`", sample.input)
        self.assertIn("at least 3 distinct `image_cluster` values", sample.input)
        self.assertIn("`fallback_feature_0`", sample.input)
        self.assertIn("Write `submission_manifest.json` with `json.dump`", sample.input)
        self.assertIn("real `/workspace/submission/main_analysis.py`", sample.input)
        self.assertIn("do not embed the substantive workflow", sample.input)
        self.assertIn("Do not hand-write final result artifacts", sample.input)
        self.assertIn("Execute Python scripts with `python script.py`", sample.input)
        self.assertIn("Execute the shell launcher with `bash run.sh`", sample.input)
        self.assertIn("python -m py_compile", sample.input)
        self.assertIn("instead of appending a second workflow below stale code", sample.input)
        self.assertIn("rewrite the full Python file with a minimal durable version", sample.input)
        self.assertFalse(
            any("/starter/" in sandbox_path for sandbox_path in file_map),
            msg="Unassisted runs must not expose starter implementation files.",
        )
        self.assertTrue(
            any(sandbox_path.endswith("/output_contract.md") for sandbox_path in file_map),
            msg="Unassisted runs should expose the public Squidpy output contract.",
        )
