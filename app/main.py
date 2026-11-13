"""FastAPI application and HTTP routes.

OWNER: Ammar (App + Deploy).

Deliberately thin: it translates HTTP into a pipeline call and back. Keeping
logic out of here means routes and pipeline evolve independently, and the
pipeline stays testable without a running server.
"""

import logging

from fastapi import FastAPI, Header

from app import pipeline
from app.schemas import ChatRequest, ChatResponse, HealthResponse

# TODO: Configure logging once, at import time, before the app is created:
#       logging.basicConfig(level=..., format=...) with a format carrying the
#       timestamp, level, and logger name. Everything in the app logs through
#       logging.getLogger(__name__), so this is the single place that decides
#       where lines go. Under Docker and Kubernetes stdout IS the log
#       destination - never write to files.

app = FastAPI(title="LLM PII Proxy", version="0.1.0")
# The name `app` matters: "app.main:app" is the import string that uvicorn, the
# Dockerfile CMD, and the Kubernetes manifest all refer to.


@app.post("/v1/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> ChatResponse:
    """Sanitize a prompt, send it to the LLM, and return the restored reply."""
    # TODO: Hand off to the pipeline and return its result:
    #           return await pipeline.run(prompt=request.prompt,
    #                                     api_key=x_api_key)
    #       Nothing else belongs in this function - no validation (ChatRequest
    #       already did it), no logging, no error handling (the pipeline raises
    #       HTTPException and FastAPI renders it).
    #
    #       default=None on the header is deliberate: a missing key should
    #       reach auth.authenticate() as None and come back as a clean 401,
    #       not a 422 from FastAPI's own validation layer.
    raise NotImplementedError


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Liveness and readiness probe. Contract agreed with Son."""
    # TODO: Return HealthResponse(status=..., checks={...}) with one entry per
    #       hard dependency.
    #   * For now: "database" and "pii_analyzer" reported as
    #     "not_implemented", and an "llm" entry derived from whether
    #     settings.llm_url is set.
    #   * status must become non-"ok" once a real check fails. Kubernetes uses
    #     this to decide whether this pod receives traffic, and Son's uptime
    #     check uses it to decide whether to alert - so a health endpoint that
    #     always returns "ok" silently defeats both.
    #   * Keep it cheap and unauthenticated: it is polled every few seconds.
    raise NotImplementedError
