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
        # TODO: Read each setting from the environment and assign it to self.
        #
        #   self.app_env              APP_ENV              default "local"
        #       Label for which deployment this is; surface it in /health and
        #       logs. Avoid branching application logic on it.
        #   self.llm_url              LLM_URL              default ""
        #       Where to POST sanitized prompts. Empty is meaningful: it means
        #       "no provider configured" and llm_client treats it as echo mode.
        #   self.llm_timeout_seconds  LLM_TIMEOUT_SECONDS  default "30"
        #       Bounded wait on the provider call. Environment variables are
        #       always strings, so this one needs an explicit float() cast.
        #   self.database_url         DATABASE_URL         default ""
        #       Postgres connection string. Empty until Son's tables exist.
        #
        # Defaults should make a bare local run work with no .env file at all.
        # Never put a real credential in a default: defaults are committed to
        # git, and secrets come from the environment (Kubernetes Secrets on
        # DOKS).
        raise NotImplementedError


# TODO: Construct the single shared instance the rest of the app imports:
#           settings = Settings()
#       Import it as `from app.config import settings`; never re-instantiate
#       Settings elsewhere.

# TODO (later, as those pieces land): add settings for
#       PRESIDIO_URL  - Hira needs the Analyzer's address in services/pii.py
#       LOG_LEVEL     - lets Son raise verbosity without a code change
#       and a validate() that raises at startup when a required setting is
#       empty and APP_ENV is not "local", so misconfiguration fails fast
#       instead of surfacing on the first request.
