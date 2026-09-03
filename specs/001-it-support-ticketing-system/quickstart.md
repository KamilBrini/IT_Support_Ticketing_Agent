# Quickstart Validation Guide

## Prerequisites
- Test environment with tenant-scoped auth claims.
- Seeded tenant knowledge collections in ChromaDB.
- Promptfoo and Phoenix endpoints configured.

## Scenario 1: Ticket Create and First Reply
1. Submit valid ticket payload.
2. Verify ticket status is `open`.
3. Verify first reply is generated or safe fallback returned.

Expected:
- Ticket persisted.
- Response path completes with trace correlation.

## Scenario 2: LangGraph Routing by Intent
1. Send a policy question.
2. Send an action request.
3. Send a direct response request.
4. Trigger escalation condition.
5. Trigger blocked condition.

Expected:
- Each request follows intended graph branch.
- Terminal node `update_memory_and_trace` executes.

## Scenario 3: ChromaDB Tenant Isolation
1. Run same query in two tenants.
2. Compare citations and chunk IDs.

Expected:
- No cross-tenant chunk leakage.
- Missing tenant predicate path fails with `ERR-ACL-001`.

## Scenario 4: FastMCP Tool Contract Paths
1. Call `lookup_kb_article` with valid inputs.
2. Call `reset_password_request` as authorized role.
3. Retry with unauthorized role.
4. Call `create_escalation_ticket` from invalid state.

Expected:
- Valid paths succeed.
- Invalid paths return documented ERR-* failures.

## Scenario 5: Promptfoo and Phoenix Gates
1. Execute Promptfoo suite.
2. Run sample workflow and inspect Phoenix traces.
3. Force one failing eval test.

Expected:
- Passing suite allows release path.
- Failing threshold blocks release with `ERR-EVAL-002`.
- Trace lineage includes API, retrieval, tool, model, terminal spans.

## References
- `spec.md`
- `plan.md`
- `data-model.md`
- `contracts/langgraph-workflow.md`
- `contracts/rag-and-tools.md`
