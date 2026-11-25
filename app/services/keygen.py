"""API key lifecycle management (create, list, revoke, rotate).

OWNER: Daniel (Security + UI).

Called by FastAPI admin endpoints. Multiple active keys per tenant are
supported, and every write enforces tenant scoping on `tenant_id`.

All database-backed functions signal failure by raising fastapi.HTTPException
directly (404 when a tenant or key does not exist, 503 when PostgreSQL is
unconfigured or unavailable), matching `app.services.auth`.

Raw API keys are NEVER stored in PostgreSQL or written to logs; only their
SHA-256 hex digest is persisted, and the plaintext key is returned once upon
creation or rotation.
"""

from dataclasses import dataclass
from datetime import datetime
import logging
import secrets
from typing import Any

from fastapi import HTTPException, status

from app.config import settings
from app.services.auth import _connect_db, hash_key_sha256

logger = logging.getLogger(__name__)

_TENANT_EXISTS_QUERY = "SELECT 1 FROM tenants WHERE id = %s"

_KEY_INSERT_QUERY = (
    "INSERT INTO api_keys (tenant_id, key_hash) "
    "VALUES (%s, %s) RETURNING id, created_at"
)

_KEY_LIST_QUERY = (
    "SELECT id, tenant_id, created_at FROM api_keys "
    "WHERE tenant_id = %s "
    "ORDER BY created_at DESC, id DESC"
)

_KEY_DELETE_QUERY = (
    "DELETE FROM api_keys "
    "WHERE id = %s AND tenant_id = %s"
)


@dataclass(frozen=True)
class CreatedApiKey:
    """Returned once when a key is created or rotated.

    `api_key` is the only time the plaintext secret is exposed; callers must
    deliver it to the tenant and never persist or log it.
    """

    id: int
    tenant_id: int
    api_key: str
    created_at: datetime


@dataclass(frozen=True)
class ApiKeyMetadata:
    """Safe view of an existing API key (never includes plaintext or hash)."""

    id: int
    tenant_id: int
    created_at: datetime


def _service_unavailable() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="API key service unavailable",
    )


def _open_db() -> Any:
    if not settings.database_url:
        logger.error("keygen unavailable: DATABASE_URL is not configured")
        raise _service_unavailable()

    try:
        return _connect_db(settings.database_url)
    except Exception as exc:
        logger.error("keygen db connect failed error=%s", type(exc).__name__)
        raise _service_unavailable() from exc


def generate_key() -> tuple[str, str]:
    """Return a 256-bit URL-safe API key and its SHA-256 hex digest."""
    plaintext_key = secrets.token_urlsafe(32)
    return plaintext_key, hash_key_sha256(plaintext_key)


def create_tenant_key(tenant_id: int) -> CreatedApiKey:
    """Create and persist a new API key for `tenant_id`.

    Tenants may hold multiple active keys simultaneously. Raises 404 if the
    tenant does not exist, or 503 if the database is unavailable.
    """
    conn = _open_db()
    try:
        with conn.cursor() as cur:
            cur.execute(_TENANT_EXISTS_QUERY, (tenant_id,))
            if cur.fetchone() is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Tenant not found",
                )

            plaintext_key, key_hash = generate_key()
            cur.execute(_KEY_INSERT_QUERY, (tenant_id, key_hash))
            row = cur.fetchone()
            if row is None:
                raise RuntimeError("INSERT INTO api_keys returned no row")
            key_id, created_at = row

        conn.commit()
        logger.info("api key created tenant=%d key_id=%d", tenant_id, int(key_id))
        return CreatedApiKey(
            id=int(key_id),
            tenant_id=tenant_id,
            api_key=plaintext_key,
            created_at=created_at,
        )
    except HTTPException:
        conn.rollback()
        raise
    except Exception as exc:
        conn.rollback()
        logger.error(
            "api key create failed tenant=%d error=%s",
            tenant_id,
            type(exc).__name__,
        )
        raise _service_unavailable() from exc
    finally:
        conn.close()


def list_tenant_keys(tenant_id: int) -> list[ApiKeyMetadata]:
    """Return metadata for all active API keys belonging to `tenant_id`.

    Raises 404 if the tenant does not exist, or 503 if the database is
    unavailable.
    """
    conn = _open_db()
    try:
        with conn.cursor() as cur:
            cur.execute(_TENANT_EXISTS_QUERY, (tenant_id,))
            if cur.fetchone() is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Tenant not found",
                )

            cur.execute(_KEY_LIST_QUERY, (tenant_id,))
            rows = cur.fetchall()

        return [
            ApiKeyMetadata(
                id=int(row[0]),
                tenant_id=int(row[1]),
                created_at=row[2],
            )
            for row in rows
        ]
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "api key list failed tenant=%d error=%s",
            tenant_id,
            type(exc).__name__,
        )
        raise _service_unavailable() from exc
    finally:
        conn.close()


def revoke_key(tenant_id: int, key_id: int) -> None:
    """Revoke a single API key owned by `tenant_id`.

    Raises 404 if no matching key exists for that tenant, or 503 if the
    database is unavailable.
    """
    conn = _open_db()
    try:
        with conn.cursor() as cur:
            cur.execute(_KEY_DELETE_QUERY, (key_id, tenant_id))
            deleted = cur.rowcount > 0

        if not deleted:
            conn.rollback()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found",
            )

        conn.commit()
        logger.info("api key revoked tenant=%d key_id=%d", tenant_id, key_id)
    except HTTPException:
        raise
    except Exception as exc:
        conn.rollback()
        logger.error(
            "api key revoke failed tenant=%d key_id=%d error=%s",
            tenant_id,
            key_id,
            type(exc).__name__,
        )
        raise _service_unavailable() from exc
    finally:
        conn.close()


def rotate_tenant_key(tenant_id: int, key_id: int) -> CreatedApiKey:
    """Atomically revoke `key_id` for `tenant_id` and issue a replacement key.

    Both the DELETE and INSERT run inside a single database transaction so a
    failure while inserting the replacement never leaves the tenant without
    its existing key. Raises 404 if the key does not exist for `tenant_id`,
    or 503 if the database is unavailable.
    """
    conn = _open_db()
    try:
        with conn.cursor() as cur:
            cur.execute(_KEY_DELETE_QUERY, (key_id, tenant_id))
            if cur.rowcount <= 0:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="API key not found",
                )

            plaintext_key, key_hash = generate_key()
            cur.execute(_KEY_INSERT_QUERY, (tenant_id, key_hash))
            row = cur.fetchone()
            if row is None:
                raise RuntimeError("INSERT INTO api_keys returned no row")
            new_key_id, created_at = row

        conn.commit()
        logger.info(
            "api key rotated tenant=%d old_key_id=%d new_key_id=%d",
            tenant_id,
            key_id,
            int(new_key_id),
        )
        return CreatedApiKey(
            id=int(new_key_id),
            tenant_id=tenant_id,
            api_key=plaintext_key,
            created_at=created_at,
        )
    except HTTPException:
        conn.rollback()
        raise
    except Exception as exc:
        conn.rollback()
        logger.error(
            "api key rotate failed tenant=%d key_id=%d error=%s",
            tenant_id,
            key_id,
            type(exc).__name__,
        )
        raise _service_unavailable() from exc
    finally:
        conn.close()
