"""LangGraph workflow for the IT support agent."""

from __future__ import annotations

import re
from typing import Any, Literal

from langgraph.graph import END, START, StateGraph

from src.agent import long_term_memory, memory
from src.llm.client import get_llm_client
from src.observability.tracing import safe_preview, traced_span
from src.rag.retrieve import retrieve_context
from src.schemas.models import AgentState
from src.security.injection_guard import is_suspicious
from src.security.pii_redaction import redact
from src.tools.mcp_server import (
    create_ticket,
    get_ticket_owner,
    get_ticket_status,
    list_tickets_for_user,
    request_password_reset,
)

Intent = Literal[
    "policy_question",
    "action_request",
    "direct_response",
    "escalation",
    "blocked",
    "remember_fact",
]

_MARKDOWN_HEADING_RE = re.compile(r"(?m)^#{1,6}\s+")
_RESPONSE_CHAR_LIMIT = 2000


def _strip_markdown_headings(text: str) -> str:
    """Drop leading '#' heading markers from retrieved chunk text.

    Policy source docs start with a Markdown H1 (e.g. "# Corporate VPN
    Access Policy"); passed through untouched into Streamlit's st.markdown,
    that renders as giant heading text instead of a normal sentence.
    """
    return _MARKDOWN_HEADING_RE.sub("", text)


def _truncate_at_sentence(text: str, limit: int) -> str:
    """Trim to at most `limit` chars, ending on a full sentence/word.

    A hard `text[:limit]` slice cuts mid-word (e.g. "...softwa"); this finds
    the last sentence boundary (falling back to the last word boundary)
    inside the window instead.
    """
    if len(text) <= limit:
        return text
    window = text[:limit]
    cut = max(window.rfind(". "), window.rfind("! "), window.rfind("? "))
    if cut == -1:
        cut = window.rfind(" ")
    if cut == -1:
        return window
    return window[: cut + 1].rstrip()


_REPEATED_WORD_RE = re.compile(r"\b(\w+)\s+\1\b", re.IGNORECASE)


def _looks_like_valid_answer(text: str) -> bool:
    """Reject obviously degenerate LLM output rather than show it to a user.

    Reasoning models occasionally emit a corrupted first line even with
    chain-of-thought disabled (observed live: "The the way...' followed by
    a stray non-ASCII glyph, on roughly 1 in 4 real NVIDIA NIM calls during
    testing). Never worth surfacing — caller falls back to the deterministic
    template, which is always coherent since it's built directly from the
    same retrieved policy text.
    """
    if len(text) < 40:
        return False
    if _REPEATED_WORD_RE.search(text[:80]):
        return False
    return True


def redact_pii(state: AgentState) -> AgentState:
    """Redact sensitive content before any downstream processing."""
    message = state.get("sanitized_message", "")
    with traced_span(
        "pii_redaction",
        {
            "input.length": len(message),
        },
    ) as span:
        redacted_message = redact(message)
        span.set_attribute("output.preview", safe_preview(redacted_message))
        span.set_attribute("output.length", len(redacted_message))
        return {"sanitized_message": redacted_message}


def detect_injection(state: AgentState) -> AgentState:
    """Flag obvious injection attempts and mark intent as blocked."""
    message = state.get("sanitized_message", "")
    with traced_span(
        "injection_check",
        {
            "input.preview": safe_preview(message),
            "input.length": len(message),
        },
    ) as span:
        suspicious = is_suspicious(message)
        span.set_attribute("output.suspicious", suspicious)
        if suspicious:
            blocked_response_text = "I cannot comply with that request."
            span.set_attribute("output.intent", "blocked")
            span.set_attribute("output.response_preview", safe_preview(blocked_response_text))
            return {
                "intent": "blocked",
                "response": blocked_response_text,
            }
        return {}


_REDACTION_TOKEN_RE = re.compile(r"\[[A-Z_]+_REDACTED\]")


