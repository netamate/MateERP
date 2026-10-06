# Lean ERP Phase C — Payments, Alerts, and Legacy Cleanup

Phase C completes the MateERP simplification around NetaMate's recurring business costs.

## Subscription workflow

Subscription is the only recurring-cost source of truth.

Each record supports:

- vendor and service type
- amount, currency, and billing cycle
- optional custom day interval
- next payment / renewal date
- payment method and reference
- auto-renew status
- reminder day offsets
- in-app, email, and Hermes reminder channels
- optional email recipient list
- optional Hermes target
- payment / renewal history

## Mark paid

Recording a payment creates an immutable `SubscriptionPayment` history row and advances the subscription's next due date.

Standard cycles use calendar-aware advancement:

- monthly: +1 month
- quarterly: +3 months
- semiannual: +6 months
- annual: +12 months
- custom: +configured day interval

Month-end dates are clipped safely when the following month has fewer days.

## Reminder engine

The daily scheduler scans active subscriptions and only delivers on configured offsets.

Default offsets for existing and new subscriptions are:

`30, 15, 7, 3, 1, 0`

Supported channels:

- in-app
- email through Django SMTP configuration
- Hermes through a webhook event

Hermes receives a clean `mateerp.subscription_reminder` JSON event containing the human-readable title/message and subscription metadata. Scheduler internals and cron job IDs are not included.

## Delivery history

Every channel attempt is recorded in `NotificationDelivery` with:

- channel
- destination
- reminder offset
- due date
- status
- attempt count
- last error
- sent timestamp

Successful deliveries are idempotent for the same subscription, due date, offset, channel, and destination.

## Safe legacy cleanup

Phase B copied Domain and Infrastructure records into Subscription.

Phase C additionally migrates historical `DomainRenewal` rows into `SubscriptionPayment` before removing the legacy:

- DomainRenewal
- Domain
- InfrastructureAsset

tables.

The old frontend Domain and Infrastructure URLs continue redirecting to Subscriptions, so existing bookmarks do not break.

## Configuration

The primary configuration surface is now **Settings → Email / SMTP & Hermes** inside MateERP.

Owners and Administrators can:

- enable or disable SMTP reminders
- set SMTP host, port, mailbox username, password, TLS/SSL, From Name, and From Email
- send a test email
- enable or disable Hermes
- set Hermes webhook URL, token, and default target
- send a test Hermes notification

SMTP passwords and Hermes tokens are encrypted before database storage. They are never returned by the API and audit events only contain masked/configured-state metadata.

Environment variables remain as a bootstrap/fallback path until ERP settings are saved:

- `EMAIL_BACKEND`
- `EMAIL_HOST`
- `EMAIL_PORT`
- `EMAIL_HOST_USER`
- `EMAIL_HOST_PASSWORD`
- `EMAIL_USE_TLS`
- `EMAIL_USE_SSL`
- `DEFAULT_FROM_EMAIL`
- `MATEERP_HERMES_WEBHOOK_URL`
- `MATEERP_HERMES_WEBHOOK_TOKEN`

For encryption, `MATEERP_SETTINGS_ENCRYPTION_KEY` can hold a dedicated Fernet key. If it is not supplied, MateERP derives a stable encryption key from Django `SECRET_KEY`.

If a channel is enabled but its configuration is incomplete or delivery fails, the attempt is recorded as FAILED instead of disappearing silently.
