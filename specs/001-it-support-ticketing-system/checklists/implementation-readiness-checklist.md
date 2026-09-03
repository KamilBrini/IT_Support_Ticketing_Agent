# Implementation Readiness Checklist (Definition of Done)

## Planning and Scope

- [ ] In-scope and out-of-scope boundaries are approved.
- [ ] Open questions are resolved or explicitly deferred with risk acceptance.
- [ ] Dependencies and integration points are documented.

## Architecture and Contracts

- [ ] Backend and frontend architecture align with plan.md.
- [ ] All API data contracts are defined in Pydantic v2 schemas.
- [ ] ERR-* error code catalog is finalized and versioned.

## Security and Compliance

- [ ] PII redaction policy is implemented and validated.
- [ ] Prompt injection controls are implemented for user and KB inputs.
- [ ] Tenant isolation checks are enforced at every data access layer.
- [ ] MCP tool policy is deny-by-default with explicit allow-list.
- [ ] Security event audit logs are immutable and searchable.

## Testing and Quality Gates

- [ ] Unit, integration, contract, and security tests are passing.
- [ ] Positive and negative acceptance scenarios pass for every user story.
- [ ] Promptfoo evaluation threshold is met.
- [ ] No critical or high unresolved vulnerabilities remain.

## Observability and Operations

- [ ] Arize Phoenix traces capture end-to-end workflow lineage.
- [ ] Trace completeness SLO monitoring is configured.
- [ ] Performance and reliability targets (NFR-003, NFR-004) are met.
- [ ] Incident response and rollback runbooks are available.

## Release Decision

- [ ] Requirements checklist fully complete.
- [ ] Stakeholders sign off: Product, Security, Support Operations.
- [ ] Go-live checklist approved with rollback criteria.