def _strip_redaction_tokens_for_search(text: str) -> str:
    """Drop PII placeholder tokens before they reach an embedding query.

    "[EMAIL_REDACTED]"/"[PHONE_REDACTED]" carry no semantic meaning, but
    they're real tokens that get embedded like any other word - on a short
    message they can measurably dilute similarity to the actual topic
    (observed live: "can you help with VPN?" alone scored 0.88 distance
    against the VPN policy chunk; the same question wrapped around two
    redaction tokens scored 1.22, just over MAX_RELEVANT_DISTANCE, wrongly
    escalating a perfectly answerable question). Only used to build search
    queries (RAG and long-term-memory recall) - the real sanitized_message
    (tokens included) is still what goes into the LLM prompt, the API
    response, and memory storage, since the tokens matter there as a
    visible record that redaction happened.
    """
    return _REDACTION_TOKEN_RE.sub("", text).strip()


def load_session_memory(state: AgentState) -> AgentState:
    """Attach short-term session history (US-008) and long-term user facts (US-009).

    Runs only after guardrails have already cleared the message (see
    _route_after_injection) — memory is context for generation, never an
    input to routing/safety decisions. Long-term recall failures (e.g. a
    fresh checkout with no ChromaDB index yet) are swallowed to an empty
    list rather than breaking the turn — memory is a nice-to-have, never a
    dependency the rest of the graph can fail on (NFR-004).
    """
    session_id = state.get("session_id", "")
    with traced_span("load_session_memory", {"input.session_id": session_id}) as span:
        history = memory.get_history(session_id)
        span.set_attribute("output.pair_count", len(history))

    user_id = state.get("user_id", "")
    message = _strip_redaction_tokens_for_search(state.get("sanitized_message", ""))
    with traced_span("load_long_term_memory", {"input.user_id": user_id}) as lt_span:
        try:
            facts = long_term_memory.recall_facts(user_id, message)
        except Exception as exc:
            facts = []
            lt_span.set_attribute("error.type", exc.__class__.__name__)
        lt_span.set_attribute("output.fact_count", len(facts))

    return {"session_history": history, "user_facts": facts}


_TICKET_ID_RE = re.compile(r"\bTCK-\d+\b", re.IGNORECASE)


def _mentions_create_ticket(message: str) -> bool:
    """True for natural create-ticket phrasing, not just the exact phrase.

    "Create ANOTHER ticket for me" or "open a new ticket" don't contain the
    literal substring "create ticket" (a word sits in between), so the
    original exact-phrase check silently missed them and fell through to a
    generic decline instead of actually creating the ticket - a real gap
    caught live when a user typed exactly that phrasing. Shared by
    classify_intent and execute_tool so they can't drift out of sync.
    """
    if "create ticket" in message or "open ticket" in message:
        return True
    return "ticket" in message and ("create" in message or "new ticket" in message)


_LIST_ALL_TICKETS_PHRASES = (
    "all my ticket",
    "all the ticket",
    "all ticket",
    "list my ticket",
    "my tickets",
    "every ticket",
)


def _mentions_list_all_tickets(message: str) -> bool:
    """True for "what are all my tickets" style requests (no single ticket ID)."""
    return "ticket" in message and any(phrase in message for phrase in _LIST_ALL_TICKETS_PHRASES)


