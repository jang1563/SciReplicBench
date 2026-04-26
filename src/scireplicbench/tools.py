"""Custom Inspect tools used by SciReplicBench tasks."""

from __future__ import annotations

import json
import posixpath
import re
from pathlib import PurePosixPath
from typing import Literal

try:
    from inspect_ai.tool import tool
    from inspect_ai.util import sandbox
except ModuleNotFoundError as exc:  # pragma: no cover - local fallback for import-only validation
    _INSPECT_IMPORT_ERROR = exc

    def tool(*args, **kwargs):  # type: ignore[override]
        if args and callable(args[0]) and len(args) == 1 and not kwargs:
            return args[0]

        def decorator(func):
            return func

        return decorator

    def sandbox(name: str | None = None):  # type: ignore[override]
        raise RuntimeError(
            "inspect-ai is required to use sandbox-backed tools. "
            "Install project dependencies before running SciReplicBench tasks."
        ) from _INSPECT_IMPORT_ERROR


DEFAULT_SCRATCHPAD_PATH = "/workspace/scratchpad.md"
SCRATCHPAD_MAX_CHARS = 24_000
WORKSPACE_TEXT_ALLOWED_ROOTS = (
    "/workspace/submission",
    "/workspace/output",
    "/workspace/logs",
)
WORKSPACE_TEXT_READ_ONLY_ROOTS = (
    "/workspace/input",
)
WORKSPACE_TEXT_MAX_CHARS = 200_000
WORKSPACE_TEXT_READ_MAX_CHARS = 12_000
PROTECTED_STARTER_LAUNCHER = "/workspace/input/paper_bundle/starter/run.sh"
PROTECTED_SUBMISSION_LAUNCHER = "/workspace/submission/run.sh"
PROTECTED_STARTER_MAIN_ANALYSIS = "/workspace/input/paper_bundle/starter/main_analysis.py"
PROTECTED_SUBMISSION_MAIN_ANALYSIS = "/workspace/submission/main_analysis.py"
PROTECTED_SUBMISSION_SCAFFOLD = "/workspace/submission/genelab_scaffold.py"
PROTECTED_SUBMISSION_MANIFEST = "/workspace/output/submission_manifest.json"
PROTECTED_GENELAB_OUTPUTS = (
    "/workspace/output/agent/lomo/summary.tsv",
    "/workspace/output/agent/transfer/cross_tissue.tsv",
    "/workspace/output/agent/negative_controls/summary.tsv",
    "/workspace/output/agent/interpretability/top_features.tsv",
)
PROTECTED_LAUNCHER_MESSAGE = (
    "GeneLab seeded launcher protection: /workspace/submission/run.sh is "
    "managed by the benchmark starter. Leave it intact and put substantive "
    "edits in /workspace/submission/main_analysis.py or other source files. "
    "The launcher already checks required artifacts, applies timeouts, and "
    "falls back to the pristine staged starter."
)
PROTECTED_GENELAB_OUTPUT_MESSAGE = (
    "GeneLab output artifact protection: this required TSV already contains "
    "a rich benchmark-style table. Do not replace it with a thinner placeholder; "
    "rerun /workspace/submission/run.sh or write a full structured TSV with "
    "comparable columns and rows."
)
PROTECTED_GENELAB_SOURCE_MESSAGE = (
    "GeneLab source protection: /workspace/submission/main_analysis.py already "
    "contains the seeded benchmark-style analysis. Do not replace it with a "
    "thin partial script; keep the LOMO, transfer, negative-control, "
    "interpretability, go/no-go, foundation-model staging, and manifest outputs. "
    "If you improve it, first read the full file with workspace_text_file "
    "using a large max_chars value, then write a complete replacement that "
    "preserves those benchmark stages and integrates your changes into the "
    "canonical workflow."
)
PROTECTED_GENELAB_MANIFEST_MESSAGE = (
    "GeneLab manifest protection: /workspace/output/submission_manifest.json "
    "already records the seeded reviewer-path run with commands, inputs, "
    "artifacts, detected tissues, folds, models, and summary counts. Do not "
    "replace it with a thinner prose summary; rerun /workspace/submission/run.sh "
    "or preserve the full structured manifest fields."
)
PROTECTED_GENELAB_SIDECAR_MESSAGE = (
    "GeneLab post-success sidecar protection: the canonical seeded workflow "
    "already produced the structured starter artifacts and manifest. Do not "
    "add an unhooked alternate analysis driver under /workspace/submission; "
    "inspect the generated TSVs and submit, or make a complete canonical "
    "workflow replacement that preserves the full artifact set."
)
_GENELAB_POST_SUCCESS_SIDECAR_NAMES = (
    "run_benchmark.py",
    "evaluate_models.py",
    "model_analysis.py",
    "model_evaluation.py",
    "evaluate_lomo.py",
    "evaluation_helpers.py",
    "gene_lab_helpers.py",
)
_GENELAB_SOURCE_REQUIRED_OUTPUT_MARKERS = (
    "lomo/summary.tsv",
    "transfer/cross_tissue.tsv",
    "negative_controls/summary.tsv",
    "interpretability/top_features.tsv",
    "go_nogo/summary.tsv",
    "foundation/geneformer_staging.tsv",
    "submission_manifest.json",
)
_GENELAB_SOURCE_RICH_MARKERS = (
    "LOMO_FIELDS",
    "TRANSFER_FIELDS",
    "NEGATIVE_FIELDS",
    "INTERPRETABILITY_FIELDS",
    "GO_NOGO_FIELDS",
    "FOUNDATION_FIELDS",
    "heldout_mission",
    "ci_lower",
    "ci_upper",
    "perm_pvalue",
    "bootstrap",
    "permutation",
    "feature_rank",
    "Geneformer",
)
_PROTECTED_LAUNCHER_WRITE_RE = re.compile(
    r"(?:^|[^<])>{1,2}\s*(?:--\s*)?['\"]?"
    + re.escape(PROTECTED_SUBMISSION_LAUNCHER)
    + r"(?:['\"]?)(?:\s|$)"
)
_PROTECTED_LAUNCHER_MUTATION_RE = re.compile(
    r"\b(?:tee|cp|mv|rm|unlink|truncate|install|sed|perl|python|python3)\b"
    r"[^\n;&|]*"
    + re.escape(PROTECTED_SUBMISSION_LAUNCHER)
)
_PROTECTED_SOURCE_WRITE_RE = re.compile(
    r"(?:^|[^<])>{1,2}\s*(?:--\s*)?['\"]?"
    + re.escape(PROTECTED_SUBMISSION_MAIN_ANALYSIS)
    + r"(?:['\"]?)(?:\s|$)"
)
_PROTECTED_SOURCE_MUTATION_RE = re.compile(
    r"\b(?:tee|cp|mv|rm|unlink|truncate|install|sed|perl)\b"
    r"[^\n;&|]*"
    + re.escape(PROTECTED_SUBMISSION_MAIN_ANALYSIS)
)
_PROTECTED_MANIFEST_WRITE_RE = re.compile(
    r"(?:^|[^<])>{1,2}\s*(?:--\s*)?['\"]?"
    + re.escape(PROTECTED_SUBMISSION_MANIFEST)
    + r"(?:['\"]?)(?:\s|$)"
)
_PROTECTED_MANIFEST_MUTATION_RE = re.compile(
    r"\b(?:tee|cp|mv|rm|unlink|truncate|install|sed|perl|python|python3)\b"
    r"[^\n;&|]*"
    + re.escape(PROTECTED_SUBMISSION_MANIFEST)
)
_SUBMISSION_PYTHON_PATH_RE = re.compile(
    r"['\"]?(?P<path>/workspace/submission/[A-Za-z0-9_./-]+\.py)['\"]?"
)
_STARTER_MAIN_ANALYSIS_COPY_RE = re.compile(
    r"^\s*cp(?:\s+-[^\s]+)*\s+['\"]?"
    + re.escape(PROTECTED_STARTER_MAIN_ANALYSIS)
    + r"['\"]?\s+['\"]?"
    + re.escape(PROTECTED_SUBMISSION_MAIN_ANALYSIS)
    + r"['\"]?\s*$"
)


