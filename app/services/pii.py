"""PII detection, placeholder substitution, and restoration.

OWNER: Hira (LLM + PII).

The privacy boundary of the whole system: scrub() runs before anything leaves
the process, restore() runs on the way back.

The Presidio Analyzer runs as its own container because it carries a
memory-heavy NLP model that is shared across proxy replicas. So this module is
an HTTP client for that container, not a place where Presidio is imported.

Entity types in scope (README team decision): EMAIL_ADDRESS, PHONE_NUMBER,
CREDIT_CARD, IP_ADDRESS, PERSON, LOCATION, plus one custom recognizer for
secrets and API keys pasted alongside code.
"""


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
                         the audit row.
    """
    # TODO: Implement detection and substitution.
    #   * Call the Presidio Analyzer container over HTTP. Its URL belongs in
    #     app/config.py as a setting, not an os.environ call in this file.
    #   * Number placeholders per entity type, and reuse the same placeholder
    #     for repeated occurrences of the same value so the model can still
    #     refer to one person consistently.
    #   * Substitution happens here rather than in Presidio's Anonymizer
    #     because the Anonymizer cannot produce numbered, reversible
    #     placeholders (proposal, Components and scaling).
    #   * Raise PIIDetectionUnavailable if the Analyzer cannot be reached.
    raise NotImplementedError


def restore(text: str, placeholder_map: dict[str, str]) -> str:
    """Swap placeholders in the LLM reply back to their real values."""
    # TODO: Substitute each placeholder in `text` with its real value.
    #   * Pure string work, no I/O, so this should not fail - which is why
    #     pipeline.py does not guard this call.
    #   * Known risk (proposal, Risks and mitigations): the model may alter or
    #     drop a placeholder. Leave an unmatched placeholder as-is and log that
    #     it happened. Never guess a value.
    raise NotImplementedError
