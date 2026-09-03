# Feature Specification: IT Support Ticketing System

**Feature Branch**: `001-it-support-ticketing-system`

**Created**: 2026-08-27

**Status**: Draft

**Input**: User description: "IT Support Ticketing System with policy-grounded RAG, secure FastMCP tooling, PII redaction, prompt injection defense, LangGraph orchestration, Phoenix observability, Promptfoo evaluation, and streaming React UX with tool cards."
_(Historical input record. Superseded per Constitution v2.0.0 (2026-09-02): UI is Streamlit over REST, not React/SSE — see Constitution Alignment above, US-002, and FR-019.)_

## Constitution Alignment

This specification is governed by `.specify/memory/constitution.md` version 2.0.0.

Priority alignment:
1. Policy-grounded RAG answers
2. Secure FastMCP tool execution (ticketing tools and external Google/Wikipedia search tool)
3. PII redaction before LLM prompts
4. Prompt injection resistance
5. LangGraph stateful routing
6. Arize Phoenix observability
7. Promptfoo evaluation gates
8. Streamlit UI with tool cards (REST transport)
9. Provider-agnostic LLM invocation (NVIDIA NIM / Gemini / OpenAI)
10. Honest Copilot documentation

## User Scenarios and Testing (Mandatory)

### US-001 - Create Ticket and Receive AI First Reply (Priority: P1)
As an employee, I want to create an IT ticket and receive an immediate safe AI first reply.

**Why this priority**: Core business value and shortest path to reduced response time.

**Independent Test**: Submit valid and invalid ticket payloads and verify creation + reply behavior.

**Acceptance Criteria**:
- AC-001-01 (positive) Given an authenticated tenant user, when a valid ticket is submitted, then a ticket ID is created with status `open`.
- AC-001-02 (positive) Given created ticket context, when first-reply workflow completes, then response is persisted with timestamps.
- AC-001-03 (negative) Given missing required fields, when submit is attempted, then request fails with `ERR-VAL-001`.
- AC-001-04 (negative) Given model timeout, when reply generation exceeds limits, then user receives fallback and `ERR-AI-001` is recorded.

### US-002 - Render Assistant Responses and Tool Cards (Priority: P1)
As an employee, I want a clear final response and structured tool cards so I can understand what the assistant did, using a simple Streamlit chat UI over REST.

**Why this priority**: Transparency improves trust and reduces duplicate user actions.

**Independent Test**: Submit a chat request via `POST /chat` and validate the JSON response renders as chat text plus, when applicable, a structured tool card in the Streamlit UI.

**Acceptance Criteria**:
- AC-002-01 (positive) Given an active chat request, when the backend finishes processing, then the full response is returned in one JSON payload (incremental/SSE delivery is an optional future enhancement, not required).
- AC-002-02 (positive) Given a tool invocation, when the tool call completes, then the response includes a structured tool result the UI renders as a card.
- AC-002-03 (negative) Given tool failure, when the response is rendered, then the tool card shows failed state with fallback guidance, never a raw stack trace.
- AC-002-04 (negative) Given the backend is unreachable, when the Streamlit UI submits a request, then a safe connection-error message is shown with `ERR-UPSTREAM-001`.

### US-003 - Policy-Grounded RAG Answers (Priority: P1)
As an employee, I want answers grounded in approved knowledge and policy constraints.

**Why this priority**: Reduces hallucinations and enforces compliance.

**Independent Test**: Ask policy and troubleshooting questions against seeded tenant knowledge.

**Acceptance Criteria**:
- AC-003-01 (positive) Given matching tenant KB content, when response is generated, then at least one citation is returned.
- AC-003-02 (positive) Given policy-labeled content, when retrieval runs, then only allowed chunks are used.
- AC-003-03 (negative) Given no evidence, when retrieval returns empty, then system returns no-evidence fallback with `ERR-RAG-001`.
- AC-003-04 (negative) Given unsupported claim request, when answer is generated, then assistant refuses unsupported certainty.

### US-004 - Prompt Injection Defense (Priority: P1)
As a security owner, I want prompt-injection attempts blocked in user input and retrieved chunks.

