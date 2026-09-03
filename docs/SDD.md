# Software Design Document — IT Support Ticketing System

**Status**: describes the system as actually built and verified, 2026-09-04. Governed by `.specify/memory/constitution.md` v2.0.0. Full requirement traceability lives in `specs/001-it-support-ticketing-system/spec.md` (user stories, FR/NFR IDs); this document is the design-level companion — how those requirements are met in code.

## 1. Overview

An IT support chat agent: an employee asks a question or requests an action in a Streamlit chat UI, a FastAPI backend runs the request through a LangGraph-orchestrated pipeline (redaction → injection guard → session memory → intent routing → RAG / tool / direct / escalate → response), and the result renders back as either a grounded text answer or a colored tool-result card. See `docs/architecture.md` for the rendered diagrams (`docs/architecture.png`, `docs/langgraph_state.png`).

## 2. Component Design

| Component | File | Responsibility |
|---|---|---|
| Chat UI | `frontend/app.py` | Streamlit chat window, tool-result cards, sidebar (user/session ID, trace viewer link) |
| API Gateway | `src/api/main.py` | `POST /chat`, `GET /health`, `GET /tickets/{id}`; loads `.env` at startup |
| PII Redaction | `src/security/pii_redaction.py` | Regex-based scrub of email/phone/etc. before anything else touches the message |
| Injection Guard | `src/security/injection_guard.py` | Keyword/pattern check for prompt-injection and jailbreak attempts |
| Session Memory | `src/agent/memory.py` | Process-local 6-turn sliding window per `session_id` |
| Orchestrator | `src/agent/graph.py` | LangGraph `StateGraph` wiring every node below into one workflow |
| RAG Retriever | `src/rag/retrieve.py`, `src/rag/ingest.py` | ChromaDB similarity search over `data/policies/*.md` with a relevance-distance cutoff |
| Tools | `src/tools/mcp_server.py` | FastMCP tools: `get_ticket_status`, `request_password_reset`, `create_ticket` |
| LLM Client | `src/llm/client.py` | Provider-agnostic wrapper (`LLMClient`/`get_llm_client()`); NVIDIA NIM (Nemotron) implemented, Gemini/OpenAI adapters spec'd |
| Schemas | `src/schemas/models.py` | Pydantic v2 models for every request/response/tool payload; `AgentState` TypedDict for graph state |
| Tracing | `src/observability/tracing.py` | Arize Phoenix spans per node, batched/non-blocking export, fails safe with no collector running |

## 3. Data Model

Defined in `src/schemas/models.py` (Pydantic v2, `extra="forbid"` on every model — unexpected fields are rejected, not silently dropped):

- **`SupportTicket`** — `ticket_id`, `tenant_id`, `requester_user_id`, `title`, `description`, `category`, `priority` (`TicketPriority`: low/medium/high/critical), `status` (`TicketStatus`: open/in_progress/waiting_user/resolved/closed), `assigned_queue`, `escalation_level`, `created_at`, `updated_at`.
- **`ChatMessage`** — `message_id`, `ticket_id`, `tenant_id`, `role` (`ChatRole`: user/assistant/tool/system), `content`, `citations`, `tool_call_id`, `redaction_applied`, `injection_screened`, `created_at`.
- **`ChatRequest`** (API input) — `user_id`, `session_id`, `user_message` (1-6000 chars, blank rejected).
- **`KnowledgeChunk`** — `chunk_id`, `tenant_id`, `source_doc_id`, `source_title`, `content`, `embedding_vector_ref`, `policy_tags` (non-empty), `active`, `revision`, `updated_at`.
- **`MemoryRecord`** — `memory_id`, `tenant_id`, `ticket_id`, `memory_scope` (`MemoryScope`: ephemeral/session/ticket), `key`, `value`, `expires_at`, `created_at`. (Schema exists for the long-term-memory design; only the session-scoped path is implemented today — see §7.)
- **Tool I/O**: `TicketLookupRequest` → `TicketStatusResponse`; `PasswordResetRequest` → `PasswordResetResult`; `TicketCreateRequest` → `TicketCreateResult`.
- **`AgentState`** (internal, `TypedDict`, not a wire schema) — `user_id`, `session_id`, `sanitized_message`, `intent`, `retrieved_context`, `tool_result`, `response`, `session_history`.

All string fields use `field_validator`s to strip whitespace and reject blank-only values before any downstream logic sees them.

## 4. API Contract

### `GET /health`
Returns `{"status": "ok", "version": "0.1.0", "nvidia_nim_key_configured": bool}`. The last field is a presence check only — it never returns the key value — used to confirm `.env` was actually loaded.

### `GET /tickets/{ticket_id}`
Thin wrapper over the `get_ticket_status` tool; returns `TicketStatusResponse` (`found=false` + `error_code="ERR-NOT-FOUND"` for an unknown ID, never a 500 or a guess).

### `POST /chat`
Request: `ChatRequest` (`user_id`, `session_id`, `user_message`). A blank `user_message` is rejected with HTTP 422 by Pydantic before the graph ever runs.

Response:
```json
{
  "response": "string",
  "intent": "policy_question | action_request | escalation | blocked | direct_response",
  "tool_result": { "...": "structured dict, or null" },
  "ticket": { "ticket_id": "...", "status": "...", "message": "..." },
  "sanitized_message": "string with PII already redacted"
}
```
`tool_result` is always real structured data (never a stringified dict) so the frontend can render a typed card directly.

## 5. LangGraph Workflow

Nodes run in this order (see `docs/langgraph_state.png` for the full branch diagram):

