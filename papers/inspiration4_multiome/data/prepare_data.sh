#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_DIR="${SCRIPT_DIR}"
RAW_DIR="${DATA_DIR}/raw"
CACHE_DIR="${DATA_DIR}/cache"

mkdir -p "${RAW_DIR}" "${CACHE_DIR}"

echo "[SciReplicBench] Preparing Inspiration4 public inputs"
echo "Data directory: ${DATA_DIR}"

if command -v git >/dev/null 2>&1; then
  if [[ ! -d "${RAW_DIR}/inspiration4-omics/.git" ]]; then
    git clone https://github.com/eliah-o/inspiration4-omics "${RAW_DIR}/inspiration4-omics"
  else
    echo "Repository already present: ${RAW_DIR}/inspiration4-omics"
  fi
else
  echo "git is not installed; skipping repository clone." >&2
fi

cat <<'EOF'

Next steps for benchmark-author data staging:
1. Download the public Inspiration4 processed multi-omic inputs referenced in the paper's Data Availability section.
2. Convert or cache the reviewer path as benchmark-ready AnnData or MuData files inside papers/inspiration4_multiome/data/cache/.
3. Record dataset shapes and checksums in a manifest file once the benchmark-author reference assets are finalized.

This script intentionally does not guess NASA OSDR or GEO accession-specific file names without author confirmation.
EOF
