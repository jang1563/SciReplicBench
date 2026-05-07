#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_DIR="${SCRIPT_DIR}"
CACHE_DIR="${DATA_DIR}/cache/squidpy_builtin"
MANIFEST_PATH="${DATA_DIR}/dataset_manifest.json"

mkdir -p "${CACHE_DIR}"

python3 - <<'PY' "${CACHE_DIR}" "${MANIFEST_PATH}"
import json
import sys
from pathlib import Path

import squidpy as sq

cache_dir = Path(sys.argv[1])
manifest_path = Path(sys.argv[2])
data_dir = manifest_path.parent
cache_dir.mkdir(parents=True, exist_ok=True)

paths = {
    "visium_hne_adata": cache_dir / "visium_hne_adata.h5ad",
    "visium_hne_image": cache_dir / "visium_hne_image.tiff",
    "seqfish": cache_dir / "seqfish.h5ad",
}

visium = sq.datasets.visium_hne_adata(path=paths["visium_hne_adata"])
image = sq.datasets.visium_hne_image(path=paths["visium_hne_image"])
seqfish = sq.datasets.seqfish(path=paths["seqfish"])

image_data = getattr(image, "data", None)
if image_data is None:
    try:
        image_data = image["image"]
    except Exception as exc:  # pragma: no cover - runtime fallback in prep script
        raise RuntimeError("Could not determine Squidpy image container payload.") from exc


def rel(path: Path) -> str:
    return path.relative_to(data_dir).as_posix()


def file_record(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise FileNotFoundError(f"Expected Squidpy cache file was not created: {path}")
    return {
        "path": rel(path),
        "workspace_path": f"/workspace/input/paper_bundle/data/{rel(path)}",
        "size_bytes": path.stat().st_size,
    }


def object_dimensions(value: object) -> dict[str, object]:
    shape = getattr(value, "shape", None)
    if shape is not None:
        return {"shape": [int(dim) for dim in shape]}

    sizes = getattr(value, "sizes", None)
    if sizes is not None:
        return {"sizes": {str(dim): int(size) for dim, size in sizes.items()}}

    dims = getattr(value, "dims", None)
    if dims is not None:
        return {"dims": [str(dim) for dim in dims]}

    return {"type": type(value).__name__}


manifest = {
    "cache_root": rel(cache_dir),
    "datasets": {
        "visium_hne_adata": {
            **file_record(paths["visium_hne_adata"]),
            "shape": list(visium.shape),
            "obs_columns": sorted(map(str, visium.obs.columns.tolist())),
            "obsm_keys": sorted(map(str, visium.obsm.keys())),
            "var_count": int(visium.n_vars),
        },
        "visium_hne_image": {
            **file_record(paths["visium_hne_image"]),
            **object_dimensions(image_data),
        },
        "seqfish": {
            **file_record(paths["seqfish"]),
            "shape": list(seqfish.shape),
            "obs_columns": sorted(map(str, seqfish.obs.columns.tolist())),
            "obsm_keys": sorted(map(str, seqfish.obsm.keys())),
            "var_count": int(seqfish.n_vars),
        },
    },
}

manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
print(f"Wrote benchmark dataset manifest to {manifest_path}")
for name, path in paths.items():
    print(f"{name}: {path} ({path.stat().st_size} bytes)")
PY
