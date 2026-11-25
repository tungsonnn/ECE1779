"""UI configuration loaded from environment variables.

OWNER: Daniel (Security + UI).

Defaults are production-safe:
  * UI_DEMO_MODE defaults to False (no hardcoded demo keys shown in prod).
  * UI_ALLOW_CUSTOM_API_URL defaults to False (locks API_URL server-side to
    prevent SSRF when the UI is exposed publicly behind Cloudflare).
"""

from __future__ import annotations

from dataclasses import dataclass
import os


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int, *, minimum: int = 1) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw.strip())
    except ValueError:
        return default
    return max(value, minimum)


def _env_float(name: str, default: float, *, minimum: float = 0.5) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = float(raw.strip())
    except ValueError:
        return default
    return max(value, minimum)


@dataclass(frozen=True)
class UISettings:
    """Immutable runtime settings for the Streamlit frontend."""

    api_url: str
    ui_env: str
    demo_mode: bool
    allow_custom_api_url: bool
    max_prompt_chars: int
    request_timeout_seconds: float
    health_timeout_seconds: float
    max_response_bytes: int
    max_session_logs: int
    log_level: str

    @classmethod
    def from_env(cls) -> "UISettings":
        return cls(
            api_url=os.environ.get("API_URL", "http://localhost:8000").strip(),
            ui_env=os.environ.get("UI_ENV", "production").strip().lower() or "production",
            demo_mode=_env_bool("UI_DEMO_MODE", default=False),
            allow_custom_api_url=_env_bool("UI_ALLOW_CUSTOM_API_URL", default=False),
            max_prompt_chars=_env_int("UI_MAX_PROMPT_CHARS", 20_000, minimum=100),
            request_timeout_seconds=_env_float("UI_REQUEST_TIMEOUT_SECONDS", 35.0, minimum=1.0),
            health_timeout_seconds=_env_float("UI_HEALTH_TIMEOUT_SECONDS", 5.0, minimum=0.5),
            max_response_bytes=_env_int("UI_MAX_RESPONSE_BYTES", 1_048_576, minimum=4_096),
            max_session_logs=_env_int("UI_MAX_SESSION_LOGS", 200, minimum=10),
            log_level=os.environ.get("UI_LOG_LEVEL", "INFO").strip().upper() or "INFO",
        )


ui_settings = UISettings.from_env()
