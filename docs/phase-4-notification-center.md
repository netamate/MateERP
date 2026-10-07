# Phase 4 — Notification Center, Alert Rules, and Scheduling

Phase 4 centralizes operational alerts in MateERP without creating a second notification stack. Existing subscription reminder behavior remains compatible while PAYG billing and reconciliation signals use the same delivery engine.

## Notification Center

The Administration → Notification Center page has three views:

- **Inbox** — active and resolved in-app alerts with signal, severity, state, source link, read, and dismiss actions.
- **Alert Rules** — organization defaults plus optional legal-entity overrides, schedules, delivery channels, audiences, and last-run health.
- **Delivery History** — In-App, Email, and Hermes attempts with source metadata, status, error details, and manual retry for failed attempts.

The global notification bell shows the unread count. The shell query uses a short stale window rather than aggressive polling.

## Supported signals

1. **RENEWAL_DUE**
   - Existing subscription renewal behavior is preserved.
   - By default the rule respects each subscription's reminder offsets, In-App/Email/Hermes toggles, recipients, and Hermes target.
   - PAYG subscriptions show estimated cost rather than presenting an uncertain amount as a fixed bill.

2. **BUDGET_THRESHOLD**
   - Applies to active PAYG billing periods with a monthly budget.
   - Tracked cost is the greater of current usage cost and non-void actual invoice total.
   - One idempotent event is created for each configured threshold reached on the subscription (for example 50%, 80%, and 100%).
   - Threshold alerts resolve automatically if the condition is no longer active.

3. **MISSING_INVOICE**
   - Detects ended billing periods that still have no non-void vendor invoice after the configured grace period.
   - Resolves automatically when an invoice is recorded.

4. **INVOICE_OVERDUE**
   - Detects non-paid/non-void vendor invoices with an outstanding allocation balance after the due date and grace period.
   - Severity escalates to Critical when the invoice is at least seven days overdue.

5. **RECONCILIATION_NEEDED**
   - Detects invoices with no accounting expense or an amount/currency mismatch.
   - Detects operational billing payments that have not been matched to an accounting expense payment.
   - Resolves when reconciliation is completed.

## Rule scope and precedence

MateERP creates one organization-level default for each supported signal. A legal entity can have one override for the same signal.

When an entity override exists, it takes precedence over the organization default for that signal. A disabled entity override therefore intentionally suppresses that organization rule for that entity.

Rule configuration includes:

- enabled state
- severity
- hourly or daily cadence
- daily schedule hour
- IANA timezone
- In-App / Email / Hermes channels
- selected in-app users (blank means all members with notification access in scope)
- explicit email recipients (blank falls back to the selected/viewer member emails)
- Hermes target
- renewal offsets
- grace days
- renewal compatibility mode that respects per-subscription channel settings

## Scheduling

The production systemd timer invokes the refresh command hourly:

```text
OnCalendar=hourly
Persistent=true
RandomizedDelaySec=5m
```

The command itself does not blindly deliver every hour. Each rule enforces its own cadence:

- **HOURLY** — at most once per local clock hour.
- **DAILY** — once per local date after the configured schedule hour.
- `--force` — bypasses scheduling for administrative testing or the UI **Run Rules Now** action.

Because the timer is persistent, a server restart can catch up without needing a second scheduler.

## Delivery idempotency and retries

Each event/channel/destination combination gets a deterministic delivery key. Re-running the engine therefore does not send the same event again after a successful delivery.

Failed deliveries retain:

- channel and destination
- signal and source
- attempt count
- last error
- timestamps

Administrators with `MANAGE_NOTIFICATIONS` can retry a failed delivery from Delivery History. Successful deliveries are not retried.

## Automatic resolution

In-app alerts represent current operational conditions rather than permanent noise. When a condition disappears, the evaluator marks its corresponding notification resolved. Resolved history remains queryable from Notification Center.

## Permissions

- `VIEW_NOTIFICATIONS` — read Notification Center and notification history.
- `MANAGE_NOTIFICATIONS` — configure rules, create legal-entity overrides, run rules immediately, and retry failed deliveries.

Owner and Administrator roles receive all permissions. Finance Manager includes notification management.

## Integration settings

Email and Hermes transport credentials continue to use the existing encrypted organization integration settings. Alert rules select *when, what, and to whom* to deliver; transport settings define *how MateERP connects* to SMTP or Hermes.

Secrets are never returned by the alert-rule APIs or stored in alert delivery context.

## Release boundary

Phase 4 is developed and validated on `feature/phase-4-notification-center-alerts` and integrated only into `integration/finance-operations-roadmap`. It does not update `main` or Production until the full roadmap review is complete.
