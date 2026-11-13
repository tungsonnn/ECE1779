"""Request/response models and the per-request internal context.

OWNER: Ammar (App + Deploy).

Two distinct jobs live here:

  * The Pydantic models are the EXTERNAL contract. FastAPI validates incoming
    requests against them before any of our code runs, and publishes them as
    the OpenAPI docs at /docs that the rest of the team builds against.
  * Tenant and PipelineContext are INTERNAL. Plain dataclasses, never on the
    wire.

The field names here are the frozen interface: changing one changes what
Daniel's UI, Son's queries, and Hira's tests all expect.
"""

from dataclasses import dataclass, field

from pydantic import BaseModel


class ChatRequest(BaseModel):
    """Body of POST /v1/chat."""

    prompt: str

    # TODO: Constrain the field so malformed input is rejected at the boundary
    #       instead of inside the pipeline: minimum length 1 (no empty prompts)
    #       and a sane maximum (~20k chars). Use pydantic's
    #       Field(min_length=..., max_length=...). A rejected body returns 422
    #       before pipeline.run() is ever called.


class ChatResponse(BaseModel):
    """Body returned by POST /v1/chat on success."""

    request_id: str
    reply: str
    pii_entities_found: int
    latency_ms: int


class HealthResponse(BaseModel):
    """Body returned by GET /health.

    `checks` maps a dependency name to its state, so one endpoint answers both
    "are you alive?" (for the load balancer) and "what exactly is broken?" (for
    Son's uptime check and dashboard).
    """

    status: str
    checks: dict[str, str]


@dataclass
class Tenant:
    """The team an API key belongs to. Resolved by services.auth."""

    id: str
    name: str


@dataclass
class PipelineContext:
    """One request's state as it moves through the pipeline.

    Created per request and discarded when the response is returned. Holding it
    in one object keeps pipeline.py readable and gives a single answer to "what
    do we keep in memory about a request?" - a question this project will be
    asked during the demo.

    placeholder_map is the sensitive field: it is the only thing in the process
    that maps a placeholder back to real PII. It must never be logged,
    returned, or written to the database.
    """

    request_id: str
    tenant: Tenant
    raw_prompt: str
    sanitized_prompt: str | None = None
    placeholder_map: dict[str, str] = field(default_factory=dict)
    pii_counts: dict[str, int] = field(default_factory=dict)
    llm_reply_sanitized: str | None = None
    restored_reply: str | None = None

    @property
    def pii_entities_found(self) -> int:
        """Total entities detected across all types, for the response body."""
        # TODO: Sum the values of pii_counts.
        #       pii_counts is per entity type ({"EMAIL_ADDRESS": 2}) rather
        #       than a bare integer because Son's audit table and Hira's
        #       accuracy measurement both need the breakdown. This property is
        #       just the rollup for the API response.
        raise NotImplementedError