**Why this priority**: Critical safety control for all AI flows.

**Independent Test**: Run adversarial payload corpus against both input and retrieval surfaces.

**Acceptance Criteria**:
- AC-004-01 (positive) Given benign content, when guardrail checks run, then flow proceeds without unnecessary blocking.
- AC-004-02 (positive) Given suspicious content above threshold, when checks run, then safe fallback is returned.
- AC-004-03 (negative) Given exfiltration instructions, when detected, then request is blocked with `ERR-SEC-001`.
- AC-004-04 (negative) Given malicious retrieval chunk, when pre-generation validation runs, then chunk is excluded and security event logged.

### US-005 - PII Redaction Before LLM Prompts (Priority: P1)
As a compliance stakeholder, I need sensitive data redacted before any prompt, log, or trace emission.

**Why this priority**: Required for legal and trust obligations.

**Independent Test**: Submit content with names/emails/employee IDs and inspect generated prompt and traces.

**Acceptance Criteria**:
- AC-005-01 (positive) Given PII in user content, when prompt is assembled, then sensitive tokens are redacted.
- AC-005-02 (positive) Given redacted content, when traces/logs are emitted, then raw PII is absent.
- AC-005-03 (negative) Given redaction uncertainty, when confidence drops below threshold, then flow fails closed with `ERR-SEC-002`.
- AC-005-04 (negative) Given unsupported PII pattern, when validation suite runs, then release is blocked.

### US-006 - LangGraph Stateful Routing (Priority: P1)
As a support agent, I need deterministic stateful routing for policy questions, actions, escalation, and blocked outcomes.

**Why this priority**: Ensures predictable behavior under mixed ticket intents.

**Independent Test**: Execute graph with intent labels policy_question, action_request, direct_response, escalation, blocked.

**Acceptance Criteria**:
- AC-006-01 (positive) Given direct_response intent, when graph executes, then route goes to generate->validate->stream path.
- AC-006-02 (positive) Given action_request intent, when policy allows, then tool execution path runs and output is validated.
- AC-006-03 (negative) Given invalid transition, when graph edge fails state rules, then response returns `ERR-STATE-001`.
- AC-006-04 (negative) Given blocked intent, when route resolves, then no tool/model action occurs and blocked event is persisted.

### US-007 - Secure FastMCP Password Reset Assist (Priority: P1)
As an employee, I want password reset assistance that remains policy-controlled and human-approved when needed.

**Why this priority**: High-frequency action with elevated security risk.

**Independent Test**: Trigger reset flow as authorized and unauthorized roles with valid/invalid approval tokens.

**Acceptance Criteria**:
- AC-007-01 (positive) Given authorized role and valid inputs, when reset request is submitted, then tool call succeeds with auditable status.
- AC-007-02 (positive) Given high-risk context, when approval token is present and valid, then request proceeds.
- AC-007-03 (negative) Given unauthorized role, when tool call is attempted, then request fails with `ERR-TOOL-001`.
- AC-007-04 (negative) Given invalid tool arguments, when schema validation runs, then request fails with `ERR-VAL-002`.

### US-008 - Ticket Lifecycle and Status Transparency (Priority: P2)
As a requester, I want clear lifecycle transitions and status visibility.

**Why this priority**: Improves collaboration between employees and support staff.

**Independent Test**: Transition through open->in_progress->waiting_user->resolved->closed.

**Acceptance Criteria**:
- AC-008-01 (positive) Given valid transition, when status update is requested, then state changes and history is appended.
- AC-008-02 (positive) Given resolved ticket and user confirmation, when close is requested, then status becomes `closed`.
- AC-008-03 (negative) Given invalid transition, when update is requested, then request fails with `ERR-STATE-002`.
- AC-008-04 (negative) Given tenant mismatch access, when status is queried, then access is denied with `ERR-ACL-001`.

### US-009 - Tenant-Isolated Retrieval and Memory (Priority: P1)
As a platform owner, I need strict tenant isolation for retrieval and memory records.

**Why this priority**: Core protection against data leakage.

**Independent Test**: Execute same query in two tenants and confirm no cross-tenant candidates.

