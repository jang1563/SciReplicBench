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


_LEAF_ALIGNMENT_PATTERNS: tuple[tuple[str, str], ...] = (
    ("geary", "geary"),
    ("moran", "moran"),
    ("ripley", "ripley"),
    ("nhood", "neighborhood-enrichment"),
    ("neighborhood", "neighborhood-enrichment"),
    ("enrichment", "neighborhood-enrichment"),
    ("centrality", "centrality"),
    ("interaction", "interaction"),
    ("ligrec", "ligrec/interactions"),
    ("ligand", "ligrec/interactions"),
    ("receptor", "ligrec/interactions"),
    ("co-occurrence", "co-occurrence"),
    ("cooccurrence", "co-occurrence"),
    ("texture", "texture"),
    ("segmentation", "segmentation"),
    ("region properties", "segmentation"),
    ("cell-shape", "segmentation"),
    ("image feature", "image features"),
    ("image-feature", "image features"),
    ("summary", "summary features"),
    ("join", "join/alignment to observations"),
    ("aligned to observations", "join/alignment to observations"),
    ("aligned to observation", "join/alignment to observations"),
    ("observations", "join/alignment to observations"),
    ("adata", "AnnData/observation alignment"),
    ("visium", "visium dataset"),
    ("spatially variable", "spatially variable genes"),
    ("svg", "spatially variable genes"),
)


def _evidence_policy_text(category: str) -> str:
    if category == "code_development":
        return (
            "For code_development leaves, README text or planning prose is not valid "
            "evidence. The evidence_quote must be copied from a "
            "`--- /workspace/submission/... ---` content block that contains "
            "agent-authored implementation code or configuration from submission "
            "files. Do not quote output artifact text, file-list lines, README or "
            "markdown text, task prose, or submission_manifest.json. If the "
            "submission only describes what it would do, score 0."
        )
    if category == "execution":
        return (
            "For execution leaves, README text or planning prose is not valid "
            "evidence. The evidence_quote must be copied from a "
            "`--- /workspace/output/... ---` content block, usually an output "
            "header, row, summary line, or runtime text showing that the requested "
            "artifact family was actually produced. Do not quote bare output paths, "
            "file-list lines, submission code, README or markdown text, task prose, "
            "or submission_manifest.json. If execution is only described but not "
            "evidenced, score 0."
        )
    if category == "result_match":
        return (
            "For result_match leaves, submission-side claims are not valid evidence. "
            "The evidence_quote must be copied from a "
            "`--- /workspace/output/... ---` content block containing "
            "benchmark-comparable values from non-README output artifacts. Do not "
            "quote bare paths, file-list lines, submission code, README or markdown "
            "text, task prose, or submission_manifest.json. If a metric is only "
            "asserted in code comments, README text, or planning prose, score 0."
        )
    return (
        "Prefer concrete evidence from the observed submission or output artifacts. "
        "Do not treat README promises as sufficient evidence of success."
    )


def _leaf_alignment_text(leaf: dict[str, Any]) -> str:
    category = str(leaf.get("category", "unknown"))
    context = " ".join(
        str(part)
        for part in (
            leaf.get("id", ""),
            leaf.get("requirement", ""),
            leaf.get("grading_notes", ""),
        )
    ).lower()

    anchors: list[str] = []
    for pattern, label in _LEAF_ALIGNMENT_PATTERNS:
        if pattern in context and label not in anchors:
            anchors.append(label)

    lines = [
        "The evidence must directly match the exact metric, artifact family, or pipeline step named by this leaf.",
        "Do not give credit for adjacent steps or different analysis families just because the threshold, file format, or numeric value looks similar.",
    ]
    if category == "code_development":
        lines.append(
            "A generic compute call does not automatically satisfy adjacent steps such as joining, storing, aligning, or writing results unless the quote explicitly shows that step."
        )
        lines.append(
            "This category grades implementation only: score 1 when the quoted submission source implements the core required behavior or an accepted documented equivalent, even if execution logs, output tables, hidden-reference comparisons, or result values are not visible in this prompt."
        )
        lines.append(
            "Do not require README documentation, result-match success, or output artifact evidence for a code_development pass when the source code itself directly implements the leaf."
        )
    elif category == "execution":
        lines.append(
            "Execution evidence must correspond to the output family named by this leaf; a file or metric from one analysis family is not enough for another."
        )
        lines.append(
            "For execution leaves about written artifacts, score 1 when a /workspace/output content block contains a header or row for the requested artifact family; do not require hidden-reference agreement."
        )
        lines.append(
            "When runtime or output text explicitly names the exact dataset, function, or artifact family required by the leaf and shows successful completion, that output-side evidence can be sufficient even if the matching code excerpt is not visible."
        )
        lines.append(
            "For execution leaves about written analysis outputs, a downstream benchmark-comparison score such as overlap, RBO, ARI, or correlation-to-reference is not enough unless the leaf explicitly asks for that comparator. Prefer the underlying analysis output or explicit runtime success for that output."
        )
    elif category == "result_match":
        lines.append(
            "Do not reuse one overlap, correlation, or ranked-metric value for a different analysis family. Evidence about Geary is not evidence about Moran, neighborhood-enrichment, ligrec, texture, centrality, or co-occurrence unless the quote explicitly names the same family as this leaf."
        )

    if anchors:
        lines.append(
            f"Expected analysis anchors for this leaf include: {', '.join(anchors)}. If the quote names a different family or omits these anchors, score 0."
        )

    lines.append("If the evidence is ambiguous, generic, or only indirectly related to the leaf, score 0.")
    return " ".join(lines)