async def _starter_launcher_is_available(env: object) -> bool:
    try:
        await env.read_file(PROTECTED_STARTER_LAUNCHER)  # type: ignore[attr-defined]
    except FileNotFoundError:
        return False
    except Exception:
        return False
    return True


async def _starter_main_analysis_is_available(env: object) -> bool:
    try:
        await env.read_file(PROTECTED_STARTER_MAIN_ANALYSIS)  # type: ignore[attr-defined]
    except FileNotFoundError:
        return False
    except Exception:
        return False
    return True


def _is_protected_launcher_path(path: str) -> bool:
    return path == PROTECTED_SUBMISSION_LAUNCHER


def _is_protected_genelab_source_path(path: str) -> bool:
    return path == PROTECTED_SUBMISSION_MAIN_ANALYSIS


def _is_protected_genelab_output_path(path: str) -> bool:
    return path in PROTECTED_GENELAB_OUTPUTS


def _is_protected_genelab_manifest_path(path: str) -> bool:
    return path == PROTECTED_SUBMISSION_MANIFEST


def _is_submission_python_path(path: str) -> bool:
    return path.startswith("/workspace/submission/") and PurePosixPath(path).suffix == ".py"


def _is_protected_genelab_sidecar_path(path: str) -> bool:
    if not _is_submission_python_path(path):
        return False
    if path in (PROTECTED_SUBMISSION_MAIN_ANALYSIS, PROTECTED_SUBMISSION_SCAFFOLD):
        return False
    return PurePosixPath(path).name in _GENELAB_POST_SUCCESS_SIDECAR_NAMES


