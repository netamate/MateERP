# Phase 3: Identity, Organization & Security Core

Phase 3 establishes the security boundary required before financial data is introduced.

Implemented foundations:

- UUID email-based user identity
- organization model
- legal-entity model
- organization membership
- explicit legal-entity membership scope
- centralized role and permission policy
- Django session authentication
- CSRF bootstrap/login/logout/session APIs
- server-side active organization/legal-entity context
- member role and scope administration services
- append-only audit event model
- request ID propagation
- initial instance bootstrap command
- frontend authenticated session gate and context selector
- backend tests for RBAC, scope isolation, API session behavior, and audit immutability

Phase 3 deliberately does not introduce Chart of Accounts, journals, accounting periods,
expenses, income, payments, transfers, balances, or financial posting behavior. Those
remain Phase 4 and later work.
