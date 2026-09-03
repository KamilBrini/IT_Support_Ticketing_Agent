# Tasks: IT Support Ticketing System

> **Note (2026-09-02, Constitution v2.0.0)**: Phases 1-16 below were generated
> against the original React + SSE + microservice-style path layout
> (`src/orchestration/`, `frontend/src/features/...`, `tests/e2e/*.spec.ts`,
> etc.). The shipped implementation instead uses the simpler layout in
> `plan.md` (`src/agent/`, `src/api/main.py`, single-file `frontend/app.py`,
> Streamlit + REST). Treat file paths in Phases 1-16 as historical/aspirational
> until reconciled task-by-task; do not assume they exist. New work — the
> provider-agnostic LLM client (US-014) and external search tool (US-015) —
> is tracked below in Phase 17 using the real, current path layout.

**Input**: Design documents from `/specs/001-it-support-ticketing-system/`

**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/, quickstart.md

**Tests**: Mandatory. Every story has explicit tests that must pass before completion.

**Organization**: Tasks are grouped by user story for independent implementation and validation.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no unfinished dependency).
- **[Story]**: User story label (`[US1]` ... `[US13]`) for story-phase tasks only.
- Every task includes an output path under `/src`, `/frontend`, `/eval`, `/tests`, or `/docs`.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish folder structure and baseline engineering workflow.

- [ ] T001 Create backend source structure in src/
- [ ] T002 Create frontend structure in frontend/src/
- [ ] T003 Create evaluation structure in eval/promptfoo/
- [ ] T004 Create test structure in tests/{unit,integration,contract,security,e2e}/
- [ ] T005 Create documentation structure in docs/{architecture,security,runbooks,quality}/
- [ ] T006 [P] Create Python project manifest in src/pyproject.toml
- [ ] T007 [P] Create frontend package manifest in frontend/package.json
- [ ] T008 [P] Create CI quality gate blueprint in docs/quality/ci-quality-gates.md

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core contracts and security controls required by all stories.

**Critical**: No story implementation begins before this phase passes.

- [ ] T009 Implement shared Pydantic base models in src/schemas/common.py
- [ ] T010 [P] Implement error schemas and ERR-* registry in src/schemas/errors.py
- [ ] T011 [P] Implement auth and tenant claim middleware in src/security/auth_middleware.py
- [ ] T012 Implement PII redaction service in src/security/pii_redaction.py
- [ ] T013 Implement prompt injection detector in src/security/prompt_injection.py
- [ ] T014 Implement tenant guard utilities in src/security/tenant_guard.py
- [ ] T015 Implement workflow state schemas in src/schemas/workflow_state.py
- [ ] T016 [P] Implement observability context wrapper in src/observability/trace_context.py
- [ ] T017 [P] Implement SSE base event schema helpers in src/schemas/streaming.py
- [ ] T018 [P] Add foundational contract tests in tests/contract/test_foundational_contracts.py
- [ ] T019 [P] Add foundational security tests in tests/security/test_foundational_security.py

**Checkpoint**: T009-T019 complete and green.

---

## Phase 3: User Story 1 - Create Ticket and Receive AI First Reply (Priority: P1) 🎯 MVP

**Goal**: Employee creates ticket and receives safe first AI reply.

**Independent Test**: Valid/invalid ticket submission and first-response persistence.

**Pydantic Schemas Required First**:
- src/schemas/common.py
- src/schemas/errors.py
- src/schemas/ticket.py

**Done When Tests Pass**:
- tests/contract/test_ticket_create_contract.py
- tests/integration/test_ticket_first_response_flow.py
- tests/integration/test_ticket_create_negative_cases.py

**Security Checkpoint**:
- tests/security/test_pii_redaction_pipeline.py
- tests/security/test_prompt_injection_gate.py
- tests/security/test_tenant_isolation_enforcement.py

- [ ] T020 [P] [US1] Implement TicketCreateRequest and ticket response schemas in src/schemas/ticket.py
- [ ] T021 [US1] Implement ticket create endpoint in src/api/tickets/create_ticket.py
- [ ] T022 [US1] Implement first-response workflow trigger in src/orchestration/first_response_workflow.py
- [ ] T023 [US1] Implement ticket create UI in frontend/src/features/tickets/TicketCreateForm.tsx
- [ ] T024 [P] [US1] Add contract tests in tests/contract/test_ticket_create_contract.py
- [ ] T025 [P] [US1] Add integration tests in tests/integration/test_ticket_first_response_flow.py
- [ ] T026 [P] [US1] Add negative tests in tests/integration/test_ticket_create_negative_cases.py

