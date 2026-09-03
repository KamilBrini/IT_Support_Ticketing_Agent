<!--
Sync Impact Report
- Version change: 1.0.0 -> 2.0.0
- Modified principles:
	- VIII. React Streaming UI with Tool Cards -> VIII. Streamlit UI with Tool Cards
		(SSE streaming demoted from mandatory to optional enhancement; REST
		request/response is the baseline contract, matching the shipped
		Streamlit + FastAPI implementation).
- Added principles:
	- IX. Provider-Agnostic LLM Invocation (new, non-negotiable)
- Renumbered sections:
	- IX. Honest Copilot Documentation -> X. Honest Copilot Documentation
- Added tool guidance:
	- Principle II (Secure FastMCP Tool Execution) now explicitly scopes the
		external knowledge search tool (Google/Wikipedia) under the same
		deny-by-default governance as ticketing tools.
- Rationale for MAJOR bump:
	- Principle VIII was redefined (frontend technology and transport
		contract changed), which is a principle redefinition per the
		Versioning Policy below.
- Removed sections:
	- None
- Follow-up TODOs:
	- Update any release checklist or CI gate wording that still references
		"React" or "SSE-mandatory" streaming.
-->

# IT Support Ticketing System Constitution

## Core Principles

### I. Policy-Grounded RAG Answers (Non-Negotiable)
The system MUST provide policy-grounded answers that are traceable to approved
knowledge and tenant-scoped retrieval.

Rules:
- Retrieval MUST enforce tenant and policy filters before generation.
- Responses MUST include citations or explicit no-evidence fallback.
- Unsupported claims MUST be refused, not fabricated.

Rationale: Grounding and policy constraints reduce hallucination risk and improve
trust and auditability.

### II. Secure FastMCP Tool Execution (Non-Negotiable)
Tool execution is privileged behavior and MUST be governed by explicit policy.

Rules:
- FastMCP tool access is deny-by-default.
- Every tool call MUST pass role, action, and schema validation.
- High-risk actions MUST require human approval and immutable audit events.
- This governance applies uniformly to internal tools (ticket status, ticket
	creation, password reset) and to the external knowledge search tool
	(Google/Wikipedia lookup): external results MUST be schema-validated,
	MUST NOT be treated as policy-authoritative in place of tenant RAG
	context, and MUST be clearly labeled as external in the response.

Rationale: Strong execution controls prevent unsafe automation and privilege abuse.

### III. PII Redaction Before LLM Prompts (Non-Negotiable)
PII protection is mandatory before any model interaction or telemetry emission.

Rules:
- Redaction MUST run before prompt assembly.
- Redaction MUST also apply to logs and trace payloads.
- If redaction confidence is insufficient, processing MUST fail closed.

Rationale: Pre-prompt redaction enforces least exposure of sensitive data.

### IV. Prompt Injection Resistance (Non-Negotiable)
The system MUST detect and neutralize injection attempts from user and retrieved
content.

Rules:
- Injection checks MUST evaluate inbound prompts and retrieval chunks.
- Unsafe content MUST route to blocked or safe-fallback behavior.
- Injection outcomes MUST produce stable error codes and audit entries.

Rationale: Dual-surface defense is required because attacks can originate from both
user input and knowledge sources.

### V. LangGraph Stateful Routing
AI orchestration MUST be explicit, deterministic, and state-aware.

Rules:
- Canonical node chain MUST be implemented and versioned.
- Intent branches MUST include policy_question, action_request,
	direct_response, escalation, and blocked.
- Invalid state transitions MUST fail with ERR-STATE-* semantics.

Rationale: Explicit graph state improves correctness, safety, and debuggability.

### VI. Arize Phoenix Observability
End-to-end traceability MUST exist for all critical workflow operations.

Rules:
- Traces MUST include API, retrieval, tool, model, and terminal update spans.
- Correlation identifiers MUST connect frontend and backend execution.
- Missing trace lineage above threshold MUST block release.

Rationale: Full observability is required for incident response and quality control.

### VII. Promptfoo Evaluation Gates
Prompt and model behavior MUST be continuously evaluated with release gates.

Rules:
- Promptfoo suites MUST include quality, safety, and policy conformance tests.
- Score thresholds and required suites MUST block deployment on failure.
- Requirement-to-test mapping MUST be maintained for every release.

Rationale: Automated evaluation reduces regression risk and enforces measurable AI
quality.

