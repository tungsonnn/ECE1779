"""API key authentication and per-tenant rate limiting.

OWNER: Daniel (Security + UI).

Runs first in the pipeline, before any text is examined or forwarded.

Both functions signal failure by raising fastapi.HTTPException directly.
FastAPI renders that into the right HTTP response, which is why pipeline.py
does not wrap these two calls in try/except.
"""

import hashlib
import logging
from typing import Any

from fastapi import HTTPException, status

from app.config import settings
from app.schemas import Tenant

logger = logging.getLogger(__name__)

# Indexed lookup against Son's api_keys + tenants tables (k.key_hash is UNIQUE).
_AUTH_LOOKUP_QUERY = (
    "SELECT t.id, t.name FROM api_keys k "
    "JOIN tenants t ON t.id = k.tenant_id "
    "WHERE k.key_hash = %s"
)

# Sliding 1-minute window count against Son's audit_log table.
_RATE_LIMIT_QUERY = (
    "SELECT count(*) FROM audit_log "
    "WHERE tenant_id = %s AND created_at > now() - interval '1 minute'"
)

_RATE_LIMIT_WINDOW_SECONDS = 60

# STUB (Daniel to replace): demo keys so the team can run the pipeline before
# Son's tenants/api_keys tables exist. Two tenants on purpose, to surface
# tenant-isolation bugs. Plaintext keys here are dev-only; the real version
# compares hashes from the database.
_DEMO_KEYS: dict[str, Tenant] = {
    "demo-key-a": Tenant(id=1, name="Demo Team A"),
    "demo-key-b": Tenant(id=2, name="Demo Team B"),
}


# Assuming we're generating 128-bit API keys, SHA-256 is safe to use for hashing API keys.
# We could also use HMAC-SHA-256 if we keep a server-side secret using a secrets manager.
def hash_key_sha256(key: str) -> str:
    """Return the hex representation of a SHA-256 hashed key."""
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


# Creating a dict of the hashed demo keys for testing purposes; in prod should
# refer to our actual hashed keys from the DB.
_HASHED_KEYS: dict[str, Tenant] = {
    hash_key_sha256(k): tenant for k, tenant in _DEMO_KEYS.items()
}


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "ApiKey"},
    )


def _overlimit(detail: str, retry_after: int = _RATE_LIMIT_WINDOW_SECONDS) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=detail,
        headers={"Retry-After": str(max(1, retry_after))},
    )


def _connect_db(database_url: str) -> Any:
    """Open a short-lived PostgreSQL connection using psycopg (v3) or psycopg2.

    Supports either driver so this module works regardless of which sync
    PostgreSQL package lands in requirements.txt. Replace with Son's shared
    connection pool once available.
    """
    try:
        import psycopg  # type: ignore[import-not-found]

        return psycopg.connect(database_url, connect_timeout=2)
    except ImportError:
        pass

    try:
        import psycopg2  # type: ignore[import-not-found]

        return psycopg2.connect(database_url, connect_timeout=2)
    except ImportError as exc:
        raise RuntimeError(
            "No PostgreSQL driver installed (install psycopg or psycopg2-binary)"
        ) from exc


def _lookup_tenant_by_hash(key_hash: str) -> Tenant | None:
    """Resolve a SHA-256 API key hash to its owning Tenant via PostgreSQL."""
    conn = _connect_db(settings.database_url)
    try:
        with conn.cursor() as cur:
            cur.execute(_AUTH_LOOKUP_QUERY, (key_hash,))
            row = cur.fetchone()
            if row is None:
                return None
            return Tenant(id=str(row[0]), name=str(row[1]))
    finally:
        conn.close()


def _count_recent_requests(tenant_id: str) -> int:
    """Count requests logged for `tenant_id` in the past 1 minute."""
    conn = _connect_db(settings.database_url)
    try:
        with conn.cursor() as cur:
            cur.execute(_RATE_LIMIT_QUERY, (tenant_id,))
            row = cur.fetchone()
            return int(row[0]) if row else 0
    finally:
        conn.close()


def authenticate(api_key: str | None) -> Tenant:
    """Resolve a presented API key to the tenant that owns it.

    Raw keys are never stored or logged; the presented key is SHA-256 hashed
    and looked up against `api_keys.key_hash` in PostgreSQL.

    Raises HTTPException 401 when the key is missing or unknown, or 503 if
    the authentication database is unavailable (fail-closed).
    """
    # Whitespace-only counts as missing, not invalid. Check before hitting DB.
    if not api_key or not api_key.strip():
        raise _unauthorized("Missing X-API-Key header")

    key_hash = hash_key_sha256(api_key)

    if not settings.database_url:
        if settings.app_env == "local":
            tenant = _HASHED_KEYS.get(key_hash)
        else:
            logger.error("auth unavailable: DATABASE_URL is not configured")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service unavailable",
            )
    else:
        try:
            tenant = _lookup_tenant_by_hash(key_hash)
        except Exception as exc:
            logger.error("auth lookup failed error=%s", type(exc).__name__)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service unavailable",
            ) from exc

    # Same 401 for any unknown key, so responses don't reveal why it failed.
    if tenant is None:
        raise _unauthorized("Invalid API key")

    return tenant


def check_rate_limit(tenant: Tenant) -> None:
    """Reject the request if the tenant is over its per-minute request budget.

    Counts rows in PostgreSQL's `audit_log` over a sliding 1-minute window so
    the limit holds across proxy replicas. Returns None when within budget;
    raises HTTPException 429 when the threshold is reached, or 503 if the
    database is unavailable (fail-closed).
    """
    limit = settings.rate_limit_per_minute

    if not settings.database_url:
        if settings.app_env == "local":
            logger.debug("skipping rate limit check: DATABASE_URL unset in local mode")
            return None
        logger.error("rate limit unavailable: DATABASE_URL is not configured")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Rate limit service unavailable",
        )

    try:
        count = _count_recent_requests(tenant.id)
    except Exception as exc:
        logger.error(
            "rate limit query failed tenant=%s error=%s",
            tenant.id,
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Rate limit service unavailable",
        ) from exc

    # Runs before audit.insert_pending(), so count == limit means this request
    # would be request #(limit + 1) in the current 1-minute window.
    if count >= limit:
        logger.warning(
            "rate limit exceeded tenant=%s count=%d limit=%d",
            tenant.id,
            count,
            limit,
        )
        raise _overlimit(
            f"Rate limit of {limit} requests/minute exceeded",
            retry_after=_RATE_LIMIT_WINDOW_SECONDS,
        )

    return None