---

## Phase 4: User Story 2 - Stream Assistant Responses with Tool Cards (Priority: P1)

**Goal**: Stream assistant output and tool card updates to users.

**Independent Test**: SSE stream and tool-card events render in sequence.

**Pydantic Schemas Required First**:
- src/schemas/chat.py
- src/schemas/tooling.py
- src/schemas/streaming.py

**Done When Tests Pass**:
- tests/contract/test_chat_stream_contract.py
- tests/integration/test_sse_stream_tool_cards.py
- tests/e2e/test_streaming_toolcard_ui.spec.ts

**Security Checkpoint**:
- tests/security/test_pii_redaction_pipeline.py
- tests/security/test_prompt_injection_gate.py
- tests/security/test_tenant_isolation_enforcement.py

- [ ] T027 [P] [US2] Implement ChatRequest and ChatStreamEvent schemas in src/schemas/chat.py
- [ ] T028 [P] [US2] Implement ToolCallCard schema in src/schemas/tooling.py
- [ ] T029 [US2] Implement SSE stream endpoint in src/api/chat/stream_chat_sse.py
- [ ] T030 [US2] Implement streaming parser in frontend/src/features/chat/streamParser.ts
- [ ] T031 [US2] Implement tool card component in frontend/src/components/toolcards/ToolCallCard.tsx
- [ ] T032 [P] [US2] Add contract tests in tests/contract/test_chat_stream_contract.py
- [ ] T033 [P] [US2] Add integration tests in tests/integration/test_sse_stream_tool_cards.py
- [ ] T034 [P] [US2] Add e2e tests in tests/e2e/test_streaming_toolcard_ui.spec.ts

---

## Phase 5: User Story 3 - Policy-Grounded RAG Answers (Priority: P1)

**Goal**: Deliver grounded answers with citations and safe no-evidence fallback.

**Independent Test**: Policy question retrieves tenant-approved chunks and citations.

**Pydantic Schemas Required First**:
- src/schemas/rag.py
- src/schemas/chat.py
- src/schemas/errors.py

**Done When Tests Pass**:
- tests/contract/test_rag_answer_contract.py
- tests/integration/test_policy_grounded_answers.py
- tests/integration/test_rag_no_evidence_fallback.py

**Security Checkpoint**:
- tests/security/test_pii_redaction_pipeline.py
- tests/security/test_prompt_injection_gate.py
- tests/security/test_tenant_isolation_enforcement.py

- [ ] T035 [P] [US3] Implement citation and no-evidence schemas in src/schemas/rag.py
- [ ] T036 [US3] Implement retrieval service with policy filters in src/rag/retrieve_with_policy_filters.py
- [ ] T037 [US3] Implement grounded answer builder in src/orchestration/grounded_answer_builder.py
- [ ] T038 [P] [US3] Add contract tests in tests/contract/test_rag_answer_contract.py
- [ ] T039 [P] [US3] Add integration tests in tests/integration/test_policy_grounded_answers.py
- [ ] T040 [P] [US3] Add fallback tests in tests/integration/test_rag_no_evidence_fallback.py

---

## Phase 6: User Story 4 - Prompt Injection Defense (Priority: P1)

**Goal**: Detect and neutralize prompt injection attempts.

**Independent Test**: Adversarial payload suite is blocked or safely neutralized.

**Pydantic Schemas Required First**:
- src/schemas/security.py
- src/schemas/errors.py
- src/schemas/workflow_state.py

**Done When Tests Pass**:
- tests/security/test_prompt_injection_gate.py
- tests/integration/test_injection_block_routing.py
- tests/contract/test_guardrail_error_contract.py

**Security Checkpoint**:
- tests/security/test_pii_redaction_pipeline.py
- tests/security/test_prompt_injection_gate.py
- tests/security/test_tenant_isolation_enforcement.py

- [ ] T041 [P] [US4] Implement injection decision schemas in src/schemas/security.py
- [ ] T042 [US4] Implement blocked-route handler in src/orchestration/guardrail_router.py
- [ ] T043 [US4] Implement blocked response service in src/services/safety/blocked_response.py
- [ ] T044 [P] [US4] Add security tests in tests/security/test_prompt_injection_gate.py
- [ ] T045 [P] [US4] Add routing integration tests in tests/integration/test_injection_block_routing.py
- [ ] T046 [P] [US4] Add contract tests in tests/contract/test_guardrail_error_contract.py

