"""Streamlit frontend for the IT support agent.

Visual/presentation layer only - every function that talks to the backend
(send_chat_message, fetch_tickets_for_user) and every session-state key is
unchanged from the plain version. See git branch `main` for that baseline;
this branch (`experiment/premium-ui-refactor`) only touches layout, CSS,
and how results are rendered.
"""

from __future__ import annotations

import os
import uuid
from typing import Any

import requests
import streamlit as st

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")
CHAT_ENDPOINT = f"{API_BASE_URL}/chat"
TICKETS_ENDPOINT = f"{API_BASE_URL}/tickets"
TRACE_VIEWER_URL = os.getenv("TRACE_VIEWER_URL", "http://localhost:6006")

# user_id values match SupportTicket.requester_user_id in src/tools/mcp_server.py's
# seed data, so picking a name here has a real, demoable ticket behind it.
_CUSTOM_ID_LABEL = "Other (type a user ID)"
EMPLOYEE_ROSTER: dict[str, str] = {
    "Alice Chen — Network (u-001)": "u-001",
    "Priya Patel — Identity (u-002)": "u-002",
    "Jordan Lee — Executive IT (u-010)": "u-010",
    "Sam Okafor — Hardware (u-021)": "u-021",
    _CUSTOM_ID_LABEL: "__custom__",
}

_STATUS_BADGE_CLASS = {
    "open": "badge-open",
    "in_progress": "badge-in_progress",
    "waiting_user": "badge-waiting_user",
    "resolved": "badge-resolved",
    "closed": "badge-closed",
}
_STATUS_DOT = {
    "open": "🔵",
    "in_progress": "🟡",
    "waiting_user": "🟣",
    "resolved": "🟢",
    "closed": "⚪",
}


def _escalation_accent(level: int | None) -> str:
    """Map a ticket's real escalation_level to an urgency accent color.

    There's no separate "priority" field in TicketStatusResponse (see
    src/schemas/models.py on main) - escalation_level is the real signal
    already flowing through the API, so accents are driven by that instead
    of inventing data the backend doesn't return.
    """
    if level is None:
        return "#6B7280"
    if level >= 2:
        return "#F87171"
    if level == 1:
        return "#F59E0B"
    return "#6B7280"


def _badge(label: str, css_class: str) -> str:
    return f'<span class="badge {css_class}">{label}</span>'


