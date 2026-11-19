"""Hardened HTTP client and session telemetry helpers for the Streamlit UI.

OWNER: Daniel (Security + UI).

Security guarantees:
  * Strict HTTP(S) URL validation; rejects non-HTTP schemes and embedded creds.
  * Disables HTTP redirects (`follow_redirects=False`) to prevent redirect SSRF.
  * Enforces client-side prompt length and response byte limits.
  * Sanitizes network errors before returning them to the browser so internal
    cluster URLs, IPs, and stack details are never leaked (detailed diagnostics
    go to stdout logs only; prompts, replies, and API keys are NEVER logged).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
import time
from typing import Any
from urllib.parse import urlparse

import httpx

try:
    from ui.config import ui_settings
except ImportError:  # When running directly inside ui/ or Docker /srv
    from config import ui_settings

logger = logging.getLogger(__name__)

DEFAULT_API_URL = ui_settings.api_url


@dataclass(frozen=True)
class ChatResult:
    """Parsed response from POST /v1/chat."""

    request_id: str
    reply: str
    pii_entities_found: int
    latency_ms: int
    raw: dict[str, Any]
    # Optional forward-compatible fields if the backend exposes them later.
    sanitized_prompt: str | None = None
    pii_counts: dict[str, int] | None = None


@dataclass(frozen=True)
class HealthResult:
    """Parsed response from GET /health."""

    status: str
    checks: dict[str, str]
    http_status: int
    raw: dict[str, Any]
    probe_ms: int = 0


@dataclass(frozen=True)
class RequestLogEntry:
    """Metadata-only client-side audit record for the current UI session.

    Mirrors the proxy's privacy guarantee: never stores prompts, replies,
    API keys, or placeholder maps.
    """

    timestamp: str
    tenant_label: str
    status_code: int | None
    outcome: str
    request_id: str | None = None
    pii_entities_found: int = 0
    latency_ms: int | None = None
    error_detail: str | None = None


class ProxyAPIError(Exception):
    """Structured, user-safe error raised when a call to the proxy API fails."""

    def __init__(
        self,
        detail: str,
        *,
        status_code: int | None = None,
        category: str = "unknown",
        retry_after: str | None = None,
    ) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code
        self.category = category
        self.retry_after = retry_after


def normalize_api_url(api_url: str) -> str:
    """Validate and normalize a proxy base URL.

    Only `http://` and `https://` URLs with an explicit hostname and no
    embedded userinfo/query/fragment are accepted.
    """
    cleaned = api_url.strip().rstrip("/")
    if not cleaned:
        raise ProxyAPIError(
            "API URL cannot be empty.",
            status_code=None,
            category="validation",
        )

    parsed = urlparse(cleaned)
    if parsed.scheme not in {"http", "https"}:
        raise ProxyAPIError(
            "API URL must use http:// or https://.",
            status_code=None,
            category="validation",
        )
    if not parsed.hostname:
        raise ProxyAPIError(
            "API URL must include a valid hostname.",
            status_code=None,
            category="validation",
        )
    if parsed.username or parsed.password:
        raise ProxyAPIError(
            "API URL must not contain embedded credentials.",
            status_code=None,
            category="validation",
        )
    if parsed.query or parsed.fragment:
        raise ProxyAPIError(
            "API URL must not include query parameters or fragments.",
            status_code=None,
            category="validation",
        )
    return cleaned


def _extract_error_detail(response: httpx.Response) -> str:
    """Pull FastAPI's `detail` field (or safe fallback) from an error response."""
    if len(response.content) > ui_settings.max_response_bytes:
        return f"HTTP {response.status_code} (oversized error payload)"

    try:
        payload = response.json()
    except ValueError:
        text = response.text.strip()[:300]
        return text or f"HTTP {response.status_code}"

    if isinstance(payload, dict) and "detail" in payload:
        detail = payload["detail"]
        if isinstance(detail, list):
            parts = []
            for item in detail:
                if isinstance(item, dict):
                    loc = ".".join(str(x) for x in item.get("loc", []))
                    msg = item.get("msg", str(item))
                    parts.append(f"{loc}: {msg}" if loc else str(msg))
                else:
                    parts.append(str(item))
            return "; ".join(parts)[:400]
        return str(detail)[:400]

    return f"HTTP {response.status_code}"


def _classify_status(status_code: int) -> str:
    """Map proxy HTTP status codes to semantic UI error categories."""
    if status_code == 401:
        return "auth"
    if status_code == 422:
        return "validation"
    if status_code == 429:
        return "rate_limit"
    if status_code == 503:
        return "fail_closed"
    if status_code == 502:
        return "upstream"
    return "server" if status_code >= 500 else "client"


