# Architecture Baseline

## Application style

MateERP is a modular monolith with a single transactional backend boundary.

```text
Browser
  -> Next.js frontend
  -> Django REST API
  -> PostgreSQL
```

The production deployment will sit behind host-native Nginx on MateServer.

## Backend module shape

Future domain apps should prefer:

```text
apps/<domain>/
├── api/
├── models/
├── selectors/
├── services/
└── tests/
```

Business writes belong in services. Complex reads and reports belong in selectors. API views and serializers should remain thin.

## Phase 2 scope

The bootstrap includes only a small `core` app for technical health and API foundation. It intentionally does not introduce organization, identity, ledger, expenses, income, payments, transfers, or other future domains.

## Frontend design baseline

The production frontend is desktop-first and data-first. Normal UI geometry is sharp and uses zero-radius surfaces. Borders are preferred over decorative shadows.