### VIII. Streamlit UI with Tool Cards
The user interface MUST provide clear responses and tool visibility through a
Streamlit chat application communicating with the FastAPI gateway over REST.

Rules:
- Chat requests/responses MUST use a schema-valid REST contract (`ChatRequest` /
	JSON response); SSE or other incremental delivery MAY be added later as an
	optional enhancement but MUST NOT be required for a compliant release.
- Tool invocations MUST render as structured tool cards (e.g. ticket status,
	password reset, ticket creation, external knowledge lookup) with status and
	outcome, never raw JSON or stack traces.
- Degraded states (backend unreachable, validation failure, blocked request,
	tool failure) MUST be explicit and recoverable in the UI.

Rationale: Streamlit + REST is the simplest transport that still satisfies
transparent tool visibility and safe-error display for this capstone's scope;
mandating SSE added transport complexity without a corresponding safety or
trust benefit.

### IX. Provider-Agnostic LLM Invocation (Non-Negotiable)
All model generation and reasoning MUST go through a single LLM client
abstraction that can target NVIDIA NIM, Google Gemini, or OpenAI without
changing agent/orchestration code.

Rules:
- The concrete provider and model MUST be selected via configuration/
	environment variables, never hardcoded in `src/agent/` or `src/tools/`.
- Provider credentials MUST be loaded from environment variables and MUST
	NOT be logged, traced, or committed.
- A provider or endpoint failure MUST fail safe to an escalation/ticket path,
	never to a fabricated answer or a silent fallback that bypasses guardrails
	(redaction, injection screening, RAG grounding).
- Swapping providers MUST NOT require changes to Pydantic schemas, LangGraph
	node signatures, or tool contracts.

Rationale: Classroom/demo environments frequently rotate between free-tier or
sponsored model endpoints; centralizing invocation keeps guardrails, tracing,
and schema validation provider-independent.

### X. Honest Copilot Documentation
Documentation MUST be truthful, current, and evidence-backed.

Rules:
- Docs MUST distinguish implemented behavior from planned behavior.
- Limitations, confidence boundaries, and fallback behavior MUST be documented.
- Security and governance claims MUST reference tests, traces, or audit evidence.

Rationale: Honest documentation prevents misuse and aligns expectations with system
behavior.

## Security Requirements and Data Contract Standards

Security controls:
- Tenant isolation MUST be enforced across storage, retrieval, cache, memory,
	and telemetry.
- Least-privilege access MUST apply to users, agents, and tools.
- Security-relevant operations MUST emit immutable audit records.

Data contract standards:
- All API and event contracts MUST use Pydantic v2 schemas.
- Contracts MUST forbid undeclared fields unless explicitly justified.
- Error payloads MUST use stable ERR-* code families.

Required error families:
- ERR-AUTH-*, ERR-ACL-*, ERR-VAL-*, ERR-SEC-*, ERR-TOOL-*, ERR-RAG-*,
	ERR-STATE-*, ERR-OBS-*, ERR-EVAL-*, ERR-DOC-*

## Development Workflow and Quality Gates

Workflow requirements:
- Every feature MUST follow Spec Kit sequence: Constitution -> Specification ->
	Plan -> Tasks.
- User stories MUST include positive and negative acceptance criteria.
- Every requirement MUST map to at least one test focus and test artifact.

Release quality gates:
- No unresolved critical security findings.
- PII redaction, prompt injection, and tenant isolation security checkpoints MUST
	pass.
- Promptfoo threshold and required suite gates MUST pass.
- Phoenix trace completeness gate MUST pass.
- Documentation accuracy gate MUST pass.

## Governance

This Constitution is the highest authority for development and release decisions
in this project.

Amendment and compliance policy:
- Every pull request MUST declare constitution impact and compliance status.
- Exceptions require documented risk acceptance by Product, Engineering, and
	Security owners.
- Amendments MUST include rationale, migration impact on active specs/tasks,
	and approval from Product, Engineering, and Security owners.

Versioning policy:
- MAJOR: incompatible governance change or principle removal/redefinition.
- MINOR: new principle or materially expanded governance obligation.
- PATCH: wording clarity, typos, or non-semantic refinements.

Compliance review expectations:
- Constitution compliance MUST be reviewed at specification approval,
	pre-implementation plan approval, and release readiness sign-off.

**Version**: 2.0.0 | **Ratified**: 2026-08-27 | **Last Amended**: 2026-09-02