def _check_response_size(response: httpx.Response, max_bytes: int) -> None:
    if len(response.content) > max_bytes:
        raise ProxyAPIError(
            "Proxy response exceeded maximum allowed size.",
            status_code=response.status_code,
            category="server",
        )


def send_chat(
    api_url: str,
    prompt: str,
    api_key: str | None,
    *,
    timeout: float | None = None,
    max_prompt_chars: int | None = None,
    max_response_bytes: int | None = None,
    transport: httpx.BaseTransport | None = None,
) -> ChatResult:
    """Send a prompt to POST /v1/chat and return the parsed ChatResult."""
    base_url = normalize_api_url(api_url)
    limit = max_prompt_chars if max_prompt_chars is not None else ui_settings.max_prompt_chars
    resp_cap = max_response_bytes if max_response_bytes is not None else ui_settings.max_response_bytes
    req_timeout = timeout if timeout is not None else ui_settings.request_timeout_seconds

    if not prompt or not prompt.strip():
        raise ProxyAPIError(
            "Prompt cannot be empty.",
            status_code=None,
            category="validation",
        )
    if len(prompt) > limit:
        raise ProxyAPIError(
            f"Prompt exceeds the maximum allowed length of {limit:,} characters.",
            status_code=None,
            category="validation",
        )

    headers: dict[str, str] = {"Content-Type": "application/json", "Accept": "application/json"}
    if api_key is not None:
        headers["X-API-Key"] = api_key

    try:
        with httpx.Client(
            timeout=req_timeout,
            follow_redirects=False,
            transport=transport,
        ) as client:
            response = client.post(
                f"{base_url}/v1/chat",
                json={"prompt": prompt},
                headers=headers,
            )
    except httpx.TimeoutException as exc:
        logger.warning("chat request timed out after %.1fs", req_timeout)
        raise ProxyAPIError(
            f"Request timed out after {req_timeout:.0f}s waiting for the proxy.",
            status_code=None,
            category="network",
        ) from exc
    except httpx.HTTPError as exc:
        logger.warning("chat request transport error: %s", type(exc).__name__)
        raise ProxyAPIError(
            "Proxy service is currently unreachable. Please try again shortly.",
            status_code=None,
            category="network",
        ) from exc

    if 300 <= response.status_code < 400:
        logger.warning("chat request received unexpected redirect status=%d", response.status_code)
        raise ProxyAPIError(
            "Proxy returned an unexpected redirect response.",
            status_code=response.status_code,
            category="server",
        )

    if response.status_code != 200:
        detail = _extract_error_detail(response)
        raise ProxyAPIError(
            detail,
            status_code=response.status_code,
            category=_classify_status(response.status_code),
            retry_after=response.headers.get("Retry-After"),
        )

    _check_response_size(response, resp_cap)

    try:
        data = response.json()
    except ValueError as exc:
        raise ProxyAPIError(
            "Proxy returned an invalid JSON response.",
            status_code=200,
            category="server",
        ) from exc

    required = ("request_id", "reply", "pii_entities_found", "latency_ms")
    missing = [k for k in required if not isinstance(data, dict) or k not in data]
    if missing:
        raise ProxyAPIError(
            f"Proxy response missing expected fields: {', '.join(missing)}",
            status_code=200,
            category="server",
        )

    raw_counts = data.get("pii_counts")
    parsed_counts = (
        {str(k): int(v) for k, v in raw_counts.items()}
        if isinstance(raw_counts, dict)
        else None
    )

    return ChatResult(
        request_id=str(data["request_id"]),
        reply=str(data["reply"]),
        pii_entities_found=int(data["pii_entities_found"]),
        latency_ms=int(data["latency_ms"]),
        raw=data,
        sanitized_prompt=(
            str(data["sanitized_prompt"]) if data.get("sanitized_prompt") is not None else None
        ),
        pii_counts=parsed_counts,
    )