---

## Phase 7: User Story 5 - PII Redaction Before LLM Prompts (Priority: P1)

**Goal**: Ensure redaction before prompt, logs, and traces.

**Independent Test**: Sensitive payloads are redacted in every downstream channel.

**Pydantic Schemas Required First**:
- src/schemas/security.py
- src/schemas/chat.py
- src/schemas/errors.py

**Done When Tests Pass**:
- tests/security/test_pii_redaction_pipeline.py
- tests/integration/test_redacted_prompt_and_trace.py
- tests/contract/test_redaction_metadata_contract.py

**Security Checkpoint**:
- tests/security/test_pii_redaction_pipeline.py
- tests/security/test_prompt_injection_gate.py
- tests/security/test_tenant_isolation_enforcement.py

- [ ] T047 [P] [US5] Implement redaction metadata schemas in src/schemas/security.py
- [ ] T048 [US5] Implement redaction middleware in src/orchestration/middleware/redaction_middleware.py
- [ ] T049 [US5] Implement redacted trace emitter in src/observability/redacted_trace_emitter.py
- [ ] T050 [P] [US5] Add security tests in tests/security/test_pii_redaction_pipeline.py
- [ ] T051 [P] [US5] Add integration tests in tests/integration/test_redacted_prompt_and_trace.py
- [ ] T052 [P] [US5] Add contract tests in tests/contract/test_redaction_metadata_contract.py

---

## Phase 8: User Story 6 - LangGraph Stateful Routing (Priority: P1)

**Goal**: Route intents deterministically across all required graph branches.

**Independent Test**: All five intents produce expected terminal outcomes.

**Pydantic Schemas Required First**:
- src/schemas/workflow_state.py
- src/schemas/chat.py
- src/schemas/errors.py

**Done When Tests Pass**:
- tests/integration/test_langgraph_intent_routing.py
- tests/integration/test_langgraph_invalid_transition.py
- tests/contract/test_workflow_state_contract.py

**Security Checkpoint**:
- tests/security/test_pii_redaction_pipeline.py
- tests/security/test_prompt_injection_gate.py
- tests/security/test_tenant_isolation_enforcement.py

- [ ] T053 [US6] Implement graph builder in src/orchestration/langgraph/build_graph.py
- [ ] T054 [US6] Implement intent classifier adapter in src/orchestration/langgraph/intent_classifier.py
- [ ] T055 [US6] Implement terminal handlers in src/orchestration/langgraph/terminal_handlers.py
- [ ] T056 [P] [US6] Add intent routing tests in tests/integration/test_langgraph_intent_routing.py
- [ ] T057 [P] [US6] Add invalid transition tests in tests/integration/test_langgraph_invalid_transition.py
- [ ] T058 [P] [US6] Add contract tests in tests/contract/test_workflow_state_contract.py

---

## Phase 9: User Story 7 - Secure FastMCP Password Reset Assist (Priority: P1)

**Goal**: Provide password reset assist with strict policy controls.

**Independent Test**: Authorized, unauthorized, and invalid-input paths are handled safely.

**Pydantic Schemas Required First**:
- src/schemas/tooling.py
- src/schemas/security.py
- src/schemas/errors.py

**Done When Tests Pass**:
- tests/contract/test_password_reset_tool_contract.py
- tests/integration/test_password_reset_policy_flow.py
- tests/security/test_mcp_policy_enforcement.py

**Security Checkpoint**:
- tests/security/test_pii_redaction_pipeline.py
- tests/security/test_prompt_injection_gate.py
- tests/security/test_tenant_isolation_enforcement.py

- [ ] T059 [P] [US7] Implement PasswordResetRequest schema in src/schemas/tooling.py
- [ ] T060 [US7] Implement reset tool adapter in src/tools/mcp/reset_password_request_tool.py
- [ ] T061 [US7] Implement approval token validator in src/security/approval_token_policy.py
- [ ] T062 [P] [US7] Add contract tests in tests/contract/test_password_reset_tool_contract.py
- [ ] T063 [P] [US7] Add integration tests in tests/integration/test_password_reset_policy_flow.py
- [ ] T064 [P] [US7] Add security tests in tests/security/test_mcp_policy_enforcement.py

---

## Phase 10: User Story 9 - Tenant-Isolated Retrieval and Memory (Priority: P1)

**Goal**: Enforce strict tenant partitioning in retrieval and memory operations.

**Independent Test**: Same queries across tenants produce isolated outputs.

