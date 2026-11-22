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


import json
import logging

import psycopg

from app.config import settings

logger = logging.getLogger(__name__)

# Fail fast: a slow database should turn into a 503, not a hung request.
_CONNECT_TIMEOUT_SECONDS = 2


class AuditUnavailable(RuntimeError):
    """Raised when an audit row cannot be written.

    pipeline.py turns a failed insert_pending() into a 503: no record, no
    request.
    """


def insert_pending(request_id: str, tenant_id: int) -> None:
    """Record that a request is about to be sent to the provider.

    Called after PII has been scrubbed and before the LLM call.
    """
    try:
        with _connect() as conn:
            conn.execute(
                "INSERT INTO audit_log (request_id, tenant_id) VALUES (%s, %s)",
                (request_id, tenant_id),
            )
    except psycopg.Error as exc:
        raise AuditUnavailable("audit insert failed") from exc
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
    # Agreed values (status / error_code):
    #   "ok"    / None              - success
    #   "error" / "llm_error"       - provider call failed (502)
    #   "error" / "internal_error"  - unexpected failure after the row exists
    try:
        with _connect() as conn:
            cur = conn.execute(
                """
                UPDATE audit_log
                SET status = %s, latency_ms = %s, entity_counts = %s, error_code = %s
                WHERE request_id = %s
                """,
                (status, latency_ms, json.dumps(pii_counts), error_code, request_id),
            )
            if cur.rowcount != 1:
                raise AuditUnavailable(f"no pending row for request_id={request_id}")
    except psycopg.Error as exc:
        raise AuditUnavailable("audit complete failed") from exc
    logger.info(
        "audit complete request_id=%s status=%s error_code=%s latency_ms=%d",
        request_id, status, error_code, latency_ms,
    )


def _connect() -> psycopg.Connection:
    """Open a short-lived connection; `with` commits on success.

    One connection per call is simple and fine at our traffic. Swap in a pool
    (psycopg_pool) later if latency shows it matters.
    """
    return psycopg.connect(
        settings.database_url, connect_timeout=_CONNECT_TIMEOUT_SECONDS
    )
