#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_DIR="${SCRIPT_DIR}"
RAW_DIR="${DATA_DIR}/raw"
HF_DIR="${DATA_DIR}/huggingface_dataset"
HF_REPO_URL="https://huggingface.co/datasets/jang1563/genelab-benchmark"

mkdir -p "${RAW_DIR}" "${HF_DIR}"

echo "[SciReplicBench] Preparing GeneLab benchmark public inputs"
echo "Data directory: ${DATA_DIR}"

if command -v git >/dev/null 2>&1; then
  if [[ ! -d "${RAW_DIR}/GeneLab_benchmark/.git" ]]; then
    git clone https://github.com/jang1563/GeneLab_benchmark "${RAW_DIR}/GeneLab_benchmark"
  else
    echo "Repository already present: ${RAW_DIR}/GeneLab_benchmark"
  fi
else
  echo "git is not installed; skipping repository clone." >&2
fi

if command -v hf >/dev/null 2>&1; then
  hf download jang1563/genelab-benchmark \
    --repo-type dataset \
    --local-dir "${HF_DIR}"
elif command -v huggingface-cli >/dev/null 2>&1 && huggingface-cli download --help >/dev/null 2>&1; then
  huggingface-cli download jang1563/genelab-benchmark \
    --repo-type dataset \
    --local-dir "${HF_DIR}"
elif command -v git >/dev/null 2>&1 && git lfs version >/dev/null 2>&1; then
  if [[ -d "${HF_DIR}/.git" ]]; then
    git -C "${HF_DIR}" pull --ff-only
    git -C "${HF_DIR}" lfs install --local
    git -C "${HF_DIR}" lfs pull
    git -C "${HF_DIR}" lfs checkout
  elif [[ -z "$(ls -A "${HF_DIR}")" ]]; then
    git clone "${HF_REPO_URL}" "${HF_DIR}"
    git -C "${HF_DIR}" lfs install --local
    git -C "${HF_DIR}" lfs pull
    git -C "${HF_DIR}" lfs checkout
  else
    echo "Dataset directory exists but is not empty or a git repo: ${HF_DIR}" >&2
    exit 1
  fi
else
  echo "No supported Hugging Face dataset client found; skipping dataset download." >&2
fi

cat <<'EOF'

Optional benchmark-author extension:
- Stage Geneformer embeddings or full fine-tuning artifacts separately on a GPU-equipped HPC.
- Keep the reviewer path focused on the public feature matrices and metadata cached under this data directory.
EOF
