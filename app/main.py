"""FastAPI application and HTTP routes.

OWNER: Ammar (App + Deploy).

Deliberately thin: it translates HTTP into a pipeline call and back.
"""

import logging

from fastapi import FastAPI, Header, Response, status

from app import pipeline
from app.config import settings
from app.schemas import ChatRequest, ChatResponse, HealthResponse

# Configure logging - stdout is the log destination under Docker and Kubernetes - never write to files.
logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)
logger.info("starting app_env=%s log_level=%s", settings.app_env, settings.log_level)

app = FastAPI(title="LLM PII Proxy")


# Check values that mean a dependency is broken. Anything else ("ok", "not_implemented", "echo_mode") does not fail the health check.
_FAILING = {"down", "error"}


@app.post("/v1/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> ChatResponse:
    """Sanitize a prompt, send it to the LLM, and return the restored reply."""
    # No validation, logging, or error handling. ChatRequest validated the
    # body, and the pipeline raises HTTPException which FastAPI renders. default=None on the header lets a missing key reach auth as None and come back as 401.
    return await pipeline.run(prompt=request.prompt, api_key=x_api_key)


@app.get("/health", response_model=HealthResponse)
async def health(response: Response) -> HealthResponse:
    """Liveness and readiness probe. Contract agreed with Son.

    Cheap and unauthenticated: it is polled every few seconds.
    """
    checks = {
        # TODO: real check - run `SELECT 1` against DATABASE_URL with a ~1-2s
        #       timeout; "ok" on success, "down" on timeout/connection error.
        #       A set URL alone is not enough: it must be reachable.
        "database": "not_implemented",
        # TODO: real check - GET {settings.presidio_url}/health via httpx with a
        #       ~1-2s timeout; "ok" on 200, "down" otherwise. Doesn't depend on
        #       Hira's code, so it can land as soon as Compose runs Presidio.
        "pii_analyzer": "not_implemented",
        # Deliberately NOT pinged: external and paid, and a vendor outage
        # shouldn't pull our pods from rotation (the pipeline returns 502).
        "llm": "ok" if settings.llm_url else "echo_mode",
    }

    if any(v in _FAILING for v in checks.values()):
        # Kubernetes and uptime checks read the status code, not the body.
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthResponse(status="degraded", checks=checks)

    return HealthResponse(status="ok", checks=checks)