**Acceptance Criteria**:
- AC-009-01 (positive) Given tenant-scoped collection, when retrieval runs, then only same-tenant chunks are returned.
- AC-009-02 (positive) Given memory read/write operation, when persistence occurs, then tenant partition is enforced.
- AC-009-03 (negative) Given missing tenant predicate, when query executes, then operation fails with `ERR-ACL-001`.
- AC-009-04 (negative) Given cross-tenant hit candidate, when validation runs, then candidate is rejected and incident logged.

### US-010 - Arize Phoenix Traceability (Priority: P2)
As an SRE or security reviewer, I need end-to-end traces for every critical path.

**Why this priority**: Required for incident response and reliability analysis.

**Independent Test**: Run successful and failed workflows and inspect trace span graph.

**Acceptance Criteria**:
- AC-010-01 (positive) Given successful workflow, when traces are queried, then API, retrieval, tool, model, and terminal spans are linked.
- AC-010-02 (positive) Given handled error, when trace is queried, then error code and correlation ID are present.
- AC-010-03 (negative) Given missing correlation metadata, when health check runs, then check fails with `ERR-OBS-001`.
- AC-010-04 (negative) Given exporter outage, when backpressure threshold is exceeded, then degraded mode event is emitted.

### US-011 - Promptfoo Evaluation Gates (Priority: P2)
As a release manager, I want prompt/model quality gates to block unsafe regressions.

**Why this priority**: Prevents quality and safety drift across releases.

**Independent Test**: Execute passing and failing Promptfoo suites in CI.

**Acceptance Criteria**:
- AC-011-01 (positive) Given CI pipeline, when Promptfoo completes, then score artifacts are published.
- AC-011-02 (positive) Given score and required suites pass, when release gate runs, then deployment is permitted.
- AC-011-03 (negative) Given score below threshold, when gate runs, then deployment is blocked with `ERR-EVAL-002`.
- AC-011-04 (negative) Given required suite missing, when gate runs, then pipeline fails with `ERR-EVAL-001`.

### US-012 - Knowledge Chunk Governance (Priority: P3)
As an IT admin, I need controlled chunk lifecycle and policy tagging.

**Why this priority**: Maintains retrieval quality and compliance over time.

**Independent Test**: Ingest, update, and retire chunks with policy tag validations.

**Acceptance Criteria**:
- AC-012-01 (positive) Given valid source material, when ingestion runs, then chunks are indexed with tenant and policy tags.
- AC-012-02 (positive) Given deprecated source, when retirement runs, then chunk is excluded from active retrieval.
- AC-012-03 (negative) Given missing policy tags, when ingestion runs, then request fails with `ERR-VAL-003`.
- AC-012-04 (negative) Given oversized chunk content, when ingestion runs, then request fails with `ERR-VAL-004`.

### US-013 - Honest Copilot Documentation (Priority: P2)
As a support org lead, I want documentation that accurately reflects behavior and limitations.

**Why this priority**: Prevents operational misuse and incorrect user expectations.

**Independent Test**: Compare release behavior versus published docs and run documentation quality gate.

**Acceptance Criteria**:
- AC-013-01 (positive) Given implemented feature behavior, when docs are reviewed, then capability and limitations are accurate.
- AC-013-02 (positive) Given fallback paths, when docs are reviewed, then next-step guidance is explicit.
- AC-013-03 (negative) Given outdated claim, when doc gate runs, then release fails with `ERR-DOC-001`.
- AC-013-04 (negative) Given unsupported security claim, when review runs, then claim is rejected until evidence is linked.

### US-014 - Provider-Agnostic LLM Invocation (Priority: P1)
As a platform owner, I want the assistant's generation calls routed through a single configurable LLM client, so we can switch between NVIDIA NIM, Gemini, and OpenAI without code changes.

**Why this priority**: Classroom/demo credentials and free-tier availability shift; the system must not be hard-wired to one vendor.

**Independent Test**: Run the same chat request with `LLM_PROVIDER` set to each of `nvidia_nim`, `gemini`, and `openai` and confirm identical schema-valid response shape.

