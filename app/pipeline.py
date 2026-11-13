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

from app.schemas import ChatResponse

logger = logging.getLogger(__name__)


async def run(prompt: str, api_key: str | None) -> ChatResponse:
    """Run one request through every step and return the response body.

    Takes plain arguments rather than a FastAPI Request object so the pipeline
    can be tested without a running server; HTTP concerns stay in app/main.py.
    """
    # TODO: Implement the orchestration, in this order:
    #
    #   1. Start a timer (time.perf_counter()) and generate a request_id
    #      (uuid4, as a str). Generate it here, not in main.py - this id is
    #      what ties the pending audit row to its completion.
    #   2. auth.authenticate(api_key) -> Tenant, then
    #      auth.check_rate_limit(tenant). Do NOT wrap these in try/except:
    #      they raise HTTPException already and FastAPI renders it.
    #   3. Build a PipelineContext(request_id=..., tenant=...,
    #      raw_prompt=prompt).
    #   4. pii.scrub(prompt) and assign all three return values onto the
    #      context. Catch pii.PIIDetectionUnavailable -> log with the
    #      request_id, then raise HTTPException 503.
    #   5. audit.insert_pending(request_id, tenant.id). Catch
    #      audit.AuditUnavailable -> log, then raise HTTPException 503.
    #      This lands after scrubbing (so pii_counts is available to write) and
    #      before the network call (so nothing leaves unrecorded). Both
    #      constraints matter, which is why this step sits exactly here.
    #   6. await llm_client.complete(ctx.sanitized_prompt). Catch
    #      llm_client.LLMUnavailable -> call audit.complete_row() with status
    #      "llm_error" FIRST, then raise HTTPException 502. Skipping that write
    #      leaves an orphaned pending row and skews Son's error-rate queries.
    #   7. pii.restore(reply, ctx.placeholder_map). No guard needed - it is
    #      pure string substitution with no I/O.
    #   8. audit.complete_row(request_id, "ok", latency_ms, ctx.pii_counts).
    #   9. Return ChatResponse(request_id=..., reply=...,
    #      pii_entities_found=..., latency_ms=...).
    #
    # Logging rule for every line in this file: include request_id=... so Son
    # can correlate, and never include the prompt, the reply, or the
    # placeholder map.
    raise NotImplementedError


def _elapsed_ms(started: float) -> int:
    """Whole milliseconds elapsed since a time.perf_counter() reading."""
    # TODO: Convert the perf_counter delta to an int number of milliseconds.
    #       Factored out because both the error path and the success path need
    #       it.
    raise NotImplementedError