**Pydantic Schemas Required First**:
- src/schemas/rag.py
- src/schemas/memory.py
- src/schemas/errors.py

**Done When Tests Pass**:
- tests/security/test_tenant_isolation_enforcement.py
- tests/integration/test_cross_tenant_retrieval.py
- tests/contract/test_tenant_filter_contract.py

**Security Checkpoint**:
- tests/security/test_pii_redaction_pipeline.py
- tests/security/test_prompt_injection_gate.py
- tests/security/test_tenant_isolation_enforcement.py

- [ ] T065 [US9] Implement tenant collection resolver in src/rag/tenant_collection_resolver.py
- [ ] T066 [US9] Implement tenant memory repository in src/memory/tenant_memory_repository.py
- [ ] T067 [US9] Implement tenant filter validator in src/rag/retrieval_filter_validator.py
- [ ] T068 [P] [US9] Add contract tests in tests/contract/test_tenant_filter_contract.py
- [ ] T069 [P] [US9] Add integration tests in tests/integration/test_cross_tenant_retrieval.py
- [ ] T070 [P] [US9] Add security tests in tests/security/test_tenant_isolation_enforcement.py

---

## Phase 11: User Story 8 - Ticket Lifecycle and Status Transparency (Priority: P2)

**Goal**: Support valid lifecycle transitions and transparent status retrieval.

**Independent Test**: Valid transitions succeed, invalid transitions fail with correct errors.

**Pydantic Schemas Required First**:
- src/schemas/ticket.py
- src/schemas/errors.py
- src/schemas/common.py

**Done When Tests Pass**:
- tests/contract/test_ticket_status_contract.py
- tests/integration/test_ticket_lifecycle_transitions.py
- tests/integration/test_ticket_status_access_control.py

**Security Checkpoint**:
- tests/security/test_pii_redaction_pipeline.py
- tests/security/test_prompt_injection_gate.py
- tests/security/test_tenant_isolation_enforcement.py

- [ ] T071 [P] [US8] Implement TicketStatusResponse schema in src/schemas/ticket.py
- [ ] T072 [US8] Implement transition validator in src/services/tickets/transition_validator.py
- [ ] T073 [US8] Implement status route in src/api/tickets/ticket_status.py
- [ ] T074 [P] [US8] Add contract tests in tests/contract/test_ticket_status_contract.py
- [ ] T075 [P] [US8] Add transition integration tests in tests/integration/test_ticket_lifecycle_transitions.py
- [ ] T076 [P] [US8] Add access control tests in tests/integration/test_ticket_status_access_control.py

---

## Phase 12: User Story 10 - Arize Phoenix Traceability (Priority: P2)

**Goal**: Ensure trace completeness for success and failure workflow paths.

**Independent Test**: Linked spans and error metadata are queryable for each critical flow.

**Pydantic Schemas Required First**:
- src/schemas/observability.py
- src/schemas/errors.py
- src/schemas/workflow_state.py

**Done When Tests Pass**:
- tests/integration/test_phoenix_trace_lineage.py
- tests/integration/test_trace_error_metadata.py
- tests/contract/test_trace_payload_contract.py

**Security Checkpoint**:
- tests/security/test_pii_redaction_pipeline.py
- tests/security/test_prompt_injection_gate.py
- tests/security/test_tenant_isolation_enforcement.py

- [ ] T077 [P] [US10] Implement trace payload schemas in src/schemas/observability.py
- [ ] T078 [US10] Implement Phoenix span emitter in src/observability/phoenix_span_emitter.py
- [ ] T079 [US10] Implement trace health endpoint in src/api/observability/trace_health.py
- [ ] T080 [P] [US10] Add lineage tests in tests/integration/test_phoenix_trace_lineage.py
- [ ] T081 [P] [US10] Add error metadata tests in tests/integration/test_trace_error_metadata.py
- [ ] T082 [P] [US10] Add contract tests in tests/contract/test_trace_payload_contract.py

---

## Phase 13: User Story 11 - Promptfoo Evaluation Gates (Priority: P2)

**Goal**: Block deployment when required evaluation quality thresholds fail.

**Independent Test**: Pass/fail Promptfoo runs enforce gate outcomes.

**Pydantic Schemas Required First**:
- src/schemas/eval.py
- src/schemas/errors.py
- src/schemas/observability.py

**Done When Tests Pass**:
- tests/integration/test_promptfoo_gate_enforcement.py
- tests/contract/test_eval_result_contract.py
- tests/security/test_eval_policy_coverage.py

