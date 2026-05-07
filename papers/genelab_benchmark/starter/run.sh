#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_ROOT="${GENELAB_OUTPUT_ROOT:-/workspace/output/agent}"
STARTER_DIR="${GENELAB_INPUT_STARTER_DIR:-/workspace/input/paper_bundle/starter}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
PRIMARY_TIMEOUT_SECONDS="${GENELAB_PRIMARY_TIMEOUT_SECONDS:-900}"
FALLBACK_TIMEOUT_SECONDS="${GENELAB_FALLBACK_TIMEOUT_SECONDS:-900}"
PRIMARY_SCRIPT="${SCRIPT_DIR}/main_analysis.py"
FALLBACK_SCRIPT="${STARTER_DIR}/main_analysis.py"
MANIFEST_PATH="$(dirname "${OUTPUT_ROOT}")/submission_manifest.json"

required_outputs=(
  "${OUTPUT_ROOT}/lomo/summary.tsv"
  "${OUTPUT_ROOT}/transfer/cross_tissue.tsv"
  "${OUTPUT_ROOT}/negative_controls/summary.tsv"
  "${OUTPUT_ROOT}/interpretability/top_features.tsv"
  "${MANIFEST_PATH}"
)

outputs_ok() {
  local path
  local line_count
  local field_count

  for path in "${required_outputs[@]}"; do
    [[ -s "${path}" ]] || return 1
    if [[ "${path}" == *.tsv ]]; then
      line_count="$(wc -l < "${path}")"
      [[ "${line_count}" -ge 2 ]] || return 1
      field_count="$(awk -F $'\t' 'NR == 1 { print NF; exit }' "${path}")"
      [[ "${field_count}" -ge 5 ]] || return 1
    fi
  done
}

run_with_timeout() {
  local timeout_seconds="$1"
  shift

  if [[ ! "${timeout_seconds}" =~ ^[0-9]+$ ]] || [[ "${timeout_seconds}" -le 0 ]]; then
    "$@"
    return $?
  fi

  "$@" &
  local child_pid=$!
  local elapsed=0
  while kill -0 "${child_pid}" 2>/dev/null; do
    if [[ "${elapsed}" -ge "${timeout_seconds}" ]]; then
      kill "${child_pid}" 2>/dev/null || true
      wait "${child_pid}" 2>/dev/null || true
      return 124
    fi
    sleep 1
    elapsed=$((elapsed + 1))
  done
  wait "${child_pid}"
}

primary_status=0
run_with_timeout "${PRIMARY_TIMEOUT_SECONDS}" "${PYTHON_BIN}" "${PRIMARY_SCRIPT}" "$@" || primary_status=$?

if outputs_ok; then
  exit 0
fi

primary_detail="exit=${primary_status}"
if [[ "${primary_status}" -eq 124 ]]; then
  primary_detail="timed out after ${PRIMARY_TIMEOUT_SECONDS}s"
fi

printf '%s\n' \
  "Primary GeneLab submission did not emit the full artifact set (${primary_detail}); rerunning the staged starter baseline from ${FALLBACK_SCRIPT}." \
  >&2
fallback_status=0
run_with_timeout "${FALLBACK_TIMEOUT_SECONDS}" "${PYTHON_BIN}" "${FALLBACK_SCRIPT}" "$@" || fallback_status=$?
if [[ "${fallback_status}" -eq 124 ]]; then
  printf '%s\n' \
    "Staged GeneLab starter baseline timed out after ${FALLBACK_TIMEOUT_SECONDS}s." \
    >&2
fi
outputs_ok
