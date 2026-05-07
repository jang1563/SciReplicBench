#!/usr/bin/env bash
set -euo pipefail

WORKSPACE_ROOT="${SCIREPLICBENCH_WORKSPACE_ROOT:-/workspace}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_ROOT="${SQUIDPY_OUTPUT_ROOT:-${WORKSPACE_ROOT}/output/agent}"
STARTER_DIR="${SQUIDPY_INPUT_STARTER_DIR:-${WORKSPACE_ROOT}/input/paper_bundle/starter}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
PRIMARY_TIMEOUT_SECONDS="${SQUIDPY_PRIMARY_TIMEOUT_SECONDS:-3600}"
FALLBACK_TIMEOUT_SECONDS="${SQUIDPY_FALLBACK_TIMEOUT_SECONDS:-3600}"
PRIMARY_SCRIPT="${SCRIPT_DIR}/main_analysis.py"
FALLBACK_SCRIPT="${STARTER_DIR}/main_analysis.py"
MANIFEST_PATH="${WORKSPACE_ROOT}/output/submission_manifest.json"

required_outputs=(
  "${OUTPUT_ROOT}/dataset_manifest.json"
  "${OUTPUT_ROOT}/spatial_graph_metrics.json"
  "${OUTPUT_ROOT}/neighborhood/nhood_enrichment_ranked.tsv"
  "${OUTPUT_ROOT}/neighborhood/centrality_scores.tsv"
  "${OUTPUT_ROOT}/neighborhood/cooccurrence_curves.tsv"
  "${OUTPUT_ROOT}/neighborhood/interaction_matrix.tsv"
  "${OUTPUT_ROOT}/autocorrelation/moran_ranked.tsv"
  "${OUTPUT_ROOT}/autocorrelation/geary_ranked.tsv"
  "${OUTPUT_ROOT}/spatial_stats/ripley_curves.tsv"
  "${OUTPUT_ROOT}/spatial_stats/svg_summary.json"
  "${OUTPUT_ROOT}/spatial_stats/gene_localization.tsv"
  "${OUTPUT_ROOT}/image_features/feature_matrix.tsv"
  "${OUTPUT_ROOT}/image_features/feature_ranking.tsv"
  "${OUTPUT_ROOT}/image_features/feature_clusters.tsv"
  "${OUTPUT_ROOT}/image_features/feature_summary.json"
  "${OUTPUT_ROOT}/interactions/ligrec_ranked.tsv"
  "${OUTPUT_ROOT}/interactions/ligrec_summary.json"
  "${OUTPUT_ROOT}/visualizations/spatial_stats_plot.svg"
  "${OUTPUT_ROOT}/visualizations/marker_localization.svg"
  "${OUTPUT_ROOT}/visualizations/report.html"
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
      [[ "${field_count}" -ge 2 ]] || return 1
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

mkdir -p "${OUTPUT_ROOT}" "${WORKSPACE_ROOT}/output"

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
  "Primary Squidpy submission did not emit the full artifact set (${primary_detail}); rerunning the staged starter baseline from ${FALLBACK_SCRIPT}." \
  >&2
fallback_status=0
run_with_timeout "${FALLBACK_TIMEOUT_SECONDS}" "${PYTHON_BIN}" "${FALLBACK_SCRIPT}" "$@" || fallback_status=$?
if [[ "${fallback_status}" -eq 124 ]]; then
  printf '%s\n' \
    "Staged Squidpy starter baseline timed out after ${FALLBACK_TIMEOUT_SECONDS}s." \
    >&2
fi
outputs_ok
