from __future__ import annotations

import py_compile
import unittest
from pathlib import Path


def _starter_dir() -> Path:
    return Path("papers") / "squidpy_spatial" / "starter"


class SquidpyStarterTest(unittest.TestCase):
    def test_starter_python_files_compile(self) -> None:
        starter = _starter_dir()
        py_compile.compile(str(starter / "main_analysis.py"), doraise=True)
        py_compile.compile(str(starter / "squidpy_spatial_workflow.py"), doraise=True)

    def test_run_sh_uses_workspace_root_and_checks_required_outputs(self) -> None:
        run_sh = (_starter_dir() / "run.sh").read_text()
        self.assertIn("SCIREPLICBENCH_WORKSPACE_ROOT", run_sh)
        self.assertIn("SQUIDPY_OUTPUT_ROOT", run_sh)
        self.assertIn("Primary Squidpy submission did not emit the full artifact set", run_sh)
        self.assertIn("${OUTPUT_ROOT}/dataset_manifest.json", run_sh)
        self.assertIn("${OUTPUT_ROOT}/neighborhood/nhood_enrichment_ranked.tsv", run_sh)
        self.assertIn("${OUTPUT_ROOT}/autocorrelation/moran_ranked.tsv", run_sh)
        self.assertIn("${OUTPUT_ROOT}/spatial_stats/ripley_curves.tsv", run_sh)
        self.assertIn("${OUTPUT_ROOT}/image_features/feature_summary.json", run_sh)
        self.assertIn("${OUTPUT_ROOT}/interactions/ligrec_summary.json", run_sh)
        self.assertIn("${OUTPUT_ROOT}/visualizations/spatial_stats_plot.svg", run_sh)
        self.assertIn("${OUTPUT_ROOT}/visualizations/marker_localization.svg", run_sh)
        self.assertIn("${OUTPUT_ROOT}/visualizations/report.html", run_sh)
        self.assertIn("${MANIFEST_PATH}", run_sh)

    def test_main_analysis_maps_generated_files_to_task_contract(self) -> None:
        source = (_starter_dir() / "main_analysis.py").read_text()
        self.assertIn('"visium_hne_moran_ranked.tsv": "autocorrelation/moran_ranked.tsv"', source)
        self.assertIn('"visium_hne_geary_ranked.tsv": "autocorrelation/geary_ranked.tsv"', source)
        self.assertIn('"visium_hne_ligrec_ranked.tsv": "interactions/ligrec_ranked.tsv"', source)
        self.assertIn('"visium_hne_image_feature_summary.json": "image_features/feature_summary.json"', source)
        self.assertIn('SPATIAL_STATS_PLOT_RELATIVE = "visualizations/spatial_stats_plot.svg"', source)
        self.assertIn('MARKER_LOCALIZATION_RELATIVE = "visualizations/marker_localization.svg"', source)
        self.assertIn('"starter_profile": "squidpy_offline_reviewer_path"', source)


if __name__ == "__main__":
    unittest.main()
