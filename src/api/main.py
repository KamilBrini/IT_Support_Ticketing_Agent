"""FastAPI entrypoint for the IT support agent service."""

from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI

from src.agent.graph import agent_graph
from src.schemas.models import AgentState, ChatRequest, TicketStatusResponse
from src.security.pii_redaction import redact
from src.tools.mcp_server import get_ticket_status

# Load .env at process startup so NVIDIA_NIM_API_KEY etc. are actually
# picked up when running `uvicorn src.api.main:app` — nothing else in this
# codebase calls load_dotenv(), so without this line .env is silently
# ignored and only pre-set shell environment variables take effect.
load_dotenv()

app = FastAPI(title="IT Support Agent API", version="0.1.0")


@app.get("/health")
def health() -> dict[str, Any]:
    """Return service health metadata.

    `nvidia_nim_key_configured` is a boolean presence check only — it never
    exposes the key value itself — so you can confirm .env was picked up
    without printing or pasting the secret anywhere.
    """
    return {
        "status": "ok",
        "version": "0.1.0",
        "nvidia_nim_key_configured": bool(os.getenv("NVIDIA_NIM_API_KEY", "").strip()),
    }


@app.get("/tickets/{ticket_id}", response_model=TicketStatusResponse)
def get_ticket(ticket_id: str) -> TicketStatusResponse:
    """Return ticket status using the MCP tool wrapper."""
    return get_ticket_status(ticket_id)


@app.post("/chat")
def chat(request: ChatRequest) -> dict[str, Any]:
    """Process a chat request through the LangGraph agent and return JSON output."""
    sanitized_message = redact(request.user_message)
    initial_state: AgentState = {
        "user_id": request.user_id,
        "session_id": request.session_id,
        "sanitized_message": sanitized_message,
    }

    final_state = agent_graph.invoke(initial_state)
    tool_result = final_state.get("tool_result")

    ticket_data: dict[str, Any] | None = None
    if isinstance(tool_result, dict) and "ticket_id" in tool_result:
        ticket_data = {
            "ticket_id": tool_result.get("ticket_id"),
            "status": tool_result.get("status"),
            "message": tool_result.get("message"),
        }

    return {
        "response": final_state.get("response", ""),
        "intent": final_state.get("intent"),
        "tool_result": tool_result,
        "ticket": ticket_data,
        "sanitized_message": sanitized_message,
    }
