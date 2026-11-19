"""Production Streamlit Web Application for the LLM PII Proxy.

OWNER: Daniel (Security + UI).

Run via Docker Compose (enables local dev demo presets via UI_DEMO_MODE=true):
    docker compose up --build

Run locally without Docker:
    UI_DEMO_MODE=true streamlit run ui/app.py

In production (e.g., DigitalOcean Kubernetes behind Cloudflare):
    Leave UI_DEMO_MODE=false and UI_ALLOW_CUSTOM_API_URL=false (the defaults).
"""

from __future__ import annotations

import logging

import streamlit as st

from client import (
    ChatResult,
    HealthResult,
    ProxyAPIError,
    RequestLogEntry,
    append_session_log,
    get_admin_metrics,
    get_health,
    now_utc_iso,
    send_chat,
    summarize_session_logs,
)
from components import (
    GLOBAL_CSS,
    render_dep_card_html,
    render_entity_chips_html,
    render_kpi_card_html,
    render_pipeline_html,
    render_security_posture_html,
    render_text_panel_html,
    render_topbar_html,
)
from config import ui_settings
from samples import DEMO_KEY_PRESETS, SAMPLE_PROMPTS

logging.basicConfig(
    level=ui_settings.log_level,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

st.set_page_config(
    page_title="PromptVeil · LLM Privacy Proxy",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _init_session_state() -> None:
    """Initialize Streamlit session state keys once per browser session."""
    defaults = {
        "api_url": ui_settings.api_url,
        "custom_api_key": "",
        "prompt_text": SAMPLE_PROMPTS[0].prompt if ui_settings.demo_mode else "",
        "last_prompt": None,
        "last_result": None,
        "last_error": None,
        "last_outcome": None,
        "session_logs": [],
        "cached_health": None,
        "cached_health_error": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _get_cloudflare_user() -> str | None:
    """Read Cloudflare Access authenticated user email header when present."""
    try:
        headers = st.context.headers
    except Exception:
        return None
    if not headers:
        return None
    for header_name in (
        "Cf-Access-Authenticated-User-Email",
        "cf-access-authenticated-user-email",
    ):
        value = headers.get(header_name)
        if value:
            return str(value).strip()
    return None


def _refresh_health(api_url: str) -> None:
    """Fetch GET /health and store the result in session state."""
    try:
        st.session_state["cached_health"] = get_health(api_url)
        st.session_state["cached_health_error"] = None
    except ProxyAPIError as exc:
        st.session_state["cached_health"] = None
        st.session_state["cached_health_error"] = exc


def _load_sample_prompt(prompt_text: str) -> None:
    st.session_state["prompt_text"] = prompt_text


def _clear_playground() -> None:
    st.session_state["prompt_text"] = ""
    st.session_state["last_result"] = None
    st.session_state["last_error"] = None
    st.session_state["last_prompt"] = None
    st.session_state["last_outcome"] = None


def _clear_session_and_key() -> None:
    st.session_state["custom_api_key"] = ""
    st.session_state["prompt_text"] = ""
    st.session_state["last_result"] = None
    st.session_state["last_error"] = None
    st.session_state["last_prompt"] = None
    st.session_state["last_outcome"] = None
    st.session_state["session_logs"] = []


def _render_sidebar() -> tuple[str, str | None, str]:
    """Render the dark enterprise sidebar; return (api_url, api_key, tenant_label)."""
    with st.sidebar:
        st.markdown(
            '<div class="sidebar-brand">'
            '  <div class="sidebar-brand-title">🛡️ PromptVeil</div>'
            '  <div class="sidebar-brand-sub">LLM Privacy Proxy Console</div>'
            "</div>",
            unsafe_allow_html=True,
        )
        st.divider()

        st.markdown("##### Authentication")
        if ui_settings.demo_mode:
            preset_label = st.selectbox(
                "Tenant Key (Demo Mode)",
                options=list(DEMO_KEY_PRESETS.keys()),
                help="Demo presets are only available when UI_DEMO_MODE=true.",
            )
            preset_value = DEMO_KEY_PRESETS[preset_label]
            if preset_value == "__custom__":
                entered = st.text_input(
                    "X-API-Key",
                    key="custom_api_key",
                    type="password",
                    placeholder="Paste tenant API key...",
                )
                api_key: str | None = entered if entered else None
                tenant_label = "Custom Tenant" if api_key else "Unauthenticated"
            else:
                api_key = preset_value
                tenant_label = preset_label.split(" (")[0]
            st.caption("Demo presets enabled (`UI_DEMO_MODE=true`). Disable in production.")
        else:
            entered = st.text_input(
                "Tenant API Key (X-API-Key)",
                key="custom_api_key",
                type="password",
                placeholder="Enter your team API key...",
                help="Sent only in the X-API-Key header to the proxy; never stored or logged.",
            )
            api_key = entered if entered else None
            tenant_label = "Authenticated Tenant" if api_key else "Unauthenticated"

        st.button(
            "Clear Session & Key",
            use_container_width=True,
            on_click=_clear_session_and_key,
            help="Wipes the API key, prompt, and local session logs from browser memory.",
        )

        st.divider()
        st.markdown("##### Upstream Gateway")
        if ui_settings.allow_custom_api_url:
            api_url = st.text_input(
                "Proxy API URL",
                value=st.session_state["api_url"],
                help="Editable because UI_ALLOW_CUSTOM_API_URL=true (dev only).",
            )
            st.session_state["api_url"] = api_url
        else:
            api_url = ui_settings.api_url
            st.caption("Locked to server-configured upstream (`API_URL`) to prevent SSRF.")

        if st.button("Probe /health", use_container_width=True):
            _refresh_health(api_url)

        health: HealthResult | None = st.session_state["cached_health"]
        health_err: ProxyAPIError | None = st.session_state["cached_health_error"]
        if health is not None:
            if health.status == "ok":
                st.caption(f"🟢 Operational · HTTP {health.http_status} ({health.probe_ms} ms)")
            else:
                st.caption(f"🔴 Degraded · HTTP {health.http_status} ({health.probe_ms} ms)")
        elif health_err is not None:
            st.caption("🔴 Proxy unreachable")
        else:
            st.caption("⚪ Not probed yet")

        st.divider()
        st.caption(
            "**Security Guarantees**\n"
            "• Fail-closed on PII/audit outage (`503`)\n"
            "• Placeholder map kept in RAM per request\n"
            "• Zero-content audit trail in PostgreSQL\n"
            "• Server-locked upstream & XSRF protection"
        )

    return api_url, api_key, tenant_label


def _render_error_callout(err: ProxyAPIError) -> None:
    """Display a clear, architecture-aware explanation of a proxy error."""
    code = f"HTTP {err.status_code}" if err.status_code is not None else "Connection Error"

    if err.category == "auth":
        st.error(
            f"**{code} — Unauthorized**\n\n{err.detail}\n\n"
            "Provide a valid tenant API key in the sidebar to access the proxy."
        )
    elif err.category == "rate_limit":
        retry_note = f" Retry after `{err.retry_after}s`." if err.retry_after else ""
        st.warning(f"**{code} — Rate Limit Exceeded**\n\n{err.detail}{retry_note}")
    elif err.category == "validation":
        st.warning(f"**{code} — Invalid Request**\n\n{err.detail}")
    elif err.category == "fail_closed":
        st.error(
            f"**{code} — Fail-Closed Protection Activated**\n\n"
            f"{err.detail}\n\n"
            "PII detection or the audit log was unavailable, so the proxy refused the "
            "request before any text could leave your security boundary."
        )
    elif err.category == "upstream":
        st.error(
            f"**{code} — Upstream LLM Provider Unavailable**\n\n"
            f"{err.detail}\n\n"
            "Your prompt was scrubbed and audited, but the external LLM provider could not complete the request."
        )
    else:
        st.error(f"**{code} — Request Failed**\n\n{err.detail}")


def _render_playground_tab(api_url: str, api_key: str | None, tenant_label: str) -> None:
    """Render the production Playground view."""
    st.markdown(
        render_pipeline_html(st.session_state["last_outcome"]),
        unsafe_allow_html=True,
    )

    st.markdown("#### Synthetic Test Samples")
    st.caption("Load fake data to verify PII detection without entering real personal information.")
    sample_cols = st.columns(len(SAMPLE_PROMPTS))
    for col, sample in zip(sample_cols, SAMPLE_PROMPTS):
        with col:
            st.button(
                sample.label,
                use_container_width=True,
                help=sample.description,
                on_click=_load_sample_prompt,
                args=(sample.prompt,),
            )
            entities_text = (
                ", ".join(sample.expected_entities) if sample.expected_entities else "Control (0 PII)"
            )
            st.caption(f"Targets: `{entities_text}`")

    st.markdown("#### Prompt Composer")
    prompt = st.text_area(
        "Prompt input",
        key="prompt_text",
        height=155,
        label_visibility="collapsed",
        placeholder="Enter a prompt to sanitize and send through the LLM proxy...",
    )

    char_count = len(prompt)
    max_chars = ui_settings.max_prompt_chars
    over_limit = char_count > max_chars

    ctrl_left, ctrl_mid, ctrl_right = st.columns([2, 1, 5])
    with ctrl_left:
        submit = st.button(
            "Send Through Proxy",
            type="primary",
            use_container_width=True,
            disabled=over_limit,
        )
    with ctrl_mid:
        st.button("Clear", use_container_width=True, on_click=_clear_playground)
    with ctrl_right:
        counter_text = f"{char_count:,} / {max_chars:,} characters"
        if over_limit:
            st.error(f"{counter_text} — exceeds maximum prompt length.")
        else:
            st.caption(counter_text)

    if submit:
        if not prompt.strip():
            st.warning("Enter a prompt before sending.")
        else:
            with st.spinner("Scrubbing PII and calling upstream LLM..."):
                try:
                    result = send_chat(api_url=api_url, prompt=prompt, api_key=api_key)
                    st.session_state["last_prompt"] = prompt
                    st.session_state["last_result"] = result
                    st.session_state["last_error"] = None
                    st.session_state["last_outcome"] = "ok"
                    st.session_state["session_logs"] = append_session_log(
                        st.session_state["session_logs"],
                        RequestLogEntry(
                            timestamp=now_utc_iso(),
                            tenant_label=tenant_label,
                            status_code=200,
                            outcome="ok",
                            request_id=result.request_id,
                            pii_entities_found=result.pii_entities_found,
                            latency_ms=result.latency_ms,
                        ),
                    )
                    st.rerun()
                except ProxyAPIError as exc:
                    st.session_state["last_prompt"] = prompt
                    st.session_state["last_result"] = None
                    st.session_state["last_error"] = exc
                    st.session_state["last_outcome"] = exc.category
                    st.session_state["session_logs"] = append_session_log(
                        st.session_state["session_logs"],
                        RequestLogEntry(
                            timestamp=now_utc_iso(),
                            tenant_label=tenant_label,
                            status_code=exc.status_code,
                            outcome=exc.category,
                            error_detail=exc.detail,
                        ),
                    )
                    st.rerun()

    last_error: ProxyAPIError | None = st.session_state["last_error"]
    last_result: ChatResult | None = st.session_state["last_result"]
    last_prompt: str | None = st.session_state["last_prompt"]

    if last_error is not None:
        st.divider()
        _render_error_callout(last_error)

    if last_result is not None:
        st.divider()
        st.markdown("#### Inspection & Response")

        k1, k2, k3, k4 = st.columns(4)
        with k1:
            st.markdown(
                render_kpi_card_html("Status", "200 OK", "Pipeline completed", "success"),
                unsafe_allow_html=True,
            )
        with k2:
            pii_tone = "success" if last_result.pii_entities_found > 0 else "info"
            st.markdown(
                render_kpi_card_html(
                    "PII Entities Scrubbed",
                    last_result.pii_entities_found,
                    "Replaced before LLM call",
                    pii_tone,
                ),
                unsafe_allow_html=True,
            )
        with k3:
            st.markdown(
                render_kpi_card_html(
                    "End-to-End Latency",
                    f"{last_result.latency_ms} ms",
                    "Scrub + audit + LLM + restore",
                    "info",
                ),
                unsafe_allow_html=True,
            )
        with k4:
            st.markdown(
                render_kpi_card_html(
                    "Request ID",
                    f"{last_result.request_id[:8]}…",
                    "Correlates with audit table",
                    "info",
                ),
                unsafe_allow_html=True,
            )

        st.write("")
        if last_result.reply.startswith("[echo mode"):
            st.info(
                "**Echo Mode Active:** No external `LLM_URL` is configured on the proxy, "
                "so the reply echoes the prompt after the scrub-and-restore cycle."
            )

        if last_result.sanitized_prompt is not None:
            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown(
                    render_text_panel_html(
                        "1. Original Prompt", "Client Input", "neutral", last_prompt or ""
                    ),
                    unsafe_allow_html=True,
                )
            with c2:
                st.markdown(
                    render_text_panel_html(
                        "2. Sanitized Prompt",
                        "Sent to LLM",
                        "info",
                        last_result.sanitized_prompt,
                    ),
                    unsafe_allow_html=True,
                )
            with c3:
                st.markdown(
                    render_text_panel_html(
                        "3. Restored Reply", "Returned to Client", "success", last_result.reply
                    ),
                    unsafe_allow_html=True,
                )
        else:
            c1, c2 = st.columns(2)
            with c1:
                st.markdown(
                    render_text_panel_html(
                        "Original Prompt", "Client Input", "neutral", last_prompt or ""
                    ),
                    unsafe_allow_html=True,
                )
            with c2:
                st.markdown(
                    render_text_panel_html(
                        "Restored LLM Reply", "Returned to Client", "success", last_result.reply
                    ),
                    unsafe_allow_html=True,
                )

        if last_result.pii_counts:
            st.markdown("**Detected Entity Breakdown**")
            st.markdown(
                render_entity_chips_html(last_result.pii_counts),
                unsafe_allow_html=True,
            )
            st.write("")

        with st.expander("Technical Details & Raw JSON Contract"):
            st.caption(f"Full `request_id`: `{last_result.request_id}`")
            st.json(last_result.raw)


def _render_admin_tab(api_url: str, api_key: str | None) -> None:
    """Render the Admin & Audit Dashboard tab."""
    st.markdown("#### Tenant Usage & Zero-Content Audit Trail")
    st.caption(
        "Audit records store metadata and entity counts only — prompts, replies, "
        "API keys, and placeholder maps are never persisted."
    )

    btn_col, _ = st.columns([2, 6])
    with btn_col:
        probe_backend = st.button("Sync Backend Admin API", use_container_width=True)

    backend_metrics = None
    if probe_backend:
        backend_metrics = get_admin_metrics(api_url=api_url, admin_key=api_key)

    if backend_metrics is not None:
        st.success("Connected to PostgreSQL-backed Admin API (`GET /admin/metrics`).")
        st.json(backend_metrics)
        st.divider()
    else:
        st.info(
            "**Session Telemetry Mode:** Displaying metadata-only metrics from this browser session. "
            "When `GET /admin/metrics` is deployed on the proxy, click **Sync Backend Admin API** to pull "
            "cluster-wide PostgreSQL audit data."
        )

    logs: list[RequestLogEntry] = st.session_state["session_logs"]
    summary = summarize_session_logs(logs)

    k1, k2, k3, k4, k5 = st.columns(5)
    with k1:
        st.markdown(
            render_kpi_card_html("Total Requests", summary["total_requests"], "Current session", "info"),
            unsafe_allow_html=True,
        )
    with k2:
        rate_tone = "success" if summary["success_rate_pct"] >= 90 or summary["total_requests"] == 0 else "warning"
        st.markdown(
            render_kpi_card_html("Success Rate", f"{summary['success_rate_pct']}%", f"{summary['ok_requests']} succeeded", rate_tone),
            unsafe_allow_html=True,
        )
    with k3:
        err_tone = "danger" if summary["error_requests"] > 0 else "success"
        st.markdown(
            render_kpi_card_html("Blocked / Errors", summary["error_requests"], "401 / 429 / 502 / 503", err_tone),
            unsafe_allow_html=True,
        )
    with k4:
        st.markdown(
            render_kpi_card_html("PII Entities Caught", summary["total_pii_caught"], "Redacted pre-LLM", "success"),
            unsafe_allow_html=True,
        )
    with k5:
        avg_lat = f"{summary['avg_latency_ms']} ms" if summary["avg_latency_ms"] is not None else "—"
        st.markdown(
            render_kpi_card_html("Avg Latency", avg_lat, "Across completed calls", "info"),
            unsafe_allow_html=True,
        )

    st.write("")
    st.markdown("#### Per-Tenant Breakdown")
    if summary["per_tenant"]:
        st.dataframe(
            summary["per_tenant"],
            use_container_width=True,
            hide_index=True,
            column_config={
                "tenant": "Tenant",
                "requests": "Requests",
                "ok": "OK",
                "errors": "Errors",
                "pii_caught": "PII Caught",
                "avg_latency_ms": "Avg Latency (ms)",
            },
        )

        chart_cols = st.columns(2)
        with chart_cols[0]:
            st.markdown("**Requests by Tenant**")
            st.bar_chart(summary["per_tenant"], x="tenant", y="requests")
        with chart_cols[1]:
            st.markdown("**PII Entities Caught by Tenant**")
            st.bar_chart(summary["per_tenant"], x="tenant", y="pii_caught")
    else:
        st.caption("No requests recorded yet. Send a prompt in the **Playground** tab to populate metrics.")

    st.divider()
    st.markdown("#### Audit Event Log (Metadata Only)")
    if logs:
        tenants = sorted({entry.tenant_label for entry in logs})
        outcomes = sorted({entry.outcome for entry in logs})

        f1, f2, f3 = st.columns([2, 2, 1])
        with f1:
            selected_tenants = st.multiselect("Filter Tenant", options=tenants, default=tenants)
        with f2:
            selected_outcomes = st.multiselect("Filter Outcome", options=outcomes, default=outcomes)
        with f3:
            st.write("")
            if st.button("Clear Log", use_container_width=True):
                st.session_state["session_logs"] = []
                st.rerun()

        filtered = [
            {
                "Timestamp": e.timestamp,
                "Tenant": e.tenant_label,
                "HTTP": e.status_code if e.status_code is not None else "ERR",
                "Outcome": e.outcome,
                "PII Caught": e.pii_entities_found,
                "Latency (ms)": e.latency_ms,
                "Request ID": e.request_id or "—",
                "Error Detail": e.error_detail or "",
            }
            for e in logs
            if e.tenant_label in selected_tenants and e.outcome in selected_outcomes
        ]
        st.dataframe(filtered, use_container_width=True, hide_index=True)
    else:
        st.caption("No audit events recorded yet.")


def _describe_check(dep_name: str, value: str) -> tuple[str, str, str]:
    """Return (status_label, pill_tone, description) for a /health check."""
    normalized = value.lower()
    descriptions = {
        "database": "PostgreSQL store for tenants, hashed API keys, rate limits, and audit rows.",
        "pii_analyzer": "Microsoft Presidio Analyzer NLP service scanning prompts for PII & secrets.",
        "llm": "External hosted LLM provider (only receives sanitized prompts).",
    }
    base_desc = descriptions.get(dep_name, "Proxy dependency reported by /health.")

    if normalized == "ok":
        return "Healthy (ok)", "success", base_desc
    if normalized in {"down", "error"}:
        return f"Failing ({value})", "danger", f"{base_desc} Failing this check triggers HTTP 503."
    if normalized == "echo_mode":
        return "Echo Mode", "info", "No external LLM_URL configured; echoing sanitized-and-restored text."
    if normalized == "not_implemented":
        return "Stub / Pending", "warning", f"{base_desc} Live probe not yet wired."
    return value, "neutral", base_desc


def _render_health_and_security_tab(api_url: str, cf_user_email: str | None) -> None:
    """Render live dependency health and active frontend security controls."""
    st.markdown("#### Live Dependency Health (`GET /health`)")
    col_btn, _ = st.columns([2, 6])
    with col_btn:
        if st.button("Refresh Health Probe", type="primary", use_container_width=True):
            _refresh_health(api_url)

    health: HealthResult | None = st.session_state["cached_health"]
    health_err: ProxyAPIError | None = st.session_state["cached_health_error"]

    if health_err is not None:
        _render_error_callout(health_err)
    elif health is not None:
        if health.status == "ok" and health.http_status == 200:
            st.success(
                f"Proxy is **OPERATIONAL** (HTTP {health.http_status} · probe latency {health.probe_ms} ms)"
            )
        else:
            st.error(
                f"Proxy is **DEGRADED** (HTTP {health.http_status} · probe latency {health.probe_ms} ms)"
            )

        if health.checks:
            cols = st.columns(min(len(health.checks), 3))
            for idx, (dep_name, dep_value) in enumerate(health.checks.items()):
                label, tone, desc = _describe_check(dep_name, dep_value)
                with cols[idx % len(cols)]:
                    st.markdown(
                        render_dep_card_html(dep_name.replace("_", " ").title(), label, tone, desc),
                        unsafe_allow_html=True,
                    )

        with st.expander("Raw /health JSON"):
            st.json(health.raw)

    st.divider()
    st.markdown("#### Frontend & Cloudflare Security Posture")
    posture_items = [
        (
            "SSRF Protection (Upstream URL)",
            "Server-Locked" if not ui_settings.allow_custom_api_url else "Custom URL Enabled (Dev)",
            "success" if not ui_settings.allow_custom_api_url else "warning",
        ),
        (
            "Demo API Keys",
            "Disabled (Production)" if not ui_settings.demo_mode else "Enabled (Dev Mode)",
            "success" if not ui_settings.demo_mode else "warning",
        ),
        (
            "Cloudflare Zero Trust Access",
            f"Authenticated ({cf_user_email})" if cf_user_email else "Header Not Present (Direct/Local)",
            "success" if cf_user_email else "info",
        ),
        (
            "HTTP Redirects & Payload Caps",
            f"No Redirects · {ui_settings.max_prompt_chars:,} char cap",
            "success",
        ),
        (
            "XSS & Error Leakage Hardening",
            "HTML Escaped · Stack Traces Hidden",
            "success",
        ),
        (
            "XSRF & Non-Root Container",
            "XSRF Enabled · Unprivileged User",
            "success",
        ),
    ]
    c1, c2, c3 = st.columns(3)
    for idx, item in enumerate(posture_items):
        with (c1, c2, c3)[idx % 3]:
            st.markdown(render_security_posture_html([item]), unsafe_allow_html=True)


def main() -> None:
    _init_session_state()
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

    api_url, api_key, tenant_label = _render_sidebar()

    # Probe health automatically once per session for the top status bar.
    if st.session_state["cached_health"] is None and st.session_state["cached_health_error"] is None:
        _refresh_health(api_url)

    health: HealthResult | None = st.session_state["cached_health"]
    health_err: ProxyAPIError | None = st.session_state["cached_health_error"]
    if health is not None:
        header_health_status: str | None = health.status
    elif health_err is not None:
        header_health_status = "unreachable"
    else:
        header_health_status = None

    cf_user = _get_cloudflare_user()
    st.markdown(
        render_topbar_html(
            health_status=header_health_status,
            ui_env=ui_settings.ui_env,
            demo_mode=ui_settings.demo_mode,
            cf_user_email=cf_user,
        ),
        unsafe_allow_html=True,
    )

    tab_playground, tab_admin, tab_health = st.tabs(
        ["Playground", "Admin & Audit", "Health & Security"]
    )
    with tab_playground:
        _render_playground_tab(api_url=api_url, api_key=api_key, tenant_label=tenant_label)
    with tab_admin:
        _render_admin_tab(api_url=api_url, api_key=api_key)
    with tab_health:
        _render_health_and_security_tab(api_url=api_url, cf_user_email=cf_user)


if __name__ == "__main__":
    main()
