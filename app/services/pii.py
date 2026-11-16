"""PII detection, placeholder substitution, and restoration.

OWNER: Hira (LLM + PII).

The privacy boundary of the whole system: scrub() runs before anything leaves
the process, restore() runs on the way back.

The Presidio Analyzer runs as its own container because it carries a
memory-heavy NLP model that is shared across proxy replicas. So this module is
an HTTP client for that container, not a place where Presidio is imported.

Entity types in scope (README team decision): EMAIL_ADDRESS, PHONE_NUMBER,
CREDIT_CARD, IP_ADDRESS, PERSON, LOCATION, plus one custom recognizer for
secrets and API keys pasted alongside code (API_KEY).

Logging rule: never log the text, the detected values, or the placeholder map.
Entity types, counts and placeholder names (e.g. "<PERSON_3>") are safe to log.
"""

import logging
import re

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# Entity types we ask Presidio for. Anything else Presidio could find (URLs,
# dates, ...) is not requested, so it is never replaced.
ENTITIES = [
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "CREDIT_CARD",
    "IP_ADDRESS",
    "PERSON",
    "LOCATION",
    "API_KEY",
]

# Our custom secrets / API-key detector, sent to Presidio with every request as
# an "ad-hoc recognizer" (no custom Presidio image needed). Patterns:
#   sk-...       OpenAI-style secret keys (at least 20 characters after "sk-")
#   ghp_...      GitHub personal access tokens (also gho_, ghu_, ghs_, ghr_)
#   AKIA...      AWS access key ids (also ASIA... temporary keys)
API_KEY_RECOGNIZER = {
    "name": "api_key_recognizer",
    "supported_language": "en",
    "supported_entity": "API_KEY",
    "patterns": [
        {"name": "openai_style_key", "regex": r"\bsk-[A-Za-z0-9_-]{20,}", "score": 0.9},
        {"name": "github_token", "regex": r"\bgh[pousr]_[A-Za-z0-9]{36,}\b", "score": 0.9},
        {"name": "aws_access_key_id", "regex": r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b", "score": 0.9},
    ],
}

# Results below this confidence are ignored. Kept low on purpose: for a privacy
# proxy, hiding a word that wasn't PII is much cheaper than leaking one that was.
# (Presidio scores weak phone-number matches around 0.4.) Revisit with the
# accuracy measurement on fake data.
SCORE_THRESHOLD = 0.35

# Fail fast if Presidio does not answer: a hung analyzer must become a 503,
# not a request that waits forever.
PRESIDIO_TIMEOUT_SECONDS = 5.0

# Matches placeholders we create, e.g. "<PERSON_1>", "<EMAIL_ADDRESS_12>".
_PLACEHOLDER_RE = re.compile(r"<([A-Z][A-Z_]*)_(\d+)>")


class PIIDetectionUnavailable(RuntimeError):
    """Raised when detection could not run at all.

    Analyzer unreachable, model missing, request timed out. pipeline.py turns
    this into a 503: text that could not be scanned is never forwarded.

    Raising this is how this module participates in the fail-closed guarantee,
    so on failure raise it rather than returning the text unchanged.
    """


def scrub(text: str) -> tuple[str, dict[str, str], dict[str, int]]:
    """Replace every detected PII span with a numbered placeholder.

    Returns a 3-tuple:
        sanitized_text:  safe to send to the provider.
        placeholder_map: placeholder -> real value, e.g. {"<PERSON_1>": "Jane"}.
                         In memory for one request only; never persisted.
        pii_counts:      entity type -> count, e.g. {"EMAIL_ADDRESS": 2}, for
                         the audit row. Counts every occurrence that was replaced.

    Raises PIIDetectionUnavailable if the Analyzer cannot be reached or answers
    with something unusable.
    """
    if not text:
        return text, {}, {}

    findings = _analyze(text)
    spans = _resolve_overlaps(findings)

    # 1. Name each distinct value, reading left to right, numbered per type.
    #    The same value always gets the same placeholder, so the model can keep
    #    referring to one person consistently.
    #    If the user's own text already contains something that looks like a
    #    placeholder (e.g. they typed "<PERSON_1>"), that name is skipped, so
    #    restore() can never confuse their text with a real value.
    already_in_text = {m.group(0) for m in _PLACEHOLDER_RE.finditer(text)}
    value_to_placeholder: dict[tuple[str, str], str] = {}
    next_number: dict[str, int] = {}
    pii_counts: dict[str, int] = {}
    for start, end, entity in spans:
        value = text[start:end]
        key = (entity, value)
        if key not in value_to_placeholder:
            placeholder = None
            while placeholder is None or placeholder in already_in_text:
                next_number[entity] = next_number.get(entity, 0) + 1
                placeholder = f"<{entity}_{next_number[entity]}>"
            value_to_placeholder[key] = placeholder
        pii_counts[entity] = pii_counts.get(entity, 0) + 1

    # 2. Swap them in, starting from the END of the text. Replacing a span
    #    changes the length of the text, which would shift the positions of
    #    every later span; working backwards keeps earlier positions valid.
    sanitized = text
    for start, end, entity in sorted(spans, key=lambda s: s[0], reverse=True):
        placeholder = value_to_placeholder[(entity, text[start:end])]
        sanitized = sanitized[:start] + placeholder + sanitized[end:]

    placeholder_map = {ph: value for (_, value), ph in value_to_placeholder.items()}

    logger.info("pii scrubbed counts=%s", pii_counts)
    return sanitized, placeholder_map, pii_counts


def restore(text: str, placeholder_map: dict[str, str]) -> str:
    """Swap placeholders in the LLM reply back to their real values.

    Pure string work, no I/O, so this does not fail. If the model invented or
    changed a placeholder (e.g. "<PERSON_3>" when only two exist), it is left
    exactly as it is and logged. We never guess a value: a wrong guess could
    show one person's data in place of another's.
    """
    unmatched: list[str] = []

    def _swap(match: re.Match[str]) -> str:
        placeholder = match.group(0)
        if placeholder in placeholder_map:
            return placeholder_map[placeholder]
        unmatched.append(placeholder)
        return placeholder

    restored = _PLACEHOLDER_RE.sub(_swap, text)

    if unmatched:
        # Placeholder names are not PII, so they are safe to log.
        logger.warning(
            "restore left %d unmatched placeholder(s): %s",
            len(unmatched),
            sorted(set(unmatched)),
        )
    return restored


def _analyze(text: str) -> list[dict]:
    """Ask the Presidio Analyzer container what PII is in `text`.

    Returns Presidio's raw findings: a list of dicts with entity_type, start,
    end and score. Any failure becomes PIIDetectionUnavailable (fail closed).
    """
    body = {
        "text": text,
        "language": "en",
        "entities": ENTITIES,
        "score_threshold": SCORE_THRESHOLD,
        "ad_hoc_recognizers": [API_KEY_RECOGNIZER],
    }
    try:
        response = httpx.post(
            f"{settings.presidio_url}/analyze",
            json=body,
            timeout=PRESIDIO_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        findings = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.error("presidio analyzer unavailable: %s", type(exc).__name__)
        raise PIIDetectionUnavailable("PII analyzer unavailable") from exc

    if not isinstance(findings, list) or not all(_is_finding(f) for f in findings):
        logger.error("presidio analyzer returned an unexpected response shape")
        raise PIIDetectionUnavailable("PII analyzer returned an unexpected response")
    return findings


def _is_finding(item: object) -> bool:
    """True if `item` looks like one Presidio result."""
    return (
        isinstance(item, dict)
        and isinstance(item.get("entity_type"), str)
        and isinstance(item.get("start"), int)
        and isinstance(item.get("end"), int)
        and isinstance(item.get("score"), (int, float))
        and 0 <= item["start"] < item["end"]
    )


def _resolve_overlaps(findings: list[dict]) -> list[tuple[int, int, str]]:
    """Keep one finding per stretch of text.

    Presidio can flag the same characters twice (e.g. a URL inside an email
    address). We keep the most confident finding, then the longest, and drop
    anything that overlaps a finding we already kept. Only entity types we
    asked for are kept. Returns (start, end, entity_type), sorted by start.
    """
    candidates = [f for f in findings if f["entity_type"] in ENTITIES]
    candidates.sort(key=lambda f: (-f["score"], -(f["end"] - f["start"]), f["start"]))

    kept: list[tuple[int, int, str]] = []
    for f in candidates:
        start, end = f["start"], f["end"]
        if all(end <= k_start or start >= k_end for k_start, k_end, _ in kept):
            kept.append((start, end, f["entity_type"]))
    return sorted(kept)
