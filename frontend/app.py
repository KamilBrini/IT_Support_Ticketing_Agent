"""Streamlit frontend for the IT support agent."""

from __future__ import annotations

import os
import uuid
from typing import Any

import requests
import streamlit as st

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")
CHAT_ENDPOINT = f"{API_BASE_URL}/chat"
TRACE_VIEWER_URL = os.getenv("TRACE_VIEWER_URL", "http://localhost:6006")


st.set_page_config(page_title="IT Support Agent", page_icon="🛠", layout="wide")
st.title("IT Support Agent")

if "user_id" not in st.session_state:
    st.session_state.user_id = "demo-user"
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []

with st.sidebar:
    st.header("Session")
    st.session_state.user_id = st.text_input("User ID", value=st.session_state.user_id)
    st.session_state.session_id = st.text_input("Session ID", value=st.session_state.session_id)
    st.caption("Trace Viewer")
    st.markdown(f"[Open trace viewer]({TRACE_VIEWER_URL})")
    st.caption("If tracing is disabled, this link may not show live spans.")


def render_tool_result(tool_result: Any) -> None:
    """Render known tool payloads as friendly cards."""
    if not isinstance(tool_result, dict):
        return

    if "found" in tool_result and "ticket_id" in tool_result:
        if tool_result.get("found"):
            st.info(
                "\n".join(
                    [
                        "Ticket Status",
                        f"- Ticket ID: {tool_result.get('ticket_id')}",
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
        if msg.get("tool_result"):
            render_tool_result(msg.get("tool_result"))

with st.form("chat_form", clear_on_submit=True):
    user_text = st.text_input("Message", placeholder="Describe your IT issue or policy question")
    submitted = st.form_submit_button("Send")

if submitted:
    if not user_text.strip():
        st.error("Please enter a message before submitting.")
    else:
        st.session_state.messages.append({"role": "user", "content": user_text})

        payload = {
            "user_id": st.session_state.user_id,
            "session_id": st.session_state.session_id,
            "user_message": user_text,
        }

        try:
            response = requests.post(CHAT_ENDPOINT, json=payload, timeout=30)
        except requests.RequestException as exc:
            error_message = f"Could not reach API at {CHAT_ENDPOINT}. Details: {exc}"
            st.session_state.messages.append({
                "role": "assistant",
                "content": "I could not connect to the backend service.",
                "error": error_message,
            })
            st.rerun()

        if response.status_code == 422:
            detail = response.json().get("detail", "Validation error")
            if isinstance(detail, list):
                detail = "; ".join(str(item) for item in detail)
            st.session_state.messages.append({
                "role": "assistant",
                "content": "Your request did not pass validation.",
                "error": f"Validation error: {detail}",
            })
            st.rerun()

        if not response.ok:
            st.session_state.messages.append({
                "role": "assistant",
                "content": "The backend returned an error.",
                "error": f"HTTP {response.status_code}: {response.text}",
            })
            st.rerun()

        data = response.json()
        assistant_text = data.get("response", "No response returned.")
        intent = str(data.get("intent", "")).lower()
        tool_result = data.get("tool_result")

        assistant_message: dict[str, Any] = {
            "role": "assistant",
            "content": assistant_text,
            "tool_result": tool_result,
        }

        if intent == "blocked":
            assistant_message["error"] = "Request was blocked by injection/safety rules."

        st.session_state.messages.append(assistant_message)
        st.rerun()

# Render any message-level errors beneath the thread for visibility.
for msg in st.session_state.messages:
    if msg.get("error"):
        st.error(str(msg["error"]))