def inject_custom_css() -> None:
    """One-time (well, once-per-rerun, which is harmless) style injection.

    Presentation only: fonts, hiding Streamlit chrome, card/badge styling.
    Nothing here reads or writes session_state or talks to the backend.

    Dark base (#0D0D0D/#161616) + lime green (#5FFB07) accent - FDM Group's
    palette. The actual theme-of-record is .streamlit/config.toml ([theme]
    base="dark", primaryColor="#5FFB07", ...) - that's what makes *native*
    widgets (chat bubbles, text inputs, the selectbox) consistently dark.
    This CSS only styles the custom elements config.toml can't reach
    (badges, result cards, the header bar) and needs to agree with it, not
    fight it - the first version of this page had light-hardcoded custom
    cards sitting next to native widgets that followed the browser's own
    dark-mode preference, so a chat reply's dark text landed on a dark
    background from an unrelated source - invisible text.
    """
    st.html(
        """
        <style>
        /* System font stack, not a Google Fonts @import: an external font
           fetch was adding a real network round-trip to first render -
           noticeable on the initial page load. Segoe UI/system-ui look
           clean and were an accepted alternative to Inter from the start. */
        html, body, [class*="css"] {
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
        }

        /* --- Hide Streamlit chrome --- */
        #MainMenu { visibility: hidden; }
        footer { visibility: hidden; }
        header[data-testid="stHeader"] { background: transparent; height: 2.5rem; }
        div[data-testid="stToolbar"] { visibility: hidden; }
        div[data-testid="stDecoration"] { visibility: hidden; }
        /* Streamlit's own generic running/"Stop" indicator - replaced by the
           branded "Thinking..." pill below, which is scoped to exactly the
           backend call instead of every rerun, so keeping both would be
           redundant. */
        div[data-testid="stStatusWidget"] { visibility: hidden; }

        .block-container { padding-top: 1.25rem; max-width: 1200px; }

        /* --- "Thinking..." indicator (wraps the requests.post call in
           send_chat_message via st.spinner - see there for why) ---
           Fixed position: st.spinner() renders wherever the current script
           position is, which differs between a callback (top of main area)
           and the main body - fixed positioning makes it always land in
           the same top-right spot regardless of which triggered it. */
        [data-testid="stSpinner"] {
            position: fixed !important;
            top: 16px;
            right: 28px;
            z-index: 9999;
            width: auto !important;
            background: #161616;
            border: 1px solid #2A2A2A;
            border-radius: 999px;
            padding: 7px 16px 7px 14px;
            box-shadow: 0 4px 14px rgba(0, 0, 0, 0.45);
        }
        [data-testid="stSpinner"] > div {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        [data-testid="stSpinner"] [data-testid="stMarkdownContainer"] p {
            color: #D4D4D4;
            font-size: 0.8rem;
            font-weight: 600;
            letter-spacing: 0.01em;
            margin: 0;
        }
        /* Three-dot pulse built from one element + its two pseudo-elements,
           replacing Streamlit's default spinner glyph entirely. */
        [data-testid="stSpinnerIcon"] {
            width: 6px; height: 6px;
            margin: 0 8px;
            border: none !important;
            border-radius: 50%;
            background: #5FFB07;
            display: inline-block;
            position: relative;
            animation: thinkPulse 1.1s ease-in-out infinite;
            animation-delay: 0.18s;
        }
        [data-testid="stSpinnerIcon"]::before,
        [data-testid="stSpinnerIcon"]::after {
            content: "";
            position: absolute;
            top: 0;
            width: 6px; height: 6px;
            border-radius: 50%;
            background: #5FFB07;
            animation: thinkPulse 1.1s ease-in-out infinite;
        }
        [data-testid="stSpinnerIcon"]::before { left: -14px; animation-delay: 0s; }
        [data-testid="stSpinnerIcon"]::after { left: 14px; animation-delay: 0.36s; }
        @keyframes thinkPulse {
            0%, 60%, 100% { opacity: 0.35; transform: scale(0.7); }
            30% { opacity: 1; transform: scale(1); }
        }

        /* --- FDM logo mark --- */
        .fdm-logo {
            background: #000000;
            border: 1px solid #2A2A2A;
            border-radius: 10px;
            padding: 8px 14px;
            display: flex;
            align-items: center;
            flex-shrink: 0;
        }

        /* --- Sidebar --- */
        [data-testid="stSidebar"] {
            border-right: 1px solid #2A2A2A;
            width: 350px !important;
        }
        [data-testid="stSidebar"] h2 { font-size: 0.95rem; color: #F2F2F2; }

        /* --- Buttons --- */
        .stButton > button {
            border-radius: 8px;
            border: 1px solid #2A2A2A;
            font-weight: 500;
            transition: transform 0.12s ease, box-shadow 0.12s ease, border-color 0.12s ease;
        }
        .stButton > button:hover {
            border-color: #5FFB07;
            color: #5FFB07;
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(95, 251, 7, 0.18);
        }
        .stButton > button[kind="primary"] {
            background: #5FFB07;
            border: none;
            color: #0D0D0D;
            font-weight: 700;
            box-shadow: 0 2px 10px rgba(95, 251, 7, 0.35);
        }
        .stButton > button[kind="primary"]:hover {
            background: #7CFF33;
            color: #0D0D0D;
        }

        /* --- st.container(border=True) -> premium card --- */
        div[data-testid="stVerticalBlockBorderWrapper"] {
            border-radius: 14px !important;
            border: 1px solid #2A2A2A !important;
            box-shadow: 0 1px 4px rgba(0, 0, 0, 0.35);
            background: #161616;
        }

        /* --- Header bar --- */
        .app-header {
            display: flex;
            align-items: center;
            gap: 16px;
            background: #161616;
            border: 1px solid #2A2A2A;
            border-radius: 14px;
            padding: 18px 24px;
            margin-bottom: 18px;
            box-shadow: 0 1px 4px rgba(0, 0, 0, 0.35);
        }
        .app-header__name { font-size: 1.3rem; font-weight: 800; color: #FFFFFF; line-height: 1.2; }
        .app-header__subtitle { font-size: 0.85rem; color: #A0A0A0; margin-top: 2px; }

        /* --- Stat cards --- */
        .stat-card {
            background: #161616;
            border: 1px solid #2A2A2A;
            border-left: 4px solid var(--accent, #5FFB07);
            border-radius: 10px;
            padding: 12px 16px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
        }
        .stat-card__label {
            font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.05em;
            color: #A0A0A0; font-weight: 700;
        }
        .stat-card__value { font-size: 1.55rem; font-weight: 800; color: #F2F2F2; margin-top: 2px; }

        /* --- Badges --- */
        .badge {
            display: inline-block;
            padding: 3px 10px;
            border-radius: 999px;
            font-size: 0.72rem;
            font-weight: 700;
            letter-spacing: 0.01em;
            white-space: nowrap;
        }
        .badge-open { background: rgba(96, 165, 250, 0.15); color: #93C5FD; }
        .badge-in_progress { background: rgba(251, 191, 36, 0.15); color: #FCD34D; }
        .badge-waiting_user { background: rgba(196, 181, 253, 0.15); color: #DDD6FE; }
        .badge-resolved { background: rgba(52, 211, 153, 0.15); color: #6EE7B7; }
        .badge-closed { background: rgba(156, 163, 175, 0.18); color: #D1D5DB; }
        .badge-completed { background: rgba(52, 211, 153, 0.15); color: #6EE7B7; }
        .badge-escalated { background: rgba(251, 191, 36, 0.15); color: #FCD34D; }
        .badge-rejected { background: rgba(248, 113, 113, 0.15); color: #FCA5A5; }
        .badge-created { background: rgba(52, 211, 153, 0.15); color: #6EE7B7; }

        /* --- Result cards (ticket / reset / creation) --- */
        .result-card {
            border-radius: 10px;
            border: 1px solid #2A2A2A;
            border-left: 4px solid var(--accent, #5FFB07);
            background: #1B1B1B;
            padding: 12px 16px;
            margin: 6px 0 2px 0;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
        }
        .result-card__title {
            font-weight: 700; color: #F2F2F2; margin-bottom: 6px;
            display: flex; align-items: center; justify-content: space-between; gap: 8px;
        }
        .result-card__row { font-size: 0.86rem; color: #C4C4C4; margin: 2px 0; }
        .result-card__row b { color: #F2F2F2; }

        /* --- Empty chat hint --- */
        .empty-chat-hint {
            text-align: center; padding: 36px 12px; color: #7A7A7A; font-size: 0.92rem;
        }

        /* --- Subtle entrance animation for new chat turns --- */
        [data-testid="stChatMessage"] { animation: fadeInUp 0.25s ease; }
        @keyframes fadeInUp {
            from { opacity: 0; transform: translateY(6px); }
            to { opacity: 1; transform: translateY(0); }
        }
        </style>
        """
    )


