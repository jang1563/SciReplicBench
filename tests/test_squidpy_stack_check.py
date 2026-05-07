from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "check_squidpy_scientific_stack.py"
SPEC = importlib.util.spec_from_file_location("check_squidpy_scientific_stack", SCRIPT_PATH)
assert SPEC is not None
stack_check = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = stack_check
SPEC.loader.exec_module(stack_check)


class SquidpyStackCheckTest(unittest.TestCase):
    def test_version_tuple_handles_simple_pep440_prefixes(self) -> None:
        self.assertEqual(stack_check.version_tuple("0.15.1"), (0, 15, 1))
        self.assertEqual(stack_check.version_tuple("82.0.1"), (82, 0, 1))
        self.assertEqual(stack_check.version_tuple("1.0rc1"), (1, 0))

    def test_version_ceiling_catches_historical_bad_numcodecs(self) -> None:
        self.assertTrue(stack_check._version_less_than("0.15.1", (0, 16)))
        self.assertFalse(stack_check._version_less_than("0.16.0", (0, 16)))

    def test_cache_manifest_reports_missing_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest = Path(tmpdir) / "dataset_manifest.json"
            manifest.write_text(
                """{
  "datasets": {
    "visium_hne_adata": {"path": "cache/visium.h5ad", "size_bytes": 10},
    "visium_hne_image": {"path": "cache/image.tiff", "size_bytes": 20},
    "seqfish": {"path": "cache/seqfish.h5ad", "size_bytes": 30}
  }
}
"""
            )
            results = stack_check.check_cache_manifest(manifest)

        self.assertTrue(results[0].ok)
        self.assertTrue(any(not result.ok and "missing:" in result.detail for result in results[1:]))


if __name__ == "__main__":
    unittest.main()
