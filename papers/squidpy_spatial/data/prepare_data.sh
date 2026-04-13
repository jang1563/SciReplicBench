#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_DIR="${SCRIPT_DIR}"
MANIFEST_PATH="${DATA_DIR}/dataset_manifest.json"

mkdir -p "${DATA_DIR}"

python3 - <<'PY' "${MANIFEST_PATH}"
import json
import sys
from pathlib import Path

import squidpy as sq

manifest_path = Path(sys.argv[1])

visium = sq.datasets.visium_hne_adata()
image = sq.datasets.visium_hne_image()
seqfish = sq.datasets.seqfish()

image_data = getattr(image, "data", None)
if image_data is None:
    try:
        image_data = image["image"]
    except Exception as exc:  # pragma: no cover - runtime fallback in prep script
        raise RuntimeError("Could not determine Squidpy image container payload.") from exc

manifest = {
    "datasets": {
        "visium_hne_adata": {
            "shape": list(visium.shape),
            "obs_columns": sorted(map(str, visium.obs.columns.tolist())),
            "var_count": int(visium.n_vars),
        },
        "visium_hne_image": {
            "shape": list(image_data.shape),
        },
        "seqfish": {
            "shape": list(seqfish.shape),
            "obs_columns": sorted(map(str, seqfish.obs.columns.tolist())),
            "var_count": int(seqfish.n_vars),
        },
    }
}

manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
print(f"Wrote benchmark dataset manifest to {manifest_path}")
PY