st.set_page_config(page_title="IT Support Agent", page_icon="🛠", layout="wide")
inject_custom_css()

if "user_id" not in st.session_state:
    st.session_state.user_id = "u-001"
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []


def send_chat_message(user_text: str) -> None:
    """Post one message through the full agent pipeline and record the exchange.

    Shared by the main chat box, the sidebar ticket-lookup chips, the
    guided password-reset form, and the demo-walkthrough shortcuts, so
    every entry point goes through the identical guardrails/tracing/
    error-handling path - no separate code path to keep in sync, and no
    "prefill the text box, then also click Send" indirection (that
    two-step version was tried first and turned out to corrupt Streamlit's
    session state under a form-in-sidebar layout - calling this directly
    from each trigger avoids it entirely).
    """
    if not user_text.strip():
        return

    user_message: dict[str, Any] = {"role": "user", "content": user_text}
    st.session_state.messages.append(user_message)

    payload = {
        "user_id": st.session_state.user_id,
        "session_id": st.session_state.session_id,
        "user_message": user_text,
    }

    try:
        # 60s, not 30s: an occasional slow NVIDIA NIM response (cold start
        # after idle time) can legitimately take 30-45s, and that shouldn't
        # look like a broken app mid-demo. st.spinner wraps the blocking
        # call so the "thinking" indicator (styled via CSS - see
        # inject_custom_css) is up for exactly as long as the backend is
        # actually working, from every trigger (chat box, ticket chips,
        # reset button, demo scenarios) since they all funnel through here.
        with st.spinner("Thinking..."):
            response = requests.post(CHAT_ENDPOINT, json=payload, timeout=60)
    except requests.RequestException as exc:
        st.session_state.messages.append({
            "role": "assistant",
            "content": "I could not connect to the backend service.",
            "error": f"Could not reach API at {CHAT_ENDPOINT}. Details: {exc}",
        })
        return

    if response.status_code == 422:
        detail = response.json().get("detail", "Validation error")
        if isinstance(detail, list):
            detail = "; ".join(str(item) for item in detail)
        st.session_state.messages.append({
            "role": "assistant",
            "content": "Your request did not pass validation.",
            "error": f"Validation error: {detail}",
        })
        return

    if not response.ok:
        st.session_state.messages.append({
            "role": "assistant",
            "content": "The backend returned an error.",
            "error": f"HTTP {response.status_code}: {response.text}",
        })
        return

    data = response.json()
    assistant_text = data.get("response", "No response returned.")
    intent = str(data.get("intent", "")).lower()
    tool_result = data.get("tool_result")
    sanitized_message = data.get("sanitized_message")

    if sanitized_message and sanitized_message != user_text:
        user_message["redacted_preview"] = sanitized_message

    assistant_message: dict[str, Any] = {
        "role": "assistant",
        "content": assistant_text,
        "tool_result": tool_result,
    }
    if intent == "blocked":
        assistant_message["error"] = "Request was blocked by injection/safety rules."
    st.session_state.messages.append(assistant_message)


