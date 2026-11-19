"""Production UI styling and XSS-safe HTML component builders.

OWNER: Daniel (Security + UI).

Every dynamic string interpolated into HTML MUST pass through `_esc()`
(`html.escape(..., quote=True)`) so untrusted input, API errors, or headers
can never inject script or markup into the browser.
"""

from __future__ import annotations

import html
from typing import Iterable


def _esc(value: object) -> str:
    """Escape any value for safe interpolation into HTML text or attributes."""
    return html.escape(str(value), quote=True)


GLOBAL_CSS = """
<style>
/* Hide default Streamlit chrome for a clean production web app feel */
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
[data-testid="stDeployButton"] { display: none; }
[data-testid="stDecoration"] { display: none; }

/* Base typography & canvas */
html, body, [class*="css"] {
    font-family: -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", Roboto,
                 Helvetica, Arial, sans-serif;
}

.stApp {
    background-color: #F8FAFC;
    color: #0F172A;
}

.block-container {
    padding-top: 1.5rem;
    padding-bottom: 3rem;
    max-width: 1240px;
}

/* Dark enterprise sidebar */
[data-testid="stSidebar"] {
    background-color: #0F172A;
    border-right: 1px solid #1E293B;
}

[data-testid="stSidebar"] * {
    color: #E2E8F0;
}

[data-testid="stSidebar"] .stCaption,
[data-testid="stSidebar"] small {
    color: #94A3B8 !important;
}

[data-testid="stSidebar"] input,
[data-testid="stSidebar"] [data-baseweb="select"] > div {
    background-color: #1E293B !important;
    color: #F8FAFC !important;
    border-color: #334155 !important;
}

[data-testid="stSidebar"] button {
    background-color: #1E293B;
    color: #F8FAFC;
    border: 1px solid #334155;
    border-radius: 8px;
}

[data-testid="stSidebar"] button:hover {
    background-color: #334155;
    border-color: #475569;
    color: #FFFFFF;
}

/* Primary action buttons */
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%);
    color: #FFFFFF;
    border: none;
    border-radius: 8px;
    font-weight: 600;
    padding: 0.55rem 1.15rem;
    box-shadow: 0 1px 2px rgba(37, 99, 235, 0.25);
    transition: all 0.15s ease;
}

.stButton > button[kind="primary"]:hover {
    background: linear-gradient(135deg, #1D4ED8 0%, #1E40AF 100%);
    box-shadow: 0 4px 10px rgba(37, 99, 235, 0.25);
}

.stButton > button[kind="secondary"] {
    background-color: #FFFFFF;
    color: #1E293B;
    border: 1px solid #CBD5E1;
    border-radius: 8px;
    font-weight: 500;
}

.stButton > button[kind="secondary"]:hover {
    border-color: #94A3B8;
    background-color: #F1F5F9;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    gap: 0.5rem;
    border-bottom: 1px solid #E2E8F0;
    padding-bottom: 0.25rem;
}

.stTabs [data-baseweb="tab"] {
    background-color: transparent;
    border-radius: 8px;
    padding: 0.5rem 1rem;
    font-weight: 600;
    color: #475569;
}

.stTabs [aria-selected="true"] {
    background-color: #EFF6FF !important;
    color: #1D4ED8 !important;
}

/* Inputs & textareas */
textarea, .stTextInput input {
    border-radius: 8px !important;
}

/* Top Application Header */
.app-topbar {
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 14px;
    padding: 1.15rem 1.4rem;
    margin-bottom: 1.25rem;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    box-shadow: 0 1px 3px rgba(15, 23, 42, 0.05);
}

.app-brand {
    display: flex;
    align-items: center;
    gap: 0.85rem;
}

.app-logo {
    width: 40px;
    height: 40px;
    border-radius: 10px;
    background: linear-gradient(135deg, #0F172A 0%, #2563EB 100%);
    color: #FFFFFF;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 800;
    font-size: 1.05rem;
    letter-spacing: -0.02em;
    flex-shrink: 0;
}

.app-title {
    font-size: 1.25rem;
    font-weight: 700;
    color: #0F172A;
    margin: 0;
    line-height: 1.2;
}

.app-subtitle {
    font-size: 0.85rem;
    color: #64748B;
    margin: 0.15rem 0 0 0;
}

.app-badges {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.5rem;
}

/* Status pills */
.pill {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    font-size: 0.78rem;
    font-weight: 600;
    padding: 0.3rem 0.7rem;
    border-radius: 999px;
    border: 1px solid transparent;
    white-space: nowrap;
}

.pill-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    display: inline-block;
}

.pill-success { background: #ECFDF5; color: #065F46; border-color: #A7F3D0; }
.pill-success .pill-dot { background: #10B981; }

.pill-warning { background: #FFFBEB; color: #92400E; border-color: #FDE68A; }
.pill-warning .pill-dot { background: #F59E0B; }

.pill-danger { background: #FEF2F2; color: #991B1B; border-color: #FECACA; }
.pill-danger .pill-dot { background: #EF4444; }

.pill-info { background: #EFF6FF; color: #1E40AF; border-color: #BFDBFE; }
.pill-info .pill-dot { background: #3B82F6; }

.pill-neutral { background: #F1F5F9; color: #334155; border-color: #CBD5E1; }
.pill-neutral .pill-dot { background: #64748B; }

/* KPI stat cards */
.kpi-card {
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 12px;
    padding: 1rem 1.15rem;
    box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
    height: 100%;
}

.kpi-label {
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: #64748B;
    margin-bottom: 0.35rem;
}

.kpi-value {
    font-size: 1.55rem;
    font-weight: 700;
    color: #0F172A;
    line-height: 1.2;
    font-variant-numeric: tabular-nums;
}

.kpi-sub {
    font-size: 0.78rem;
    color: #64748B;
    margin-top: 0.3rem;
}

.kpi-card.tone-success { border-top: 3px solid #10B981; }
.kpi-card.tone-warning { border-top: 3px solid #F59E0B; }
.kpi-card.tone-danger  { border-top: 3px solid #EF4444; }
.kpi-card.tone-info    { border-top: 3px solid #2563EB; }

/* Pipeline visualizer */
.pipeline-bar {
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 12px;
    padding: 0.85rem 1.1rem;
    margin-bottom: 1.1rem;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem;
}

.pipe-step {
    flex: 1 1 130px;
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.45rem 0.65rem;
    border-radius: 8px;
    border: 1px solid #E2E8F0;
    background: #F8FAFC;
    font-size: 0.8rem;
    font-weight: 600;
    color: #475569;
}

.pipe-num {
    width: 20px;
    height: 20px;
    border-radius: 50%;
    background: #CBD5E1;
    color: #0F172A;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 0.72rem;
    font-weight: 700;
    flex-shrink: 0;
}

.pipe-step.done {
    background: #ECFDF5;
    border-color: #A7F3D0;
    color: #065F46;
}
.pipe-step.done .pipe-num { background: #10B981; color: #FFFFFF; }

.pipe-step.blocked {
    background: #FEF2F2;
    border-color: #FECACA;
    color: #991B1B;
}
.pipe-step.blocked .pipe-num { background: #EF4444; color: #FFFFFF; }

.pipe-step.warn {
    background: #FFFBEB;
    border-color: #FDE68A;
    color: #92400E;
}
.pipe-step.warn .pipe-num { background: #F59E0B; color: #FFFFFF; }

/* Text comparison panels */
.panel-box {
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 12px;
    overflow: hidden;
    box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
    margin-bottom: 0.75rem;
}

.panel-header {
    background: #F8FAFC;
    border-bottom: 1px solid #E2E8F0;
    padding: 0.6rem 0.95rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: 0.82rem;
    font-weight: 700;
    color: #1E293B;
}

.panel-body {
    padding: 0.95rem 1rem;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    font-size: 0.85rem;
    line-height: 1.55;
    color: #0F172A;
    white-space: pre-wrap;
    word-break: break-word;
    margin: 0;
    background: #FFFFFF;
}

/* Health & security cards */
.dep-card {
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 12px;
    padding: 1rem 1.15rem;
    box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
    margin-bottom: 0.75rem;
}

.dep-title {
    font-size: 0.92rem;
    font-weight: 700;
    color: #0F172A;
    margin-bottom: 0.45rem;
}

.dep-desc {
    font-size: 0.8rem;
    color: #64748B;
    margin-top: 0.45rem;
}

.entity-chip {
    display: inline-block;
    background: #EFF6FF;
    color: #1E40AF;
    border: 1px solid #BFDBFE;
    border-radius: 6px;
    padding: 0.2rem 0.55rem;
    font-size: 0.78rem;
    font-weight: 600;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    margin: 0.15rem 0.3rem 0.15rem 0;
}

.sidebar-brand {
    padding: 0.25rem 0 0.75rem 0;
}

.sidebar-brand-title {
    font-size: 1.15rem;
    font-weight: 700;
    color: #FFFFFF !important;
    letter-spacing: -0.01em;
}

.sidebar-brand-sub {
    font-size: 0.78rem;
    color: #94A3B8 !important;
    margin-top: 0.15rem;
}
</style>
"""