**Security Checkpoint**:
- tests/security/test_pii_redaction_pipeline.py
- tests/security/test_prompt_injection_gate.py
- tests/security/test_tenant_isolation_enforcement.py

- [ ] T083 [P] [US11] Implement eval schemas in src/schemas/eval.py
- [ ] T084 [US11] Implement Promptfoo config in eval/promptfoo/promptfooconfig.yaml
- [ ] T085 [US11] Implement CI gate script in eval/ci/promptfoo_gate.py
- [ ] T086 [P] [US11] Add gate enforcement tests in tests/integration/test_promptfoo_gate_enforcement.py
- [ ] T087 [P] [US11] Add contract tests in tests/contract/test_eval_result_contract.py
- [ ] T088 [P] [US11] Add security coverage tests in tests/security/test_eval_policy_coverage.py

---

## Phase 14: User Story 13 - Honest Copilot Documentation (Priority: P2)

**Goal**: Ensure released documentation is accurate and evidence-backed.

**Independent Test**: Documentation checks fail when claims drift from implementation.

**Pydantic Schemas Required First**:
- src/schemas/errors.py
- src/schemas/eval.py
- src/schemas/observability.py

**Done When Tests Pass**:
- tests/integration/test_docs_claim_consistency.py
- tests/contract/test_error_catalog_doc_sync.py
- tests/security/test_docs_security_claim_evidence.py

**Security Checkpoint**:
- tests/security/test_pii_redaction_pipeline.py
- tests/security/test_prompt_injection_gate.py
- tests/security/test_tenant_isolation_enforcement.py

- [ ] T089 [US13] Implement docs gate script in docs/quality/check_docs_accuracy.py
- [ ] T090 [US13] Publish assistant limitations guide in docs/assistant/limitations-and-fallbacks.md
- [ ] T091 [US13] Publish evidence index in docs/security/evidence-index.md
- [ ] T092 [P] [US13] Add docs consistency tests in tests/integration/test_docs_claim_consistency.py
- [ ] T093 [P] [US13] Add contract sync tests in tests/contract/test_error_catalog_doc_sync.py
- [ ] T094 [P] [US13] Add docs evidence tests in tests/security/test_docs_security_claim_evidence.py

---

## Phase 15: User Story 12 - Knowledge Chunk Governance (Priority: P3)

**Goal**: Manage chunk ingestion/retirement with policy-tag compliance.

**Independent Test**: Ingestion and retirement obey size/tag requirements.

**Pydantic Schemas Required First**:
- src/schemas/rag.py
- src/schemas/errors.py
- src/schemas/common.py

**Done When Tests Pass**:
- tests/contract/test_knowledge_chunk_contract.py
- tests/integration/test_chunk_ingestion_and_retirement.py
- tests/integration/test_chunk_policy_tag_validation.py

**Security Checkpoint**:
- tests/security/test_pii_redaction_pipeline.py
- tests/security/test_prompt_injection_gate.py
- tests/security/test_tenant_isolation_enforcement.py

- [ ] T095 [P] [US12] Implement chunk admin schemas in src/schemas/rag.py
- [ ] T096 [US12] Implement chunk ingestion service in src/rag/chunk_ingestion_service.py
- [ ] T097 [US12] Implement chunk retirement service in src/rag/chunk_retirement_service.py
- [ ] T098 [P] [US12] Add contract tests in tests/contract/test_knowledge_chunk_contract.py
- [ ] T099 [P] [US12] Add integration tests in tests/integration/test_chunk_ingestion_and_retirement.py
- [ ] T100 [P] [US12] Add policy-tag tests in tests/integration/test_chunk_policy_tag_validation.py

---

## Phase 16: Polish and Cross-Cutting Concerns

**Purpose**: Final hardening for performance, reliability, and operational readiness.

- [ ] T101 [P] Implement performance SLO benchmarks in tests/integration/test_performance_slo_benchmarks.py
- [ ] T102 [P] Implement reliability and uptime checks in tests/integration/test_reliability_uptime_targets.py
- [ ] T103 [P] Implement full security regression suite in tests/security/test_full_security_regression.py
- [ ] T104 Implement release readiness report in docs/release/release-readiness-report.md
- [ ] T105 Implement quickstart validation report in docs/runbooks/quickstart-validation-report.md
- [ ] T106 [P] Implement Promptfoo trend report in eval/reports/promptfoo-trend-report.md
- [ ] T107 [P] Implement architecture completion summary in docs/architecture/adr-task-completion-summary.md