def send_and_notify(user_text: str, toast: str = "Sent") -> None:
    """Thin UI-feedback wrapper around send_chat_message - adds a st.toast.

    Kept separate from send_chat_message itself (which stays untouched)
    so every trigger point (chips, reset button, demo shortcuts) can show
    a friendly confirmation without duplicating the actual pipeline call.
    """
    send_chat_message(user_text)
    st.toast(toast, icon="✅")


def fetch_tickets_for_user(user_id: str) -> list[dict[str, Any]]:
    """Read-only lookup for the sidebar panel - bypasses the chat/graph entirely."""
    try:
        resp = requests.get(TICKETS_ENDPOINT, params={"user_id": user_id}, timeout=10)
    except requests.RequestException:
        return []
    if not resp.ok:
        return []
    return resp.json()


if "pending_switch_label" not in st.session_state:
    st.session_state.pending_switch_label = None

with st.sidebar:
    st.header("Employee")
    roster_labels = list(EMPLOYEE_ROSTER.keys())
    current_label = next(
        (label for label, uid in EMPLOYEE_ROSTER.items() if uid == st.session_state.user_id),
        _CUSTOM_ID_LABEL,
    )
    display_label = st.session_state.pending_switch_label or current_label
    selected_label = st.selectbox("Signed in as", roster_labels, index=roster_labels.index(display_label))
    selected_uid = EMPLOYEE_ROSTER[selected_label]

    if selected_label == current_label:
        # Matches the active identity (or a pending switch got reselected
        # back to it) - nothing to confirm.
        st.session_state.pending_switch_label = None
        if selected_uid == "__custom__":
            st.session_state.user_id = st.text_input("User ID", value=st.session_state.user_id)
    elif selected_uid == "__custom__":
        # "Other" is a no-confirm testing escape hatch, not a real identity
        # switch - typing a fresh ID every keystroke shouldn't need a
        # confirm click each time.
        st.session_state.pending_switch_label = None
        st.session_state.user_id = st.text_input("User ID", value=st.session_state.user_id)
    else:
        # Picked a different named employee: this is a stand-in for a real
        # login, so require an explicit confirm - and reset the session on
        # confirm, same as a fresh login would. (A real deployment would
        # need actual per-user authentication; see docs/SDD.md's Known
        # Deviations - this confirm click is only a demo-appropriate
        # stand-in, not real access control.)
        st.session_state.pending_switch_label = selected_label
        display_name = selected_label.split(" — ")[0]
        st.warning(f"Switch to {display_name}? This starts a fresh session and clears the current chat.")
        confirm_col, cancel_col = st.columns(2)
        if confirm_col.button("Yes, switch", use_container_width=True, key="confirm_switch_btn", type="primary"):
            st.session_state.user_id = selected_uid
            st.session_state.session_id = str(uuid.uuid4())
            st.session_state.messages = []
            st.session_state.pending_switch_label = None
            st.toast(f"Signed in as {display_name}", icon="👤")
        if cancel_col.button("Cancel", use_container_width=True, key="cancel_switch_btn"):
            st.session_state.pending_switch_label = None

    st.session_state.session_id = st.text_input("Session ID", value=st.session_state.session_id)

    # Fetched once here, reused by both the demo walkthrough (below) and
    # the ticket list (further below) - same read-only call as before.
    my_tickets = fetch_tickets_for_user(st.session_state.user_id)

    st.divider()
    with st.expander("💡 Interactive Demo Walkthrough", expanded=True):
        st.caption("Click a scenario to watch the agent handle it live - no typing required.")

        demo_ticket_id = my_tickets[0]["ticket_id"] if my_tickets else None
        if demo_ticket_id:
            ticket_scenario_text = f"ticket status {demo_ticket_id}"
            ticket_scenario_label = f"🔍 Check ticket {demo_ticket_id}"
        else:
            ticket_scenario_text = "create ticket: my laptop screen flickers intermittently"
            ticket_scenario_label = "🔍 Create a new ticket"

        st.button(
            ticket_scenario_label,
            use_container_width=True,
            key="demo_ticket_btn",
            help="Looks up a real ticket through the same guardrail pipeline as manual chat.",
            on_click=send_and_notify,
            args=(ticket_scenario_text, "Ticket lookup sent"),
        )
        st.button(
            "🔑 Reset a forgotten password",
            use_container_width=True,
            key="demo_reset_btn",
            help="Runs the guided password-reset flow end-to-end.",
            on_click=send_and_notify,
            args=(
                "reset password: I just got back from a business trip and forgot my password",
                "Reset request sent",
            ),
        )
        st.button(
            "📄 Ask a grounded policy question",
            use_container_width=True,
            key="demo_policy_btn",
            help="Retrieves real policy text from the knowledge base and grounds the answer in it.",
            on_click=send_and_notify,
            args=("What does our VPN policy require for remote access and MFA?", "Policy question sent"),
        )
        st.button(
            "🧠 Teach it a fact (long-term memory)",
            use_container_width=True,
            key="demo_memory_btn",
            help="Stores a fact in long-term memory - try asking 'What laptop am I using?' right after.",
            on_click=send_and_notify,
            args=("Remember that I primarily work from the Austin office on a Dell laptop.", "Memory saved"),
        )

    st.divider()
    st.header("Your tickets")
    if my_tickets:
        for ticket in my_tickets:
            dot = _STATUS_DOT.get(ticket.get("status"), "⚪")
            st.button(
                f"{dot} {ticket['ticket_id']} · {ticket['status']}",
                key=f"ticket_btn_{ticket['ticket_id']}",
                use_container_width=True,
                help=ticket.get("title"),
                on_click=send_and_notify,
                args=(f"ticket status {ticket['ticket_id']}", f"Checking {ticket['ticket_id']}"),
            )
    else:
        st.caption("No tickets on file for this user.")

    st.divider()
    with st.expander("Reset my password"):
        # Plain widgets + on_click callback, not st.form: an st.form here
        # alongside the main chat box was observed to silently stop the
        # *other* widget's submit event from ever firing again after the
        # first one submitted once (a real, reproducible Streamlit
        # interaction on this page's layout, not a false alarm). Plain
        # buttons never had that problem, and a single text field doesn't
        # need a form anyway.
        def _handle_reset_submit() -> None:
            reason = st.session_state.get("reset_reason_input", "").strip() or "forgot my password"
            send_chat_message(f"reset password: {reason}")
            st.session_state.reset_reason_input = ""
            st.toast("Reset request sent", icon="🔑")

        st.text_input(
            "Briefly describe why you need a reset (5+ characters)",
            key="reset_reason_input",
        )
        st.button("Prepare request", on_click=_handle_reset_submit, type="primary")

    st.divider()
    st.caption("Trace Viewer")
    st.markdown(f"[Open trace viewer]({TRACE_VIEWER_URL})")
    st.caption("If tracing is disabled, this link may not show live spans.")


