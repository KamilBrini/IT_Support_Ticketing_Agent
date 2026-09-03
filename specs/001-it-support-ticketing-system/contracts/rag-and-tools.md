# Contract: ChromaDB Isolation and FastMCP Tools

## ChromaDB Collection Design

### Naming Convention
- `kb_{tenant_id}_{domain}_{version}`
- Example: `kb_tenantA_it-support_v1`

### Metadata Contract
- chunk_id
- tenant_id
- source_doc_id
- source_title
- policy_tags
- active
- revision
- updated_at

### Tenant Isolation Rules
- Query MUST include `tenant_id == request.tenant_id`.
- Query MUST include `active == true`.
- Missing tenant filter fails closed with `ERR-ACL-001`.
- Shared cross-tenant production collections are prohibited.
- Cache keys include tenant_id + policy context + query fingerprint.

### Retrieval Failure Modes
- ERR-RAG-001 no evidence found
- ERR-RAG-002 retrieval timeout
- ERR-ACL-001 tenant filter missing or mismatch
- ERR-VAL-003 missing policy tags
- ERR-VAL-004 oversized chunk payload

## FastMCP Tool Schemas

### lookup_kb_article
Input:
- tenant_id: string
- article_id: string

Output:
- article_id: string
- title: string
- status: enum(active, deprecated)
- policy_tags: list[string]

Failure modes:
- ERR-TOOL-001 unauthorized invocation
- ERR-TOOL-002 runtime failure
- ERR-ACL-001 tenant mismatch

### reset_password_request
Input:
- tenant_id: string
- target_user_id: string
- reason: string
- approval_token: string | null

Output:
- request_id: string
- status: enum(pending_approval, approved, denied, submitted)
- policy_reason: string

Failure modes:
- ERR-TOOL-001 unauthorized role/action
- ERR-VAL-002 invalid arguments
- ERR-SEC-001 safety policy block
- ERR-UPSTREAM-001 dependency unavailable

### create_escalation_ticket
Input:
- tenant_id: string
- source_ticket_id: string
- escalation_reason: string
- severity: enum(low, medium, high, critical)

Output:
- escalation_ticket_id: string
- assigned_queue: string
- created_at: datetime

Failure modes:
- ERR-STATE-001 invalid workflow state
- ERR-TOOL-002 runtime failure
- ERR-UPSTREAM-001 queue service unavailable

## Tool Policy Rules
- Deny-by-default for all tools.
- Role + action + schema validation required.
- Immutable audit logs require tenant_id, actor_id, correlation_id.
- High-risk actions require human approval token.
