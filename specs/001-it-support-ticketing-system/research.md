# Research: IT Support Ticketing System

## Decision 1: Canonical LangGraph Node Chain
- Decision: Use the mandatory chain `apply_pii_redaction -> detect_prompt_injection -> load_session_memory -> classify_intent -> retrieve_from_rag -> execute_tool -> generate_response -> validate_structured_output -> stream_response_sse -> update_memory_and_trace`.
- Rationale: Enforces constitution priorities for safety-first processing, deterministic routing, and trace closure.
- Alternatives considered:
  - Single LLM call path: rejected due to weak safety checkpoints.
  - Tool-first orchestration: rejected due to unnecessary action risk before grounding.

## Decision 2: Intent Branching Contract
- Decision: Restrict intent branches to `policy_question`, `action_request`, `direct_response`, `escalation`, `blocked`.
- Rationale: Stable intent taxonomy improves graph predictability and testability.
- Alternatives considered:
  - Open-ended intent labels from model output: rejected for inconsistent routing.
  - Two-class intent model: rejected due to insufficient escalation/blocked semantics.

## Decision 3: ChromaDB Tenant Isolation Strategy
- Decision: Use collection naming `kb_{tenant_id}_{domain}_{version}` with strict query filters `tenant_id` and `active`.
- Rationale: Minimizes cross-tenant blast radius and supports auditable retrieval.
- Alternatives considered:
  - Shared collection with metadata filtering only: rejected for higher leakage risk.
  - Physical DB per tenant at v1: deferred due to operational overhead.

## Decision 4: FastMCP Policy and Schema Governance
- Decision: Enforce deny-by-default tool execution, schema-validated inputs, and approval tokens for high-risk actions.
- Rationale: Aligns with secure execution and least-privilege mandates.
- Alternatives considered:
  - Role-only checks: rejected due to parameter abuse risk.
  - Agent-selected unrestricted tools: rejected due to policy bypass risk.

## Decision 5: Observability and Evaluation Gates
- Decision: Make Promptfoo and Phoenix lineage gates blocking for release.
- Rationale: Prevents silent quality and safety regressions.
- Alternatives considered:
  - Non-blocking quality dashboards: rejected because regressions could ship.
  - Partial tracing only on errors: rejected because it weakens forensic coverage.

## Clarifications Resolved for Planning
- Authentication contract: OIDC-compatible SSO with tenant and role claims.
- Data handling baseline: configurable retention with secure defaults.
- Attachment scope: metadata-only in v1.
- Performance objective: p95 first response <= 60 seconds.
- Integration scope: internal ticketing is source of truth in v1.

## Key Risks and Mitigations
- Retrieval leakage -> strict tenant filters + isolation tests.
- Prompt injection bypass -> adversarial suites + blocked path enforcement.
- Tool misuse -> schema validation + approval policy + immutable audit.
- Latency spikes -> async streaming + timeout fallback.
- Trace gaps -> required correlation IDs at each workflow node.