def format_leaf_judge_prompt(
    leaf: dict[str, Any],
    *,
    paper_summary: str,
    reality_context: str,
    comparator_guidance: str | None = None,
) -> str:
    """Render a structured prompt for one rubric leaf."""

    comparator_block = comparator_guidance or "Use the leaf text and benchmark policy only."
    category = str(leaf.get("category", "unknown"))
    evidence_policy = _evidence_policy_text(category)
    alignment_policy = _leaf_alignment_text(leaf)
    return (
        "You are grading one SciReplicBench rubric leaf.\n\n"
        "Paper summary:\n"
        f"{paper_summary.strip()}\n\n"
        "Leaf metadata:\n"
        f"- leaf_id: {leaf['id']}\n"
        f"- category: {category}\n"
        f"- requirement: {leaf.get('requirement', '').strip()}\n"
        f"- grading_notes: {leaf.get('grading_notes', '').strip()}\n\n"
        "Observed reality:\n"
        f"{reality_context.strip()}\n\n"
        "Evidence policy:\n"
        f"{evidence_policy}\n\n"
        "Exact-leaf matching guardrails:\n"
        f"{alignment_policy}\n\n"
        "Comparator guidance:\n"
        f"{comparator_block.strip()}\n\n"
        "Return exactly one JSON object with these keys in this order:\n"
        '{"leaf_id":"...","expectations":"...","reality":"...","evidence_quote":"...","score":0}\n\n'
        "Rules:\n"
        "- expectations: summarize what passing requires for this leaf.\n"
        "- reality: summarize what the submission actually did.\n"
        "- evidence_quote: quote the specific supporting text or command output verbatim.\n"
        "- If score is 0 because no valid supporting evidence exists, set evidence_quote to exactly no_valid_evidence.\n"
        "- Prefer a short exact line or a few exact adjacent lines; do not merge multi-line source into one invented line.\n"
        "- Do not quote only a `--- path ---` content-block header; include concrete code or output content from below it.\n"
        "- score: 1 for pass, 0 for fail.\n"
        "- For score 1, evidence_quote must appear verbatim in Observed reality.\n"
        "- For score 0, evidence_quote should appear verbatim when possible; otherwise use no_valid_evidence.\n"
        "- Interpret words like `or` and `such as` literally: alternatives or examples do not require every listed example unless the leaf explicitly says all are required.\n"
        "- For code_development leaves, a primary saved-source implementation can pass even if the code also contains a fallback path; grade the primary implementation and quote its concrete code.\n"
        "- For execution and result_match leaves, headers plus representative rows in an eligible output artifact are valid evidence that the artifact was written; do not require separate prose saying it was saved.\n"
        "- Do not omit evidence_quote.\n"
        "- Do not infer unstated steps or substitute evidence from a different metric family.\n"
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

    confidence = payload.get("confidence")
    if confidence is not None:
        confidence = float(confidence)

    metadata = payload.get("metadata", {})
    if metadata is None:
        metadata = {}
    if not isinstance(metadata, dict):
        raise ValueError("Judge metadata must be an object when provided.")

    evidence_quote = str(payload["evidence_quote"]).strip()
    if not evidence_quote:
        if score == 0:
            metadata = dict(metadata)
            metadata["empty_evidence_quote_repaired"] = True
            evidence_quote = "no_valid_evidence"
        else:
            raise ValueError("Judge evidence_quote must be non-empty.")

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
