#!/usr/bin/env bash
# Prepare the Squidpy paper bundle on Cayuga.
#
# Usage from a staged repo on Cayuga:
#   cd /athena/masonlab/scratch/users/$USER/SciReplicBench_hpc/scireplicbench_<stamp>
#   /opt/ohpc/pub/software/slurm/24.05.2/bin/sbatch scripts/cayuga_squidpy_prepare.sbatch
#
# Optional overrides:
#   ENV_ROOT=/path/to/envs
#   ENV_NAME=squidpy_spatial_py311
#   CONDA_SH=/path/to/conda.sh
#   SKIP_INSTALL=1  # reuse an already-prepared env

#SBATCH --job-name=srb-squidpy-prep
#SBATCH --partition=scu-cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=06:00:00
#SBATCH --output=%x_%j.out
#SBATCH --error=%x_%j.err

set -euo pipefail

PROJECT="${SLURM_SUBMIT_DIR:-$(pwd)}"
ENV_ROOT="${ENV_ROOT:-/athena/masonlab/scratch/users/${USER}/SciReplicBench_hpc/envs}"
ENV_NAME="${ENV_NAME:-squidpy_spatial_py311}"
ENV_PATH="${ENV_ROOT}/${ENV_NAME}"
CONDA_SH="${CONDA_SH:-/home/fs01/${USER}/miniconda3/miniconda3/etc/profile.d/conda.sh}"
SKIP_INSTALL="${SKIP_INSTALL:-0}"

cd "${PROJECT}"
mkdir -p "${ENV_ROOT}"

echo "[srb] host=$(hostname)"
echo "[srb] project=${PROJECT}"
echo "[srb] env=${ENV_PATH}"
echo "[srb] started=$(date -Is)"

if [ ! -f "${CONDA_SH}" ]; then
  echo "[srb] missing conda activation script: ${CONDA_SH}" >&2
  exit 2
fi

source "${CONDA_SH}"

if [ ! -x "${ENV_PATH}/bin/python" ]; then
  echo "[srb] creating conda env"
  conda create -y -p "${ENV_PATH}" python=3.11 pip
else
  echo "[srb] reusing existing conda env"
fi

conda run -p "${ENV_PATH}" python --version
if [ "${SKIP_INSTALL}" = "1" ]; then
  echo "[srb] SKIP_INSTALL=1; reusing existing Python packages"
else
  echo "[srb] installing/updating Python packages"
  conda run -p "${ENV_PATH}" python -m pip install --upgrade pip setuptools wheel uv
  conda run -p "${ENV_PATH}" python -m uv pip install \
    --python "${ENV_PATH}/bin/python" \
    -r "${PROJECT}/environments/requirements.squidpy_spatial.txt"
  conda run -p "${ENV_PATH}" python -m pip install -e "${PROJECT}[dev]"
fi

export PYTHONPATH="${PROJECT}/src"
conda run -p "${ENV_PATH}" python scripts/check_squidpy_scientific_stack.py
conda run -p "${ENV_PATH}" bash papers/squidpy_spatial/data/prepare_data.sh
conda run -p "${ENV_PATH}" python scripts/check_squidpy_scientific_stack.py \
  --check-cache \
  --load-cache \
  --analysis-smoke

conda run -p "${ENV_PATH}" python - <<'PY'
import json
from pathlib import Path

manifest = Path("papers/squidpy_spatial/data/dataset_manifest.json")
print("[srb] manifest_exists", manifest.exists())
if manifest.exists():
    payload = json.loads(manifest.read_text())
    for name, record in payload.get("datasets", {}).items():
        path = Path("papers/squidpy_spatial/data") / record["path"]
        size = path.stat().st_size if path.exists() else 0
        print(f"[srb] {name}: exists={path.exists()} size={size} path={path}")
PY

echo "[srb] completed=$(date -Is)"