def _looks_like_rich_genelab_tsv(contents: str) -> bool:
    rows = [line for line in str(contents).splitlines() if line.strip()]
    if len(rows) < 5:
        return False
    header_cols = rows[0].count("\t") + 1
    return header_cols >= 5


def _looks_like_rich_genelab_source(contents: str) -> bool:
    text = str(contents)
    nonempty_lines = [line for line in text.splitlines() if line.strip()]
    if len(nonempty_lines) < 80:
        return False
    if not all(marker in text for marker in _GENELAB_SOURCE_REQUIRED_OUTPUT_MARKERS):
        return False
    marker_hits = sum(1 for marker in _GENELAB_SOURCE_RICH_MARKERS if marker in text)
    return marker_hits >= 7


def _looks_like_rich_genelab_manifest(contents: str) -> bool:
    try:
        payload = json.loads(str(contents))
    except (TypeError, json.JSONDecodeError):
        return False

    if not isinstance(payload, dict):
        return False
    if payload.get("paper_id") != "genelab_benchmark":
        return False

    commands = payload.get("commands")
    inputs = payload.get("inputs")
    artifacts = payload.get("artifacts")
    detected_tissues = payload.get("detected_tissues")
    models_run = payload.get("models_run")
    summary = payload.get("summary")
    if not (
        isinstance(commands, list)
        and isinstance(inputs, dict)
        and isinstance(artifacts, list)
        and isinstance(detected_tissues, list)
        and isinstance(models_run, list)
        and isinstance(summary, dict)
    ):
        return False
    if not any("run.sh" in str(command) for command in commands):
        return False
    if len(detected_tissues) < 3 or len(models_run) < 3:
        return False
    if int(payload.get("n_folds") or 0) < 3:
        return False

    artifact_text = "\n".join(str(artifact) for artifact in artifacts)
    required_artifacts = (
        "/workspace/output/agent/lomo/summary.tsv",
        "/workspace/output/agent/transfer/cross_tissue.tsv",
        "/workspace/output/agent/negative_controls/summary.tsv",
        "/workspace/output/agent/interpretability/top_features.tsv",
    )
    if not all(artifact in artifact_text for artifact in required_artifacts):
        return False

    required_summary_keys = (
        "successful_lomo_rows",
        "successful_transfer_rows",
        "successful_negative_control_rows",
        "interpretability_rows",
    )
    return all(key in summary for key in required_summary_keys)


def _looks_like_genelab_alternate_sidecar_source(contents: str) -> bool:
    text = str(contents)
    marker_hits = sum(
        1
        for marker in (
            "GENELAB_FEATURE_ROOT",
            "GENELAB_LABEL_ROOT",
            "FEATURE_ROOT",
            "LABEL_ROOT",
            "OUTPUT_ROOT",
            "LOMO_FIELDS",
            "TRANSFER_FIELDS",
            "discover_fold_specs",
            "load_aligned_fold",
            "LogisticRegression",
            "RandomForestClassifier",
            "XGBClassifier",
            "roc_auc_score",
        )
        if marker in text
    )
    output_hits = sum(
        1
        for marker in (
            "/workspace/output/agent",
            "lomo/summary.tsv",
            "transfer/cross_tissue.tsv",
            "negative_controls/summary.tsv",
            "interpretability/top_features.tsv",
            "submission_manifest.json",
        )
        if marker in text
    )
    return marker_hits >= 4 and output_hits >= 1