def get_health(
    api_url: str,
    *,
    timeout: float | None = None,
    max_response_bytes: int | None = None,
    transport: httpx.BaseTransport | None = None,
) -> HealthResult:
    """Query GET /health. Handles both 200 (ok) and 503 (degraded) bodies."""
    base_url = normalize_api_url(api_url)
    req_timeout = timeout if timeout is not None else ui_settings.health_timeout_seconds
    resp_cap = max_response_bytes if max_response_bytes is not None else ui_settings.max_response_bytes

    started = time.perf_counter()
    try:
        with httpx.Client(
            timeout=req_timeout,
            follow_redirects=False,
            transport=transport,
        ) as client:
            response = client.get(f"{base_url}/health", headers={"Accept": "application/json"})
    except httpx.TimeoutException as exc:
        logger.warning("health check timed out after %.1fs", req_timeout)
        raise ProxyAPIError(
            f"Health check timed out after {req_timeout:.0f}s.",
            status_code=None,
            category="network",
        ) from exc
    except httpx.HTTPError as exc:
        logger.warning("health check transport error: %s", type(exc).__name__)
        raise ProxyAPIError(
            "Proxy health endpoint is currently unreachable.",
            status_code=None,
            category="network",
        ) from exc

    probe_ms = int((time.perf_counter() - started) * 1000)

    if response.status_code not in (200, 503):
        raise ProxyAPIError(
            _extract_error_detail(response),
            status_code=response.status_code,
            category=_classify_status(response.status_code),
        )

    _check_response_size(response, resp_cap)

    try:
        data = response.json()
    except ValueError as exc:
        raise ProxyAPIError(
            "Health endpoint returned non-JSON body.",
            status_code=response.status_code,
            category="server",
        ) from exc

    if not isinstance(data, dict) or "status" not in data or "checks" not in data:
        raise ProxyAPIError(
            "Health response missing 'status' or 'checks' fields.",
            status_code=response.status_code,
            category="server",
        )

    checks = {str(k): str(v) for k, v in dict(data["checks"]).items()}
    return HealthResult(
        status=str(data["status"]),
        checks=checks,
        http_status=response.status_code,
        raw=data,
        probe_ms=probe_ms,
    )


def get_admin_metrics(
    api_url: str,
    admin_key: str | None = None,
    *,
    timeout: float | None = None,
    transport: httpx.BaseTransport | None = None,
) -> dict[str, Any] | None:
    """Fetch backend admin metrics if the admin API has been implemented.

    Returns None when the endpoint is not yet available (404/405/501) or fails,
    so the Admin tab cleanly falls back to session-local telemetry.
    """
    base_url = normalize_api_url(api_url)
    req_timeout = timeout if timeout is not None else ui_settings.health_timeout_seconds
    headers: dict[str, str] = {"Accept": "application/json"}
    if admin_key:
        headers["X-API-Key"] = admin_key

    try:
        with httpx.Client(
            timeout=req_timeout,
            follow_redirects=False,
            transport=transport,
        ) as client:
            response = client.get(f"{base_url}/admin/metrics", headers=headers)
    except httpx.HTTPError:
        return None

    if response.status_code != 200 or len(response.content) > ui_settings.max_response_bytes:
        return None

    try:
        data = response.json()
    except ValueError:
        return None

    return data if isinstance(data, dict) else None


def append_session_log(
    logs: list[RequestLogEntry],
    entry: RequestLogEntry,
    *,
    max_entries: int | None = None,
) -> list[RequestLogEntry]:
    """Prepend a log entry while capping total stored session history."""
    cap = max_entries if max_entries is not None else ui_settings.max_session_logs
    return [entry, *logs][:cap]


def now_utc_iso() -> str:
    """Compact UTC timestamp for session audit rows."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def summarize_session_logs(entries: list[RequestLogEntry]) -> dict[str, Any]:
    """Compute aggregate and per-tenant stats from metadata-only session logs."""
    total = len(entries)
    ok_entries = [e for e in entries if e.outcome == "ok"]
    error_entries = [e for e in entries if e.outcome != "ok"]
    latencies = [e.latency_ms for e in entries if e.latency_ms is not None]
    total_pii = sum(e.pii_entities_found for e in entries)

    per_tenant: dict[str, dict[str, Any]] = {}
    for entry in entries:
        bucket = per_tenant.setdefault(
            entry.tenant_label,
            {
                "tenant": entry.tenant_label,
                "requests": 0,
                "ok": 0,
                "errors": 0,
                "pii_caught": 0,
                "_latencies": [],
            },
        )
        bucket["requests"] += 1
        if entry.outcome == "ok":
            bucket["ok"] += 1
        else:
            bucket["errors"] += 1
        bucket["pii_caught"] += entry.pii_entities_found
        if entry.latency_ms is not None:
            bucket["_latencies"].append(entry.latency_ms)

    tenant_rows = []
    for row in per_tenant.values():
        lats = row.pop("_latencies")
        row["avg_latency_ms"] = round(sum(lats) / len(lats), 1) if lats else None
        tenant_rows.append(row)
    tenant_rows.sort(key=lambda r: r["requests"], reverse=True)

    return {
        "total_requests": total,
        "ok_requests": len(ok_entries),
        "error_requests": len(error_entries),
        "success_rate_pct": round((len(ok_entries) / total) * 100, 1) if total else 0.0,
        "total_pii_caught": total_pii,
        "avg_latency_ms": round(sum(latencies) / len(latencies), 1) if latencies else None,
        "per_tenant": tenant_rows,
    }
