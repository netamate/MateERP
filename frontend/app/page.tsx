"use client";

import { AuthGate } from "@/components/auth/auth-gate";
import { AppShell } from "@/components/layout/app-shell";

const foundationItems = [
  ["Identity", "UUID email-based users"],
  ["Scope", "Organization + legal entity"],
  ["Access", "Central RBAC policy"],
  ["Audit", "Append-only security events"],
];

export default function Home() {
  return (
    <AuthGate>
      {({ session, onLogout, onContextChange }) => {
        const membership = session.memberships.find(
          (item) => item.organization_id === session.active_organization_id,
        );
        const organization = session.organizations.find(
          (item) => item.id === session.active_organization_id,
        );
        const legalEntity = session.active_legal_entities.find(
          (item) => item.id === session.active_legal_entity_id,
        );

        return (
          <AppShell
            onContextChange={onContextChange}
            onLogout={onLogout}
            session={session}
          >
            <section className="border-b border-[var(--color-border)] bg-white px-6 py-5">
              <p className="mb-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--color-text-muted)]">
                Phase 3
              </p>
              <div className="flex items-end justify-between gap-6">
                <div>
                  <h1 className="text-2xl font-semibold tracking-tight">
                    Identity, Organization & Security Core
                  </h1>
                  <p className="mt-1 max-w-3xl text-sm text-[var(--color-text-muted)]">
                    Authenticated ERP foundation with server-enforced organization and
                    legal-entity scope, role permissions, and auditable access.
                  </p>
                </div>
                <div className="border border-[var(--color-border)] bg-[var(--color-surface-subtle)] px-3 py-2 text-xs">
                  Role: <strong>{membership?.role ?? "Unscoped"}</strong>
                </div>
              </div>
            </section>

            <section className="grid grid-cols-4 border-b border-[var(--color-border)] bg-white">
              {foundationItems.map(([label, value]) => (
                <div
                  className="border-r border-[var(--color-border)] px-5 py-4 last:border-r-0"
                  key={label}
                >
                  <div className="text-[10px] font-semibold uppercase tracking-[0.1em] text-[var(--color-text-muted)]">
                    {label}
                  </div>
                  <div className="mt-1 text-sm font-semibold">{value}</div>
                </div>
              ))}
            </section>

            <section className="grid grid-cols-2 gap-5 p-6">
              <div className="border border-[var(--color-border)] bg-white">
                <div className="border-b border-[var(--color-border)] px-4 py-3">
                  <h2 className="text-sm font-semibold">Active security context</h2>
                </div>
                <dl className="grid grid-cols-[160px_1fr] text-sm">
                  <dt className="border-b border-r border-[var(--color-border)] bg-[var(--color-surface-subtle)] px-4 py-3 font-semibold">
                    User
                  </dt>
                  <dd className="border-b border-[var(--color-border)] px-4 py-3">
                    {session.user.email}
                  </dd>
                  <dt className="border-b border-r border-[var(--color-border)] bg-[var(--color-surface-subtle)] px-4 py-3 font-semibold">
                    Organization
                  </dt>
                  <dd className="border-b border-[var(--color-border)] px-4 py-3">
                    {organization?.name ?? "Not selected"}
                  </dd>
                  <dt className="border-r border-[var(--color-border)] bg-[var(--color-surface-subtle)] px-4 py-3 font-semibold">
                    Legal entity
                  </dt>
                  <dd className="px-4 py-3">
                    {legalEntity?.name ?? "Organization scope"}
                  </dd>
                </dl>
              </div>

              <div className="border border-[var(--color-border)] bg-white">
                <div className="border-b border-[var(--color-border)] px-4 py-3">
                  <h2 className="text-sm font-semibold">Phase boundary</h2>
                </div>
                <div className="px-4 py-4 text-sm leading-6 text-[var(--color-text-muted)]">
                  Phase 3 establishes identity and authorization only. Financial ledgers,
                  Chart of Accounts, accounting periods, posting, expenses, payments, and
                  balances are intentionally not introduced here.
                </div>
              </div>
            </section>
          </AppShell>
        );
      }}
    </AuthGate>
  );
}