async def _would_downgrade_protected_genelab_output(
    env: object,
    path: str,
    replacement: str,
) -> bool:
    if not _is_protected_genelab_output_path(path):
        return False
    if not await _starter_launcher_is_available(env):
        return False
    try:
        existing = await env.read_file(path)  # type: ignore[attr-defined]
    except FileNotFoundError:
        return False
    except Exception:
        return False
    return _looks_like_rich_genelab_tsv(str(existing)) and not _looks_like_rich_genelab_tsv(
        replacement
    )


async def _would_downgrade_protected_genelab_source(
    env: object,
    path: str,
    replacement: str,
) -> bool:
    if not _is_protected_genelab_source_path(path):
        return False
    starter_source: str | None = None
    try:
        starter_source = str(
            await env.read_file(PROTECTED_STARTER_MAIN_ANALYSIS)  # type: ignore[attr-defined]
        )
    except FileNotFoundError:
        starter_source = None
    except Exception:
        starter_source = None
    try:
        existing = str(await env.read_file(path))  # type: ignore[attr-defined]
    except FileNotFoundError:
        existing = ""
    except Exception:
        existing = ""

    baseline_candidates = [
        candidate for candidate in (existing, starter_source) if candidate
    ]
    has_rich_baseline = any(
        _looks_like_rich_genelab_source(candidate)
        for candidate in baseline_candidates
    )
    return has_rich_baseline and not _looks_like_rich_genelab_source(replacement)


async def _would_downgrade_protected_genelab_manifest(
    env: object,
    path: str,
    replacement: str,
) -> bool:
    if not _is_protected_genelab_manifest_path(path):
        return False
    if not await _starter_launcher_is_available(env):
        return False
    try:
        existing = await env.read_file(path)  # type: ignore[attr-defined]
    except FileNotFoundError:
        return False
    except Exception:
        return False
    return (
        _looks_like_rich_genelab_manifest(str(existing))
        and not _looks_like_rich_genelab_manifest(replacement)
    )


async def _protected_genelab_manifest_is_rich(env: object) -> bool:
    try:
        existing = await env.read_file(PROTECTED_SUBMISSION_MANIFEST)  # type: ignore[attr-defined]
    except FileNotFoundError:
        return False
    except Exception:
        return False
    return _looks_like_rich_genelab_manifest(str(existing))


async def _would_create_protected_genelab_sidecar(
    env: object,
    path: str,
    replacement: str,
) -> bool:
    if not _is_submission_python_path(path):
        return False
    if path in (PROTECTED_SUBMISSION_MAIN_ANALYSIS, PROTECTED_SUBMISSION_SCAFFOLD):
        return False
    if not await _protected_genelab_manifest_is_rich(env):
        return False
    return _is_protected_genelab_sidecar_path(
        path
    ) or _looks_like_genelab_alternate_sidecar_source(replacement)


async def _would_append_to_protected_genelab_source(env: object, path: str) -> bool:
    if not _is_protected_genelab_source_path(path):
        return False
    baseline_candidates: list[str] = []
    try:
        baseline_candidates.append(str(await env.read_file(path)))  # type: ignore[attr-defined]
    except FileNotFoundError:
        pass
    except Exception:
        pass
    try:
        baseline_candidates.append(
            str(await env.read_file(PROTECTED_STARTER_MAIN_ANALYSIS))  # type: ignore[attr-defined]
        )
    except FileNotFoundError:
        pass
    except Exception:
        pass
    return any(_looks_like_rich_genelab_source(candidate) for candidate in baseline_candidates)


def _bash_command_writes_protected_launcher(cmd: str) -> bool:
    if PROTECTED_SUBMISSION_LAUNCHER not in cmd:
        return False
    compact = cmd.replace("\\\n", " ")
    return bool(
        _PROTECTED_LAUNCHER_WRITE_RE.search(compact)
        or _PROTECTED_LAUNCHER_MUTATION_RE.search(compact)
    )