def render_tool_result(tool_result: Any) -> None:
    """Render known tool payloads as styled cards (same shape-detection logic as before)."""
    if not isinstance(tool_result, dict):
        return

    if "found" in tool_result and "ticket_id" in tool_result:
        if tool_result.get("found"):
            accent = _escalation_accent(tool_result.get("escalation_level"))
            status_val = str(tool_result.get("status") or "")
            badge_html = _badge(
                status_val.replace("_", " ").title(),
                _STATUS_BADGE_CLASS.get(status_val, "badge-closed"),
            )
            title_row = (
                f'<div class="result-card__row">🗂️ {tool_result.get("title")}</div>'
                if tool_result.get("title")
                else ""
            )
            st.markdown(
                f'''<div class="result-card" style="--accent:{accent}">
                    <div class="result-card__title"><span>🎫 {tool_result.get("ticket_id")}</span>{badge_html}</div>
                    {title_row}
                    <div class="result-card__row"><b>Queue:</b> {tool_result.get("assigned_queue") or "n/a"}</div>
                    <div class="result-card__row"><b>Escalation level:</b> {tool_result.get("escalation_level")}</div>
                </div>''',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f'''<div class="result-card" style="--accent:#F87171">
                    <div class="result-card__title">
                        <span>🎫 {tool_result.get("ticket_id")}</span>{_badge("Not found", "badge-rejected")}
                    </div>
                    <div class="result-card__row">{tool_result.get("error_code") or "ERR-NOT-FOUND"}</div>
                </div>''',
                unsafe_allow_html=True,
            )
        return

    if "status" in tool_result and "next_action" in tool_result:
        status_val = str(tool_result.get("status", "")).lower()
        accent = {"completed": "#34D399", "escalated": "#FBBF24"}.get(status_val, "#F87171")
        badge_class = {"completed": "badge-completed", "escalated": "badge-escalated"}.get(
            status_val, "badge-rejected"
        )
        st.markdown(
            f'''<div class="result-card" style="--accent:{accent}">
                <div class="result-card__title">
                    <span>🔑 Password Reset</span>{_badge(status_val.title() or "Unknown", badge_class)}
                </div>
                <div class="result-card__row">{tool_result.get("next_action")}</div>
            </div>''',
            unsafe_allow_html=True,
        )
        return

    if "ticket_id" in tool_result and "status" in tool_result and "message" in tool_result:
        status_val = str(tool_result.get("status", "")).lower()
        is_created = status_val == "created"
        accent = "#34D399" if is_created else "#F87171"
        badge_class = "badge-created" if is_created else "badge-rejected"
        st.markdown(
            f'''<div class="result-card" style="--accent:{accent}">
                <div class="result-card__title">
                    <span>🎫 {tool_result.get("ticket_id") or "New ticket"}</span>
                    {_badge(status_val.title() or "Unknown", badge_class)}
                </div>
                <div class="result-card__row">{tool_result.get("message")}</div>
            </div>''',
            unsafe_allow_html=True,
        )


