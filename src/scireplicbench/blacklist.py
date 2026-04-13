"""Simple lexical blacklist helpers for paper-author repositories."""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from typing import Iterable

DEFAULT_BLACKLIST_PATTERNS = (
    "github.com/eliah-o/inspiration4-omics",
    "github.com/jang1563/GeneLab_benchmark",
    "github.com/scverse/squidpy",
)


@dataclass
class BlacklistHit:
    """Structured description of a blacklist match."""

    pattern: str
    matched_text: str
    match_type: str
    score: float


def normalize_repo_reference(reference: str) -> str:
    """Normalize a GitHub-style reference for lexical matching."""

    normalized = reference.strip().lower()
    normalized = re.sub(r"^https?://", "", normalized)
    normalized = normalized.rstrip("/")
    if normalized.endswith(".git"):
        normalized = normalized[:-4]
    return normalized


def _pattern_variants(pattern: str) -> set[str]:
    normalized = normalize_repo_reference(pattern)
    parts = normalized.split("/")
    variants = {normalized}
    if len(parts) >= 2:
        variants.add("/".join(parts[-2:]))
        variants.add(parts[-1])
    return {variant for variant in variants if variant}


def find_blacklist_hits(
    text: str,
    *,
    patterns: Iterable[str] = DEFAULT_BLACKLIST_PATTERNS,
    fuzzy_threshold: float = 0.92,
) -> list[BlacklistHit]:
    """Find exact or near-exact references to blacklisted repositories.

    This is intentionally lexical rather than embedding-based so it can be tested
    and run locally without extra services. A future pass can layer semantic search
    on top of these exact-match heuristics.
    """

    normalized_text = normalize_repo_reference(text)
    hits: list[BlacklistHit] = []

    for pattern in patterns:
        variants = _pattern_variants(pattern)
        for variant in variants:
            if variant in normalized_text:
                hits.append(
                    BlacklistHit(
                        pattern=pattern,
                        matched_text=variant,
                        match_type="exact_substring",
                        score=1.0,
                    )
                )
                break
        else:
            for token in re.findall(r"[a-z0-9._/-]+", normalized_text):
                score = difflib.SequenceMatcher(None, token, max(variants, key=len)).ratio()
                if score >= fuzzy_threshold:
                    hits.append(
                        BlacklistHit(
                            pattern=pattern,
                            matched_text=token,
                            match_type="fuzzy_token",
                            score=score,
                        )
                    )
                    break

    return hits


def contains_blacklisted_reference(
    text: str, *, patterns: Iterable[str] = DEFAULT_BLACKLIST_PATTERNS
) -> bool:
    """Return True when the text references a blacklisted repository."""

    return bool(find_blacklist_hits(text, patterns=patterns))


__all__ = [
    "BlacklistHit",
    "DEFAULT_BLACKLIST_PATTERNS",
    "contains_blacklisted_reference",
    "find_blacklist_hits",
    "normalize_repo_reference",
]
