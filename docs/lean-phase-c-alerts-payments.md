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

Secrets remain environment-driven.

Email:

- `EMAIL_BACKEND`
- `EMAIL_HOST`
- `EMAIL_PORT`
- `EMAIL_HOST_USER`
- `EMAIL_HOST_PASSWORD`
- `EMAIL_USE_TLS`
- `EMAIL_USE_SSL`
- `DEFAULT_FROM_EMAIL`

Hermes:

- `MATEERP_HERMES_WEBHOOK_URL`
- `MATEERP_HERMES_WEBHOOK_TOKEN`

If Hermes is enabled on a subscription but the webhook is not configured, the attempt is recorded as FAILED instead of disappearing silently.