**Acceptance Criteria**:
- AC-014-01 (positive) Given `LLM_PROVIDER=openai` (or `nvidia_nim`/`gemini`), when a policy question is asked, then the grounded answer is generated through that provider with no other code path change.
- AC-014-02 (positive) Given a provider switch, when the agent runs, then Phoenix records an `llm_call` span with provider and model attributes.
- AC-014-03 (negative) Given the configured provider times out or errors, when generation fails, then the system escalates/creates a ticket instead of fabricating an answer.
- AC-014-04 (negative) Given no `LLM_PROVIDER` (or an unsupported value) is configured, when the app starts, then startup fails fast with a clear configuration error rather than a runtime crash mid-conversation.

### US-015 - External Knowledge Search Tool (Priority: P2)
As an employee, I want the assistant to optionally look up general (non-policy) information via Google or Wikipedia, so questions outside the internal KB still get a helpful, clearly-labeled answer.

**Why this priority**: Extends usefulness beyond the tenant policy corpus without weakening policy-grounding guarantees.

**Independent Test**: Ask a general knowledge question with no internal KB match and confirm the tool is invoked, results are labeled external, and internal policy questions never trigger this tool when internal context exists.

**Acceptance Criteria**:
- AC-015-01 (positive) Given a question with no matching internal policy chunk, when routed, then `search_external_knowledge` is called and results render as an "external source" tool card.
- AC-015-02 (positive) Given a question with a matching internal policy chunk, when routed, then internal RAG is used and the external search tool is NOT called.
- AC-015-03 (negative) Given the external API is unavailable, when the tool is invoked, then the tool card shows a failed state (`ERR-TOOL-002`) and the assistant offers ticket escalation, without blocking the rest of the response.
- AC-015-04 (negative) Given an invalid/empty query, when the tool is invoked, then the call is rejected with `ERR-VAL-002` before any outbound request is made.

## Functional Requirements

- FR-001 System MUST accept authenticated tenant-scoped ticket creation requests.
- FR-002 System MUST generate and persist AI first-response drafts.
- FR-003 System MUST stream assistant response events to clients.
- FR-004 System MUST stream structured tool-card events for tool actions.
- FR-005 System MUST perform policy-grounded tenant-scoped RAG retrieval.
- FR-006 System MUST provide citations or explicit no-evidence fallback in responses.
- FR-007 System MUST redact configured PII classes before prompts, logs, and traces.
- FR-008 System MUST detect and mitigate prompt injection from user and retrieved content.
- FR-009 System MUST execute LangGraph stateful routing with required intent branches.
- FR-010 System MUST enforce deny-by-default FastMCP tool authorization.
- FR-011 System MUST require human approval for high-risk tool operations.
- FR-012 System MUST enforce ticket lifecycle transition rules.
- FR-013 System MUST enforce tenant isolation for storage, retrieval, cache, and memory.
- FR-014 System MUST emit Phoenix traces with correlation IDs across critical spans.
- FR-015 System MUST enforce Promptfoo release gates in CI/CD.
- FR-016 System MUST enforce honest Copilot documentation gates before release.
- FR-017 System MUST invoke LLM generation through a single provider-agnostic client selectable among NVIDIA NIM, Gemini, and OpenAI via configuration.
- FR-018 System MUST provide an external knowledge search tool (Google/Wikipedia) as a governed FastMCP tool, used only when internal policy RAG has no matching context, with results labeled as external.
- FR-019 System MUST deliver chat responses to the Streamlit frontend as REST JSON; incremental/streaming delivery is optional and MUST NOT be required for compliance.

## Non-Functional Requirements

