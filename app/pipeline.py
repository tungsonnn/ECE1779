"""The ordered request pipeline.

OWNER: Ammar (App + Deploy).

This module owns two things and delegates everything else: the ORDER of the
steps, and the FAILURE POLICY. Each step lives in app/services/, owned by
whoever owns that area, so once the order is frozen this should be the file
that changes least.

Order (proposal, Request flow):
    1. authenticate the API key
    2. check the tenant's rate limit
    3. detect PII and substitute numbered placeholders
    4. insert a PENDING audit row       <- before anything leaves the system
    5. call the LLM with sanitized text only
    6. restore real values in the reply
    7. complete the audit row

Failure policy - fail closed. If PII detection or the audit write is
unavailable, refuse the request rather than forward text we could not scan or
forward text we have no record of. The status codes carry that distinction:

    503  our own dependency failed, so we refused (fail-closed worked)
    502  the upstream provider failed, so we tried and could not finish

That split means a dashboard or a grader can tell "we protected the data" from
"the vendor was down" without reading logs.
"""

import logging
import time
import uuid

from fastapi import HTTPException, status

from app.schemas import ChatResponse, PipelineContext
from app.services import audit, auth, llm_client, pii

logger = logging.getLogger(__name__)


async def run(prompt: str, api_key: str | None) -> ChatResponse:
    """Run one request through every step and return the response body.

    Takes plain arguments rather than a FastAPI Request object so the pipeline
    can be tested without a running server; HTTP concerns stay in app/main.py.

    Logging rule: every line carries request_id, and never the prompt, the
    reply, or the placeholder map.
    """
    started = time.perf_counter()
    request_id = str(uuid.uuid4())

    # 1-2. Auth and rate limit. Both raise HTTPException (401/429) themselves.
    tenant = auth.authenticate(api_key)
    auth.check_rate_limit(tenant)

    ctx = PipelineContext(request_id=request_id, tenant=tenant, raw_prompt=prompt)

    # 3. Scrub. Fail closed: text we couldn't scan never leaves.
    # TODO: becomes `await pii.scrub(prompt)` once Hira makes scrub() async
    #       (it makes a network call to Presidio; a sync call blocks the loop).
    try:
        ctx.sanitized_prompt, ctx.placeholder_map, ctx.pii_counts = pii.scrub(prompt)
    except pii.PIIDetectionUnavailable:
        logger.error("pii detection unavailable request_id=%s", request_id)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "PII detection unavailable"
        )

    # 4. Pending audit row. After scrub, before anything leaves the system.
    try:
        audit.insert_pending(request_id, tenant.id)
    except audit.AuditUnavailable:
        logger.error("audit insert failed request_id=%s", request_id)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Audit log unavailable"
        )

    # 5. LLM call with sanitized text only. Data leaves the system here.
    try:
        ctx.llm_reply_sanitized = await llm_client.complete(ctx.sanitized_prompt)
    except llm_client.LLMUnavailable:
        logger.error("llm unavailable request_id=%s", request_id)
        # Close the pending row first so it doesn't stay orphaned.
        _complete_audit(ctx, "llm_error", started)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "LLM provider unavailable")

    # 6. Restore real values. Pure string substitution, no I/O.
    ctx.restored_reply = pii.restore(ctx.llm_reply_sanitized, ctx.placeholder_map)

    # 7. Close the audit row.
    latency_ms = _complete_audit(ctx, "ok", started)

    logger.info(
        "request ok request_id=%s tenant=%s pii_found=%d latency_ms=%d",
        request_id, tenant.id, ctx.pii_entities_found, latency_ms,
    )
    return ChatResponse(
        request_id=request_id,
        reply=ctx.restored_reply,
        pii_entities_found=ctx.pii_entities_found,
        latency_ms=latency_ms,
    )


def _complete_audit(ctx: PipelineContext, final_status: str, started: float) -> int:
    """Close the pending audit row; return the latency it recorded.

    A failure here is logged, not raised: by now the sanitized prompt has
    already left, so refusing protects nothing. The pending row still proves
    the request happened; Son treats long-stuck "pending" rows as
    "completion lost".
    """
    latency_ms = _elapsed_ms(started)
    try:
        audit.complete_row(ctx.request_id, final_status, latency_ms, ctx.pii_counts)
    except audit.AuditUnavailable:
        logger.error(
            "audit complete failed request_id=%s status=%s",
            ctx.request_id, final_status,
        )
    return latency_ms


def _elapsed_ms(started: float) -> int:
    """Whole milliseconds elapsed since a time.perf_counter() reading."""
    return int((time.perf_counter() - started) * 1000)
