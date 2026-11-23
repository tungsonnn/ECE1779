"""Dependency checks for /health/deep.

OWNER: Son (Monitoring + Ops).

Each check returns one word: "ok", "down", or "not_configured". main.py turns
any "down" into a 503, which pulls the pod out of the load balancer (readiness
probe) and trips the DigitalOcean uptime check.

"not_configured" does NOT fail the check: an empty setting means that
dependency is not deployed in this environment yet, not that it broke.
"""

import logging

import httpx
import psycopg

from app.config import settings

logger = logging.getLogger(__name__)

# Probes run every few seconds, so a check must answer fast or fail.
_TIMEOUT_SECONDS = 2

def check_database() -> str:
    """Run SELECT 1 against Postgres."""
    if not settings.database_url:
        return "not_configured"
    try:
        with psycopg.connect(
            settings.database_url, connect_timeout=_TIMEOUT_SECONDS
        ) as conn:
            conn.execute("SELECT 1")
        return "ok"
    except psycopg.Error as exc:
        logger.warning("health database down: %s", type(exc).__name__)
        return "down"

def check_pii_analyzer() -> str:
    """GET the Presidio Analyzer's own /health endpoint."""
    if not settings.presidio_url:
        return "not_configured"
    try:
        response = httpx.get(
            f"{settings.presidio_url}/health", timeout=_TIMEOUT_SECONDS
        )
        return "ok" if response.status_code == 200 else "down"
    except httpx.HTTPError as exc:
        logger.warning("health pii_analyzer down: %s", type(exc).__name__)
        return "down"