def classify_intent(state: AgentState) -> AgentState:
    """Classify request intent using simple deterministic keyword rules."""
    message = state.get("sanitized_message", "").casefold()
    with traced_span(
        "intent_classification",
        {
            "input.preview": safe_preview(message),
            "input.was_blocked": state.get("intent") == "blocked",
        },
    ) as span:
        if state.get("intent") == "blocked":
            intent: Intent = "blocked"
        elif any(keyword in message for keyword in ("remember that", "remember my", "please remember")):
            intent = "remember_fact"
        elif any(
            # Checked before the "policy" keyword below on purpose - "give me
            # a list of what policy questions I can ask" contains "policy"
            # but is a question about the assistant's own capabilities, not
            # an actual policy lookup. Routing it into RAG retrieval finds no
            # semantic match and wrongly escalates a perfectly normal
            # "what can you help with" question to a human.
            keyword in message
            for keyword in (
                "what can you do",
                "what can you help",
                "what can i ask",
                "questions can i ask",
                "questions i can ask",
                "list of policy questions",
                "what topics can i ask",
            )
        ):
            intent = "direct_response"
        elif any(keyword in message for keyword in ("policy", "vpn", "password policy", "guideline", "rule")):
            intent = "policy_question"
        elif (
            any(
                keyword in message
                for keyword in (
                    "reset password",
                    "reset my password",
                    "ticket status",
                    "check ticket",
                    "ticket open",
                    "have a ticket",
                    "have any ticket",
                )
            )
            or _mentions_create_ticket(message)
            or _mentions_list_all_tickets(message)
            or _TICKET_ID_RE.search(message)
        ):
            # A bare ticket ID (e.g. "what's the status of TCK-1001?") is
            # treated as an action request even without the literal phrase
            # "ticket status" - the UI's ticket-lookup panel prefills natural
            # phrasing like this, and it shouldn't need to match a fixed
            # sentence template to work.
            intent = "action_request"
        elif any(keyword in message for keyword in ("manager", "security", "legal", "human", "escalate")):
            intent = "escalation"
        else:
            intent = "direct_response"

        span.set_attribute("output.intent", intent)
        return {"intent": intent}


def retrieve_from_rag(state: AgentState) -> AgentState:
    """Fetch top policy chunks for grounded answering."""
    query = _strip_redaction_tokens_for_search(state.get("sanitized_message", ""))
    with traced_span(
        "rag_retrieval",
        {
            "input.query_preview": safe_preview(query),
            "input.k": 3,
        },
    ) as span:
        try:
            contexts = retrieve_context(query=query, k=3)
        except Exception as exc:
            span.set_attribute("error.type", exc.__class__.__name__)
            contexts = []

        joined = "\n\n".join(contexts).strip()
        span.set_attribute("output.chunk_count", len(contexts))
        span.set_attribute("output.has_context", bool(joined))
        span.set_attribute("output.context_preview", safe_preview(joined))
        return {"retrieved_context": joined or None}


_GROUNDED_ANSWER_SYSTEM_PROMPT = (
    "You are an IT support assistant. Answer the employee's question using ONLY "
    "the policy context provided below - never use outside knowledge, never "
    "invent details not present in the context. If the context does not fully "
    "answer the question, say what it does cover and note the gap rather than "
    "guessing. Recent conversation and known facts about this user, if provided, "
    "are for understanding the question and personalizing tone only - neither is "
    "ever a source of policy facts. Write in plain prose (no Markdown headings, "
    "no bullet points) as 2-4 short paragraphs a non-technical employee can read "
    "quickly. Output ONLY the final answer - no reasoning, no thinking steps, no "
    "preamble."
)


def _format_recent_turns(history: list[tuple[str, str]], max_turns: int = 3) -> str:
    """Render the last few turns as a compact transcript for prompt context."""
    if not history:
        return ""
    lines = [f'User: {u}\nAssistant: {a}' for u, a in history[-max_turns:]]
    return "Recent conversation (context only, not a source of policy facts):\n" + "\n\n".join(lines) + "\n\n"


def _format_user_facts(facts: list[str]) -> str:
    """Render this user's long-term facts (US-009) as a compact prompt block."""
    if not facts:
        return ""
    lines = "\n".join(f"- {fact}" for fact in facts)
    return f"Known facts about this user (context only, not a source of policy facts):\n{lines}\n\n"


