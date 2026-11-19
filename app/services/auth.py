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

# Assuming we're generating 128-bit API keys, SHA-256 is safe to use for hashing API keys
# We could also use HMAC-SHA-256 if we keep a server side secret using a secrets manager
import hashlib

logger = logging.getLogger(__name__)


# STUB (Daniel to replace): demo keys so the team can run the pipeline before
# Son's tenants/api_keys tables exist. Two tenants on purpose, to surface
# tenant-isolation bugs. Plaintext keys here are dev-only; the real version
# compares hashes from the database.
_DEMO_KEYS: dict[str, Tenant] = {
    "demo-key-a": Tenant(id=1, name="Demo Team A"),
    "demo-key-b": Tenant(id=2, name="Demo Team B"),
}

# Returns the hex representation of a SHA256 hashed key
def hash_key_sha256(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()

# Creating a dict of the hashed demo keys for testing purposes, in prod should 
# refer to our actual hashed keys from the DB
_HASHED_KEYS: dict[str, Tenant] = {
    hash_key_sha256(k): tenant for k, tenant in _DEMO_KEYS.items()
}

def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate", "ApiKey"}
    )

def _overlimit(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=detail,
        headers={"Retry-After", "60"} # Placeholder until actual rate limits determined
    )

def authenticate(api_key: str | None) -> Tenant:
    """Resolve a presented API key to the tenant that owns it.

    Raw keys are never stored or logged; the presented key is hashed and
    looked up against stored hashes.

    Raises HTTPException 401 when the key is missing or unknown.
    """
    # STUB (Daniel to replace): lookup is backed by the in-memory _HASHED_KEYS
    # (built from two demo tenants) until the tenants/api_keys tables land.
    # Keep at least two tenants in the stub so tenant-isolation bugs surface.

    # Whitespace-only counts as missing, not invalid.
    if not api_key or not api_key.strip():
        raise _unauthorized("Missing X-API-Key header")

    # In prod, _HASHED_KEYS should refer to our DB of saved hashed keys
    tenant = _HASHED_KEYS.get(hash_key_sha256(api_key))

    # Same 401 for any unknown key, so responses don't reveal why it failed.
    if tenant is None:
        raise _unauthorized("Invalid API key")

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

    if count > limit:
        raise _overlimit(
            f"Rate limit of {limit} requests/second exceeded",
            retry_after = retry_after,
        )
    return None
