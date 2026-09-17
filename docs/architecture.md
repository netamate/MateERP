# MateERP architecture

MateERP is a modular monolith with a single transactional PostgreSQL boundary.

```text
Browser
  -> Host Nginx in production
  -> Next.js
  -> Django REST API
  -> PostgreSQL
```

## Backend modules established through Phase 3

### `core`

Cross-cutting application infrastructure such as health checks and request ID propagation.

### `identity`

Owns the UUID user identity, organizations, legal entities, memberships, legal-entity
scope, centralized role/permission policy, session context services, and browser
authentication APIs.

### `audit`

Owns append-only `AuditEvent` records. Financial modules added in later phases must use
this audit foundation for sensitive actions.

## Security boundary

Django is authoritative for authentication, authorization, organization membership,
legal-entity access, and later financial permissions. The Next.js frontend may hide or
disable controls for usability, but it never grants access.

The active organization/legal entity is stored in the server-side session and revalidated
against membership scope before use.

## Future domain modules

Accounting, finance operations, planning, assets, reporting, and other domain apps are
added only in their scheduled phases. They must reuse the Phase 3 identity, scope, RBAC,
and audit foundations rather than implementing parallel security rules.