def _bash_command_writes_protected_source(cmd: str) -> bool:
    if PROTECTED_SUBMISSION_MAIN_ANALYSIS not in cmd:
        return False
    compact = cmd.replace("\\\n", " ")
    segments = [segment.strip() for segment in re.split(r"[\n;&|]+", compact) if segment.strip()]
    for segment in segments:
        if PROTECTED_SUBMISSION_MAIN_ANALYSIS not in segment:
            continue
        if _STARTER_MAIN_ANALYSIS_COPY_RE.match(segment):
            continue
        if _PROTECTED_SOURCE_WRITE_RE.search(segment) or _PROTECTED_SOURCE_MUTATION_RE.search(segment):
            return True
    return False


def _bash_command_writes_protected_manifest(cmd: str) -> bool:
    if PROTECTED_SUBMISSION_MANIFEST not in cmd:
        return False
    compact = cmd.replace("\\\n", " ")
    return bool(
        _PROTECTED_MANIFEST_WRITE_RE.search(compact)
        or _PROTECTED_MANIFEST_MUTATION_RE.search(compact)
    )


def _bash_command_writes_or_runs_protected_sidecar(cmd: str) -> bool:
    compact = cmd.replace("\\\n", " ")
    for match in _SUBMISSION_PYTHON_PATH_RE.finditer(compact):
        path = match.group("path").strip("'\"")
        if not _is_protected_genelab_sidecar_path(path):
            continue
        quoted_path = re.escape(path)
        if re.search(r"\bpython(?:3)?\b[^\n;&|]*" + quoted_path, compact):
            return True
        if re.search(r"(?:^|[^<])>{1,2}\s*(?:--\s*)?['\"]?" + quoted_path, compact):
            return True
        if re.search(
            r"\b(?:tee|cp|mv|rm|unlink|truncate|install|sed|perl)\b"
            r"[^\n;&|]*"
            + quoted_path,
            compact,
        ):
            return True
    return False


def _normalize_scratchpad(existing: str, action: str, content: str) -> str:
    if action == "clear":
        return ""
    if action == "replace":
        return content.strip() + ("\n" if content.strip() else "")
    if action == "append":
        base = existing.rstrip()
        addition = content.strip()
        if not addition:
            return existing
        if not base:
            return addition + "\n"
        return f"{base}\n{addition}\n"
    raise ValueError(f"Unsupported scratchpad action: {action}")


def _normalize_workspace_text_path(
    path: str,
    *,
    action: Literal["read", "write", "append"],
) -> str:
    candidate = (path or "").strip()
    if not candidate:
        raise ValueError("A non-empty file path is required.")

    normalized = PurePosixPath(posixpath.normpath(candidate)).as_posix()
    if not normalized.startswith("/"):
        raise ValueError(
            "workspace_text_file paths must be absolute paths under /workspace."
        )

    allowed_roots = WORKSPACE_TEXT_ALLOWED_ROOTS
    if action == "read":
        allowed_roots = WORKSPACE_TEXT_ALLOWED_ROOTS + WORKSPACE_TEXT_READ_ONLY_ROOTS

    for root in allowed_roots:
        if normalized == root or normalized.startswith(f"{root}/"):
            return normalized

    allowed = ", ".join(allowed_roots)
    raise ValueError(
        "workspace_text_file only supports paths under "
        f"{allowed}. Received: {normalized}"
    )


def _truncate_workspace_text(contents: str, *, path: str, max_chars: int) -> str:
    if max_chars <= 0:
        raise ValueError("max_chars must be greater than 0.")
    if len(contents) <= max_chars:
        return contents
    omitted = len(contents) - max_chars
    return (
        contents[:max_chars]
        + f"\n\n[truncated {omitted} characters from {path}]"
    )


