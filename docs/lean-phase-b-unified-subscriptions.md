# Lean ERP Phase B — Unified Subscriptions

Phase B makes `Subscription` the single source of truth for NetaMate recurring business costs.

## Unified record

Every recurring cost is represented by one subscription with:

- vendor
- name
- type: Domain, VPS / Server, Cloud, Hosting, SaaS / Software, API / Usage Service, Storage / Backup, Email Service, AI Service, or Other
- amount and currency
- billing cycle
- start date
- next payment / renewal date
- auto-renew status
- payment method
- reference / account ID
- description and notes
- active / archived status

## Safe legacy migration

Migration `operations.0002_unify_recurring_items` preserves existing data before removing the accounting/planning fields from Subscription.

- existing Subscription categories are normalized into the new type field
- existing Financial Account labels are copied to the plain payment-method field when available
- Domain rows are migrated into annual Domain subscriptions
- InfrastructureAsset rows are migrated into typed subscriptions
- an exact-name match is enriched instead of duplicated
- legacy Domain, InfrastructureAsset, and DomainRenewal tables remain in place during this phase as a safety/history buffer

## Runtime source of truth

The active product/API no longer creates separate domain or infrastructure records.

- public operations API exposes subscriptions and renewals
- legacy domain and infrastructure frontend URLs redirect to Subscriptions
- renewal calendar reads only Subscription
- renewal notifications read only the unified renewal calendar
- finance approval notifications are no longer part of the scheduled renewal refresh

Legacy models can be removed in the final cleanup phase after the unified path is validated.
