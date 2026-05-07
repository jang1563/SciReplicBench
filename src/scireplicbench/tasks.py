"""Inspect task definitions for SciReplicBench."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent
from typing import Any

try:
    from inspect_ai import Task, task
    from inspect_ai.agent import react
    from inspect_ai.dataset import Sample
    from inspect_ai.tool import python
except ModuleNotFoundError as exc:  # pragma: no cover - local fallback for import-only validation
    _INSPECT_IMPORT_ERROR = exc

    @dataclass
    class Sample:  # type: ignore[override]
        input: str
        id: str | None = None
        metadata: dict[str, Any] | None = None
        files: dict[str, str] | None = None
        setup: str | None = None
        target: str | None = None

    @dataclass
    class Task:  # type: ignore[override]
        dataset: list[Sample]
        solver: Any
        sandbox: Any = None
        scorer: Any = None
        message_limit: int | None = None
        time_limit: int | None = None
        working_limit: int | None = None

    def task(*args, **kwargs):  # type: ignore[override]
        if args and callable(args[0]) and len(args) == 1 and not kwargs:
            return args[0]

        def decorator(func):
            return func

        return decorator

    def react(*args, **kwargs):  # type: ignore[override]
        raise RuntimeError(
            "inspect-ai is required to construct SciReplicBench agents."
        ) from _INSPECT_IMPORT_ERROR

    def python(*args, **kwargs):  # type: ignore[override]
        raise RuntimeError(
            "inspect-ai is required to construct SciReplicBench agents."
        ) from _INSPECT_IMPORT_ERROR

try:
    from .tools import guarded_bash, scratchpad, workspace_text_file
    from .scorers import rubric_tree_scorer
    from .workspace import rewrite_workspace_paths, workspace_root
except ImportError:  # pragma: no cover - file-based Inspect loading fallback
    PACKAGE_PARENT = Path(__file__).resolve().parent.parent
    if str(PACKAGE_PARENT) not in sys.path:
        sys.path.insert(0, str(PACKAGE_PARENT))
    from scireplicbench.tools import guarded_bash, scratchpad, workspace_text_file
    from scireplicbench.scorers import rubric_tree_scorer
    from scireplicbench.workspace import rewrite_workspace_paths, workspace_root

_JUDGE_MODEL_ENV = "SCIREPLICBENCH_JUDGE_MODEL"
_SANDBOX_TYPE_ENV = "SCIREPLICBENCH_SANDBOX_TYPE"
_SANDBOX_CONFIG_ENV = "SCIREPLICBENCH_SANDBOX_CONFIG"

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PAPERS_DIR = PROJECT_ROOT / "papers"
COMPOSE_FILE = PROJECT_ROOT / "environments" / "compose.yaml"
COMPOSE_TEMPLATE = "compose.{paper_id}.yaml"
COMPOSE_VARIANT_TEMPLATE = "compose.{paper_id}.{variant}.yaml"
GENERIC_VARIANT_TEMPLATE = "compose.{variant}.yaml"
COMPOSE_OVERRIDE_ENV = "SCIREPLICBENCH_COMPOSE_FILE"
ENV_VARIANT_ENV = "SCIREPLICBENCH_ENV_VARIANT"
STARTER_MODE_ENV = "SCIREPLICBENCH_STARTER_MODE"

DEFAULT_MESSAGE_LIMIT = 60
DEFAULT_TIME_LIMIT_SECONDS = 90 * 60
DEFAULT_WORKING_LIMIT_SECONDS = 90 * 60


def available_paper_ids() -> list[str]:
    """Return paper ids that have task manifests."""

    return sorted(
        path.parent.name for path in PAPERS_DIR.glob("*/task.json") if path.is_file()
    )


def load_task_records(paper_id: str) -> list[dict[str, Any]]:
    """Load one or more task records for a paper."""

    manifest_path = PAPERS_DIR / paper_id / "task.json"
    payload = json.loads(manifest_path.read_text())
    if isinstance(payload, dict):
        payload = [payload]
    if not isinstance(payload, list) or not payload:
        raise ValueError(f"Task manifest for {paper_id} must be a non-empty JSON object/list.")
    return payload


def compose_file_for_paper(paper_id: str) -> Path:
    """Return the docker compose file for a paper-specific sandbox image."""

    compose_override = os.getenv(COMPOSE_OVERRIDE_ENV, "").strip()
    if compose_override:
        override_path = Path(compose_override).expanduser()
        if not override_path.is_absolute():
            override_path = (PROJECT_ROOT / override_path).resolve()
        return override_path

    variant = os.getenv(ENV_VARIANT_ENV, "").strip()
    candidate_paths: list[Path] = []
    if variant:
        candidate_paths.extend(
            [
                PROJECT_ROOT
                / "environments"
                / COMPOSE_VARIANT_TEMPLATE.format(paper_id=paper_id, variant=variant),
                PROJECT_ROOT
                / "environments"
                / GENERIC_VARIANT_TEMPLATE.format(variant=variant),
            ]
        )

    candidate_paths.extend(
        [
            PROJECT_ROOT / "environments" / COMPOSE_TEMPLATE.format(paper_id=paper_id),
            COMPOSE_FILE,
        ]
    )

    for compose_file in candidate_paths:
        if compose_file.exists():
            return compose_file
    return COMPOSE_FILE


def sandbox_type() -> str:
    """Return the Inspect sandbox backend for paper tasks."""

    return os.getenv(_SANDBOX_TYPE_ENV, "docker").strip() or "docker"


def sandbox_config_for_paper(paper_id: str) -> str | None:
    """Return backend-specific sandbox config for paper tasks."""

    sandbox_config = os.getenv(_SANDBOX_CONFIG_ENV, "").strip()
    if sandbox_config:
        return sandbox_config
    if sandbox_type() == "docker":
        return str(compose_file_for_paper(paper_id))
    return None


def sandbox_spec_for_paper(paper_id: str) -> str | tuple[str, str]:
    """Return an Inspect sandbox spec for a paper task."""

    backend = sandbox_type()
    config = sandbox_config_for_paper(paper_id)
    if config is None:
        return backend
    return (backend, config)


def starter_mode() -> str:
    """Return how paper starter files should be exposed to the agent."""

    raw = os.getenv(STARTER_MODE_ENV, "seed").strip().lower().replace("-", "_")
    aliases = {
        "": "seed",
        "on": "seed",
        "copy": "seed",
        "seed": "seed",
        "seeded": "seed",
        "available": "available",
        "bundle": "available",
        "bundle_only": "available",
        "off": "off",
        "none": "off",
        "no": "off",
        "false": "off",
        "disabled": "off",
        "unassisted": "off",
    }
    if raw not in aliases:
        raise ValueError(
            f"{STARTER_MODE_ENV} must be one of seed, available, or off; got {raw!r}"
        )
    return aliases[raw]


def _starter_files_are_staged() -> bool:
    return starter_mode() in {"seed", "available"}


def _starter_is_seeded(record: dict[str, Any]) -> bool:
    return starter_mode() == "seed" and bool(record.get("seed_submission_from_starter"))


def _should_stage_bundle_file(local_path: Path, paper_dir: Path) -> bool:
    """Skip VCS internals that are irrelevant inside the sandbox."""

    relative_path = local_path.relative_to(paper_dir)
    relative_parts = relative_path.parts
    relative_posix = relative_path.as_posix()
    if relative_parts[:1] == ("starter",) and not _starter_files_are_staged():
        return False
    if ".git" in relative_parts:
        return False
    if "reference_outputs" in relative_parts:
        return False
    if "__pycache__" in relative_parts or local_path.suffix == ".pyc":
        return False
    if paper_dir.name == "genelab_benchmark":
        raw_prefix = ("data", "raw", "GeneLab_benchmark")
        task_prefix = ("data", "raw", "GeneLab_benchmark", "tasks")
        if (
            relative_posix.startswith("data/huggingface_dataset/v4/")
            or relative_posix.startswith("data/huggingface_dataset/v5/")
            or relative_posix.startswith("data/huggingface_dataset/v6/")
            or relative_posix.startswith("data/raw/GeneLab_benchmark/evaluation/")
            or relative_posix.startswith("data/raw/GeneLab_benchmark/processed/")
            or relative_posix.startswith("data/raw/GeneLab_benchmark/docs/")
            or relative_posix.startswith("data/raw/GeneLab_benchmark/figures/")
        ):
            return False
        if relative_parts[:3] == raw_prefix:
            if relative_parts[:4] != task_prefix:
                return False
        if relative_parts[:4] == task_prefix:
            if len(relative_parts) == 4:
                return False
            task_group = relative_parts[4]
            filename = relative_parts[-1]
            if task_group == "README.md" or not task_group.startswith("A"):
                return False
            if not (paper_dir / "data" / "huggingface_dataset" / task_group).is_dir():
                return False
            if filename in {
                "selected_genes.txt",
                "fold_info.json",
                "task_info.json",
                "geneformer_v1_tokenize_summary.json",
            }:
                return False
    return True


def _paper_bundle_file_map(
    paper_id: str,
    *,
    backend: str | None = None,
    root: str | None = None,
) -> dict[str, str]:
    paper_dir = PAPERS_DIR / paper_id
    if not paper_dir.exists():
        raise FileNotFoundError(f"Unknown paper id: {paper_id}")

    files: dict[str, str] = {}
    backend = backend or sandbox_type()
    root = root or workspace_root()
    for local_path in sorted(path for path in paper_dir.rglob("*") if path.is_file()):
        if not _should_stage_bundle_file(local_path, paper_dir):
            continue
        relative = local_path.relative_to(paper_dir).as_posix()
        target = f"{root}/input/paper_bundle/{relative}"
        if backend == "docker":
            files[f"agent:{target}"] = str(local_path)
            files[f"reproducer:{target}"] = str(local_path)
        else:
            files[target] = str(local_path)
    return files


def _required_output_parent_dirs(record: dict[str, Any], *, root: str) -> list[str]:
    """Return output parent directories that should exist before agent execution."""

    directories = {
        f"{root}/input/paper_bundle",
        f"{root}/submission",
        f"{root}/output/agent",
        f"{root}/output/reproducer",
        f"{root}/logs",
    }
    for output in record.get("required_outputs", []):
        path = rewrite_workspace_paths(str(output), root=root).rstrip("/")
        if "/" not in path:
            continue
        directories.add(path.rsplit("/", 1)[0])
    return sorted(directories)


def _sample_setup_script(record: dict[str, Any]) -> str:
    root = workspace_root()
    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "",
    ]
    lines.extend(f"mkdir -p {directory}" for directory in _required_output_parent_dirs(record, root=root))
    if _starter_is_seeded(record):
        lines.extend(
            [
                "",
                f"if [ -d {root}/input/paper_bundle/starter ]; then",
                f"  cp -R {root}/input/paper_bundle/starter/. {root}/submission/",
                f"  chmod 0555 {root}/submission/run.sh || true",
                "fi",
            ]
        )
    lines.extend(["", f"chmod -R a+rX {root}/input || true"])
    return "\n".join(lines) + "\n"


def _bullet_block(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def _starter_block(record: dict[str, Any]) -> str:
    starter_files = record.get("starter_files", [])
    if not starter_files:
        return ""
    root = workspace_root()
    mode = starter_mode()
    if mode == "off":
        paper_id = str(record.get("paper_id", ""))
        paper_notes: list[str] = [
            "This run is intentionally unassisted: no starter implementation is staged or seeded into the sandbox.",
            f"Create your own saved workflow under `{root}/submission`, including `{root}/submission/run.sh`, before executing it.",
        ]
        if paper_id == "squidpy_spatial":
            paper_notes.extend(
                [
                    "Use the benchmark-pinned offline Squidpy cache paths and the public custom ligand-receptor panel from the paper bundle.",
                    f"Read `{root}/input/paper_bundle/output_contract.md` before writing code; it is the public artifact/schema contract, not a hidden reference.",
                    "For the benchmark-pinned objects, use Visium `adata.obs['cluster']` as the cluster key and seqFISH `adata.obs['celltype_mapped_refined']` as the cluster key; `cluster_labels`, `cell_type`, and `clusters` are not valid Visium obs columns.",
                    "Use public Squidpy APIs such as `sq.gr.spatial_neighbors`, `sq.gr.nhood_enrichment`, `sq.gr.centrality_scores`, `sq.gr.co_occurrence`, `sq.gr.interaction_matrix`, `sq.gr.spatial_autocorr`, `sq.gr.ripley`, `sq.im.segment`, `sq.im.calculate_image_features`, and `sq.gr.ligrec`.",
                    "Do not use nonexistent helper namespaces such as `sq.graphtools`, `sq.stats.moran`, or `ImageContainer.compute_and_save`.",
                    "Call `sq.gr.spatial_neighbors` before graph statistics, but do not pass `cluster_key` to it: use `sq.gr.spatial_neighbors(visium, spatial_key='spatial', coord_type='grid', n_neighs=6, n_rings=1)` and `sq.gr.spatial_neighbors(seqfish, spatial_key='spatial', coord_type='generic', n_neighs=6)`.",
                    "Use `cluster_key=...`, not `key=...`, for graph statistics: `sq.gr.nhood_enrichment(..., cluster_key='cluster', copy=True)`, `sq.gr.centrality_scores(..., cluster_key='cluster', copy=True)`, `sq.gr.interaction_matrix(..., cluster_key='cluster', normalized=False, copy=True)`, and `sq.gr.co_occurrence(..., cluster_key='cluster', interval=..., copy=True)`.",
                    "If you pass `connectivity_key`, pass the base key `connectivity_key='spatial'`, not `connectivity_key='spatial_connectivities'`; Squidpy appends `_connectivities` internally, so `spatial_connectivities` becomes the invalid lookup `spatial_connectivities_connectivities`.",
                    "`sq.gr.nhood_enrichment(..., copy=True)` returns `(zscore, count)`, `sq.gr.co_occurrence(..., copy=True)` returns `(cooccurrence, intervals)`, and `sq.gr.interaction_matrix(..., copy=True)` returns a NumPy array; convert these arrays to long pandas TSVs before writing instead of calling `.to_csv()` on the raw tuple or array.",
                    "For square cluster-by-cluster arrays, flatten with explicit cluster labels in matching nested loops; do not use `np.column_stack` on two square matrices and then claim it has only `zscore` and `count` columns.",
                    "For spatial autocorrelation, use `sq.gr.spatial_autocorr(..., mode='moran', genes=None, n_perms=None, copy=True)` and `mode='geary'`; normalize exported statistic columns to `moran_i` and `geary_c` in ranked TSVs.",
                    "For seqFISH Ripley statistics, use the seqFISH object, not Visium: `sq.gr.ripley(seqfish, cluster_key='celltype_mapped_refined', mode='L', copy=True)`, then export the returned `L_stat` table rather than inventing a separate distance routine.",
                    "For image features, attempt watershed segmentation FIRST with `sq.im.segment(image, layer='image', method='watershed', channel=0, layer_added='segmented_watershed', copy=False)` so the segmentation layer exists and `sq.im.segment` appears in the saved source. Skipping `sq.im.segment` entirely will fail both `code_development/.../compute_segmentation_features` and `execution/.../segmentation_features_written` even when the rest of the pipeline succeeds.",
                    "Use the benchmark-pinned `features_kwargs` so the resulting matrix matches the hidden reference's 26-column shape: `sq.im.calculate_image_features(adata, image, layer='image', features=['histogram', 'segmentation', 'summary', 'texture'], features_kwargs={'histogram': {'channels': [0], 'bins': 4}, 'segmentation': {'label_layer': 'segmented_watershed', 'props': ['label', 'area', 'mean_intensity'], 'channels': [0]}, 'summary': {'channels': [0, 1, 2]}, 'texture': {'channels': [0], 'props': ['contrast', 'homogeneity'], 'distances': [1], 'angles': [0]}}, copy=True)`; defaults expand texture into many distance/angle combinations and produce ~100+ off-shape columns that will fail `image_feature_matrix_dimensionality_band` and `texture_feature_rank_overlap`.",
                    "Do not let image feature extraction block final scoring: wrap each long image call with a real Python timeout such as `signal.alarm(...)`; checking elapsed time after `sq.im.segment` returns is not enough because it cannot interrupt a hanging call.",
                    "If `sq.im.segment` watershed itself raises a TimeoutError or other failure, the `sq.im.segment` call still belongs in the saved source and `feature_families` should record what actually executed (e.g. `['histogram', 'summary', 'texture']`); set `segmentation_feature_count: 0` honestly. Do NOT omit the `sq.im.segment` call from the source just because it might fail, and do NOT write a placeholder `feature_summary.json` with `feature_families: ['fallback']`, `status: 'fallback_placeholder'`, fake `fallback_feature_*` columns, or every observation in cluster `0`.",
                    "`feature_summary.json` must report `n_features >= 20` from the executed recipe and an honest `feature_families` list of the families that actually executed; never list `'fallback'` as a feature family.",
                    "`feature_clusters.tsv` must have at least 3 distinct `image_cluster` values with no single cluster containing more than 60% of observations; if KMeans on the real feature matrix collapses, increase `n_clusters` or drop near-constant columns rather than emitting a single-cluster placeholder.",
                    "`feature_ranking.tsv` rows must come from the executed feature columns (e.g. `texture_ch-0_contrast_dist-1_angle-0.00`, `summary_ch-2_quantile-0.9`, `histogram_ch-0_bin-1`); placeholder names like `fallback_feature_0` will fail every image-feature result-match leaf.",
                    "For ligand-receptor analysis, read `/workspace/input/paper_bundle/data/ligrec_interactions.tsv` and call `sq.gr.ligrec(..., cluster_key='cluster', interactions=..., threshold=0.01, n_perms=10, seed=1, copy=True, use_raw=False)` for the bounded unassisted pass; only rerun with `n_perms=100` after every required artifact already exists, including `visualizations/report.html` and `output/submission_manifest.json`.",
                    "For Squidpy functions that normally write into `adata.uns`, either pass `copy=True` when supported or export the documented result from `adata.uns`; do not assume every function returns a pandas DataFrame by default.",
                    "Generate `dataset_manifest.json` from executed code, not by hand, using the required nested schema: `{'datasets': {'visium_hne_adata': {'shape': list(visium.shape), 'cluster_key': 'cluster', 'cluster_labels': [...]}, 'seqfish': {'shape': list(seqfish.shape), 'cluster_key': 'celltype_mapped_refined', 'cluster_labels': [...]}, 'visium_hne_image': {'sizes': {'y': ..., 'x': ..., 'channels': ...}}}}`.",
                    "Generate `spatial_graph_metrics.json` with nested graph keys, for example `{'visium': {'spatial_neighbors': {'edges': int(visium.obsp['spatial_connectivities'].nnz)}}, 'seqfish': {'spatial_neighbors': {'edges': int(seqfish.obsp['spatial_connectivities'].nnz)}}}` after running `spatial_neighbors` on both datasets.",
                    "The scorer reads those exact JSON paths, so flat payloads such as `{'visium_hne_adata': [...]}` or `{'edges': 15580}` are not equivalent to the required nested artifact schema.",
                    "Use exact graph table keys: nhood and interaction matrix `pair_key` should be `cluster_1|cluster_2`, cooccurrence `pair_key` should be `cluster_1->cluster_2`, and nhood top ranks should omit or demote diagonal/self pairs.",
                    "For cooccurrence, prefer `sq.gr.co_occurrence(..., interval=25, copy=True)` and export the returned intervals; do not replace the benchmark-standard radii with an arbitrary `np.linspace(...)`.",
                    "For Ripley L, flatten `ripley['L_stat']`, rename `bins` to `radius`, the seqFISH cluster column to `label`, and `stats` to `ripley_l`, then compute `radius_index` with `groupby('label').cumcount()`.",
                    "Write `spatial_stats/svg_summary.json` with exact keys `method`, `fdr_column`, `fdr_threshold`, and `significant_gene_count`; aliases such as `significant_moran_fdr_0_05` are less likely to receive deterministic credit.",
                    f"Create required output directories with `mkdir -p` or `Path(...).mkdir(parents=True, exist_ok=True)` before writing TSV, JSON, SVG, or HTML artifacts under `{root}/output/agent`.",
                    "At the top of both `run.sh` and the Python workflow, create every required subdirectory (`neighborhood`, `autocorrelation`, `spatial_stats`, `image_features`, `interactions`, and `visualizations`) before the first `to_csv()` or `open()` call; a missing subdirectory can erase otherwise valid work.",
                    "Write durable cheap artifacts first, then continue to heavier steps: dataset manifest, graph metrics, autocorrelation/neighborhood TSVs, spatial statistics, bounded image features, visualizations, submission manifest, and finally ligand-receptor tables. Flush each artifact as soon as it is computed so partial scientific progress survives if later image or ligand-receptor steps are slow.",
                    "Do not postpone `dataset_manifest.json` to the bottom of the script; write it immediately after loading the datasets, before any graph, autocorrelation, image, or ligand-receptor call can fail.",
                    "Write `spatial_graph_metrics.json` immediately after `sq.gr.spatial_neighbors` by counting `adata.obsp['spatial_connectivities'].nnz` for each dataset.",
                    "Use stable TSV schemas: ranked graph/statistic tables should include explicit `rank` and key columns such as `gene`, `cluster_1`, `cluster_2`, `pair_key`, `obs_id`, or `interaction_key` plus the statistic columns needed by the task brief.",
                    "Do not let ligand-receptor permutations block final scoring: create `visualizations/spatial_stats_plot.svg`, `visualizations/marker_localization.svg`, `visualizations/report.html`, and `output/submission_manifest.json` before any long `sq.gr.ligrec` refinement.",
                    "Make visualizations recognizable to deterministic checks: `spatial_stats_plot.svg` should contain `<svg` and `Top Moran`, `marker_localization.svg` should contain `<svg` and `Marker localization`, and `report.html` should contain `Squidpy spatial reviewer-path report`, `spatial_stats_plot.svg`, and `marker_localization.svg`.",
                    "For `ligrec_ranked.tsv`, sort the executed custom-panel interaction table by mean descending and set `interaction_key` exactly as `source|target|cluster_1->cluster_2`; do not collapse it to `source_target` or a cluster-free key.",
                    "For `ligrec_summary.json`, record `n_input_pairs`, the actual `n_perms`, `significant_count_p_le_0_05`, and any bounded-timeout status. Treat `n_perms=100` as optional refinement, not as the first-pass path.",
                    "Do not leave placeholder sections for ligand-receptor outputs or visualizations; if a heavy step is too slow, write a small executed summary and simple SVG/HTML based on the completed tables so the artifact contract remains concrete.",
                    "Write `submission_manifest.json` with `json.dump` as valid JSON only; do not include `//` comments, trailing commas, or escaped literal `\\n` strings pretending to be JSON formatting.",
                    f"Put the analysis Python in a real `{root}/submission/main_analysis.py` or `{root}/submission/squidpy_spatial_workflow.py` file; do not embed the substantive workflow as a Python heredoc inside `run.sh`.",
                    "Do not hand-write final result artifacts directly from the prompt; generate them by executing the saved workflow from `run.sh`.",
                    "Execute Python scripts with `python script.py`; do not run `.py` files directly through `bash`.",
                    "Execute the shell launcher with `bash run.sh`; never run `python run.sh`, because `run.sh` is shell syntax and Python will report a misleading `SyntaxError`.",
                    "Before running the workflow, run `python -m py_compile main_analysis.py` or `python -m py_compile squidpy_spatial_workflow.py` and fix any syntax error by rewriting the full file.",
                    "After a failed execution, overwrite the affected source file cleanly instead of appending a second workflow below stale code.",
                    "When repairing a failed workflow, rewrite the full Python file with a minimal durable version; do not append diagnostic print blocks below the first failing block, because the stale failing code will still run first.",
                    f"After your first saved workflow run, inspect the concrete artifacts under `{root}/output/agent` and repair missing schemas before submitting.",
                    "A result-match-ready Squidpy submission with no non-document output artifacts will fail precheck before judge-mediated scoring.",
                ]
            )
        return dedent(
            f"""\

            Starter policy:
            {_bullet_block(paper_notes)}
            """
        )

    bullets = _bullet_block([f"`{root}/input/paper_bundle/{path}`" for path in starter_files])
    common_notes = [
        f"For this paper, prefer copying/adapting these starter files into the matching paths under `{root}/submission` rather than starting from a blank script.",
        f"After the first run, inspect the concrete generated artifacts under `{root}/output/agent` before deciding what still needs work.",
    ]
    if mode == "seed":
        common_notes.extend(
            [
                f"Keep the seeded `{root}/submission/run.sh` launcher intact and put substantive edits in Python source files under `{root}/submission` instead of rewriting the launcher from scratch.",
                "The seeded launcher includes required artifact checks, a primary-script timeout, and fallback to the pristine staged starter; preserve those guardrails if you inspect or lightly edit `run.sh`.",
            ]
        )
    else:
        common_notes.append(
            f"These starter files are staged for reference only; they are not pre-copied into `{root}/submission`."
        )
    paper_id = str(record.get("paper_id", ""))
    paper_notes: list[str] = []
    if _starter_is_seeded(record):
        paper_notes.append(
            f"For this paper, the same baseline files are already seeded under `{root}/submission`, so run them in place before deciding what to rewrite."
        )
    if paper_id == "genelab_benchmark":
        paper_notes.extend(
            [
                "For GeneLab, these files already implement a runnable reviewer-path baseline, so preserve the fold discovery and structured outputs unless you have a better benchmark-consistent replacement.",
                f"The benchmark tools may reject attempts to overwrite the seeded GeneLab `run.sh`; edit `{root}/submission/main_analysis.py` or add helper source files instead.",
                "Do not replace the runnable GeneLab baseline with a shorter placeholder or file-enumeration stub; if you edit it, preserve the required output writers and the saved launcher workflow.",
                f"For GeneLab, run `bash {root}/submission/run.sh` as the canonical saved workflow before adding optional extensions.",
                "Do not add an alternate GeneLab driver that bypasses the seeded launcher or leaves the canonical output families stale.",
                "The benchmark tools may reject unhooked post-success sidecars that mutate the submission after the canonical workflow already produced rich outputs.",
                "once that structured manifest exists, leave it intact unless you are replacing it with an equally complete rerun manifest from the canonical workflow.",
            ]
        )
    elif paper_id == "squidpy_spatial":
        paper_notes.extend(
            [
                f"For Squidpy, do not spend the first turns summarizing every package file; the seeded starter is already present, so your first substantive tool action should be `bash {root}/submission/run.sh`.",
                "For Squidpy, the starter is an offline reviewer-path workflow for the staged Visium H&E and seqFISH cache; execute it once before replacing any analysis code.",
                f"For Squidpy, run `bash {root}/submission/run.sh` as the canonical saved workflow so the required output families are created under `{root}/output/agent`.",
                f"After that first run, inspect `{root}/output/agent/dataset_manifest.json`, `{root}/output/agent/spatial_graph_metrics.json`, and one or two TSV summaries rather than reading every long JSON/rubric section.",
                "If you improve the workflow, preserve the output filenames and schemas used by the starter: dataset manifest, graph metrics, neighborhood TSVs, autocorrelation TSVs, spatial-statistics TSV/JSON files, image-feature TSV/JSON files, ligand-receptor TSV/JSON files, and the submission manifest.",
                f"The benchmark tools may reject attempts to overwrite the seeded Squidpy `{root}/submission/main_analysis.py` with a thin partial script; add helper files or preserve the full starter workflow.",
                "Do not switch Squidpy dataset loading back to live downloads; use the benchmark-pinned cache paths from the reviewer path.",
                "A result-match-ready Squidpy submission with no non-document output artifacts will fail precheck before judge-mediated scoring.",
            ]
        )
    return dedent(
        f"""\

        Starter files available for this paper:
        {bullets}
        {_bullet_block(common_notes + paper_notes)}
        """
    )


def build_sample_input(record: dict[str, Any]) -> str:
    """Render the agent-facing prompt for a single manifest record."""

    root = workspace_root()
    focus = _bullet_block(record["analysis_focus"])
    outputs = _bullet_block(
        [rewrite_workspace_paths(str(output), root=root) for output in record["required_outputs"]]
    )
    success_checks = _bullet_block(record["success_checks"])
    public_sources = _bullet_block(record["public_data_sources"])
    starter_block = _starter_block(record)
    primary_output_root = rewrite_workspace_paths(str(record["primary_output_root"]), root=root)
    reviewer_path = rewrite_workspace_paths(str(record["reviewer_path"]), root=root)

    return dedent(
        f"""\
        You are reproducing the computational-biology benchmark task `{record["paper_id"]}`:
        {record["paper_title"]}.

        Start by reading these benchmark package files inside the sandbox:
        - `{root}/input/paper_bundle/paper.md`
        - `{root}/input/paper_bundle/rubric.json`
        - `{root}/input/paper_bundle/task.json`
        - `{root}/input/paper_bundle/novel_contrast.json`
        - `{root}/input/paper_bundle/output_contract.md` if present
        - `{root}/input/paper_bundle/method_equivalence.md` if present
        - `{root}/input/paper_bundle/data/prepare_data.sh` if the required public inputs have not been staged yet

        Objective:
        {record["task_brief"]}

        Analysis focus:
        {focus}

        Public data / code sources expected by this paper package:
        {public_sources}
        {starter_block}

        Reproducibility contract:
        - Write agent-authored scripts, notebooks, configs, and rerun instructions under `{root}/submission`.
        - If `{root}/submission/run.sh` is a required output, use it as a thin launcher that calls substantive source files under `{root}/submission` (for example `.py`, `.R`, or notebook-backed workflows) rather than placing the whole analysis or planning notes directly in `run.sh`.
        - Make launcher scripts location-independent by changing to their own directory first, for example `cd "$(dirname "$0")"`, before calling saved analysis files.
        - Put the main analysis logic in saved source files under `{root}/submission` before running it. Work that exists only inside ad-hoc `python()` tool calls or scratchpad notes will not survive the reproducer pass and should be treated as disposable exploration only.
        - Prefer the `workspace_text_file` tool for exact multi-line source files, launcher scripts, README files, manifests, and small text outputs. Use `bash` for directory creation and program execution, not fragile shell-quoted file bodies.
        - When writing multi-line code or documentation files, prefer heredocs or another method that preserves real newlines. Avoid `echo "...\\n..."` patterns for substantive files because they often create broken one-line outputs.
        - Before you submit, execute the saved workflow from `{root}/submission` (for example via `run.sh` or the project entrypoint), inspect the resulting files under `{primary_output_root}`, and make sure they contain real outputs rather than empty placeholders.
        - Write analysis outputs from this run under `{primary_output_root}`.
        - Assume a fresh `reproducer` container will later receive `{root}/submission` as a read-only input and will rerun against the same `{root}/input/paper_bundle`.
        - Do not rely on shell history, unstaged temp files, or state outside `{root}/submission` and `{primary_output_root}`.
        - Do not copy scratchpad or planning text into deliverable files; the deliverables must be runnable code or explicit documentation.
        - Do not create empty files with `touch` just to satisfy required outputs. Required outputs should be generated or filled by the saved workflow whenever the task is feasible.
        - If a benchmark-prepared input is missing, stage the workflow honestly and document the remaining gap instead of fabricating results.

        Required outputs:
        {outputs}

        Success checks:
        {success_checks}

        Reviewer path:
        {reviewer_path}

        Held-out anti-memorization target:
        `{record["novel_contrast_id"]}`

        Use the scratchpad tool to keep short working notes when helpful, and finish by writing `{root}/output/submission_manifest.json` that lists the important commands, inputs, and deliverables.
        """
    ).strip()


def record_to_sample(record: dict[str, Any]) -> Sample:
    """Convert a manifest record into an Inspect Sample."""

    paper_id = record["paper_id"]
    metadata = {
        "paper_id": paper_id,
        "paper_title": record["paper_title"],
        "task_manifest": str(PAPERS_DIR / paper_id / "task.json"),
        "cpu_limit": str(record["resource_hints"]["cpu_limit"]),
        "memory_limit": str(record["resource_hints"]["memory_limit"]),
        "novel_contrast_id": record["novel_contrast_id"],
        "starter_mode": starter_mode(),
    }
    return Sample(
        id=record["id"],
        input=build_sample_input(record),
        metadata=metadata,
        files=_paper_bundle_file_map(paper_id),
        setup=_sample_setup_script(record),
    )


def _paper_task(
    paper_id: str,
    *,
    attempts: int = 1,
    message_limit: int | None = None,
    time_limit_seconds: int | None = None,
    working_limit_seconds: int | None = None,
) -> Task:
    records = load_task_records(paper_id)
    dataset = [record_to_sample(record) for record in records]
    first = records[0]
    agent_limits = first.get("agent_limits", {})

    judge_model = os.getenv(_JUDGE_MODEL_ENV, "").strip() or "openai/gpt-4o-mini"
    return Task(
        dataset=dataset,
        solver=react(
            description=(
                "Reproduce a computational-biology paper analysis inside a sandboxed "
                "benchmark environment and leave a rerunnable submission package."
            ),
            tools=[guarded_bash(), python(), scratchpad(), workspace_text_file()],
            attempts=attempts,
        ),
        scorer=rubric_tree_scorer(judge_model=judge_model),
        sandbox=sandbox_spec_for_paper(paper_id),
        message_limit=message_limit or int(
            agent_limits.get("message_limit", DEFAULT_MESSAGE_LIMIT)
        ),
        time_limit=time_limit_seconds
        or int(agent_limits.get("time_limit_minutes", DEFAULT_TIME_LIMIT_SECONDS // 60)) * 60,
        working_limit=working_limit_seconds
        or int(
            agent_limits.get("working_limit_minutes", DEFAULT_WORKING_LIMIT_SECONDS // 60)
        )
        * 60,
    )


@task
def scireplicbench(
    paper_id: str = "inspiration4_multiome",
    attempts: int = 1,
    message_limit: int | None = None,
    time_limit_seconds: int | None = None,
    working_limit_seconds: int | None = None,
) -> Task:
    """Generic entrypoint for a SciReplicBench paper task."""

    if paper_id not in available_paper_ids():
        raise ValueError(
            f"Unknown paper_id '{paper_id}'. Expected one of: {', '.join(available_paper_ids())}"
        )
    return _paper_task(
        paper_id,
        attempts=attempts,
        message_limit=message_limit,
        time_limit_seconds=time_limit_seconds,
        working_limit_seconds=working_limit_seconds,
    )


@task
def inspiration4_multiome(
    attempts: int = 1,
    message_limit: int | None = None,
    time_limit_seconds: int | None = None,
    working_limit_seconds: int | None = None,
) -> Task:
    """Inspect task for the Inspiration4 multimodal paper."""

    return _paper_task(
        "inspiration4_multiome",
        attempts=attempts,
        message_limit=message_limit,
        time_limit_seconds=time_limit_seconds,
        working_limit_seconds=working_limit_seconds,
    )


@task
def squidpy_spatial(
    attempts: int = 1,
    message_limit: int | None = None,
    time_limit_seconds: int | None = None,
    working_limit_seconds: int | None = None,
) -> Task:
    """Inspect task for the Squidpy external-anchor paper."""

    return _paper_task(
        "squidpy_spatial",
        attempts=attempts,
        message_limit=message_limit,
        time_limit_seconds=time_limit_seconds,
        working_limit_seconds=working_limit_seconds,
    )


@task
def genelab_benchmark(
    attempts: int = 1,
    message_limit: int | None = None,
    time_limit_seconds: int | None = None,
    working_limit_seconds: int | None = None,
) -> Task:
    """Inspect task for the GeneLab benchmark paper."""

    return _paper_task(
        "genelab_benchmark",
        attempts=attempts,
        message_limit=message_limit,
        time_limit_seconds=time_limit_seconds,
        working_limit_seconds=working_limit_seconds,
    )


__all__ = [
    "COMPOSE_FILE",
    "COMPOSE_OVERRIDE_ENV",
    "ENV_VARIANT_ENV",
    "STARTER_MODE_ENV",
    "_SANDBOX_CONFIG_ENV",
    "_SANDBOX_TYPE_ENV",
    "compose_file_for_paper",
    "sandbox_config_for_paper",
    "sandbox_spec_for_paper",
    "sandbox_type",
    "starter_mode",
    "PROJECT_ROOT",
    "available_paper_ids",
    "build_sample_input",
    "genelab_benchmark",
    "inspiration4_multiome",
    "load_task_records",
    "record_to_sample",
    "scireplicbench",
    "squidpy_spatial",
]