---

## Phase 17: User Story 14/15 - LLM Provider Abstraction and External Search Tool (Priority: P1/P2)

**Goal**: Replace keyword-rule generation with a real, swappable LLM call, and
add a governed external (Google/Wikipedia) search tool. Paths match the
actual current repo layout, not Phases 1-16's historical layout.

**Independent Test**: Run `/chat` for a policy question with `LLM_PROVIDER`
set to each of `nvidia_nim`, `gemini`, `openai` and confirm a real
provider-generated answer; ask a non-policy question and confirm
`search_external_knowledge` is invoked only when internal RAG has no match.

**Pydantic Schemas Required First**:
- src/schemas/models.py (extend: `LLMProviderConfig`, `ExternalSearchRequest`, `ExternalSearchResult`)

**Done When Tests Pass**:
- tests/test_llm_client.py
- tests/test_external_search_tool.py
- tests/test_langgraph_nodes.py (updated for real generation + external-tool routing)

**Security Checkpoint**:
- tests/test_pii_redaction.py
- tests/test_prompt_injection.py

- [ ] T108 [P] [US14] Implement `LLMClient` protocol + NVIDIA NIM/Gemini/OpenAI adapters in src/llm/client.py
- [ ] T109 [US14] Wire `classify_intent` and `generate_grounded_answer` in src/agent/graph.py to call `LLMClient.generate` instead of keyword rules/templates
- [ ] T110 [US14] Add `llm_call` Phoenix span (provider, model, latency) in src/observability/tracing.py usage within src/agent/graph.py
- [ ] T111 [P] [US14] Add unit tests for provider selection/failure-to-escalate in tests/test_llm_client.py
- [ ] T112 [P] [US15] Implement `search_external_knowledge` FastMCP tool in src/tools/mcp_server.py
- [ ] T113 [US15] Add routing: call external search only when `retrieve_from_rag` returns no context, in src/agent/graph.py
- [ ] T114 [P] [US15] Add unit tests for the external search tool (success, failure, invalid query) in tests/test_external_search_tool.py
- [ ] T115 [US15] Render external-source tool card in frontend/app.py `render_tool_result`

---

## Dependencies and Execution Order

### Phase Dependencies

- Setup (Phase 1): starts immediately.
- Foundational (Phase 2): depends on setup and blocks all stories.
- Story phases: depend on foundational completion.
- Polish: depends on all targeted stories.

### User Story Completion Order

1. US1 (MVP)
2. US2
3. US3
4. US4
5. US5
6. US6
7. US7
8. US9
9. US8
10. US10
11. US11
12. US13
13. US12

### Security Gate Rule

Every story phase is complete only after all three tests pass:
- tests/security/test_pii_redaction_pipeline.py
- tests/security/test_prompt_injection_gate.py
- tests/security/test_tenant_isolation_enforcement.py

---

## Parallel Opportunities

- Setup tasks T006-T008 run in parallel.
- Foundational tasks T010, T011, T016, T017, T018, T019 run in parallel.
- Story schema and test tasks marked [P] run in parallel.
- Multiple stories can be split across teams after foundational completion.

## Parallel Example: US2

```bash
Task: T027 Implement ChatRequest and ChatStreamEvent schemas in src/schemas/chat.py
Task: T028 Implement ToolCallCard schema in src/schemas/tooling.py
Task: T032 Add contract tests in tests/contract/test_chat_stream_contract.py
Task: T034 Add e2e tests in tests/e2e/test_streaming_toolcard_ui.spec.ts
```

---

## Implementation Strategy

### MVP First

1. Complete Phase 1 and Phase 2.
2. Complete US1 and validate its test/security checkpoints.
3. Demo MVP before expanding scope.

### Incremental Delivery

1. Deliver US2 and US3 for user-facing quality and grounding.
2. Deliver US4, US5, US6, US7, US9 for safety and policy controls.
3. Deliver US8, US10, US11, US13 for operations and governance.
4. Deliver US12 for admin governance enhancements.

### Team Parallelization

1. Product track: US1, US2, US8
2. AI track: US3, US6
3. Security track: US4, US5, US7, US9
4. Reliability/governance track: US10, US11, US13, US12

---

## Notes

- All tasks follow strict checklist format.
- IDs are sequential and execution-oriented.
- Story labels appear only in story phases.
- Each task maps to required path roots: `/src`, `/frontend`, `/eval`, `/tests`, `/docs`.
- Per-story schema prerequisites, done-tests, and security checkpoints are mandatory.
