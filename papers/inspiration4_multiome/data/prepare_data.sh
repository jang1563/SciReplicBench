#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_DIR="${SCRIPT_DIR}"
RAW_DIR="${DATA_DIR}/raw"
CACHE_DIR="${DATA_DIR}/cache"
PUBLIC_OSDR_DIR="${CACHE_DIR}/osdr_public"
OSDR_STUDY_ID="OSD-570"
OSDR_DOWNLOAD_PREFIX="https://osdr.nasa.gov/geode-py/ws/studies/${OSDR_STUDY_ID}/download?source=datamanager&file="

OSDR_PUBLIC_FILES=(
  "GLDS-562_snRNA-Seq_PBMC_Gene_Expression_snRNA-seq_Processed_Data.xlsx"
  "GLDS-562_snATAC-Seq_PBMC_Chromatin_Accessibility_snATAC-seq_Processed_Data.xlsx"
  "OSD-570_metadata_OSD-570-ISA.zip"
)

mkdir -p "${RAW_DIR}" "${CACHE_DIR}" "${PUBLIC_OSDR_DIR}"

sha256_file() {
  local path="$1"
  if command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "${path}" | awk '{print $1}'
  elif command -v sha256sum >/dev/null 2>&1; then
    sha256sum "${path}" | awk '{print $1}'
  else
    echo "unavailable"
  fi
}

write_manifest() {
  local manifest_path="${PUBLIC_OSDR_DIR}/manifest.tsv"
  printf 'filename\tbytes\tsha256\trole\tsource_url\n' > "${manifest_path}"

  local filename path bytes sha256 role
  for filename in "${OSDR_PUBLIC_FILES[@]}"; do
    path="${PUBLIC_OSDR_DIR}/${filename}"
    if [[ ! -f "${path}" ]]; then
      continue
    fi

    bytes="$(wc -c < "${path}" | tr -d '[:space:]')"
    sha256="$(sha256_file "${path}")"
    case "${filename}" in
      GLDS-562_snRNA-Seq_PBMC_Gene_Expression_snRNA-seq_Processed_Data.xlsx)
        role="public_processed_snRNA_deg_table"
        ;;
      GLDS-562_snATAC-Seq_PBMC_Chromatin_Accessibility_snATAC-seq_Processed_Data.xlsx)
        role="public_processed_snATAC_dar_table"
        ;;
      OSD-570_metadata_OSD-570-ISA.zip)
        role="public_isa_metadata"
        ;;
      *)
        role="unknown"
        ;;
    esac

    printf '%s\t%s\t%s\t%s\t%s%s\n' \
      "${filename}" \
      "${bytes}" \
      "${sha256}" \
      "${role}" \
      "${OSDR_DOWNLOAD_PREFIX}" \
      "${filename}" >> "${manifest_path}"
  done

  echo "Wrote manifest: ${manifest_path}"
}

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

if command -v curl >/dev/null 2>&1; then
  for filename in "${OSDR_PUBLIC_FILES[@]}"; do
    destination="${PUBLIC_OSDR_DIR}/${filename}"
    if [[ -f "${destination}" ]]; then
      echo "OSDR file already present: ${destination}"
      continue
    fi

    echo "Downloading OSDR public file: ${filename}"
    curl -fL --retry 3 --retry-delay 2 \
      "${OSDR_DOWNLOAD_PREFIX}${filename}" \
      -o "${destination}"
  done
  write_manifest
else
  echo "curl is not installed; skipping OSDR public downloads." >&2
fi

cat <<'EOF'

Public staging completed:
1. The upstream analysis repository is cloned at `papers/inspiration4_multiome/data/raw/inspiration4-omics/`.
2. Public OSDR study `OSD-570` assets are downloaded to `papers/inspiration4_multiome/data/cache/osdr_public/`.
3. A local manifest with file sizes and SHA-256 hashes is written to `papers/inspiration4_multiome/data/cache/osdr_public/manifest.tsv`.

Remaining blocker:
1. The public `OSD-570` downloads are processed DEG/DAR tables plus ISA metadata, not the benchmark-ready reviewer AnnData or MuData object.
2. A benchmark-author multimodal cache still needs to be staged under `papers/inspiration4_multiome/data/cache/` before a real production eval can run.
EOF