_FDM_LOGO_SVG = (
    '<svg width="108" height="38" viewBox="0 0 168 60" xmlns="http://www.w3.org/2000/svg" '
    'role="img" aria-label="FDM">'
    '<text x="2" y="47" font-family="Arial, Helvetica, sans-serif" font-weight="900" '
    'font-size="50" fill="#5FFB07" transform="skewX(-8)">FD</text>'
    '<polyline points="94,55 104,24 114,42 126,16 134,30 150,1" fill="none" stroke="#5FFB07" '
    'stroke-width="10" stroke-linecap="square" stroke-linejoin="miter" />'
    '</svg>'
)

st.markdown(
    f'''<div class="app-header">
        <div class="fdm-logo">{_FDM_LOGO_SVG}</div>
        <div>
            <div class="app-header__name">IT Support Agent</div>
            <div class="app-header__subtitle">Grounded policy answers, live ticket actions, and human escalation — every step traced.</div>
        </div>
    </div>''',
    unsafe_allow_html=True,
)

stat_cols = st.columns(4)
_stat_values = [
    ("My Tickets", len(my_tickets), "#5FFB07"),
    ("Open", sum(1 for t in my_tickets if t.get("status") == "open"), "#60A5FA"),
    ("In Progress", sum(1 for t in my_tickets if t.get("status") == "in_progress"), "#FBBF24"),
    ("Resolved", sum(1 for t in my_tickets if t.get("status") in ("resolved", "closed")), "#34D399"),
]
for col, (label, value, accent) in zip(stat_cols, _stat_values):
    with col:
        st.markdown(
            f'''<div class="stat-card" style="--accent:{accent}">
                <div class="stat-card__label">{label}</div>
                <div class="stat-card__value">{value}</div>
            </div>''',
            unsafe_allow_html=True,
        )

