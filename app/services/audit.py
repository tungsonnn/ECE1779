"""Audit log writes.

OWNER: Son (Monitoring + Ops).

Postgres is a separate server process; this module is the client that sends it
SQL. The table definitions themselves live in migrations, not here.

Two properties must survive the real implementation:

  1. Two-phase. insert_pending() runs BEFORE the provider call and
     complete_row() after, so a crash mid-request still leaves a trace. The
     call sites in pipeline.py encode this ordering - keep these as two
     functions even though one combined write would be less code.
  2. Metadata only. Tenant, entity counts, status, latency. Never the prompt,
     the reply, or the placeholder map: the audit trail must not become the
     store of sensitive data this project exists to avoid.
"""


import logging

logger = logging.getLogger(__name__)


class AuditUnavailable(RuntimeError):
    """Raised when an audit row cannot be written.

    pipeline.py turns a failed insert_pending() into a 503: no record, no
    request.
    """


def insert_pending(request_id: str, tenant_id: int) -> None:
    """Record that a request is about to be sent to the provider.

    Called after PII has been scrubbed and before the LLM call.
    """
    # TODO: Insert a row keyed on request_id with status "pending" and the
    #       tenant id, then return.
    #   * Raise AuditUnavailable if the write fails, so the pipeline refuses
    #     the request rather than letting text leave unrecorded.
    #   * A log line to stdout is an adequate placeholder until the table
    #     exists, and it keeps the two-phase ordering visible in the terminal.
    # STUB (Son to replace): log instead of writing a row.
    logger.info("audit pending request_id=%s tenant=%s", request_id, tenant_id)


def complete_row(
    request_id: str,
    status: str,
    latency_ms: int,
    pii_counts: dict[str, int],
    error_code: str | None = None,
) -> None:
    """Close out the row opened by insert_pending().

    Called on both the success path and the LLM-failure path, so every pending
    row reaches a terminal state.
    """
    # TODO: Update the row matching request_id with the final status, the
    #       error code, the latency, and the per-type entity counts.
    #   * Agreed values (status / error_code):
    #       "ok"    / None              - success
    #       "error" / "llm_error"       - provider call failed (502)
    #       "error" / "internal_error"  - unexpected failure after the row exists
    #     Failures before insert_pending() (auth, rate limit, PII, audit
    #     insert) never reach here: there is no row to close.
    #   * Leaving pending rows unresolved would make error-rate queries
    #     undercount failures and show phantom in-flight requests.
    # STUB (Son to replace): log instead of updating the row.
    logger.info(
        "audit complete request_id=%s status=%s error_code=%s latency_ms=%d pii_counts=%s",
        request_id, status, error_code, latency_ms, pii_counts,
    )