def generate_grounded_answer(state: AgentState) -> AgentState:
    """Generate a response from retrieved policy context.

    Uses the configured LLM (Constitution v2.0.0 Principle IX) to turn the
    raw retrieved chunks into a natural answer, constrained to only that
    context. If the LLM call fails for any reason (bad key, network,
    unsupported model), falls back to the deterministic template built
    directly from the same retrieved text - never fabricates, never blocks
    the response on a provider outage (NFR-004: fail safe).
    """
    context = state.get("retrieved_context") or ""
    with traced_span(
        "final_response_generation",
        {
            "input.mode": "grounded",
            "input.has_context": bool(context),
            "input.context_preview": safe_preview(context),
        },
    ) as span:
        if not context:
            response_text = "I could not find approved policy evidence for this question."
            span.set_attribute("output.response_preview", safe_preview(response_text))
            return {
                "response": response_text,
            }

        cleaned = _strip_markdown_headings(context)
        question = state.get("sanitized_message", "")
        answer_body = _truncate_at_sentence(cleaned, _RESPONSE_CHAR_LIMIT)
        generation_mode = "template_fallback"

        with traced_span("llm_call", {"input.mode": "grounded_answer"}) as llm_span:
            try:
                client = get_llm_client()
                llm_span.set_attribute("output.provider", client.provider)
                llm_span.set_attribute("output.model", client.model)
                recent_turns = _format_recent_turns(state.get("session_history") or [])
                user_facts = _format_user_facts(state.get("user_facts") or [])
                llm_answer = client.generate(
                    system=_GROUNDED_ANSWER_SYSTEM_PROMPT,
                    user=f"{user_facts}{recent_turns}Policy context:\n{cleaned}\n\nEmployee question:\n{question}",
                )
                if llm_answer and _looks_like_valid_answer(llm_answer):
                    answer_body = llm_answer
                    generation_mode = "llm"
                    llm_span.set_attribute("output.status", "success")
                else:
                    llm_span.set_attribute(
                        "output.status", "empty_response" if not llm_answer else "rejected_degenerate_output"
                    )
            except Exception as exc:
                llm_span.set_attribute("output.status", "failed")
                llm_span.set_attribute("error.type", exc.__class__.__name__)

        response = f"Based on policy documents, here is the grounded guidance:\n\n{answer_body}"
        span.set_attribute("output.generation_mode", generation_mode)
        span.set_attribute("output.response_preview", safe_preview(response))
        span.set_attribute("output.response_length", len(response))
        return {"response": response}


def _describe_tool_result(tool_name: str, result: dict[str, Any]) -> str:
    """Build a short, human-readable sentence for a tool result.

    Never hand the raw result dict to the user directly (FR-008 / forbidden
    pattern: "exposing raw JSON ... to end users") — this is the only place
    that turns a tool result into chat text.
    """
    if tool_name == "get_ticket_status":
        if result.get("found"):
            title_part = f" ('{result.get('title')}')" if result.get("title") else ""
            return (
                f"Ticket {result.get('ticket_id')}{title_part} is currently '{result.get('status')}' "
                f"(queue: {result.get('assigned_queue') or 'n/a'})."
            )
        return f"I could not find ticket {result.get('ticket_id')}."
    if tool_name == "request_password_reset":
        return f"Password reset request: {result.get('status')}. {result.get('next_action', '')}".strip()
    if tool_name == "create_ticket":
        if result.get("status") == "created":
            return f"Created ticket {result.get('ticket_id')}. {result.get('message', '')}".strip()
        return f"Could not create the ticket: {result.get('message', '')}".strip()
    return result.get("next_action") or "I don't have an automated action for that request."


_TICKET_MODIFY_VERBS = ("complete", "close", "finish", "resolve", "cancel")


def _describe_all_tickets(tickets: list[dict[str, Any]]) -> str:
    """Build a short spoken summary of every ticket owned by this user."""
    if not tickets:
        return "You don't have any tickets on file."
    lines = [f"{t.get('ticket_id')} ('{t.get('title')}') - {t.get('status')}" for t in tickets]
    return "Here are all your tickets: " + "; ".join(lines) + "."


_TICKET_CATEGORY_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("network", ("vpn", "wifi", "wi-fi", "network", "internet", "connect")),
    ("hardware", ("laptop", "monitor", "keyboard", "mouse", "printer", "hardware", "device", "battery", "boot")),
    ("software", ("software", "install", "license", "application", "app ", "update")),
    ("security", ("password", "login", "log in", "account", "locked", "access", "credential", "mfa", "2fa")),
)


def _categorize_ticket(description: str) -> str:
    """Deterministic keyword-based category guess for a new ticket.

    Same philosophy as classify_intent - simple, explainable rules rather
    than an LLM call for something this low-stakes. A wrong guess here just
    means a slightly mis-routed queue for a human triager to correct, never
    a safety-relevant decision, so it doesn't need the LLM's judgment.
    """
    lower = description.casefold()
    for category, keywords in _TICKET_CATEGORY_KEYWORDS:
        if any(keyword in lower for keyword in keywords):
            return category
    return "general"