@tool(name="bash", parallel=False)
def guarded_bash(
    timeout: int | None = None,
    user: str | None = None,
    sandbox_name: str | None = None,
):
    """Bash shell command execution with seeded launcher protection.

    Execute bash commands in the sandbox. For seeded GeneLab tasks, common
    attempts to overwrite `/workspace/submission/run.sh` are rejected so the
    starter launcher can keep its artifact checks, timeout, and fallback.

    Args:
      timeout: Timeout (in seconds) for command.
      user: User to execute commands as.
      sandbox_name: Optional sandbox environment name.

    Returns:
      String with command output (stdout) or command error (stderr).
    """

    async def execute(cmd: str) -> str:
        """
        Use this function to execute bash commands.

        Args:
          cmd (str): The bash command to execute.

        Returns:
          The output of the command.
        """
        env = sandbox(sandbox_name)
        if _bash_command_writes_protected_launcher(cmd) and await _starter_launcher_is_available(env):
            return f"bash error: {PROTECTED_LAUNCHER_MESSAGE}"
        if _bash_command_writes_protected_source(cmd) and await _starter_main_analysis_is_available(env):
            return f"bash error: {PROTECTED_GENELAB_SOURCE_MESSAGE}"
        if (
            _bash_command_writes_protected_manifest(cmd)
            and await _protected_genelab_manifest_is_rich(env)
        ):
            return f"bash error: {PROTECTED_GENELAB_MANIFEST_MESSAGE}"
        if (
            _bash_command_writes_or_runs_protected_sidecar(cmd)
            and await _protected_genelab_manifest_is_rich(env)
        ):
            return f"bash error: {PROTECTED_GENELAB_SIDECAR_MESSAGE}"

        result = await env.exec(
            cmd=["bash", "--login", "-c", cmd], timeout=timeout, user=user
        )
        output = ""
        if result.stderr:
            output = f"{result.stderr}\n"
        return f"{output}{result.stdout}"

    return execute


@tool(parallel=False)
def scratchpad():
    """Read or update a dedicated scratchpad file inside the sandbox."""

    async def execute(
        action: Literal["read", "append", "replace", "clear"] = "read",
        content: str = "",
    ) -> str:
        """
        Read or update a persistent scratchpad file inside the sandbox.

        Use this to keep multi-turn notes, plans, and intermediate results
        in one place across agent steps. The scratchpad lives at a fixed
        path inside the sandbox and is preserved between tool calls.

        Args:
          action (str): One of 'read', 'append', 'replace', 'clear'.
            'read' returns current contents, 'append' adds content to the
            end, 'replace' overwrites with content, 'clear' empties the file.
          content (str): Text to write. Required for 'append' and 'replace';
            ignored for 'read' and 'clear'.

        Returns:
          The current scratchpad contents (for 'read') or a short status
          message describing the update (for write actions).
        """
        env = sandbox()
        try:
            existing = await env.read_file(DEFAULT_SCRATCHPAD_PATH)
        except FileNotFoundError:
            existing = ""

        if action == "read":
            return existing or "Scratchpad is currently empty."

        updated = _normalize_scratchpad(existing=existing, action=action, content=content)
        if len(updated) > SCRATCHPAD_MAX_CHARS:
            raise ValueError(
                "Scratchpad update rejected because it would exceed "
                f"{SCRATCHPAD_MAX_CHARS} characters."
            )

        await env.write_file(DEFAULT_SCRATCHPAD_PATH, updated)
        if action == "clear":
            return "Scratchpad cleared."
        return (
            f"Scratchpad updated at {DEFAULT_SCRATCHPAD_PATH} "
            f"({len(updated)} characters total)."
        )

    return execute


