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
from src.tools.mcp_server import create_ticket, get_ticket_status, request_password_reset

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
    message = state.get("sanitized_message", "")
    with traced_span("load_long_term_memory", {"input.user_id": user_id}) as lt_span:
        try:
            facts = long_term_memory.recall_facts(user_id, message)
        except Exception as exc:
            facts = []
            lt_span.set_attribute("error.type", exc.__class__.__name__)
        lt_span.set_attribute("output.fact_count", len(facts))

    return {"session_history": history, "user_facts": facts}


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
        elif any(keyword in message for keyword in ("policy", "vpn", "password policy", "guideline", "rule")):
            intent = "policy_question"
        elif any(keyword in message for keyword in ("reset password", "ticket status", "create ticket", "open ticket")):
            intent = "action_request"
        elif any(keyword in message for keyword in ("manager", "security", "legal", "human", "escalate")):
            intent = "escalation"
        else:
            intent = "direct_response"

        span.set_attribute("output.intent", intent)
        return {"intent": intent}


def retrieve_from_rag(state: AgentState) -> AgentState:
    """Fetch top policy chunks for grounded answering."""
    query = state.get("sanitized_message", "")
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


_TICKET_ID_RE = re.compile(r"\bTCK-\d+\b", re.IGNORECASE)


def _describe_tool_result(tool_name: str, result: dict[str, Any]) -> str:
    """Build a short, human-readable sentence for a tool result.

    Never hand the raw result dict to the user directly (FR-008 / forbidden
    pattern: "exposing raw JSON ... to end users") — this is the only place
    that turns a tool result into chat text.
    """
    if tool_name == "get_ticket_status":
        if result.get("found"):
            return (
                f"Ticket {result.get('ticket_id')} is currently '{result.get('status')}' "
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
        result: dict[str, Any] | None
        if "ticket status" in message_lower:
            tool_name = "get_ticket_status"
            ticket_match = _TICKET_ID_RE.search(message)
            if ticket_match is None:
                result = None
                response_text = "Please provide a ticket ID (e.g. TCK-1001) so I can look up its status."
            else:
                result = get_ticket_status(ticket_match.group(0).upper()).model_dump(mode="json")
                response_text = _describe_tool_result(tool_name, result)
        elif "reset password" in message_lower:
            tool_name = "request_password_reset"
            result = request_password_reset(user_id=state.get("user_id", "unknown"), reason=message)
            response_text = _describe_tool_result(tool_name, result)
        elif "create ticket" in message_lower or "open ticket" in message_lower:
            tool_name = "create_ticket"
            result = create_ticket(
                tenant_id="default-tenant",
                requester_user_id=state.get("user_id", "unknown"),
                title="User-created support request",
                description=(message + " Additional details pending triage.")[:300],
                category="general",
                priority="medium",
            )
            response_text = _describe_tool_result(tool_name, result)
        else:
            tool_name = "none"
            result = {
                "status": "unsupported",
                "next_action": "Escalate to human support for manual handling.",
            }
            response_text = _describe_tool_result(tool_name, result)

        span.set_attribute("output.tool_name", tool_name)
        span.set_attribute("output.status", result.get("status", "unknown") if isinstance(result, dict) else "unknown")
        span.set_attribute("output.result_preview", safe_preview(result))

        return {
            "tool_result": result,
            "response": response_text,
        }


def remember_fact(state: AgentState) -> AgentState:
    """Store a user-stated fact in per-user long-term memory (US-009).

    Deterministic trigger only ("remember that ..." in classify_intent) -
    the graph never decides on its own what's worth remembering; the user
    always has to say so explicitly (Constitution Principle IV).
    """
    user_id = state.get("user_id", "")
    fact = state.get("sanitized_message", "")
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


def direct_response(state: AgentState) -> AgentState:
    """Provide a non-tool direct response for general requests."""
    with traced_span(
        "final_response_generation",
        {
            "input.mode": "direct",
            "input.intent": state.get("intent"),
        },
    ) as span:
        response_text = "I can help with IT support questions, policy guidance, and ticket actions."
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


def _route_after_retrieval(state: AgentState) -> Literal["generate_grounded_answer", "escalate"]:
    """Escalate when no grounding evidence is available."""
    if state.get("retrieved_context"):
        return "generate_grounded_answer"
    return "escalate"


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
            "escalate": "escalate",
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
