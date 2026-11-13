"""Outbound call to the hosted LLM provider.

OWNER: Ammar (App + Deploy); provider choice with Hira.

The only component that talks to the outside world, and the reason the rest of
the system exists: by the time a call reaches this module the text has already
been through services.pii.scrub(), so only sanitized text ever leaves.

Points at whatever config.settings.llm_url holds - the fake LLM container under
Docker Compose, the hosted gpt-oss-120b endpoint on DOKS - so switching
providers is an environment change, not a code change.
"""


class LLMUnavailable(RuntimeError):
    """Raised when the provider is unreachable or returns an unusable response.

    pipeline.py turns this into a 502 (upstream failed), deliberately distinct
    from the 503 our own failing dependencies produce.
    """


async def complete(sanitized_prompt: str) -> str:
    """Send a sanitized prompt to the provider and return its completion text.

    Async because this is a network call on the request path; a blocking client
    here would stall the event loop for every other in-flight request.
    """
    # TODO: Implement the provider call.
    #   * If settings.llm_url is empty, return an obvious echo string instead
    #     of calling out. That keeps the pipeline exercisable locally with
    #     nothing else running, and makes "no provider configured" visible in
    #     the response rather than silent.
    #   * POST with httpx.AsyncClient and always pass an explicit timeout from
    #     settings.llm_timeout_seconds. An unbounded wait ties up a worker
    #     forever, which under Kubernetes becomes failing health checks and a
    #     pod restart loop.
    #   * Wrap transport and decode errors (httpx.HTTPError, ValueError) in
    #     LLMUnavailable, so pipeline.py has exactly one exception type to
    #     catch here.
    #   * Validate the response shape before returning. A provider that
    #     answers 200 with unexpected JSON should raise, not return None.
    #   * Never log the prompt or the completion, even though both are
    #     sanitized at this point.
    raise NotImplementedError
