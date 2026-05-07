from __future__ import annotations

import csv
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path


def _starter_dir() -> Path:
    return (
        Path(__file__).resolve().parents[1]
        / "papers"
        / "genelab_benchmark"
        / "starter"
    )


def _load_genelab_starter_module() -> types.ModuleType:
    module_path = _starter_dir() / "main_analysis.py"
    spec = importlib.util.spec_from_file_location("genelab_starter_main_analysis", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load GeneLab starter module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_csv(path: Path, rows: list[list[object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerows(rows)


def _write_minimal_genelab_fixture(root: Path) -> tuple[Path, Path]:
    feature_root = root / "features" / "A2_gastrocnemius_lomo" / "fold_RR-1_test"
    label_root = root / "labels" / "A2_gastrocnemius_lomo" / "fold_RR-1_test"
    _write_csv(
        feature_root / "train_X.csv",
        [
            ["sample_id", "gene_a", "gene_b"],
            ["s1", 0.1, 0.2],
            ["s2", 0.2, 0.3],
            ["s3", 0.8, 0.7],
            ["s4", 0.9, 0.8],
        ],
    )
    _write_csv(
        feature_root / "test_X.csv",
        [
            ["sample_id", "gene_a", "gene_b"],
            ["s5", 0.15, 0.25],
            ["s6", 0.85, 0.75],
        ],
    )
    _write_csv(
        label_root / "train_y.csv",
        [
            ["sample_id", "label"],
            ["s1", 0],
            ["s2", 0],
            ["s3", 1],
            ["s4", 1],
        ],
    )
    _write_csv(
        label_root / "test_y.csv",
        [
            ["sample_id", "label"],
            ["s5", 0],
            ["s6", 1],
        ],
    )
    _write_csv(
        label_root / "train_meta.csv",
        [
            ["sample_id", "mission", "tissue"],
            ["s1", "RR-3", "gastrocnemius"],
            ["s2", "RR-4", "gastrocnemius"],
            ["s3", "RR-5", "gastrocnemius"],
            ["s4", "RR-6", "gastrocnemius"],
        ],
    )
    _write_csv(
        label_root / "test_meta.csv",
        [
            ["sample_id", "mission", "tissue"],
            ["s5", "RR-1", "gastrocnemius"],
            ["s6", "RR-1", "gastrocnemius"],
        ],
    )
    return feature_root, label_root


class GeneLabStarterIntegrationTest(unittest.TestCase):
    def test_variance_screening_caps_model_features(self) -> None:
        module = _load_genelab_starter_module()

        names, train_x, test_x = module._variance_screened_matrices(
            ["flat_a", "high", "flat_b", "medium"],
            [
                [1.0, 0.0, 2.0, 0.0],
                [1.0, 10.0, 2.0, 2.0],
                [1.0, 20.0, 2.0, 4.0],
            ],
            [
                [1.0, 5.0, 2.0, 1.0],
            ],
            max_features=2,
        )

        self.assertEqual(names, ["high", "medium"])
        self.assertEqual(train_x, [[0.0, 0.0], [10.0, 2.0], [20.0, 4.0]])
        self.assertEqual(test_x, [[5.0, 1.0]])

    def test_main_writes_machine_readable_outputs(self) -> None:
        module = _load_genelab_starter_module()

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            feature_root = root / "features" / "A2_gastrocnemius_lomo" / "fold_RR-1_test"
            label_root = root / "labels" / "A2_gastrocnemius_lomo" / "fold_RR-1_test"
            output_root = root / "output"

            _write_csv(
                feature_root / "train_X.csv",
                [
                    ["sample_id", "gene_a", "gene_b"],
                    ["s1", 0.1, 0.2],
                    ["s2", 0.2, 0.3],
                    ["s3", 0.8, 0.7],
                    ["s4", 0.9, 0.8],
                ],
            )
            _write_csv(
                feature_root / "test_X.csv",
                [
                    ["sample_id", "gene_a", "gene_b"],
                    ["s5", 0.15, 0.25],
                    ["s6", 0.85, 0.75],
                ],
            )
            _write_csv(
                label_root / "train_y.csv",
                [
                    ["sample_id", "label"],
                    ["s1", 0],
                    ["s2", 0],
                    ["s3", 1],
                    ["s4", 1],
                ],
            )
            _write_csv(
                label_root / "test_y.csv",
                [
                    ["sample_id", "label"],
                    ["s5", 0],
                    ["s6", 1],
                ],
            )
            _write_csv(
                label_root / "train_meta.csv",
                [
                    ["sample_id", "mission", "tissue"],
                    ["s1", "RR-3", "gastrocnemius"],
                    ["s2", "RR-4", "gastrocnemius"],
                    ["s3", "RR-5", "gastrocnemius"],
                    ["s4", "RR-6", "gastrocnemius"],
                ],
            )
            _write_csv(
                label_root / "test_meta.csv",
                [
                    ["sample_id", "mission", "tissue"],
                    ["s5", "RR-1", "gastrocnemius"],
                    ["s6", "RR-1", "gastrocnemius"],
                ],
            )

            module.FEATURE_ROOT = root / "features"
            module.LABEL_ROOT = root / "labels"
            module.OUTPUT_ROOT = output_root

            module.main()

            lomo_path = output_root / "lomo" / "summary.tsv"
            split_manifest_path = output_root / "lomo" / "split_manifest.tsv"
            preprocessed_path = output_root / "lomo" / "preprocessed_features.tsv"
            transfer_path = output_root / "transfer" / "cross_tissue.tsv"
            negative_path = output_root / "negative_controls" / "summary.tsv"
            interpretability_path = output_root / "interpretability" / "top_features.tsv"
            go_nogo_path = output_root / "go_nogo" / "summary.tsv"
            foundation_path = output_root / "foundation" / "geneformer_staging.tsv"
            manifest_path = output_root.parent / "submission_manifest.json"

            for path in (
                lomo_path,
                split_manifest_path,
                preprocessed_path,
                transfer_path,
                negative_path,
                interpretability_path,
                go_nogo_path,
                foundation_path,
                manifest_path,
            ):
                self.assertTrue(path.exists(), msg=f"Missing output {path}")
                if path.suffix == ".tsv":
                    rows = path.read_text().strip().splitlines()
                    self.assertGreaterEqual(len(rows), 2, msg=f"{path} should contain header + data row")

            lomo_rows = lomo_path.read_text().strip().splitlines()
            self.assertIn("heldout_mission", lomo_rows[0])
            self.assertTrue(any("reviewer-path baseline" in row for row in lomo_rows[1:]))
            self.assertTrue(
                any(
                    model_name in "\n".join(lomo_rows[1:])
                    for model_name in ("ElasticNetLogReg", "RandomForest", "XGBoost", "PCALogReg")
                )
            )

            split_manifest_rows = split_manifest_path.read_text().strip().splitlines()
            self.assertIn("heldout_mission", split_manifest_rows[0])
            self.assertIn("RR-1", split_manifest_rows[1])

            transfer_rows = transfer_path.read_text().strip().splitlines()
            self.assertIn("n_common_genes", transfer_rows[0])
            self.assertTrue(
                any(status in transfer_rows[1] for status in ("ok", "not_applicable", "failed"))
            )

            foundation_rows = foundation_path.read_text().strip().splitlines()
            self.assertIn("Geneformer", foundation_rows[1])

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["starter_profile"], "reviewer_path_baseline")
            self.assertEqual(manifest["n_folds"], 1)

    def test_run_sh_falls_back_to_staged_input_baseline(self) -> None:
        starter_dir = _starter_dir()

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            feature_root = root / "features" / "A2_gastrocnemius_lomo" / "fold_RR-1_test"
            label_root = root / "labels" / "A2_gastrocnemius_lomo" / "fold_RR-1_test"
            output_root = root / "output" / "agent"
            submission_dir = root / "submission"
            input_starter_dir = root / "input" / "paper_bundle" / "starter"

            _write_csv(
                feature_root / "train_X.csv",
                [
                    ["sample_id", "gene_a", "gene_b"],
                    ["s1", 0.1, 0.2],
                    ["s2", 0.2, 0.3],
                    ["s3", 0.8, 0.7],
                    ["s4", 0.9, 0.8],
                ],
            )
            _write_csv(
                feature_root / "test_X.csv",
                [
                    ["sample_id", "gene_a", "gene_b"],
                    ["s5", 0.15, 0.25],
                    ["s6", 0.85, 0.75],
                ],
            )
            _write_csv(
                label_root / "train_y.csv",
                [
                    ["sample_id", "label"],
                    ["s1", 0],
                    ["s2", 0],
                    ["s3", 1],
                    ["s4", 1],
                ],
            )
            _write_csv(
                label_root / "test_y.csv",
                [
                    ["sample_id", "label"],
                    ["s5", 0],
                    ["s6", 1],
                ],
            )
            _write_csv(
                label_root / "train_meta.csv",
                [
                    ["sample_id", "mission", "tissue"],
                    ["s1", "RR-3", "gastrocnemius"],
                    ["s2", "RR-4", "gastrocnemius"],
                    ["s3", "RR-5", "gastrocnemius"],
                    ["s4", "RR-6", "gastrocnemius"],
                ],
            )
            _write_csv(
                label_root / "test_meta.csv",
                [
                    ["sample_id", "mission", "tissue"],
                    ["s5", "RR-1", "gastrocnemius"],
                    ["s6", "RR-1", "gastrocnemius"],
                ],
            )

            submission_dir.mkdir(parents=True, exist_ok=True)
            input_starter_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(starter_dir / "run.sh", submission_dir / "run.sh")
            shutil.copy2(starter_dir / "main_analysis.py", input_starter_dir / "main_analysis.py")
            (submission_dir / "main_analysis.py").write_text(
                "print('placeholder rewrite')\n",
                encoding="utf-8",
            )

            env = os.environ.copy()
            env.update(
                {
                    "GENELAB_FEATURE_ROOT": str(root / "features"),
                    "GENELAB_LABEL_ROOT": str(root / "labels"),
                    "GENELAB_OUTPUT_ROOT": str(output_root),
                    "GENELAB_INPUT_STARTER_DIR": str(input_starter_dir),
                    "PYTHON_BIN": sys.executable,
                }
            )

            result = subprocess.run(
                ["bash", str(submission_dir / "run.sh")],
                capture_output=True,
                check=True,
                cwd=submission_dir,
                env=env,
                text=True,
            )

            self.assertIn("rerunning the staged starter baseline", result.stderr)
            lomo_path = output_root / "lomo" / "summary.tsv"
            self.assertTrue(lomo_path.exists(), msg="Fallback baseline should emit LOMO outputs")
            self.assertGreaterEqual(len(lomo_path.read_text(encoding="utf-8").strip().splitlines()), 2)

            manifest = json.loads((output_root.parent / "submission_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["starter_profile"], "reviewer_path_baseline")

    def test_run_sh_rejects_shallow_primary_outputs_then_falls_back(self) -> None:
        starter_dir = _starter_dir()

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            output_root = root / "output" / "agent"
            submission_dir = root / "submission"
            input_starter_dir = root / "input" / "paper_bundle" / "starter"
            _write_minimal_genelab_fixture(root)

            submission_dir.mkdir(parents=True, exist_ok=True)
            input_starter_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(starter_dir / "run.sh", submission_dir / "run.sh")
            shutil.copy2(starter_dir / "main_analysis.py", input_starter_dir / "main_analysis.py")
            (submission_dir / "main_analysis.py").write_text(
                (
                    "from pathlib import Path\n"
                    f"root = Path({str(output_root)!r})\n"
                    "files = {\n"
                    "    'lomo/summary.tsv': 'Tissue\\tFold\\tAUROC\\nA\\tfold_1\\t0.7\\n',\n"
                    "    'transfer/cross_tissue.tsv': 'Tissue_Train\\tTissue_Test\\tFold\\tAUROC\\nA\\tB\\tfold_1\\t0.7\\n',\n"
                    "    'negative_controls/summary.tsv': 'Metric\\tValue\\nAUROC near chance\\t0.5\\n',\n"
                    "    'interpretability/top_features.tsv': 'Feature\\tImportance\\nGene_1\\t0.25\\n',\n"
                    "}\n"
                    "for rel, text in files.items():\n"
                    "    path = root / rel\n"
                    "    path.parent.mkdir(parents=True, exist_ok=True)\n"
                    "    path.write_text(text, encoding='utf-8')\n"
                    "(root.parent / 'submission_manifest.json').write_text('{}\\n', encoding='utf-8')\n"
                ),
                encoding="utf-8",
            )

            env = os.environ.copy()
            env.update(
                {
                    "GENELAB_FEATURE_ROOT": str(root / "features"),
                    "GENELAB_LABEL_ROOT": str(root / "labels"),
                    "GENELAB_OUTPUT_ROOT": str(output_root),
                    "GENELAB_INPUT_STARTER_DIR": str(input_starter_dir),
                    "PYTHON_BIN": sys.executable,
                }
            )

            result = subprocess.run(
                ["bash", str(submission_dir / "run.sh")],
                capture_output=True,
                check=True,
                cwd=submission_dir,
                env=env,
                text=True,
            )

            self.assertIn("rerunning the staged starter baseline", result.stderr)
            lomo_path = output_root / "lomo" / "summary.tsv"
            top_features_path = output_root / "interpretability" / "top_features.tsv"
            self.assertIn("heldout_mission", lomo_path.read_text(encoding="utf-8").splitlines()[0])
            self.assertIn("feature_rank", top_features_path.read_text(encoding="utf-8").splitlines()[0])

    def test_run_sh_times_out_slow_primary_then_falls_back(self) -> None:
        starter_dir = _starter_dir()

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            output_root = root / "output" / "agent"
            submission_dir = root / "submission"
            input_starter_dir = root / "input" / "paper_bundle" / "starter"
            _write_minimal_genelab_fixture(root)

            submission_dir.mkdir(parents=True, exist_ok=True)
            input_starter_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(starter_dir / "run.sh", submission_dir / "run.sh")
            shutil.copy2(starter_dir / "main_analysis.py", input_starter_dir / "main_analysis.py")
            (submission_dir / "main_analysis.py").write_text(
                "import time\ntime.sleep(5)\n",
                encoding="utf-8",
            )

            env = os.environ.copy()
            env.update(
                {
                    "GENELAB_FEATURE_ROOT": str(root / "features"),
                    "GENELAB_LABEL_ROOT": str(root / "labels"),
                    "GENELAB_OUTPUT_ROOT": str(output_root),
                    "GENELAB_INPUT_STARTER_DIR": str(input_starter_dir),
                    "GENELAB_PRIMARY_TIMEOUT_SECONDS": "1",
                    "PYTHON_BIN": sys.executable,
                }
            )

            result = subprocess.run(
                ["bash", str(submission_dir / "run.sh")],
                capture_output=True,
                check=True,
                cwd=submission_dir,
                env=env,
                text=True,
                timeout=20,
            )

            self.assertIn("timed out after 1s", result.stderr)
            lomo_path = output_root / "lomo" / "summary.tsv"
            self.assertTrue(lomo_path.exists(), msg="Timed-out primary should fall back to baseline outputs")
            self.assertGreaterEqual(len(lomo_path.read_text(encoding="utf-8").strip().splitlines()), 2)