_TICKET_TITLE_PREFIX_RE = re.compile(
    r"^(create|open|raise|log|file|submit)\s+(a\s+|another\s+|a\s+new\s+|new\s+)?ticket\s*(for\s+me)?[:,\-]?\s*",
    re.IGNORECASE,
)


def _extract_ticket_title(message: str) -> str:
    """Turn the raw request into a real ticket title instead of a generic one.

    Every auto-created ticket used to get the exact same placeholder title
    ("User-created support request") regardless of what was actually wrong -
    directly the thing flagged in early feedback ("I don't know what sort of
    problem they were dealing with"). Strips the trigger phrase and keeps
    the actual issue description, same idea as _extract_fact_text.
    """
    stripped = _TICKET_TITLE_PREFIX_RE.sub("", message).strip()
    if not stripped:
        # The message was just the trigger phrase itself ("create ticket",
        # nothing else) - falling back to the raw message here would just
        # put the literal words "create ticket" back as the title.
        return "User-created support request"
    if len(stripped) > 80:
        stripped = stripped[:80].rstrip() + "..."
    return stripped[0].upper() + stripped[1:]


def execute_tool(state: AgentState) -> AgentState:
    """Execute a basic tool action based on user request patterns."""
    message = state.get("sanitized_message", "")
    message_lower = message.casefold()
    with traced_span(
        "tool_call",
        {
            "input.message_preview": safe_preview(message),
        },
    ) as span:
        result: dict[str, Any] | list[dict[str, Any]] | None
        ticket_match = _TICKET_ID_RE.search(message)
        if ticket_match is None and _mentions_list_all_tickets(message_lower):
            tool_name = "list_tickets_for_user"
            tickets = [
                t.model_dump(mode="json") for t in list_tickets_for_user(state.get("user_id", ""))
            ]
            result = tickets
            response_text = _describe_all_tickets(tickets)
        elif (
            "ticket status" in message_lower
            or "check ticket" in message_lower
            or "ticket open" in message_lower
            or "have a ticket" in message_lower
            or "have any ticket" in message_lower
            or ticket_match
        ):
            tool_name = "get_ticket_status"
            if ticket_match is None:
                result = None
                response_text = "Please provide a ticket ID (e.g. TCK-1001) so I can look up its status."
            else:
                ticket_id = ticket_match.group(0).upper()
                owner = get_ticket_owner(ticket_id)
                requesting_user = state.get("user_id", "")
                # An employee-facing agent should only surface *your own*
                # tickets by ID - without this, anyone could enumerate any
                # TCK-#### and read another employee's ticket details.
                # owner is None for a genuinely nonexistent ID, which falls
                # through to get_ticket_status's normal not-found response
                # instead of a denial (no reason to distinguish the two).
                if owner is not None and owner != requesting_user:
                    result = None
                    response_text = (
                        f"I can only share ticket details for your own account. "
                        f"{ticket_id} isn't associated with your account."
                    )
                else:
                    result = get_ticket_status(ticket_id).model_dump(mode="json")
                    if any(verb in message_lower for verb in _TICKET_MODIFY_VERBS):
                        # They asked to close/finish/resolve it, not just
                        # check it - silently answering with only the status
                        # (as the old code did) reads like the request was
                        # carried out when nothing actually happened to the
                        # ticket. Say so plainly instead of leaving it
                        # ambiguous, but still surface the real status since
                        # that's genuinely useful context.
                        response_text = (
                            "I can check ticket status, but I can't close, complete, or resolve "
                            f"a ticket myself - a human agent handles that. {_describe_tool_result(tool_name, result)}"
                        )
                    else:
                        response_text = _describe_tool_result(tool_name, result)
        elif "reset password" in message_lower or "reset my password" in message_lower:
            tool_name = "request_password_reset"
            result = request_password_reset(user_id=state.get("user_id", "unknown"), reason=message)
            response_text = _describe_tool_result(tool_name, result)
        elif _mentions_create_ticket(message_lower):
            tool_name = "create_ticket"
            category = _categorize_ticket(message)
            result = create_ticket(
                tenant_id="default-tenant",
                requester_user_id=state.get("user_id", "unknown"),
                title=_extract_ticket_title(message),
                description=(message + " Additional details pending triage.")[:300],
                category=category,
                priority="medium",
            )
            if result.get("status") == "created":
                response_text = (
                    f"Created ticket {result.get('ticket_id')} in the '{category}' category. "
                    f"{result.get('message', '')}"
                ).strip()
            else:
                response_text = _describe_tool_result(tool_name, result)
        else:
            tool_name = "none"
            result = {
                "status": "unsupported",
                "next_action": "Escalate to human support for manual handling.",
            }
            response_text = _describe_tool_result(tool_name, result)

        span.set_attribute("output.tool_name", tool_name)
        span.set_attribute(
            "output.status",
            result.get("status", "unknown") if isinstance(result, dict) else "unknown",
        )
        span.set_attribute("output.result_preview", safe_preview(result))

        return {
            "tool_result": result,
            "response": response_text,
        }


