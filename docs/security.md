# Phase 3 security foundation

MateERP uses Django-backed browser sessions. Authentication cookies are HttpOnly and
state-changing requests are protected by Django CSRF validation.

## Identity

Users use UUID primary keys and authenticate with unique email addresses. User records
are global identities. Access to business data is granted through organization
memberships rather than through flags stored directly on the user.

## Organization and legal-entity scope

A membership belongs to exactly one organization. A membership can either access all
legal entities in that organization or an explicit set of legal entities.

The browser stores the selected organization and legal entity in the server-side Django
session. Backend services revalidate membership and legal-entity access whenever the
active context changes. Frontend state is never authoritative for access control.

## Roles and permissions

Initial roles:

- OWNER
- ADMINISTRATOR
- FINANCE_MANAGER
- APPROVER
- MEMBER
- VIEWER

Permission policy lives in `apps.identity.policy`. Sensitive financial permissions are
declared now so later phases can enforce the same central policy rather than creating
ad hoc role checks.

## Audit

`AuditEvent` is append-only during normal application operation. It stores actor,
organization/legal-entity context, action, object identity, before/after JSON where
appropriate, request ID, IP address, user agent, and timestamp.

## Initial bootstrap

Run the bootstrap command once after migrations. The bootstrap password is read only
from the `MATEERP_BOOTSTRAP_PASSWORD` environment variable and must never be committed.

Example:

```powershell
$env:MATEERP_BOOTSTRAP_PASSWORD = "<set-locally>"
python manage.py bootstrap_instance --email owner@example.com --organization "Example Company"
```

The command is intentionally idempotent once an organization exists.
