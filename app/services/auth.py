"""API key authentication and per-tenant rate limiting.

OWNER: Daniel (Security + UI).

Runs first in the pipeline, before any text is examined or forwarded.

Both functions signal failure by raising fastapi.HTTPException directly.
FastAPI renders that into the right HTTP response, which is why pipeline.py
does not wrap these two calls in try/except.
"""

import logging

from fastapi import HTTPException, status

from app.schemas import Tenant

logger = logging.getLogger(__name__)

# STUB (Daniel to replace): demo keys so the team can run the pipeline before
# Son's tenants/api_keys tables exist. Two tenants on purpose, to surface
# tenant-isolation bugs. Plaintext keys here are dev-only; the real version
# compares hashes from the database.
_DEMO_KEYS: dict[str, Tenant] = {
    "demo-key-a": Tenant(id="tenant-a", name="Demo Team A"),
    "demo-key-b": Tenant(id="tenant-b", name="Demo Team B"),
}


def authenticate(api_key: str | None) -> Tenant:
    """Resolve a presented API key to the tenant that owns it.

    Raises HTTPException 401 when the key is missing or unknown.
    """
    # TODO: Implement tenant lookup.
    #   * Missing or empty api_key -> raise HTTPException(401, "Missing
    #     X-API-Key header"). Unknown key -> raise HTTPException(401, "Invalid
    #     API key").
    #   * Hash the presented key and compare against a stored hash. Raw keys
    #     are never stored or logged (proposal: "hashed per-tenant API keys").
    #   * Blocked on Son's tenants/api_keys tables for the real lookup. Until
    #     then, a module-level dict of demo keys unblocks everyone else. Use
    #     two tenants, not one: a single-tenant stub hides tenant-isolation
    #     bugs, and multi-tenancy is a graded core feature.
    # STUB (Daniel to replace): in-memory demo key lookup.
    if not api_key:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing X-API-Key header")
    tenant = _DEMO_KEYS.get(api_key)
    if tenant is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid API key")
    return tenant


def check_rate_limit(tenant: Tenant) -> None:
    """Reject the request if the tenant is over its request budget.

    Returns None when the tenant is within budget; raises HTTPException 429
    when it is not.
    """
    # TODO: Implement the rate limit check.
    #   * Counters must live in PostgreSQL, not in process memory. The proxy
    #     runs two replicas, so a per-process counter would let a tenant send
    #     double its limit (proposal: "Keeping rate limits in PostgreSQL makes
    #     them hold across replicas").
    #   * Blocked on Son's rate-limit table.
    # STUB (Daniel to replace): always within budget.
    return None
