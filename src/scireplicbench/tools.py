"""Custom Inspect tools used by SciReplicBench tasks."""

from __future__ import annotations

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


@tool(parallel=False)
def scratchpad():
    """Read or update a dedicated scratchpad file inside the sandbox."""

    async def execute(
        action: Literal["read", "append", "replace", "clear"] = "read",
        content: str = "",
    ) -> str:
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


__all__ = ["DEFAULT_SCRATCHPAD_PATH", "scratchpad"]
