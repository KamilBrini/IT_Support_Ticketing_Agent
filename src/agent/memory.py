"""In-memory short-term session conversation history (US-008).

Sliding window: the last 6 user/assistant turn pairs per session_id, held
in a process-local dict (matches the "In-memory list or session store"
option named in plan.md S11.2). Not persisted across restarts and not
shared across multiple backend workers - a durable/shared store is future
work if this needs to survive restarts or scale beyond one uvicorn process.

Only ever stores the already-redacted message and the final response text,
never raw user input, so PII redaction guarantees (NFR-007) extend to
memory the same way they extend to prompts and traces.
"""

from __future__ import annotations

from collections import deque

_MAX_PAIRS = 6
_sessions: dict[str, deque[tuple[str, str]]] = {}


def get_history(session_id: str) -> list[tuple[str, str]]:
    """Return this session's stored (user, assistant) pairs, oldest first."""
    return list(_sessions.get(session_id, ()))


def append_turn(session_id: str, sanitized_user_message: str, assistant_response: str) -> None:
    """Record a completed turn, trimming to the last _MAX_PAIRS pairs."""
    if not sanitized_user_message or not assistant_response:
        return
    history = _sessions.setdefault(session_id, deque(maxlen=_MAX_PAIRS))
    history.append((sanitized_user_message, assistant_response))