_REMEMBER_TRIGGER_RE = re.compile(
    r"^(please\s+)?remember\s+(that|my)?\s*", re.IGNORECASE
)


def _extract_fact_text(message: str) -> str:
    """Strip the trigger phrase itself before storing, keeping just the fact.

    "Remember that I work from the London office" stored verbatim embeds
    the noise words "Remember that" right alongside the actual fact,
    measurably hurting later similarity search (observed live: this alone
    was enough to push a genuinely relevant recall query from ~1.5 to 1.78
    distance, past the relevance cutoff). Falls back to the full message if
    stripping would leave nothing.
    """
    stripped = _REMEMBER_TRIGGER_RE.sub("", message).strip()
    return stripped or message.strip()


def remember_fact(state: AgentState) -> AgentState:
    """Store a user-stated fact in per-user long-term memory (US-009).

    Deterministic trigger only ("remember that ..." in classify_intent) -
    the graph never decides on its own what's worth remembering; the user
    always has to say so explicitly (Constitution Principle IV).
    """
    user_id = state.get("user_id", "")
    fact = _extract_fact_text(state.get("sanitized_message", ""))
    with traced_span(
        "remember_fact",
        {"input.user_id": user_id, "input.fact_preview": safe_preview(fact)},
    ) as span:
        try:
            long_term_memory.remember_fact(user_id, fact)
            span.set_attribute("output.status", "stored")
            response_text = "Got it — I'll remember that for future conversations."
        except Exception as exc:
            span.set_attribute("output.status", "failed")
            span.set_attribute("error.type", exc.__class__.__name__)
            response_text = "I couldn't save that right now, but you're welcome to try again."
        return {"response": response_text}


# Mirrors frontend/app.py's EMPLOYEE_ROSTER (first names only, for a warm
# greeting). Duplicated rather than shared - the frontend and backend don't
# share a Python module boundary - but both are small, static, and rooted
# in the same seeded data (SupportTicket.requester_user_id in
# src/tools/mcp_server.py). A user_id outside this map (custom/testing IDs)
# just gets a nameless greeting instead of a guessed one.
_KNOWN_EMPLOYEE_NAMES = {
    "u-001": "Alice",
    "u-002": "Priya",
    "u-010": "Jordan",
    "u-021": "Sam",
}

