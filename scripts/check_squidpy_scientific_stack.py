#!/usr/bin/env python3
"""Smoke-check the pinned Squidpy scientific stack.

The historical Squidpy failure mode was not subtle: the benchmark image
contained a zarr 2.x stack with numcodecs 0.16+, so importing zarr/Squidpy
failed before an agent could produce any durable artifacts. This script keeps
that failure visible in CI and in the Cayuga Slurm scripts.
"""

from __future__ import annotations

import argparse
import importlib
import importlib.metadata
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


PINNED_VERSION_CEILINGS = {
    "numcodecs": (0, 16),
    "setuptools": (82, 0),
}
REQUIRED_DATASETS = ("visium_hne_adata", "visium_hne_image", "seqfish")


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str


def version_tuple(version: str) -> tuple[int, ...]:
    """Parse the numeric prefix of a PEP 440-ish version for simple ceilings."""

    parts: list[int] = []
    current = ""
    for char in version:
        if char.isdigit():
            current += char
            continue
        if char == "." and current:
            parts.append(int(current))
            current = ""
            continue
        break
    if current:
        parts.append(int(current))
    return tuple(parts) or (0,)


def _version_less_than(version: str, ceiling: tuple[int, ...]) -> bool:
    parsed = version_tuple(version)
    padded = parsed + (0,) * max(0, len(ceiling) - len(parsed))
    ceiling_padded = ceiling + (0,) * max(0, len(parsed) - len(ceiling))
    return padded < ceiling_padded


def distribution_version(distribution: str) -> str:
    return importlib.metadata.version(distribution)


def check_distribution_ceiling(distribution: str, ceiling: tuple[int, ...]) -> CheckResult:
    try:
        version = distribution_version(distribution)
    except importlib.metadata.PackageNotFoundError as exc:
        return CheckResult(distribution, False, f"not installed: {exc}")
    ceiling_text = ".".join(str(part) for part in ceiling)
    ok = _version_less_than(version, ceiling)
    detail = f"{distribution}=={version}; expected <{ceiling_text}"
    return CheckResult(distribution, ok, detail)


def check_import(module_name: str) -> CheckResult:
    try:
        module = importlib.import_module(module_name)
    except Exception as exc:
        return CheckResult(module_name, False, f"{type(exc).__name__}: {exc}")
    version = getattr(module, "__version__", "unknown")
    return CheckResult(module_name, True, f"{module_name}=={version}")


def check_pkg_resources() -> CheckResult:
    try:
        importlib.import_module("pkg_resources")
    except Exception as exc:
        return CheckResult("pkg_resources", False, f"{type(exc).__name__}: {exc}")
    return CheckResult("pkg_resources", True, "pkg_resources importable")


def check_zarr_numcodecs_abi() -> CheckResult:
    try:
        import numcodecs.blosc as blosc
        import zarr
    except Exception as exc:
        return CheckResult("zarr_numcodecs_abi", False, f"{type(exc).__name__}: {exc}")

    missing = [
        name for name in ("cbuffer_sizes", "cbuffer_metainfo") if not hasattr(blosc, name)
    ]
    if missing:
        return CheckResult(
            "zarr_numcodecs_abi",
            False,
            f"missing numcodecs.blosc helpers required by zarr 2.x: {', '.join(missing)}",
        )
    return CheckResult(
        "zarr_numcodecs_abi",
        True,
        f"zarr=={getattr(zarr, '__version__', 'unknown')} sees public blosc helpers",
    )


def load_manifest(manifest_path: Path) -> dict[str, object]:
    return json.loads(manifest_path.read_text())


def check_cache_manifest(manifest_path: Path) -> list[CheckResult]:
    if not manifest_path.is_file():
        return [CheckResult("squidpy_cache_manifest", False, f"missing: {manifest_path}")]

    try:
        manifest = load_manifest(manifest_path)
    except Exception as exc:
        return [CheckResult("squidpy_cache_manifest", False, f"{type(exc).__name__}: {exc}")]

    datasets = manifest.get("datasets") if isinstance(manifest, dict) else None
    if not isinstance(datasets, dict):
        return [CheckResult("squidpy_cache_manifest", False, "manifest lacks datasets object")]

    results = [
        CheckResult(
            "squidpy_cache_manifest",
            all(name in datasets for name in REQUIRED_DATASETS),
            "datasets=" + ",".join(sorted(map(str, datasets))),
        )
    ]
    data_root = manifest_path.parent
    for name in REQUIRED_DATASETS:
        record = datasets.get(name)
        if not isinstance(record, dict):
            results.append(CheckResult(f"squidpy_cache_file:{name}", False, "missing record"))
            continue
        rel_path = record.get("path")
        expected_size = int(record.get("size_bytes", 0) or 0)
        path = data_root / str(rel_path)
        if not path.is_file():
            results.append(CheckResult(f"squidpy_cache_file:{name}", False, f"missing: {path}"))
            continue
        observed_size = path.stat().st_size
        results.append(
            CheckResult(
                f"squidpy_cache_file:{name}",
                observed_size == expected_size,
                f"{path} size={observed_size} expected={expected_size}",
            )
        )
    return results