- NFR-001 Security: PII redaction recall MUST be >= 99% on validation corpus.
- NFR-002 Security: Confirmed cross-tenant retrieval leakage MUST be zero.
- NFR-003 Security: 100% FastMCP tool calls MUST be policy-evaluated and audited.
- NFR-004 Reliability: p95 first-response latency MUST be <= 60 seconds.
- NFR-005 Reliability: p95 stream start time MUST be <= 2 seconds.
- NFR-006 Availability: Ticketing and chat APIs MUST target >= 99.9% monthly uptime.
- NFR-007 Observability: >= 98% requests MUST have complete trace lineage.
- NFR-008 Quality: Promptfoo aggregate score MUST meet release threshold (initial 0.85).
- NFR-009 UX: Streamlit UI and tool cards MUST work on supported desktop and mobile (incremental/streaming delivery is optional, not required — see FR-019).
- NFR-010 Governance: Documentation accuracy gate pass rate MUST be 100% for release candidates.
- NFR-011 Portability: Switching `LLM_PROVIDER` among NVIDIA NIM, Gemini, and OpenAI MUST require zero changes outside `src/llm/` and environment configuration.

## Data Model

### SupportTicket
- ticket_id: string
- tenant_id: string
- requester_user_id: string
- title: string
- description: string
- category: string
- priority: enum(low, medium, high, critical)
- status: enum(open, in_progress, waiting_user, resolved, closed)
- assigned_queue: string | null
- escalation_level: integer
- created_at: datetime
- updated_at: datetime

### ChatMessage
- message_id: string
- ticket_id: string
- tenant_id: string
- role: enum(user, assistant, tool, system)
- content: string
- citations: list[string]
- tool_call_id: string | null
- redaction_applied: boolean
- injection_screened: boolean
- created_at: datetime

### KnowledgeChunk
- chunk_id: string
- tenant_id: string
- source_doc_id: string
- source_title: string
- content: string
- embedding_vector_ref: string
- policy_tags: list[string]
- active: boolean
- revision: integer
- updated_at: datetime

### MemoryRecord
- memory_id: string
- tenant_id: string
- ticket_id: string | null
- memory_scope: enum(ephemeral, session, ticket)
- key: string
- value: string
- expires_at: datetime | null
- created_at: datetime

## API Contracts (Pydantic v2)

```python
from datetime import datetime
from enum import Enum
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

class StreamEventType(str, Enum):
    delta = "delta"
    tool_call = "tool_call"
    tool_result = "tool_result"
    final = "final"
    error = "error"

class TicketStatus(str, Enum):
    open = "open"
    in_progress = "in_progress"
    waiting_user = "waiting_user"
    resolved = "resolved"
    closed = "closed"

class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=2, max_length=80)
    ticket_id: str = Field(min_length=3, max_length=64)
    user_message: str = Field(min_length=1, max_length=6000)
    stream: bool = True

class ToolCallCard(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tool_call_id: str
    tool_name: str
    status: Literal["queued", "running", "succeeded", "failed", "denied"]
    summary: str
    started_at: datetime | None = None
    ended_at: datetime | None = None

class ChatStreamEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_type: StreamEventType
    sequence: int = Field(ge=0)
    ticket_id: str
    correlation_id: str
    content_delta: str | None = None
    tool_card: ToolCallCard | None = None
    error_code: str | None = None

class TicketStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ticket_id: str
    status: TicketStatus
    updated_at: datetime
    assigned_queue: str | None = None

class PasswordResetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str
    target_user_id: str
    reason: str = Field(min_length=5, max_length=400)
    approval_token: str | None = None

class TicketCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str
    title: str = Field(min_length=5, max_length=180)
    description: str = Field(min_length=20, max_length=6000)
    category: str = Field(min_length=2, max_length=80)
    priority: Literal["low", "medium", "high", "critical"]
```

## Error Code Catalog (User-Facing)