def render_pill_html(text: str, tone: str = "neutral") -> str:
    """Render an escaped status pill badge."""
    safe_tone = tone if tone in {"success", "warning", "danger", "info", "neutral"} else "neutral"
    return (
        f'<span class="pill pill-{safe_tone}">'
        f'<span class="pill-dot"></span>{_esc(text)}'
        f"</span>"
    )


def render_topbar_html(
    *,
    health_status: str | None,
    ui_env: str,
    demo_mode: bool,
    cf_user_email: str | None = None,
) -> str:
    """Render the top production application header bar."""
    if health_status == "ok":
        status_pill = render_pill_html("Proxy Operational", "success")
    elif health_status == "degraded":
        status_pill = render_pill_html("Proxy Degraded (503)", "danger")
    elif health_status == "unreachable":
        status_pill = render_pill_html("Proxy Unreachable", "danger")
    else:
        status_pill = render_pill_html("Status Unchecked", "neutral")

    env_pill = render_pill_html(
        "Demo Mode" if demo_mode else f"Env: {ui_env.upper()}",
        "warning" if demo_mode else "info",
    )

    user_pill = ""
    if cf_user_email:
        user_pill = render_pill_html(f"CF Access: {cf_user_email}", "neutral")

    return (
        '<div class="app-topbar">'
        '  <div class="app-brand">'
        '    <div class="app-logo">PV</div>'
        '    <div>'
        '      <div class="app-title">PromptVeil &middot; LLM Privacy Proxy</div>'
        '      <div class="app-subtitle">'
        '        Automatic PII redaction, reversible restoration, and zero-content auditing'
        '      </div>'
        '    </div>'
        '  </div>'
        f'  <div class="app-badges">{status_pill}{env_pill}{user_pill}</div>'
        '</div>'
    )


