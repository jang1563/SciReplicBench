"""Structured judge prompt and parsing helpers."""

from __future__ import annotations

import inspect
import json
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, Union


@dataclass
class LeafJudgement:
    """Structured per-leaf judgement compatible with the benchmark design."""

    leaf_id: str
    expectations: str
    reality: str
    evidence_quote: str
    score: int
    confidence: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "leaf_id": self.leaf_id,
            "expectations": self.expectations,
            "reality": self.reality,
            "evidence_quote": self.evidence_quote,
            "score": self.score,
        }
        if self.confidence is not None:
            payload["confidence"] = self.confidence
        if self.metadata:
            payload["metadata"] = self.metadata
        return payload


JudgeClient = Callable[
    [str],
    Union[str, Dict[str, Any], Awaitable[str], Awaitable[Dict[str, Any]]],
]


def format_leaf_judge_prompt(
    leaf: dict[str, Any],
    *,
    paper_summary: str,
    reality_context: str,
    comparator_guidance: str | None = None,
) -> str:
    """Render a structured prompt for one rubric leaf."""

    comparator_block = comparator_guidance or "Use the leaf text and benchmark policy only."
    return (
        "You are grading one SciReplicBench rubric leaf.\n\n"
        "Paper summary:\n"
        f"{paper_summary.strip()}\n\n"
        "Leaf metadata:\n"
        f"- leaf_id: {leaf['id']}\n"
        f"- category: {leaf.get('category', 'unknown')}\n"
        f"- requirement: {leaf.get('requirement', '').strip()}\n"
        f"- grading_notes: {leaf.get('grading_notes', '').strip()}\n\n"
        "Observed reality:\n"
        f"{reality_context.strip()}\n\n"
        "Comparator guidance:\n"
        f"{comparator_block.strip()}\n\n"
        "Return exactly one JSON object with these keys in this order:\n"
        '{"leaf_id":"...","expectations":"...","reality":"...","evidence_quote":"...","score":0}\n\n'
        "Rules:\n"
        "- expectations: summarize what passing requires for this leaf.\n"
        "- reality: summarize what the submission actually did.\n"
        "- evidence_quote: quote the specific supporting text or command output verbatim.\n"
        "- score: 1 for pass, 0 for fail.\n"
        "- Do not omit evidence_quote.\n"
        "- Do not add markdown fences or commentary outside the JSON object."
    )


def _extract_json_payload(raw: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    text = raw.strip()
    if text.startswith("```"):
        lines = [line for line in text.splitlines() if not line.strip().startswith("```")]
        text = "\n".join(lines).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        for index, character in enumerate(text):
            if character != "{":
                continue
            try:
                payload, _ = decoder.raw_decode(text[index:])
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                return payload
        raise ValueError("Could not extract a JSON object from judge output.") from None


def parse_leaf_judgement(
    raw: str | dict[str, Any], *, expected_leaf_id: str | None = None
) -> LeafJudgement:
    """Parse a judge response into a validated LeafJudgement."""

    payload = _extract_json_payload(raw) if isinstance(raw, str) else raw
    required = ["leaf_id", "expectations", "reality", "evidence_quote", "score"]
    missing = [field for field in required if field not in payload]
    if missing:
        raise ValueError(f"Judge response missing required fields: {missing}")

    leaf_id = str(payload["leaf_id"])
    if expected_leaf_id is not None and leaf_id != expected_leaf_id:
        raise ValueError(f"Judge leaf_id mismatch: expected {expected_leaf_id}, observed {leaf_id}")

    score_raw = payload["score"]
    if isinstance(score_raw, bool):
        score = int(score_raw)
    elif isinstance(score_raw, (int, float)) and score_raw in (0, 1):
        score = int(score_raw)
    elif isinstance(score_raw, str):
        normalized = score_raw.strip().lower()
        if normalized in {"pass", "1", "true"}:
            score = 1
        elif normalized in {"fail", "0", "false"}:
            score = 0
        else:
            raise ValueError(f"Unsupported score value: {score_raw}")
    else:
        raise ValueError(f"Unsupported score value: {score_raw}")

    evidence_quote = str(payload["evidence_quote"]).strip()
    if not evidence_quote:
        raise ValueError("Judge evidence_quote must be non-empty.")

    confidence = payload.get("confidence")
    if confidence is not None:
        confidence = float(confidence)

    metadata = payload.get("metadata", {})
    if metadata is None:
        metadata = {}
    if not isinstance(metadata, dict):
        raise ValueError("Judge metadata must be an object when provided.")

    return LeafJudgement(
        leaf_id=leaf_id,
        expectations=str(payload["expectations"]).strip(),
        reality=str(payload["reality"]).strip(),
        evidence_quote=evidence_quote,
        score=score,
        confidence=confidence,
        metadata=metadata,
    )


def needs_self_consistency_retry(
    judgements: list[LeafJudgement], *, min_confidence: float = 0.6
) -> bool:
    """Flag judgements that merit a self-consistency retry."""

    if not judgements:
        return True
    scores = {judgement.score for judgement in judgements}
    if len(scores) > 1:
        return True
    for judgement in judgements:
        if not judgement.evidence_quote.strip():
            return True
        if judgement.confidence is not None and judgement.confidence < min_confidence:
            return True
    return False


def majority_vote_judgements(judgements: list[LeafJudgement]) -> LeafJudgement:
    """Select a consensus judgement by majority vote on score."""

    if not judgements:
        raise ValueError("At least one judgement is required for majority vote.")

    vote_counts = Counter(judgement.score for judgement in judgements)
    majority_score, majority_votes = max(vote_counts.items(), key=lambda item: (item[1], item[0]))
    majority_candidates = [judgement for judgement in judgements if judgement.score == majority_score]
    selected = max(
        majority_candidates,
        key=lambda judgement: (
            judgement.confidence is not None,
            judgement.confidence or 0.0,
            len(judgement.evidence_quote),
        ),
    )
    metadata = dict(selected.metadata)
    metadata.update({"votes_for_score": majority_votes, "total_votes": len(judgements)})
    return LeafJudgement(
        leaf_id=selected.leaf_id,
        expectations=selected.expectations,
        reality=selected.reality,
        evidence_quote=selected.evidence_quote,
        score=selected.score,
        confidence=selected.confidence,
        metadata=metadata,
    )


async def judge_leaf(
    client: JudgeClient,
    *,
    leaf: dict[str, Any],
    paper_summary: str,
    reality_context: str,
    comparator_guidance: str | None = None,
) -> LeafJudgement:
    """Judge a single leaf with a sync or async client callable."""

    prompt = format_leaf_judge_prompt(
        leaf,
        paper_summary=paper_summary,
        reality_context=reality_context,
        comparator_guidance=comparator_guidance,
    )
    response = client(prompt)
    if inspect.isawaitable(response):
        response = await response
    return parse_leaf_judgement(response, expected_leaf_id=leaf["id"])


__all__ = [
    "JudgeClient",
    "LeafJudgement",
    "format_leaf_judge_prompt",
    "judge_leaf",
    "majority_vote_judgements",
    "needs_self_consistency_retry",
    "parse_leaf_judgement",
]