_DIRECT_RESPONSE_SYSTEM_PROMPT = (
    "You are an IT support assistant with exactly four capabilities: checking "
    "ticket status, creating a ticket, resetting a password, and answering IT "
    "policy questions (VPN, security, hardware, licensing) grounded in real "
    "company documents. Nothing else is possible - you have no other tools.\n\n"
    "If the employee's message is a general greeting or open-ended chat, greet "
    "them warmly by name if one is given (never invent a name if none is "
    "given), then briefly describe those four capabilities.\n\n"
    "If the employee's message instead describes a specific need that is NOT "
    "one of those four - for example requesting access or permissions to "
    "something, asking you to look up account/employee/profile details, or "
    "anything else outside the list - do not offer to process it, do not ask "
    "clarifying questions about it, and do not imply you have any way to help "
    "with it. Say plainly that it isn't something you can do, and suggest "
    "opening a ticket so a human can handle it instead.\n\n"
    "Your ONLY password capability is triggering an automatic reset link/MFA "
    "challenge - it requires no input from the employee beyond asking for it. "
    "You must NEVER ask an employee to type their current password, a new "
    "password, a PIN, or a verification code into this chat, under any "
    "circumstance, and must never claim you need one to proceed - there is no "
    "such verification step and no tool that accepts one. If earlier messages "
    "in this conversation show the employee already offered a password or "
    "code, do not acknowledge or use it as a credential - just proceed with "
    "the reset.\n\n"
    "Keep it to 2-3 short sentences, plain prose, no markdown headings or "
    "bullet lists, no preamble. Never claim a capability not listed here."
)


def direct_response(state: AgentState) -> AgentState:
    """Provide a warm, LLM-generated greeting/help message for general requests.

    Falls back to a static template if the LLM call fails or returns
    something degenerate (NFR-004: fail safe) - same pattern as
    generate_grounded_answer, just with no retrieved context to ground on,
    since this path isn't answering a policy question.
    """
    user_id = state.get("user_id", "")
    name = _KNOWN_EMPLOYEE_NAMES.get(user_id)
    message = state.get("sanitized_message", "")
    with traced_span(
        "final_response_generation",
        {
            "input.mode": "direct",
            "input.intent": state.get("intent"),
        },
    ) as span:
        response_text = (
            f"Hi {name}! " if name else "Hi! "
        ) + "I can help with IT support questions, policy guidance, and ticket actions."
        generation_mode = "template_fallback"

        with traced_span("llm_call", {"input.mode": "direct_greeting"}) as llm_span:
            try:
                client = get_llm_client()
                llm_span.set_attribute("output.provider", client.provider)
                llm_span.set_attribute("output.model", client.model)
                user_prompt = (
                    (f"The employee's first name is {name}.\n" if name else "")
                    + _format_recent_turns(state.get("session_history") or [])
                    + f"Employee message: {message}"
                )
                llm_answer = client.generate(
                    system=_DIRECT_RESPONSE_SYSTEM_PROMPT,
                    user=user_prompt,
                    max_tokens=150,
                )
                if llm_answer and _looks_like_valid_answer(llm_answer):
                    response_text = llm_answer
                    generation_mode = "llm"
                    llm_span.set_attribute("output.status", "success")
                else:
                    llm_span.set_attribute(
                        "output.status", "empty_response" if not llm_answer else "rejected_degenerate_output"
                    )
            except Exception as exc:
                llm_span.set_attribute("output.status", "failed")
                llm_span.set_attribute("error.type", exc.__class__.__name__)

        span.set_attribute("output.generation_mode", generation_mode)
        span.set_attribute("output.response_preview", safe_preview(response_text))
        return {
            "response": response_text,
        }


def blocked_response(state: AgentState) -> AgentState:
    """Return safe refusal when content is unsafe or policy-blocked."""
    with traced_span(
        "final_response_generation",
        {
            "input.mode": "blocked",
            "input.intent": state.get("intent"),
        },
    ) as span:
        response_text = "I cannot help with that request. Please ask a safe IT support question."
        span.set_attribute("output.response_preview", safe_preview(response_text))
        return {
            "intent": "blocked",
            "response": response_text,
        }


def escalate(state: AgentState) -> AgentState:
    """Escalate requests that need human intervention."""
    with traced_span(
        "final_response_generation",
        {
            "input.mode": "escalation",
            "input.intent": state.get("intent"),
        },
    ) as span:
        response_text = "I am escalating this to a human IT support specialist."
        span.set_attribute("output.response_preview", safe_preview(response_text))
        return {
            "intent": "escalation",
            "response": response_text,
        }