| Error Code | HTTP | User-Facing Message | Notes |
|---|---:|---|---|
| ERR-AUTH-001 | 401 | Your session has expired. Please sign in again. | Missing or invalid auth claims |
| ERR-ACL-001 | 403 | You do not have access to this resource. | Tenant or role mismatch |
| ERR-VAL-001 | 422 | Some required fields are missing or invalid. | Request validation failure |
| ERR-VAL-002 | 422 | The requested action used invalid tool inputs. | FastMCP argument validation |
| ERR-VAL-003 | 422 | Knowledge content is missing required policy tags. | Chunk governance |
| ERR-VAL-004 | 413 | Knowledge content is too large to process. | Chunk size limits |
| ERR-RATE-001 | 429 | Too many requests. Please wait and try again. | Rate limiting |
| ERR-AI-001 | 504 | The assistant took too long. Your request is saved and safe fallback was applied. | Generation timeout |
| ERR-RAG-001 | 404 | We could not find enough trusted knowledge to answer confidently. | No evidence fallback |
| ERR-RAG-002 | 504 | Knowledge retrieval timed out. Please try again shortly. | Retrieval timeout |
| ERR-SEC-001 | 400 | Your request triggered safety protections and cannot be processed as submitted. | Prompt injection risk |
| ERR-SEC-002 | 500 | We could not safely process sensitive data in this request. | Redaction failure |
| ERR-TOOL-001 | 403 | This automated action is not permitted for your role. | Tool authorization denied |
| ERR-TOOL-002 | 502 | The requested tool action failed. Please try again or contact support. | Tool runtime failure |
| ERR-STATE-001 | 409 | This action cannot be performed in the current workflow state. | LangGraph state conflict |
| ERR-STATE-002 | 409 | Ticket cannot transition to that status from its current state. | Lifecycle conflict |
| ERR-UPSTREAM-001 | 502 | A dependent service is unavailable. Please try again shortly. | Upstream failure |
| ERR-OBS-001 | 500 | Internal trace metadata is incomplete for this request. | Observability gate failure |
| ERR-EVAL-001 | 500 | Required evaluation suites did not complete successfully. | Missing Promptfoo suite |
| ERR-EVAL-002 | 500 | Quality threshold was not met. Deployment is blocked. | Promptfoo score below gate |
| ERR-DOC-001 | 500 | Documentation quality checks failed for this release. | Honesty gate failure |

## Guardrail Rules

- GR-001 Redaction-first: PII redaction MUST run before prompt assembly.
- GR-002 Injection scan: User and retrieved text MUST be scanned for prompt injection risk.
- GR-003 Tenant predicate: Every data read/write MUST include tenant scoping.
- GR-004 Tool policy: FastMCP execution MUST be deny-by-default with allow-list checks.
- GR-005 Human approval: High-risk actions MUST require approval token validation.
- GR-006 Structured response: Model output MUST pass schema validation before streaming finalization.
- GR-007 Fallback integrity: Blocked or uncertain outputs MUST use explicit safe fallback messages.
- GR-008 Trace completeness: Correlation metadata MUST be emitted through terminal workflow node.

## Forbidden Libraries and Patterns

### Forbidden Patterns
- FP-001 Using `eval` or `exec` on user or retrieved content.
- FP-002 Unscoped vector search without tenant filter.
- FP-003 Logging prompt text before redaction.
- FP-004 User-controlled tool name execution without allow-list validation.
- FP-005 Silent exception swallowing in security-sensitive paths.
- FP-006 Hidden behavior that contradicts published documentation.

### Forbidden Libraries (Runtime)
- FL-001 `pickle` for untrusted deserialization.
- FL-002 `subprocess` execution paths with user-controlled arguments lacking strict allow-list wrappers.
- FL-003 Legacy Pydantic v1 APIs for request/response contracts.
- FL-004 Any orchestration helper that bypasses guardrail middleware.

## Assumptions

- Enterprise SSO provides tenant_id and role claims.
- Exactly one of NVIDIA NIM, Gemini, or OpenAI is configured and reachable at a time via `LLM_PROVIDER`; the client abstraction makes the active choice swappable without code changes.
- Policy-tagged knowledge corpus exists per tenant.
- Google/Wikipedia search API access is available for the external knowledge tool (mock/stub acceptable for classroom demo).
- CI can run Promptfoo and publish evaluation artifacts.

## Success Criteria

- SC-001 At least 40% of incoming tickets receive safe usable AI first responses without human rewrite.
- SC-002 p95 time from ticket creation to first response is <= 60 seconds.
- SC-003 Confirmed cross-tenant retrieval incidents remain at 0.
- SC-004 At least 95% adversarial injection attempts are blocked in evaluation suites.
- SC-005 Promptfoo gates pass for every release candidate.
- SC-006 Documentation honesty gate passes for every release candidate.
