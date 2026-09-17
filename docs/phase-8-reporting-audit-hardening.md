# Phase 8 — Reporting, Audit & Enterprise Hardening

Phase 8 is the final MateERP development phase before Production Deployment & Go-Live.
It closes the remaining reporting, control, auditability, notification, reconciliation,
document-integrity, and production-security gaps without creating a second financial source
of truth.

## Enterprise reporting

The `reporting` module exposes read-only, legal-entity-scoped reports derived from posted
accounting and finance records:

- financial overview
- expense detail
- revenue detail
- vendor spend
- product cost from authoritative expense allocations
- cost-center spend from authoritative expense allocations
- account balances
- currency exposure for financial accounts
- founder capital and founder-loan reporting

Existing Trial Balance, Profit & Loss, Balance Sheet, Cash Flow, and Budget vs Actual reports
remain authoritative in their existing accounting/planning modules.

## Account reconciliation

The `reconciliation` module provides statement-based financial-account reconciliation.

- A reconciliation belongs to one legal entity and one financial account.
- Users enter a statement period and native-currency ending balance.
- Eligible posted ledger lines can be cleared against the statement, including older
  outstanding items up to the statement date.
- A journal line can belong to only one reconciliation.
- Bank/cash accounts use debit-minus-credit movement; credit-card accounts use
  credit-minus-debit movement.
- Completion requires an exact zero difference.
- Completed reconciliations and their selected items are immutable.
- Create, item-replacement, and completion actions are audited.

## Audit log

`AuditEvent` remains append-only. Phase 8 adds a read-only paginated API and production UI
with server-side filtering by date, action, object type, actor/request context, and free-text
search. Access requires the dedicated `VIEW_AUDIT_LOG` permission.

## Notifications

The `notifications` module implements targeted in-app alerts without Redis or Celery.
Notifications have separate read and resolved state, are deduplicated per organization/user,
and can be legal-entity scoped.

The idempotent management command below refreshes renewal and approval notifications:

```bash
python manage.py refresh_notifications --horizon-days 30
```

Phase 9 should schedule this command using the chosen production scheduler. The command
creates renewal alerts from the Phase 7 aggregated renewal calendar, creates approval alerts
for submitted expenses and reimbursements, and resolves stale generated notifications.

## Document integrity

Finance documents continue to use Django's storage abstraction. Phase 8 adds one-to-one
integrity metadata with MIME type, byte size, SHA-256 checksum, uploader, and upload time.
New uploads are capped at 25 MB and capture integrity metadata atomically.

Existing documents can be backfilled idempotently:

```bash
python manage.py backfill_document_metadata
```

## Production security hardening

- Production no longer falls back to the local development `DJANGO_SECRET_KEY`.
- `DJANGO_SECRET_KEY` is required when `DJANGO_DEBUG=false`.
- Session and CSRF cookies remain Secure in production.
- `X-Content-Type-Options`, same-origin referrer policy, and clickjacking protection are set.
- SSL redirect and HSTS are environment-controlled so Phase 9 can enable them only after
  HTTPS is verified end-to-end.
- Server-side RBAC permissions cover reporting, audit, notifications, and reconciliation.

## Phase boundary

Phase 8 does not deploy MateERP. Docker/GHCR build-and-deploy automation, MateServer
configuration, production PostgreSQL volume and backup/restore validation, host-native Nginx,
domain/TLS configuration, scheduler installation, production migrations, smoke tests,
rollback validation, and go-live belong to Phase 9.