def check_offline_dataset_loads(manifest_path: Path, *, analysis_smoke: bool = False) -> list[CheckResult]:
    results: list[CheckResult] = []
    manifest = load_manifest(manifest_path)
    datasets = manifest["datasets"]
    data_root = manifest_path.parent

    import squidpy as sq

    paths = {
        name: data_root / datasets[name]["path"]  # type: ignore[index]
        for name in REQUIRED_DATASETS
    }
    try:
        visium = sq.datasets.visium_hne_adata(path=paths["visium_hne_adata"])
        seqfish = sq.datasets.seqfish(path=paths["seqfish"])
        image = sq.datasets.visium_hne_image(path=paths["visium_hne_image"])
    except Exception as exc:
        return [CheckResult("squidpy_offline_load", False, f"{type(exc).__name__}: {exc}")]

    image_data = getattr(image, "data", None)
    image_shape = getattr(image_data, "shape", None)
    results.extend(
        [
            CheckResult("squidpy_visium_load", tuple(visium.shape) == (2688, 18078), f"shape={visium.shape}"),
            CheckResult("squidpy_seqfish_load", tuple(seqfish.shape) == (19416, 351), f"shape={seqfish.shape}"),
            CheckResult("squidpy_image_load", image_data is not None, f"shape={image_shape}"),
        ]
    )

    if analysis_smoke:
        try:
            sq.gr.spatial_neighbors(visium, coord_type="grid", n_neighs=6, n_rings=1)
            genes = list(visium.var_names[:25])
            sq.gr.spatial_autocorr(
                visium,
                mode="geary",
                genes=genes,
                n_perms=None,
                n_jobs=1,
                show_progress_bar=False,
            )
            seqfish_subset = seqfish[:500].copy()
            sq.gr.spatial_neighbors(seqfish_subset, coord_type="generic", n_neighs=6)
        except Exception as exc:
            results.append(
                CheckResult("squidpy_analysis_smoke", False, f"{type(exc).__name__}: {exc}")
            )
        else:
            graph_edges = int(visium.obsp["spatial_connectivities"].nnz)
            geary_rows = len(visium.uns.get("gearyC", []))
            seqfish_edges = int(seqfish_subset.obsp["spatial_connectivities"].nnz)
            results.append(
                CheckResult(
                    "squidpy_analysis_smoke",
                    graph_edges > 0 and geary_rows == 25 and seqfish_edges > 0,
                    f"visium_edges={graph_edges}; geary_rows={geary_rows}; seqfish_subset_edges={seqfish_edges}",
                )
            )

    return results


def base_checks() -> list[CheckResult]:
    results = [check_distribution_ceiling(name, ceiling) for name, ceiling in PINNED_VERSION_CEILINGS.items()]
    results.extend(check_import(module) for module in ("scanpy", "squidpy", "spatialdata", "zarr"))
    results.append(check_pkg_resources())
    results.append(check_zarr_numcodecs_abi())
    return results


def print_results(results: Iterable[CheckResult]) -> bool:
    ok = True
    for result in results:
        status = "ok" if result.ok else "FAIL"
        print(f"[{status}] {result.name}: {result.detail}")
        ok = ok and result.ok
    return ok


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("papers/squidpy_spatial/data/dataset_manifest.json"),
        help="Dataset manifest to validate when cache checks are requested.",
    )
    parser.add_argument(
        "--check-cache",
        action="store_true",
        help="Validate that benchmark-pinned Squidpy cache files exist with manifest sizes.",
    )
    parser.add_argument(
        "--load-cache",
        action="store_true",
        help="Load the offline Squidpy datasets from the manifest paths.",
    )
    parser.add_argument(
        "--analysis-smoke",
        action="store_true",
        help="After --load-cache, run a small graph/autocorrelation smoke analysis.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    results = base_checks()
    if args.check_cache:
        results.extend(check_cache_manifest(args.manifest))
    if args.load_cache or args.analysis_smoke:
        results.extend(check_offline_dataset_loads(args.manifest, analysis_smoke=args.analysis_smoke))
    return 0 if print_results(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
