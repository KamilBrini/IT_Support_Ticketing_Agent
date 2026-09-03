# Data Model: IT Support Ticketing System

## Entities

### SupportTicket
- ticket_id: string (unique, immutable)
- tenant_id: string (required)
- requester_user_id: string (required)
- title: string (5-180 chars)
- description: string (20-6000 chars)
- category: string
- priority: enum(low, medium, high, critical)
- status: enum(open, in_progress, waiting_user, resolved, closed)
- assigned_queue: string | null
- escalation_level: integer >= 0
- created_at: datetime
- updated_at: datetime

Validation and transitions:
- tenant_id is mandatory.
- Allowed transitions: open->in_progress->waiting_user->in_progress->resolved->closed.
- Invalid transitions return ERR-STATE-002.

### ChatMessage
- message_id: string
- ticket_id: string
- tenant_id: string
- role: enum(user, assistant, tool, system)
- content: string
- citations: list[string]
- tool_call_id: string | null
- redaction_applied: bool
- injection_screened: bool
- created_at: datetime

Validation:
- model-bound assistant/tool content requires redaction_applied=true.

### KnowledgeChunk
- chunk_id: string
- tenant_id: string
- source_doc_id: string
- source_title: string
- content: string
- embedding_vector_ref: string
- policy_tags: list[string]
- active: bool
- revision: int >= 1
- updated_at: datetime

Validation:
- policy_tags cannot be empty (ERR-VAL-003).
- oversized content fails ingestion (ERR-VAL-004).
- inactive chunks are excluded from retrieval.

### MemoryRecord
- memory_id: string
- tenant_id: string
- ticket_id: string | null
- memory_scope: enum(ephemeral, session, ticket)
- key: string
- value: string
- expires_at: datetime | null
- created_at: datetime

Validation:
- ticket scope requires ticket_id.
- expired records are not loaded into active graph state.

## Relationships
- SupportTicket 1..N ChatMessage
- SupportTicket 0..N MemoryRecord
- Tenant 1..N SupportTicket
- Tenant 1..N KnowledgeChunk

## Invariants
- Every query path is tenant-scoped.
- No raw PII reaches model prompts or trace payloads.
- User-visible responses pass structured-output validation before stream finalization.