def update_memory(state: AgentState) -> AgentState:
    """Persist this turn into session memory and finalize terminal outputs.

    Blocked requests are deliberately NOT written to memory - an injection
    attempt shouldn't become "recent conversation" context for the next
    turn's grounded answer.
    """
    response_text = state.get("response") or ""
    if state.get("intent") != "blocked":
        memory.append_turn(
            state.get("session_id", ""),
            state.get("sanitized_message", ""),
            response_text,
        )
    return {
        "tool_result": state.get("tool_result"),
        "response": response_text,
    }


def _route_after_injection(state: AgentState) -> Literal["blocked_response", "load_session_memory"]:
    """Bypass memory/classification when injection was detected."""
    if state.get("intent") == "blocked":
        return "blocked_response"
    return "load_session_memory"


def _route_after_classify(
    state: AgentState,
) -> Literal[
    "retrieve_from_rag",
    "execute_tool",
    "direct_response",
    "blocked_response",
    "escalate",
    "remember_fact",
]:
    """Route by classified intent."""
    intent = state.get("intent")
    if intent == "policy_question":
        return "retrieve_from_rag"
    if intent == "action_request":
        return "execute_tool"
    if intent == "escalation":
        return "escalate"
    if intent == "blocked":
        return "blocked_response"
    if intent == "remember_fact":
        return "remember_fact"
    return "direct_response"


def _route_after_retrieval(state: AgentState) -> Literal["generate_grounded_answer", "direct_response"]:
    """Decline gracefully, not escalate, when no grounding evidence exists.

    A question that merely isn't covered by any policy document (weather,
    Mars mining policy, ...) isn't the same situation as someone explicitly
    asking for a manager/human (see classify_intent's "escalation" intent,
    routed to `escalate` directly) - it doesn't need a real person's time,
    it just needs an honest "that's not something I can help with." Reusing
    direct_response gives it the same LLM-generated, capability-aware
    decline already used for off-topic direct messages, instead of a
    separate "escalating to a human" message for what's really the same
    situation.
    """
    if state.get("retrieved_context"):
        return "generate_grounded_answer"
    return "direct_response"


def build_graph():
    """Build and compile the LangGraph workflow."""
    graph = StateGraph(AgentState)

    graph.add_node("redact_pii", redact_pii)
    graph.add_node("detect_injection", detect_injection)
    graph.add_node("load_session_memory", load_session_memory)
    graph.add_node("classify_intent", classify_intent)
    graph.add_node("retrieve_from_rag", retrieve_from_rag)
    graph.add_node("generate_grounded_answer", generate_grounded_answer)
    graph.add_node("execute_tool", execute_tool)
    graph.add_node("remember_fact", remember_fact)
    graph.add_node("direct_response", direct_response)
    graph.add_node("blocked_response", blocked_response)
    graph.add_node("escalate", escalate)
    graph.add_node("update_memory", update_memory)

    graph.add_edge(START, "redact_pii")
    graph.add_edge("redact_pii", "detect_injection")
    graph.add_conditional_edges(
        "detect_injection",
        _route_after_injection,
        {
            "blocked_response": "blocked_response",
            "load_session_memory": "load_session_memory",
        },
    )
    graph.add_edge("load_session_memory", "classify_intent")

    graph.add_conditional_edges(
        "classify_intent",
        _route_after_classify,
        {
            "retrieve_from_rag": "retrieve_from_rag",
            "execute_tool": "execute_tool",
            "direct_response": "direct_response",
            "blocked_response": "blocked_response",
            "escalate": "escalate",
            "remember_fact": "remember_fact",
        },
    )

    graph.add_conditional_edges(
        "retrieve_from_rag",
        _route_after_retrieval,
        {
            "generate_grounded_answer": "generate_grounded_answer",
            "direct_response": "direct_response",
        },
    )

    graph.add_edge("generate_grounded_answer", "update_memory")
    graph.add_edge("execute_tool", "update_memory")
    graph.add_edge("remember_fact", "update_memory")
    graph.add_edge("direct_response", "update_memory")
    graph.add_edge("blocked_response", "update_memory")
    graph.add_edge("escalate", "update_memory")
    graph.add_edge("update_memory", END)

    return graph.compile()


agent_graph = build_graph()