@tool(parallel=False)
def workspace_text_file():
    """Read or update durable text files in the sandbox workspace."""

    async def execute(
        action: Literal["read", "write", "append"] = "read",
        path: str = "",
        content: str = "",
        max_chars: int = WORKSPACE_TEXT_READ_MAX_CHARS,
    ) -> str:
        """
        Read or update a text file under /workspace/submission, /workspace/output, or /workspace/logs.

        This tool is designed for exact multi-line writes of source code,
        launcher scripts, README files, manifests, and small text outputs.
        It preserves real newlines and avoids shell-quoting issues.

        Args:
          action (str): One of 'read', 'write', or 'append'.
          path (str): Absolute path to a text file under an allowed workspace root.
          content (str): Text to write or append. Required for 'write' and 'append'.
          max_chars (int): Maximum number of characters to return for 'read'.

        Returns:
          File contents (for 'read') or a short status message for write actions.
        """
        try:
            resolved = _normalize_workspace_text_path(path, action=action)
        except ValueError as exc:
            return f"workspace_text_file error: {exc}"

        env = sandbox()

        if action == "read":
            try:
                existing = await env.read_file(resolved)
            except FileNotFoundError:
                return f"File not found: {resolved}"
            try:
                return _truncate_workspace_text(
                    str(existing), path=resolved, max_chars=max_chars
                )
            except ValueError as exc:
                return f"workspace_text_file error: {exc}"

        if not content:
            return (
                f"workspace_text_file error: action '{action}' requires non-empty "
                "content."
            )

        if _is_protected_launcher_path(resolved) and await _starter_launcher_is_available(env):
            return f"workspace_text_file error: {PROTECTED_LAUNCHER_MESSAGE}"

        if action == "append" and await _would_append_to_protected_genelab_source(
            env, resolved
        ):
            return f"workspace_text_file error: {PROTECTED_GENELAB_SOURCE_MESSAGE}"

        replacement = content
        if action == "append":
            try:
                existing = await env.read_file(resolved)
            except FileNotFoundError:
                existing = ""
            replacement = str(existing) + content

        if await _would_downgrade_protected_genelab_source(env, resolved, replacement):
            return f"workspace_text_file error: {PROTECTED_GENELAB_SOURCE_MESSAGE}"

        if await _would_downgrade_protected_genelab_manifest(env, resolved, replacement):
            return f"workspace_text_file error: {PROTECTED_GENELAB_MANIFEST_MESSAGE}"

        if await _would_create_protected_genelab_sidecar(env, resolved, replacement):
            return f"workspace_text_file error: {PROTECTED_GENELAB_SIDECAR_MESSAGE}"

        if await _would_downgrade_protected_genelab_output(env, resolved, replacement):
            return f"workspace_text_file error: {PROTECTED_GENELAB_OUTPUT_MESSAGE}"

        if action == "write":
            if len(content) > WORKSPACE_TEXT_MAX_CHARS:
                return (
                    "workspace_text_file error: write rejected because it would exceed "
                    f"{WORKSPACE_TEXT_MAX_CHARS} characters."
                )
            await env.write_file(resolved, content)
            return f"Wrote {len(content)} characters to {resolved}."

        if action == "append":
            try:
                existing = await env.read_file(resolved)
            except FileNotFoundError:
                existing = ""
            updated = str(existing) + content
            if len(updated) > WORKSPACE_TEXT_MAX_CHARS:
                return (
                    "workspace_text_file error: append rejected because it would exceed "
                    f"{WORKSPACE_TEXT_MAX_CHARS} characters."
                )
            await env.write_file(resolved, updated)
            return (
                f"Appended {len(content)} characters to {resolved} "
                f"({len(updated)} total)."
            )

        return (
            "workspace_text_file error: unsupported action "
            f"'{action}'. Expected one of read, write, append."
        )

    return execute


__all__ = [
    "DEFAULT_SCRATCHPAD_PATH",
    "PROTECTED_GENELAB_OUTPUTS",
    "PROTECTED_GENELAB_MANIFEST_MESSAGE",
    "PROTECTED_GENELAB_SIDECAR_MESSAGE",
    "PROTECTED_GENELAB_SOURCE_MESSAGE",
    "PROTECTED_STARTER_LAUNCHER",
    "PROTECTED_STARTER_MAIN_ANALYSIS",
    "PROTECTED_SUBMISSION_LAUNCHER",
    "PROTECTED_SUBMISSION_MAIN_ANALYSIS",
    "PROTECTED_SUBMISSION_MANIFEST",
    "PROTECTED_SUBMISSION_SCAFFOLD",
    "WORKSPACE_TEXT_ALLOWED_ROOTS",
    "_bash_command_writes_protected_manifest",
    "_bash_command_writes_protected_source",
    "_bash_command_writes_or_runs_protected_sidecar",
    "_is_protected_genelab_output_path",
    "_is_protected_genelab_manifest_path",
    "_is_protected_genelab_sidecar_path",
    "_is_protected_genelab_source_path",
    "_looks_like_genelab_alternate_sidecar_source",
    "_looks_like_rich_genelab_manifest",
    "_looks_like_rich_genelab_source",
    "_looks_like_rich_genelab_tsv",
    "_would_append_to_protected_genelab_source",
    "_would_create_protected_genelab_sidecar",
    "_would_downgrade_protected_genelab_manifest",
    "_would_downgrade_protected_genelab_source",
    "guarded_bash",
    "workspace_text_file",
    "scratchpad",
]
