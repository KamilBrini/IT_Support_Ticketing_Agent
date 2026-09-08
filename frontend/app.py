"""Streamlit frontend for the IT support agent."""

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


st.set_page_config(page_title="IT Support Agent", page_icon="🛠", layout="wide")
st.title("IT Support Agent")

if "user_id" not in st.session_state:
    st.session_state.user_id = "u-001"
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []


def send_chat_message(user_text: str) -> None:
    """Post one message through the full agent pipeline and record the exchange.

    Shared by the main chat box, the sidebar ticket-lookup chips, and the
    guided password-reset form, so all three entry points go through the
    identical guardrails/tracing/error-handling path - no separate code path
    to keep in sync, and no "prefill the text box, then also click Send"
    indirection (that two-step version was tried first and turned out to
    corrupt Streamlit's session state under the form-in-sidebar layout here -
    calling this directly from each trigger avoids it entirely).
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
        # look like a broken app mid-demo.
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
        # login, so require an explicit confirm - it's what a user asked
        # for after noticing chat history didn't reset between employees -
        # and reset the session on confirm, same as a fresh login would.
        # (A real deployment would need actual per-user authentication;
        # see docs/SDD.md's Known Deviations - this confirm click is only
        # a demo-appropriate stand-in, not real access control.)
        st.session_state.pending_switch_label = selected_label
        display_name = selected_label.split(" — ")[0]
        st.warning(f"Switch to {display_name}? This starts a fresh session and clears the current chat.")
        confirm_col, cancel_col = st.columns(2)
        if confirm_col.button("Yes, switch", use_container_width=True, key="confirm_switch_btn"):
            st.session_state.user_id = selected_uid
            st.session_state.session_id = str(uuid.uuid4())
            st.session_state.messages = []
            st.session_state.pending_switch_label = None
        if cancel_col.button("Cancel", use_container_width=True, key="cancel_switch_btn"):
            st.session_state.pending_switch_label = None

    st.session_state.session_id = st.text_input("Session ID", value=st.session_state.session_id)

    st.divider()
    st.header("Your tickets")
    my_tickets = fetch_tickets_for_user(st.session_state.user_id)
    if my_tickets:
        for ticket in my_tickets:
            st.button(
                f"{ticket['ticket_id']} · {ticket['status']}",
                key=f"ticket_btn_{ticket['ticket_id']}",
                use_container_width=True,
                help=ticket.get("title"),
                on_click=send_chat_message,
                args=(f"ticket status {ticket['ticket_id']}",),
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

        st.text_input(
            "Briefly describe why you need a reset (5+ characters)",
            key="reset_reason_input",
        )
        st.button("Prepare request", on_click=_handle_reset_submit)

    st.divider()
    st.caption("Trace Viewer")
    st.markdown(f"[Open trace viewer]({TRACE_VIEWER_URL})")
    st.caption("If tracing is disabled, this link may not show live spans.")


def render_tool_result(tool_result: Any) -> None:
    """Render known tool payloads as friendly cards."""
    if not isinstance(tool_result, dict):
        return

    if "found" in tool_result and "ticket_id" in tool_result:
        if tool_result.get("found"):
            title_line = [f"- Issue: {tool_result.get('title')}"] if tool_result.get("title") else []
            st.info(
                "\n".join(
                    [
                        "Ticket Status",
                        f"- Ticket ID: {tool_result.get('ticket_id')}",
                        *title_line,
                        f"- Status: {tool_result.get('status')}",
                        f"- Queue: {tool_result.get('assigned_queue') or 'n/a'}",
                        f"- Escalation Level: {tool_result.get('escalation_level')}",
                    ]
                )
            )
        else:
            st.error(
                f"Ticket {tool_result.get('ticket_id')} was not found"
                f" ({tool_result.get('error_code') or 'ERR-NOT-FOUND'})."
            )
        return

    if "status" in tool_result and "next_action" in tool_result:
        status = str(tool_result.get("status", "")).lower()
        if status == "completed":
            st.success(
                "\n".join(
                    [
                        "Password Reset Request",
                        f"- Status: {tool_result.get('status')}",
                        f"- Next Action: {tool_result.get('next_action')}",
                    ]
                )
            )
        elif status == "escalated":
            st.info(
                "\n".join(
                    [
                        "Password Reset Request",
                        f"- Status: {tool_result.get('status')}",
                        f"- Next Action: {tool_result.get('next_action')}",
                    ]
                )
            )
        else:
            st.error(
                "\n".join(
                    [
                        "Password Reset Request",
                        f"- Status: {tool_result.get('status')}",
                        f"- Next Action: {tool_result.get('next_action')}",
                    ]
                )
            )
        return

    if "ticket_id" in tool_result and "status" in tool_result and "message" in tool_result:
        status = str(tool_result.get("status", "")).lower()
        if status == "created":
            st.success(
                "\n".join(
                    [
                        "Ticket Created",
                        f"- Ticket ID: {tool_result.get('ticket_id')}",
                        f"- Status: {tool_result.get('status')}",
                        f"- Message: {tool_result.get('message')}",
                    ]
                )
            )
        else:
            st.error(
                "\n".join(
                    [
                        "Ticket Creation",
                        f"- Status: {tool_result.get('status')}",
                        f"- Message: {tool_result.get('message')}",
                    ]
                )
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
    else:
        st.session_state["_chat_empty_error"] = True


st.text_input(
    "Message",
    key="chat_message_input",
    placeholder="Describe your IT issue or policy question",
)
st.button("Send", on_click=_handle_chat_send)

if st.session_state.pop("_chat_empty_error", False):
    st.error("Please enter a message before submitting.")

# Render any message-level errors beneath the thread for visibility.
for msg in st.session_state.messages:
    if msg.get("error"):
        st.error(str(msg["error"]))
