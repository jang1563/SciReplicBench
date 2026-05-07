#!/usr/bin/env bash
# Run a Squidpy Inspect eval on Cayuga without Docker.
#
# This uses Inspect's local sandbox backend plus a writable scratch workspace.
# It is intended for Cayuga, where Docker is unavailable. It is less isolated
# than the default Docker Compose benchmark lane, but keeps the heavy Squidpy
# work off the laptop.
#
# Typical use from a staged repo on Cayuga:
#   cd /athena/masonlab/scratch/users/$USER/SciReplicBench_hpc/scireplicbench_<stamp>
#   /opt/ohpc/pub/software/slurm/24.05.2/bin/sbatch scripts/cayuga_squidpy_eval_local.sbatch
#
# Common overrides:
#   MODEL=openai/gpt-4o-mini
#   JUDGE_MODEL=openai/gpt-4o-mini
#   JUDGE_LEAF_LIMIT=5        # unset or set empty for all leaves
#   MESSAGE_LIMIT=50
#   TIME_LIMIT=1800
#   WORKING_LIMIT=1800
#   COST_LIMIT=5
#   MODEL_COST_CONFIG=configs/anthropic_model_costs.json
#   STARTER_MODE=off        # seed (default), available, or off/unassisted
#   WORKSPACE_ROOT=/athena/.../workspace
#   SKIP_INSTALL=1          # reuse an already-prepared env

#SBATCH --job-name=srb-squidpy-eval
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
WORKSPACE_ROOT="${WORKSPACE_ROOT:-${PROJECT}/hpc_workspace/${SLURM_JOB_ID:-manual}}"
LOG_DIR="${LOG_DIR:-${PROJECT}/logs-hpc}"
SKIP_INSTALL="${SKIP_INSTALL:-0}"

MODEL="${MODEL:-openai/gpt-4o-mini}"
JUDGE_MODEL="${JUDGE_MODEL:-openai/gpt-4o-mini}"
MESSAGE_LIMIT="${MESSAGE_LIMIT:-50}"
TIME_LIMIT="${TIME_LIMIT:-1800}"
WORKING_LIMIT="${WORKING_LIMIT:-1800}"
JUDGE_LEAF_LIMIT="${JUDGE_LEAF_LIMIT-5}"
COST_LIMIT="${COST_LIMIT:-}"
MODEL_COST_CONFIG="${MODEL_COST_CONFIG:-}"
STARTER_MODE="${STARTER_MODE:-seed}"

cd "${PROJECT}"
mkdir -p "${WORKSPACE_ROOT}" "${LOG_DIR}" "${ENV_ROOT}"

echo "[srb] host=$(hostname)"
echo "[srb] project=${PROJECT}"
echo "[srb] env=${ENV_PATH}"
echo "[srb] workspace=${WORKSPACE_ROOT}"
echo "[srb] model=${MODEL}"
echo "[srb] judge_model=${JUDGE_MODEL}"
echo "[srb] judge_leaf_limit=${JUDGE_LEAF_LIMIT:-all}"
echo "[srb] starter_mode=${STARTER_MODE}"
echo "[srb] started=$(date -Is)"

if [ ! -f "${CONDA_SH}" ]; then
  echo "[srb] missing conda activation script: ${CONDA_SH}" >&2
  exit 2
fi

source "${CONDA_SH}"

if [ ! -x "${ENV_PATH}/bin/python" ]; then
  echo "[srb] missing env; creating it first"
  conda create -y -p "${ENV_PATH}" python=3.11 pip
fi

if [ -f "${HOME}/.api_keys" ]; then
  set -a
  # shellcheck disable=SC1090
  source "${HOME}/.api_keys"
  set +a
fi

if [ -f "${PROJECT}/configs/runtime.env" ]; then
  set -a
  # shellcheck disable=SC1091
  source "${PROJECT}/configs/runtime.env"
  set +a
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
export SCIREPLICBENCH_SANDBOX_TYPE=local
export SCIREPLICBENCH_WORKSPACE_ROOT="${WORKSPACE_ROOT}"
export SCIREPLICBENCH_JUDGE_MODEL="${JUDGE_MODEL}"
export SCIREPLICBENCH_STARTER_MODE="${STARTER_MODE}"
if [ -n "${JUDGE_LEAF_LIMIT}" ]; then
  export SCIREPLICBENCH_JUDGE_LEAF_LIMIT="${JUDGE_LEAF_LIMIT}"
else
  unset SCIREPLICBENCH_JUDGE_LEAF_LIMIT || true
fi

conda run -p "${ENV_PATH}" python scripts/check_squidpy_scientific_stack.py \
  --check-cache \
  --load-cache \
  --analysis-smoke
conda run -p "${ENV_PATH}" python - <<'PY'
from scireplicbench.tasks import load_task_records, record_to_sample, sandbox_spec_for_paper

sample = record_to_sample(load_task_records("squidpy_spatial")[0])
print("[srb] sandbox", sandbox_spec_for_paper("squidpy_spatial"))
print("[srb] sample", sample.id)
print("[srb] staged_files", len(sample.files or {}))
print("[srb] local_prefixes", sum(path.startswith(("agent:", "reproducer:")) for path in (sample.files or {})))
PY

COMMAND=(
  python -m inspect_ai eval
  src/scireplicbench/tasks.py@scireplicbench
  --model "${MODEL}"
  --log-dir "${LOG_DIR}"
  -T "paper_id=squidpy_spatial"
  --message-limit "${MESSAGE_LIMIT}"
  --time-limit "${TIME_LIMIT}"
  --working-limit "${WORKING_LIMIT}"
)

if [ -n "${COST_LIMIT}" ]; then
  COMMAND+=(--cost-limit "${COST_LIMIT}")
fi

if [ -n "${MODEL_COST_CONFIG}" ]; then
  COMMAND+=(--model-cost-config "${MODEL_COST_CONFIG}")
fi

echo "[srb] command=${COMMAND[*]}"
conda run -p "${ENV_PATH}" "${COMMAND[@]}"

echo "[srb] completed=$(date -Is)"
