"""Application configuration, read from environment variables.

OWNER: Ammar (App + Deploy).

Purpose: one place that reads the environment, so the same container image can
run locally, under Docker Compose, and on DOKS with only its environment
changing. Nothing else in the app should touch os.environ.
"""

import os


class Settings:
    """Values the app needs to be told at startup.

    Read once at import time; configuration does not change while the process
    is running, so re-reading it per request would be pointless work.
    """

    def __init__(self) -> None:
        # Deployment label (local / compose / doks). Shown in /health and logs;
        self.app_env: str = os.environ.get("APP_ENV", "local")

        # Where sanitized prompts are POSTed. Empty means "no provider configured" -> llm_client runs in echo mode.
        self.llm_url: str = os.environ.get("LLM_URL", "")

        self.llm_timeout_seconds: float = float(
            os.environ.get("LLM_TIMEOUT_SECONDS", "30")
        )

        # Postgres connection string
        self.database_url: str = os.environ.get("DATABASE_URL", "")

        # Presidio Analyzer address, used by services/pii.py. The default is the Docker Compose service name.
        self.presidio_url: str = os.environ.get(
            "PRESIDIO_URL", "http://presidio-analyzer:3000"
        )

        # logging
        self.log_level: str = os.environ.get("LOG_LEVEL", "INFO").upper()

    # TODO (later): a validate() that raises at startup when a required setting
    #       is empty and APP_ENV is not "local", so misconfiguration fails fast
    #       instead of surfacing on the first request.


# Single shared instance. Import as `from app.config import settings
settings = Settings()
