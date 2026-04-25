"""Deterministic Inspect probes for scorer-policy validation."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from inspect_ai import Task, task
    from inspect_ai.agent import react
    from inspect_ai.model import ModelOutput
    from inspect_ai.solver import Generate, TaskState, solver
    from inspect_ai.tool import bash, python
    from inspect_ai.util import sandbox
except ModuleNotFoundError as exc:  # pragma: no cover - local fallback for import-only validation
    _INSPECT_IMPORT_ERROR = exc

    @dataclass
    class Task:  # type: ignore[override]
        dataset: list[Any]
        solver: Any
        sandbox: Any = None
        scorer: Any = None
        message_limit: int | None = None
        time_limit: int | None = None
        working_limit: int | None = None

    class TaskState:  # type: ignore[override]
        sample_id: str | None = None
        output: Any = None

    class Generate:  # type: ignore[override]
        pass

    class ModelOutput:  # type: ignore[override]
        completion: str

        def __init__(self, completion: str) -> None:
            self.completion = completion

        @classmethod
        def from_content(cls, model: str, content: str) -> "ModelOutput":
            return cls(content)

    def task(*args, **kwargs):  # type: ignore[override]
        if args and callable(args[0]) and len(args) == 1 and not kwargs:
            return args[0]

        def decorator(func):
            return func

        return decorator

    def solver(*args, **kwargs):  # type: ignore[override]
        if args and callable(args[0]) and len(args) == 1 and not kwargs:
            return args[0]

        def decorator(func):
            return func

        return decorator

    def react(*args, **kwargs):  # type: ignore[override]
        raise RuntimeError(
            "inspect-ai is required to construct SciReplicBench probe agents."
        ) from _INSPECT_IMPORT_ERROR

    def bash(*args, **kwargs):  # type: ignore[override]
        raise RuntimeError(
            "inspect-ai is required to construct SciReplicBench probe agents."
        ) from _INSPECT_IMPORT_ERROR

    def python(*args, **kwargs):  # type: ignore[override]
        raise RuntimeError(
            "inspect-ai is required to construct SciReplicBench probe agents."
        ) from _INSPECT_IMPORT_ERROR

    def sandbox(name: str | None = None):  # type: ignore[override]
        raise RuntimeError(
            "inspect-ai is required to run SciReplicBench probes."
        ) from _INSPECT_IMPORT_ERROR

try:
    from .scorers import rubric_tree_scorer
    from .tasks import PROJECT_ROOT, load_task_records, record_to_sample
except ImportError:  # pragma: no cover - file-based Inspect loading fallback
    import sys

    PACKAGE_PARENT = Path(__file__).resolve().parent.parent
    if str(PACKAGE_PARENT) not in sys.path:
        sys.path.insert(0, str(PACKAGE_PARENT))
    from scireplicbench.scorers import rubric_tree_scorer
    from scireplicbench.tasks import PROJECT_ROOT, load_task_records, record_to_sample


PROBE_PAPER_ID = "evidence_policy_probe"
PROBE_JUDGE_MODEL = "mockllm/model"
PROBE_FAIL_SAMPLE_ID = "evidence_policy_probe_prose_fail"
PROBE_CONTROL_SAMPLE_ID = "evidence_policy_probe_control_pass"
PROBE_SMOKE_COMPOSE = PROJECT_ROOT / "environments" / "compose.smoke.yaml"

PROBE_CODE_QUOTE = "def build_spatial_graph(dataset_path: str) -> dict[str, str]:"
PROBE_README_QUOTE = "README: would compute segmentation features in a future revision."
PROBE_EXECUTION_QUOTE = "command exited with status 0"
PROBE_RESULT_QUOTE = "top20_overlap=0.90"

SQUIDPY_PROBE_PAPER_ID = "squidpy_spatial"
SQUIDPY_PROBE_FAIL_SAMPLE_ID = "squidpy_spatial_evidence_probe_prose_fail"
SQUIDPY_PROBE_CONTROL_SAMPLE_ID = "squidpy_spatial_evidence_probe_control_pass"
SQUIDPY_PROBE_COMPOSE = PROJECT_ROOT / "environments" / "compose.squidpy_spatial.yaml"
SQUIDPY_AGENT_PROBE_TASK_NAME = "squidpy_evidence_policy_agent_probe"
SQUIDPY_AGENT_PROBE_DEFAULT_MODEL = "openai/gpt-4o-mini"

SQUIDPY_SEGMENTATION_README_QUOTE = (
    'README: would compute segmentation-derived regionprops with '
    'sq.im.calculate_image_features(..., features="segmentation").'
)
SQUIDPY_SEGMENTATION_CODE_QUOTE = (
    'sq.im.calculate_image_features(img, adata, features="segmentation", '
    'key_added="segmentation_features")'
)
SQUIDPY_EXECUTION_INVALID_QUOTE = "/workspace/output/agent/spatial_graph_metrics.json"
SQUIDPY_EXECUTION_VALID_QUOTE = "sq.datasets.visium_hne_adata() completed with status 0"
SQUIDPY_RESULT_QUOTE = "geary_top20_rbo=0.90"
SQUIDPY_FALLBACK_FAIL_QUOTE = "/workspace/submission/pipeline.py"

SQUIDPY_TARGET_LEAF_IDS = (
    "squidpy_spatial/code_development/image_features_segmentation/compute_segmentation_features",
    "squidpy_spatial/execution/datasets_and_containers/visium_dataset_executes",
    "squidpy_spatial/result_match/spatial_statistics/geary_rank_overlap_threshold",
)


@dataclass(frozen=True)
class ProbeCase:
    sample_id: str
    artifact_map: dict[str, str]


def _squidpy_segmentation_readme_variants() -> tuple[str, ...]:
    canonical = SQUIDPY_SEGMENTATION_README_QUOTE
    single_quoted = canonical.replace('features="segmentation"', "features='segmentation'")
    if single_quoted == canonical:
        return (canonical,)
    return (canonical, single_quoted)


def _probe_case(sample_id: str) -> ProbeCase:
    if sample_id == PROBE_FAIL_SAMPLE_ID:
        return ProbeCase(
            sample_id=sample_id,
            artifact_map={
                "/workspace/submission/README.md": (
                    "# Probe README\n\n"
                    f"{PROBE_README_QUOTE}\n"
                    "The plan also claims the overlap metric already looks correct.\n"
                ),
                "/workspace/submission/pipeline.py": (
                    "def stage_only_pipeline(dataset_path: str) -> dict[str, str]:\n"
                    "    mode = 'stage_only'\n"
                    "    return {'dataset_path': dataset_path, 'mode': mode}\n\n"
                    f"# {PROBE_RESULT_QUOTE}\n"
                ),
                "/workspace/output/agent/results.txt": "",
            },
        )
    if sample_id == PROBE_CONTROL_SAMPLE_ID:
        return ProbeCase(
            sample_id=sample_id,
            artifact_map={
                "/workspace/submission/README.md": (
                    "# Probe README\n\n"
                    "Control case: implementation and output artifacts contain the real evidence.\n"
                ),
                "/workspace/submission/pipeline.py": (
                    f"{PROBE_CODE_QUOTE}\n"
                    "    graph_mode = 'grid'\n"
                    "    return {'dataset_path': dataset_path, 'graph_mode': graph_mode}\n"
                ),
                "/workspace/output/agent/results.log": (
                    "starting probe workflow\n"
                    f"{PROBE_EXECUTION_QUOTE}\n"
                ),
                "/workspace/output/agent/metrics.txt": f"{PROBE_RESULT_QUOTE}\n",
            },
        )
    raise ValueError(f"Unknown probe sample id: {sample_id}")


def _squidpy_probe_case(sample_id: str) -> ProbeCase:
    if sample_id == SQUIDPY_PROBE_FAIL_SAMPLE_ID:
        return ProbeCase(
            sample_id=sample_id,
            artifact_map={
                "/workspace/submission/README.md": (
                    "# Squidpy Probe README\n\n"
                    f"{SQUIDPY_SEGMENTATION_README_QUOTE}\n"
                    "The staged workflow also claims that the Visium dataset should load and that "
                    "the hidden Geary overlap target is already in range.\n"
                ),
                "/workspace/submission/pipeline.py": (
                    "def stage_visium_probe(dataset_path: str) -> dict[str, str]:\n"
                    "    dataset_name = 'visium_hne_adata'\n"
                    "    return {'dataset_path': dataset_path, 'dataset_name': dataset_name}\n\n"
                    f"# {SQUIDPY_RESULT_QUOTE}\n"
                ),
                SQUIDPY_EXECUTION_INVALID_QUOTE: "",
            },
        )
    if sample_id == SQUIDPY_PROBE_CONTROL_SAMPLE_ID:
        return ProbeCase(
            sample_id=sample_id,
            artifact_map={
                "/workspace/submission/README.md": (
                    "# Squidpy Probe README\n\n"
                    "Control case: the Squidpy-targeted evidence is present in code and output files.\n"
                ),
                "/workspace/submission/pipeline.py": (
                    "import squidpy as sq\n\n"
                    "def build_probe_features(img, adata):\n"
                    f'    {SQUIDPY_SEGMENTATION_CODE_QUOTE}\n'
                    "    return adata\n"
                ),
                "/workspace/output/agent/run.log": (
                    "starting squidpy probe\n"
                    f"{SQUIDPY_EXECUTION_VALID_QUOTE}\n"
                ),
                "/workspace/output/agent/geary_metrics.txt": f"{SQUIDPY_RESULT_QUOTE}\n",
            },
        )
    raise ValueError(f"Unknown squidpy probe sample id: {sample_id}")


def mock_probe_judge_completion(prompt: str) -> str:
    """Return a deterministic judge payload for the probe task."""

    leaf_match = re.search(r"- leaf_id: ([^\n]+)", prompt)
    if leaf_match is None:
        raise ValueError("Probe judge prompt did not contain a leaf_id.")
    leaf_id = leaf_match.group(1).strip()

    is_fail_case = PROBE_README_QUOTE in prompt
    if leaf_id.endswith("/implements_pipeline"):
        evidence_quote = PROBE_README_QUOTE if is_fail_case else PROBE_CODE_QUOTE
        reality = (
            "Submission stages a non-trivial Python file but only README prose is cited as proof."
            if is_fail_case
            else "Submission includes concrete implementation code in pipeline.py."
        )
    elif leaf_id.endswith("/runtime_completed"):
        evidence_quote = "/workspace/output/agent/results.txt" if is_fail_case else PROBE_EXECUTION_QUOTE
        reality = (
            "Execution is implied by an output-path listing only."
            if is_fail_case
            else "Runtime text is captured in a non-README output log."
        )
    elif leaf_id.endswith("/overlap_metric_reported"):
        evidence_quote = PROBE_RESULT_QUOTE
        reality = (
            "The overlap metric is asserted from the submission side rather than emitted from outputs."
            if is_fail_case
            else "The overlap metric is emitted from an output artifact."
        )
    else:
        raise ValueError(f"Unexpected probe leaf_id: {leaf_id}")

    payload = {
        "leaf_id": leaf_id,
        "expectations": "Probe leaf should pass when the cited evidence satisfies the benchmark policy.",
        "reality": reality,
        "evidence_quote": evidence_quote,
        "score": 1,
    }
    return json.dumps(payload)


def mock_squidpy_probe_judge_completion(prompt: str) -> str:
    """Return deterministic judge payloads for the real-paper Squidpy probe."""

    leaf_match = re.search(r"- leaf_id: ([^\n]+)", prompt)
    if leaf_match is None:
        raise ValueError("Squidpy probe judge prompt did not contain a leaf_id.")
    leaf_id = leaf_match.group(1).strip()

    fail_readme_quote = next(
        (variant for variant in _squidpy_segmentation_readme_variants() if variant in prompt),
        None,
    )
    is_fail_case = fail_readme_quote is not None
    if leaf_id == SQUIDPY_TARGET_LEAF_IDS[0]:
        evidence_quote = (
            fail_readme_quote if is_fail_case else SQUIDPY_SEGMENTATION_CODE_QUOTE
        )
        reality = (
            "The sample stages a non-trivial Python file, but the passing evidence still comes from README prose."
            if is_fail_case
            else "The sample cites a concrete Squidpy segmentation-feature call from pipeline.py."
        )
        score = 1
    elif leaf_id == SQUIDPY_TARGET_LEAF_IDS[1]:
        evidence_quote = (
            SQUIDPY_EXECUTION_INVALID_QUOTE if is_fail_case else SQUIDPY_EXECUTION_VALID_QUOTE
        )
        reality = (
            "The sample cites only an output-file path, not runtime text or file contents."
            if is_fail_case
            else "The sample cites runtime text from a non-README output log that names the exact Visium loader."
        )
        score = 1
    elif leaf_id == SQUIDPY_TARGET_LEAF_IDS[2]:
        evidence_quote = SQUIDPY_RESULT_QUOTE
        reality = (
            "The sample asserts the Geary overlap target from a submission-side comment."
            if is_fail_case
            else "The sample cites the Geary overlap target from an output artifact."
        )
        score = 1
    else:
        evidence_quote = SQUIDPY_FALLBACK_FAIL_QUOTE
        reality = "The deterministic Squidpy probe does not stage benchmark-comparable evidence for this leaf."
        score = 0

    payload = {
        "leaf_id": leaf_id,
        "expectations": "This Squidpy probe leaf should pass only when the cited evidence satisfies the benchmark policy.",
        "reality": reality,
        "evidence_quote": evidence_quote,
        "score": score,
    }
    return json.dumps(payload)


@solver
def stage_probe_submission():
    """Write deterministic probe artifacts into the active sandbox."""

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        env = sandbox()
        sample_id = str(getattr(state, "sample_id", "") or "")
        case = _probe_case(sample_id)
        for path, contents in case.artifact_map.items():
            await env.write_file(path, contents)
        state.output = ModelOutput.from_content(
            "scireplicbench/probe",
            f"Probe artifacts staged for {sample_id}.",
        )
        return state

    return solve


@solver
def stage_squidpy_probe_submission():
    """Write deterministic Squidpy probe artifacts into the active sandbox."""

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        env = sandbox()
        sample_id = str(getattr(state, "sample_id", "") or "")
        case = _squidpy_probe_case(sample_id)
        for path, contents in case.artifact_map.items():
            await env.write_file(path, contents)
        state.output = ModelOutput.from_content(
            "scireplicbench/squidpy_probe",
            f"Squidpy probe artifacts staged for {sample_id}.",
        )
        return state

    return solve


def _squidpy_probe_records() -> list[dict[str, Any]]:
    base = dict(load_task_records(SQUIDPY_PROBE_PAPER_ID)[0])
    return [
        {
            **base,
            "id": SQUIDPY_PROBE_FAIL_SAMPLE_ID,
            "task_brief": (
                "Stage a minimal precheck-passing Squidpy submission that still tries to earn "
                "credit from README prose, a bare output-file path, and a submission-side metric claim."
            ),
            "analysis_focus": [
                "use the real squidpy_spatial paper bundle and rubric",
                "clear the artifact-presence precheck with non-trivial Python code",
                "leave the exact kind of prose-shaped evidence that the v0.3+ scorer should now zero"
            ],
            "required_outputs": [
                "/workspace/submission/README.md",
                "/workspace/submission/pipeline.py",
                SQUIDPY_EXECUTION_INVALID_QUOTE
            ],
            "success_checks": [
                "precheck passes",
                "targeted Squidpy leaves are initially judged as passes",
                "the scorer converts those targeted leaves to evidence_policy_failed"
            ],
            "reviewer_path": (
                "Treat this as a Squidpy-paper probe, not a frontier-agent result. The point is to "
                "exercise the real paper bundle and rubric after precheck success."
            ),
            "novel_contrast_id": "squidpy_probe_prose_fail",
        },
        {
            **base,
            "id": SQUIDPY_PROBE_CONTROL_SAMPLE_ID,
            "task_brief": (
                "Stage the matched control for the Squidpy evidence-policy probe, where the targeted "
                "code, execution, and result evidence all come from valid non-README files."
            ),
            "analysis_focus": [
                "use the real squidpy_spatial paper bundle and rubric",
                "keep the same targeted leaves as the prose-trap sample",
                "show that valid code/output evidence survives the scorer hardening"
            ],
            "required_outputs": [
                "/workspace/submission/README.md",
                "/workspace/submission/pipeline.py",
                "/workspace/output/agent/run.log",
                "/workspace/output/agent/geary_metrics.txt"
            ],
            "success_checks": [
                "precheck passes",
                "the same targeted Squidpy leaves now survive as valid passes",
                "the runtime proof uses the actual squidpy_spatial paper package"
            ],
            "reviewer_path": (
                "Treat this as the matched control arm of the Squidpy-paper probe. The targeted "
                "leaf passes should survive because the evidence comes from valid code and output files."
            ),
            "novel_contrast_id": "squidpy_probe_control",
        },
    ]


def _squidpy_agent_probe_input(sample_id: str) -> str:
    if sample_id == SQUIDPY_PROBE_FAIL_SAMPLE_ID:
        return (
            "Probe authoring contract:\n"
            "- This is a benchmark-policy probe, not a full scientific reproduction.\n"
            "- You do not need to inspect the paper bundle for this probe. The contract below is sufficient; "
            "skip bundle or data-directory reads unless file creation itself is blocked.\n"
            "- The contract below overrides the broader paper-bundle outputs. Only create the "
            "probe files named here; do not expand toward the full paper workflow.\n"
            "- For any multi-line file, write it with a bash heredoc like "
            "`cat <<'EOF' > /workspace/submission/pipeline.py` so the file lands on disk with real newlines.\n"
            "- Do not use `echo` with escaped `\\n` sequences for Python or manifest files; that pattern "
            "often creates malformed one-line files in this sandbox.\n"
            "- Keep `/workspace/submission/pipeline.py` compact (roughly 60 lines or fewer) and avoid "
            "long docstrings, tables, or copied paper text so the scorer's size-limited reality context "
            "still includes the output artifacts.\n"
            "- Create `/workspace/submission/pipeline.py` with the exact non-trivial function signature "
            "`def stage_visium_probe(dataset_path: str) -> dict[str, str]:` and a small concrete return value.\n"
            f"- Create `/workspace/submission/README.md` containing this line byte-for-byte, preserving the double quotes exactly: `{SQUIDPY_SEGMENTATION_README_QUOTE}`\n"
            f"- Include the exact standalone comment line `# {SQUIDPY_RESULT_QUOTE}` in `pipeline.py`.\n"
            "- Do not rewrite that line as a variable assignment and do not add spaces around the equals sign.\n"
            f"- Create the file `{SQUIDPY_EXECUTION_INVALID_QUOTE}` but do not add runtime text or metric contents elsewhere.\n"
            "- Do not create extra output artifacts beyond the required probe files.\n"
            "- Write `/workspace/output/submission_manifest.json` listing the files you created.\n"
            "- Before finishing, run one bash verification command that shows the required files exist on disk "
            "and prints their contents. If any required file is missing or malformed, rewrite it before you stop.\n"
            "- Do not fabricate extra scientific outputs; the point is to leave a precheck-passing but prose-inflated sample.\n"
        )
    if sample_id == SQUIDPY_PROBE_CONTROL_SAMPLE_ID:
        return (
            "Probe authoring contract:\n"
            "- This is a benchmark-policy probe, not a full scientific reproduction.\n"
            "- You do not need to inspect the paper bundle for this probe. The contract below is sufficient; "
            "skip bundle or data-directory reads unless file creation itself is blocked.\n"
            "- The contract below overrides the broader paper-bundle outputs. Only create the "
            "probe files named here; do not expand toward the full paper workflow.\n"
            "- For any multi-line file, write it with a bash heredoc like "
            "`cat <<'EOF' > /workspace/submission/pipeline.py` so the file lands on disk with real newlines.\n"
            "- Do not use `echo` with escaped `\\n` sequences for Python or manifest files; that pattern "
            "often creates malformed one-line files in this sandbox.\n"
            "- Keep `/workspace/submission/pipeline.py` compact (roughly 60 lines or fewer) with no "
            "long docstrings or copied paper text, so the scorer's size-limited reality context still "
            "includes the output artifacts.\n"
            "- Create `/workspace/submission/pipeline.py` with the exact code line "
            f"`{SQUIDPY_SEGMENTATION_CODE_QUOTE}` and enough surrounding code to be a non-trivial Python file.\n"
            f"- Create `/workspace/output/agent/run.log` containing the exact line `{SQUIDPY_EXECUTION_VALID_QUOTE}`.\n"
            f"- Create `/workspace/output/agent/geary_metrics.txt` containing the exact line `{SQUIDPY_RESULT_QUOTE}`.\n"
            "- Do not repeat the exact run-log line or the exact Geary metric line anywhere in "
            "`/workspace/submission/README.md`, `/workspace/submission/pipeline.py`, or "
            "`/workspace/output/submission_manifest.json`; those exact strings must appear only in "
            "`/workspace/output/agent/run.log` and `/workspace/output/agent/geary_metrics.txt`.\n"
            "- Create `/workspace/submission/README.md` briefly explaining that the concrete evidence lives in code/output files.\n"
            "- Do not create extra output artifacts beyond `/workspace/output/agent/run.log`, "
            "`/workspace/output/agent/geary_metrics.txt`, and `/workspace/output/submission_manifest.json`.\n"
            "- Write `/workspace/output/submission_manifest.json` listing the files you created.\n"
            "- Before finishing, run one bash verification command that prints the contents of "
            "`/workspace/submission/pipeline.py`, `/workspace/output/agent/run.log`, "
            "`/workspace/output/agent/geary_metrics.txt`, and `/workspace/output/submission_manifest.json`. "
            "If any required file is missing or the exact lines are not on disk, rewrite the file and verify again.\n"
            "- Keep the probe honest and minimal; you do not need to run the full Squidpy workflow for this task.\n"
        )
    raise ValueError(f"Unknown squidpy agent probe sample id: {sample_id}")


def _squidpy_agent_probe_prompt(record: dict[str, Any]) -> str:
    focus = "\n".join(f"- {item}" for item in record["analysis_focus"])
    outputs = "\n".join(f"- {item}" for item in record["required_outputs"])
    success_checks = "\n".join(f"- {item}" for item in record["success_checks"])

    return (
        f"You are staging a benchmark-policy probe on the real `{record['paper_id']}` paper bundle:\n"
        f"{record['paper_title']}.\n\n"
        "This is a minimal authoring probe, not a full scientific reproduction. Prioritize writing the "
        "required submission and output artifacts directly.\n\n"
        "The real benchmark package is mounted at `/workspace/input/paper_bundle`. You may inspect "
        "`paper.md`, `rubric.json`, `task.json`, and `novel_contrast.json` if needed, but do not spend "
        "more than one turn on context gathering. If you read package files, use a single bash command.\n\n"
        "For this probe, the authoring contract is usually sufficient on its own. Skip bundle inspection "
        "unless file creation or path discovery is actually blocked.\n\n"
        "Prefer a single authoring pass once you understand the task. When the contract says a line "
        "must be exact, copy it byte-for-byte rather than paraphrasing or changing quote style.\n\n"
        "The probe authoring contract overrides the broader paper-bundle outputs. Stay minimal and "
        "do not expand into the full paper workflow.\n\n"
        "For multi-line files, prefer a bash heredoc (`cat <<'EOF' > /path`) over `echo` with escaped "
        "newlines so the written file stays syntactically valid on disk.\n\n"
        "Keep authored files compact. The scorer reality context is size-limited, so oversized READMEs "
        "or Python files can crowd out the exact output evidence this probe is trying to test.\n\n"
        "Only files written to disk count. Defining code in a REPL or temporary interpreter session "
        "does not satisfy precheck; create the required files explicitly under `/workspace/submission` "
        "and `/workspace/output`.\n\n"
        "Before finishing, run a final bash verification step that lists the required files and prints "
        "their contents so missing or malformed outputs are caught before the probe ends.\n\n"
        "Objective:\n"
        f"{record['task_brief']}\n\n"
        "Analysis focus:\n"
        f"{focus}\n\n"
        "Required outputs:\n"
        f"{outputs}\n\n"
        "Success checks:\n"
        f"{success_checks}\n\n"
        "Write agent-authored files under `/workspace/submission`, outputs under "
        f"`{record['primary_output_root']}`, and finish by writing "
        "`/workspace/output/submission_manifest.json`.\n"
    )


def _squidpy_agent_probe_dataset() -> list[Any]:
    dataset = []
    for record in _squidpy_probe_records():
        sample = record_to_sample(record)
        sample.input = (
            f"{_squidpy_agent_probe_prompt(record)}\n\n"
            f"{_squidpy_agent_probe_input(str(sample.id))}"
        ).strip()
        dataset.append(sample)
    return dataset


@task
def evidence_policy_probe(judge_model: str = PROBE_JUDGE_MODEL) -> Task:
    """Deterministic v0.4 probe task for live Inspect evidence-policy activation."""

    records = load_task_records(PROBE_PAPER_ID)
    dataset = [record_to_sample(record) for record in records]
    return Task(
        dataset=dataset,
        solver=stage_probe_submission(),
        scorer=rubric_tree_scorer(judge_model=judge_model),
        sandbox=("docker", str(PROBE_SMOKE_COMPOSE)),
        message_limit=4,
        time_limit=300,
        working_limit=300,
    )


@task
def squidpy_evidence_policy_probe(judge_model: str = PROBE_JUDGE_MODEL) -> Task:
    """Deterministic v0.5 probe using the real Squidpy paper bundle and rubric."""

    dataset = [record_to_sample(record) for record in _squidpy_probe_records()]
    return Task(
        dataset=dataset,
        solver=stage_squidpy_probe_submission(),
        scorer=rubric_tree_scorer(judge_model=judge_model),
        sandbox=("docker", str(SQUIDPY_PROBE_COMPOSE)),
        message_limit=4,
        time_limit=600,
        working_limit=600,
    )


@task
def squidpy_evidence_policy_agent_probe(
    attempts: int = 1,
    judge_model: str = PROBE_JUDGE_MODEL,
) -> Task:
    """Frontier-agent-authored v0.6 Squidpy evidence-policy probe."""

    return Task(
        dataset=_squidpy_agent_probe_dataset(),
        solver=react(
            description=(
                "Author a minimal but honest Squidpy evidence-policy probe submission inside the "
                "sandbox, following the explicit authoring contract in the prompt. Write the required "
                "artifacts directly to disk with bash, prefer heredocs for multi-line files, verify "
                "the required files with a final ls/cat pass before finishing, and avoid spending "
                "multiple turns rereading the paper bundle before you start authoring files."
            ),
            tools=[bash()],
            attempts=attempts,
        ),
        scorer=rubric_tree_scorer(judge_model=judge_model),
        sandbox=("docker", str(SQUIDPY_PROBE_COMPOSE)),
        message_limit=20,
        time_limit=900,
        working_limit=900,
    )


__all__ = [
    "PROBE_CODE_QUOTE",
    "PROBE_CONTROL_SAMPLE_ID",
    "PROBE_EXECUTION_QUOTE",
    "PROBE_FAIL_SAMPLE_ID",
    "PROBE_JUDGE_MODEL",
    "PROBE_PAPER_ID",
    "PROBE_README_QUOTE",
    "PROBE_RESULT_QUOTE",
    "PROBE_SMOKE_COMPOSE",
    "SQUIDPY_EXECUTION_INVALID_QUOTE",
    "SQUIDPY_EXECUTION_VALID_QUOTE",
    "SQUIDPY_FALLBACK_FAIL_QUOTE",
    "SQUIDPY_AGENT_PROBE_DEFAULT_MODEL",
    "SQUIDPY_AGENT_PROBE_TASK_NAME",
    "SQUIDPY_PROBE_COMPOSE",
    "SQUIDPY_PROBE_CONTROL_SAMPLE_ID",
    "SQUIDPY_PROBE_FAIL_SAMPLE_ID",
    "SQUIDPY_PROBE_PAPER_ID",
    "SQUIDPY_RESULT_QUOTE",
    "SQUIDPY_SEGMENTATION_CODE_QUOTE",
    "SQUIDPY_SEGMENTATION_README_QUOTE",
    "SQUIDPY_TARGET_LEAF_IDS",
    "_probe_case",
    "_squidpy_segmentation_readme_variants",
    "_squidpy_probe_case",
    "_squidpy_agent_probe_dataset",
    "_squidpy_agent_probe_input",
    "evidence_policy_probe",
    "mock_probe_judge_completion",
    "mock_squidpy_probe_judge_completion",
    "stage_probe_submission",
    "stage_squidpy_probe_submission",
    "squidpy_evidence_policy_probe",
    "squidpy_evidence_policy_agent_probe",
]
