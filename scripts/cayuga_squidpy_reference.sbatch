#!/usr/bin/env bash
# Generate sealed Squidpy reference outputs on Cayuga.
#
# Usage from a staged repo on Cayuga:
#   cd /athena/masonlab/scratch/users/$USER/SciReplicBench_hpc/scireplicbench_<stamp>
#   /opt/ohpc/pub/software/slurm/24.05.2/bin/sbatch scripts/cayuga_squidpy_reference.sbatch
#
# Optional overrides:
#   ENV_ROOT=/path/to/envs
#   ENV_NAME=squidpy_spatial_py311
#   CONDA_SH=/path/to/conda.sh
#   N_JOBS=8
#   NHOOD_N_PERMS=100
#   COOCCURRENCE_INTERVALS=25
#   RIPLEY_N_SIMULATIONS=20
#   RIPLEY_N_OBSERVATIONS=1000
#   RIPLEY_N_STEPS=25
#   LIGREC_N_PERMS=100

#SBATCH --job-name=srb-squidpy-ref
#SBATCH --partition=scu-cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=08:00:00
#SBATCH --output=%x_%j.out
#SBATCH --error=%x_%j.err

set -euo pipefail

PROJECT="${SLURM_SUBMIT_DIR:-$(pwd)}"
ENV_ROOT="${ENV_ROOT:-/athena/masonlab/scratch/users/${USER}/SciReplicBench_hpc/envs}"
ENV_NAME="${ENV_NAME:-squidpy_spatial_py311}"
ENV_PATH="${ENV_ROOT}/${ENV_NAME}"
CONDA_SH="${CONDA_SH:-/home/fs01/${USER}/miniconda3/miniconda3/etc/profile.d/conda.sh}"
N_JOBS="${N_JOBS:-${SLURM_CPUS_PER_TASK:-1}}"
NHOOD_N_PERMS="${NHOOD_N_PERMS:-100}"
COOCCURRENCE_INTERVALS="${COOCCURRENCE_INTERVALS:-25}"
RIPLEY_N_SIMULATIONS="${RIPLEY_N_SIMULATIONS:-20}"
RIPLEY_N_OBSERVATIONS="${RIPLEY_N_OBSERVATIONS:-1000}"
RIPLEY_N_STEPS="${RIPLEY_N_STEPS:-25}"
LIGREC_N_PERMS="${LIGREC_N_PERMS:-100}"

cd "${PROJECT}"

echo "[srb-ref] host=$(hostname)"
echo "[srb-ref] project=${PROJECT}"
echo "[srb-ref] env=${ENV_PATH}"
echo "[srb-ref] n_jobs=${N_JOBS}"
echo "[srb-ref] nhood_n_perms=${NHOOD_N_PERMS}"
echo "[srb-ref] cooccurrence_intervals=${COOCCURRENCE_INTERVALS}"
echo "[srb-ref] ripley_n_simulations=${RIPLEY_N_SIMULATIONS}"
echo "[srb-ref] ripley_n_observations=${RIPLEY_N_OBSERVATIONS}"
echo "[srb-ref] ripley_n_steps=${RIPLEY_N_STEPS}"
echo "[srb-ref] ligrec_n_perms=${LIGREC_N_PERMS}"
echo "[srb-ref] started=$(date -Is)"

if [ ! -f "${CONDA_SH}" ]; then
  echo "[srb-ref] missing conda activation script: ${CONDA_SH}" >&2
  exit 2
fi
if [ ! -x "${ENV_PATH}/bin/python" ]; then
  echo "[srb-ref] missing env python: ${ENV_PATH}/bin/python" >&2
  exit 2
fi

source "${CONDA_SH}"
export PYTHONPATH="${PROJECT}/src"

conda run -p "${ENV_PATH}" python scripts/check_squidpy_scientific_stack.py \
  --check-cache \
  --load-cache

conda run -p "${ENV_PATH}" python scripts/generate_squidpy_reference_outputs.py \
  --manifest papers/squidpy_spatial/data/dataset_manifest.json \
  --interactions papers/squidpy_spatial/data/ligrec_interactions.tsv \
  --out-dir papers/squidpy_spatial/reference_outputs/generated \
  --n-jobs "${N_JOBS}" \
  --nhood-n-perms "${NHOOD_N_PERMS}" \
  --cooccurrence-intervals "${COOCCURRENCE_INTERVALS}" \
  --ripley-n-simulations "${RIPLEY_N_SIMULATIONS}" \
  --ripley-n-observations "${RIPLEY_N_OBSERVATIONS}" \
  --ripley-n-steps "${RIPLEY_N_STEPS}" \
  --ligrec-n-perms "${LIGREC_N_PERMS}"

echo "[srb-ref] completed=$(date -Is)"
