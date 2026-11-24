"""Outbound call to the hosted LLM provider.

OWNER: Ammar (App + Deploy); provider choice with Hira.

The only component that talks to the outside world, and the reason the rest of
the system exists: by the time a call reaches this module the text has already
been through services.pii.scrub(), so only sanitized text ever leaves.

Points at whatever config.settings.llm_url holds - the fake LLM container under
Docker Compose, the hosted gpt-oss-120b endpoint on DOKS - so switching
providers is an environment change, not a code change.
"""

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


# Sent with every request, before the user's (sanitized) prompt.
# Why: services.pii.restore() can only put a value back if the placeholder
# comes back unchanged. In testing, gpt-oss-120b sometimes wrote "\\<PERSON_1\\>"
# with backslashes inside Markdown tables and lists. restore() now tolerates
# that, and this prompt asks the model not to do it in the first place.
SYSTEM_PROMPT = (
    "Some private details in the user's message have been replaced with "
    "placeholders such as <PERSON_1> or <EMAIL_ADDRESS_2>. Treat each placeholder "
    "as the real value it stands for. When you use one in your answer, copy it "
    "exactly, character for character: keep the angle brackets, do not add "
    "backslashes or any other escape characters, and do not translate, rename, "
    "renumber or reformat it. Do not invent new placeholders, and do not comment "
    "on the placeholders."
)


class LLMUnavailable(RuntimeError):
    """Raised when the provider is unreachable or returns an unusable response.

    pipeline.py turns this into a 502 (upstream failed), deliberately distinct
    from the 503 our own failing dependencies produce.
    """


def complete(sanitized_prompt: str) -> str:
    """Send a sanitized prompt to the provider and return its completion text.

    Sync, like the rest of the pipeline: the route runs in FastAPI's thread
    pool, so a blocking HTTP call here only holds its own thread.

    Speaks the OpenAI-style chat completions format, which DO Serverless
    Inference (and most other providers) accept.

    Never logs the prompt or the completion, even though both are sanitized.
    """
    # Echo mode: no provider configured. Keeps the pipeline runnable locally
    if not settings.llm_url:
        return f"[echo mode - no LLM_URL configured] {sanitized_prompt}"

    body = {
        "model": settings.llm_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": sanitized_prompt},
        ],
    }
    headers = {"Authorization": f"Bearer {settings.llm_api_key}"}

    try:
        # Explicit timeout: an unbounded wait ties up a worker thread forever.
        with httpx.Client(timeout=settings.llm_timeout_seconds) as client:
            response = client.post(settings.llm_url, json=body, headers=headers)
        # 4xx/5xx -> httpx.HTTPStatusError (a subclass of httpx.HTTPError).
        response.raise_for_status()
        # Only the final answer. gpt-oss also returns `reasoning_content` ignored.
        content = response.json()["choices"][0]["message"]["content"]
    except httpx.HTTPStatusError as exc:
        # Status code only - the response body may echo the prompt.
        logger.error("llm provider returned status=%d", exc.response.status_code)
        raise LLMUnavailable(f"provider returned {exc.response.status_code}") from exc
    except httpx.HTTPError as exc:
        # Timeouts, DNS failures, refused connections.
        logger.error("llm provider unreachable error=%s", type(exc).__name__)
        raise LLMUnavailable("provider unreachable") from exc
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        # 200 with a body we can't use: not JSON, or missing fields.
        logger.error("llm provider returned unexpected response shape")
        raise LLMUnavailable("unexpected provider response") from exc

    # A 200 with an empty or non-string answer is still unusable.
    if not isinstance(content, str) or not content.strip():
        logger.error("llm provider returned empty content")
        raise LLMUnavailable("empty completion")

    return content