st.write("")

chat_panel = st.container(border=True)
with chat_panel:
    if not st.session_state.messages:
        st.markdown(
            '<div class="empty-chat-hint">👋 Start the conversation below — try a policy question, '
            "a ticket lookup, or a demo scenario from the sidebar.</div>",
            unsafe_allow_html=True,
        )

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("redacted_preview"):
                st.caption(f"🔒 PII redacted before processing: {msg['redacted_preview']}")
            if msg.get("tool_result"):
                render_tool_result(msg.get("tool_result"))

    def _handle_chat_send() -> None:
        text = st.session_state.get("chat_message_input", "")
        if text.strip():
            send_chat_message(text)
            st.session_state.chat_message_input = ""
            st.toast("Message sent", icon="✅")
        else:
            st.session_state["_chat_empty_error"] = True

    st.text_input(
        "Message",
        key="chat_message_input",
        placeholder="Describe your IT issue or policy question",
        label_visibility="collapsed",
    )
    send_col, _spacer_col = st.columns([1, 5])
    with send_col:
        st.button("Send", on_click=_handle_chat_send, type="primary", use_container_width=True)

if st.session_state.pop("_chat_empty_error", False):
    st.error("Please enter a message before submitting.")

# Render any message-level errors beneath the thread for visibility.
for msg in st.session_state.messages:
    if msg.get("error"):
        st.error(str(msg["error"]))