1. `redact_pii` — strips PII from the raw message; always runs first, no exceptions (Constitution Principle III).
2. `detect_injection` — flags prompt-injection/jailbreak patterns → routes straight to `blocked_response`, skipping every other node (an injection attempt never reaches the LLM, RAG, or a tool).
3. `load_session_memory` — loads this session's last 6 turns from `src/agent/memory.py` (only reached on the safe path).
4. `classify_intent` — deterministic keyword rules (Constitution Principle IV: routing runs before any model call, not after).
5. Branch by intent:
   - `policy_question` → `retrieve_from_rag` → (context found) `generate_grounded_answer`, or (no context) `escalate`.
   - `action_request` → `execute_tool`.
   - `escalation` → `escalate`.
   - `direct_response` (default) → `direct_response`.
6. `update_memory` — appends the turn to session memory (skipped for blocked turns, so injection attempts never pollute future context), then `END`.

`generate_grounded_answer` is the only node that calls an LLM (NVIDIA NIM/Nemotron via `src/llm/client.py`), and only after RAG has already retrieved and relevance-filtered the policy context — the model's job is strictly "phrase this retrieved text," never "answer from general knowledge." On any API failure or a degenerate/garbled response (`_looks_like_valid_answer()` check in `graph.py`), it silently falls back to the deterministic template built from the same retrieved text, so a bad model sample can never surface as a worse answer than the non-LLM baseline.

## 6. Security & Guardrails Design

- **PII redaction** runs before intent classification, tool execution, or any model call — the graph has no path that skips it.
- **Injection detection** short-circuits the entire remaining pipeline on a match; the frontend and API both surface a fixed refusal string, never the injected instruction or any internal state.
- **RAG grounding cutoff**: `MAX_RELEVANT_DISTANCE = 1.2` in `src/rag/retrieve.py` — chunks past this ChromaDB distance are dropped, so an off-topic question (no relevant policy in the corpus) escalates instead of confidently answering from the nearest-but-wrong document.
- **Tool validation**: every tool input/output is a Pydantic model with `extra="forbid"`; malformed input returns a structured rejection, never a stack trace.
- **Secrets**: `.env` (holding `NVIDIA_NIM_API_KEY`) is git-ignored; `/health` exposes only a boolean presence check, never the value.

## 7. Observability

`src/observability/tracing.py` wraps every graph node in a named Phoenix span (`pii_redaction`, `injection_check`, `load_session_memory`, `rag_retrieval`, `llm_call`, etc.) via `register(batch=True, verbose=False)` — batched export so tracing latency never blocks a response, and if no Phoenix collector is running the app degrades silently (NFR-004: fail safe) instead of erroring.

## 8. Known Deviations From the Original Spec Documents

Documented per Constitution Principle X (Honest Documentation) — nothing below is hidden, all of it is either an explicit, justified architecture decision or an acknowledged gap:

| Area | Original spec | What's actually built | Why |
|---|---|---|---|
| Frontend | React + TypeScript (NFR-002) | Streamlit (`frontend/app.py`) | The spec's own Scope §4.1 explicitly names "React/streamlit" as acceptable; ratified in Constitution v2.0.0 Principle VIII |
| Response transport | Server-Sent Events (FR-007) | REST request/response | Simpler, sufficient for demo scope; SSE left as an optional enhancement, not required |
| Multi-tenancy | `specs/.../data-model.md` and `contracts/rag-and-tools.md` describe a `tenant_id`-scoped, multi-tenant design (`kb_{tenant}_{domain}_{version}` collections, `lookup_kb_article`/`reset_password_request`/`create_escalation_ticket` tool names, `ERR-ACL-001` tenant-mismatch failure mode) | Single-tenant: one ChromaDB collection (`it_policy_docs`), tools named `get_ticket_status`/`request_password_reset`/`create_ticket`, no tenant filter enforced | Those two spec files describe an aspirational enterprise design that was written but never implemented for this capstone's scope — flagged here rather than silently diverging. `SupportTicket` still carries a `tenant_id` field for forward compatibility, but nothing reads or filters on it today. |
| Long-term memory (US-009) | Per-user memory persisted across sessions | Not built — only session-scoped memory (`src/agent/memory.py`, in-process, cleared on restart) exists | Open item, tracked in `docs/roadmap.md` Checkpoint 4b |
| External search tool (US-015) | `search_external_knowledge` (Google/Wikipedia) | Not built — no-context questions escalate instead | Open item, tracked in `docs/roadmap.md` Checkpoint 3 |
| LLM providers | Provider-agnostic (NVIDIA NIM/Gemini/OpenAI) | NVIDIA NIM (Nemotron) only; `LLMClient` interface is provider-agnostic but only one adapter exists | Open item, tracked in `docs/roadmap.md` Checkpoint 2 |
| Test coverage (NFR-008) | Unit tests across guardrails, tools, routing, RAG, schemas | Only `tests/test_pii_redaction.py` exists | Open item, tracked in `docs/roadmap.md` Checkpoint 5 |

## 9. References

- Requirements & acceptance criteria: `specs/001-it-support-ticketing-system/spec.md`
- Technical plan: `specs/001-it-support-ticketing-system/plan.md`
- Aspirational (not fully built) data/contract design: `specs/001-it-support-ticketing-system/data-model.md`, `specs/001-it-support-ticketing-system/contracts/`
- Diagrams: `docs/architecture.md` (source), `docs/architecture.png`, `docs/langgraph_state.png`
- Build status and open work: `docs/roadmap.md`
- Demo walkthrough: `docs/demo_script.md`
- Evaluation results: `eval/promptfooconfig.yaml`, `eval/results.json`