def render_kpi_card_html(
    label: str,
    value: object,
    subtext: str = "",
    tone: str = "info",
) -> str:
    """Render an escaped KPI metric card."""
    safe_tone = tone if tone in {"success", "warning", "danger", "info"} else "info"
    sub_html = f'<div class="kpi-sub">{_esc(subtext)}</div>' if subtext else ""
    return (
        f'<div class="kpi-card tone-{safe_tone}">'
        f'  <div class="kpi-label">{_esc(label)}</div>'
        f'  <div class="kpi-value">{_esc(value)}</div>'
        f"  {sub_html}"
        f"</div>"
    )


def render_pipeline_html(last_outcome: str | None) -> str:
    """Render the 5-stage proxy pipeline strip reflecting the last request's state."""
    steps = [
        (1, "Auth & Rate Limit"),
        (2, "PII Scrub"),
        (3, "Audit Pending"),
        (4, "LLM Call"),
        (5, "Restore & Audit"),
    ]

    # Map outcome to per-step visual state: "done", "blocked", "warn", or "".
    states = [""] * len(steps)
    if last_outcome == "ok":
        states = ["done"] * len(steps)
    elif last_outcome in {"auth", "validation"}:
        states[0] = "blocked"
    elif last_outcome == "rate_limit":
        states[0] = "warn"
    elif last_outcome == "fail_closed":
        states[0] = "done"
        states[1] = "blocked"
        states[2] = "blocked"
    elif last_outcome == "upstream":
        states[0] = "done"
        states[1] = "done"
        states[2] = "done"
        states[3] = "blocked"

    step_html = []
    for (num, title), state in zip(steps, states):
        cls = f"pipe-step {state}".strip()
        step_html.append(
            f'<div class="{cls}">'
            f'<span class="pipe-num">{num}</span>'
            f"<span>{_esc(title)}</span>"
            f"</div>"
        )

    return f'<div class="pipeline-bar">{"".join(step_html)}</div>'


def render_text_panel_html(title: str, badge_text: str, badge_tone: str, content: str) -> str:
    """Render an escaped monospace text comparison panel."""
    badge = render_pill_html(badge_text, badge_tone)
    return (
        '<div class="panel-box">'
        f'  <div class="panel-header"><span>{_esc(title)}</span>{badge}</div>'
        f'  <pre class="panel-body">{_esc(content)}</pre>'
        "</div>"
    )


def render_entity_chips_html(pii_counts: dict[str, int]) -> str:
    """Render escaped entity count chips (e.g. EMAIL_ADDRESS: 2)."""
    chips = [
        f'<span class="entity-chip">{_esc(entity)}: {_esc(count)}</span>'
        for entity, count in sorted(pii_counts.items())
    ]
    return f"<div>{''.join(chips)}</div>"


def render_dep_card_html(name: str, status_label: str, tone: str, description: str) -> str:
    """Render a dependency health card."""
    pill = render_pill_html(status_label, tone)
    return (
        '<div class="dep-card">'
        f'  <div class="dep-title">{_esc(name)}</div>'
        f"  {pill}"
        f'  <div class="dep-desc">{_esc(description)}</div>'
        "</div>"
    )


def render_security_posture_html(items: Iterable[tuple[str, str, str]]) -> str:
    """Render a grid of security control cards: (control_name, badge_text, tone)."""
    cards = []
    for title, badge_text, tone in items:
        pill = render_pill_html(badge_text, tone)
        cards.append(
            '<div class="dep-card">'
            f'  <div class="dep-title">{_esc(title)}</div>'
            f"  {pill}"
            "</div>"
        )
    return "".join(cards)
