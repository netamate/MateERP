"use client";

import { AuthGate } from "@/components/auth/auth-gate";
import { AppShell } from "@/components/layout/app-shell";

const operationItems = [
  ["Payables", "Vendors + expense payments"],
  ["Receipts", "Income + financial accounts"],
  ["Movement", "Transfers + account transactions"],
  ["People", "Founder funding + reimbursements"],
];

const workflows = [
  ["Expense", "Draft → Submitted → Approved/Rejected → Paid"],
  ["Reimbursement", "Draft → Submitted → Approved/Rejected → Paid"],
  ["Income", "Record → Post to ledger"],
  ["Transfer", "Validate base balance → Post to ledger"],
];

export default function Home() {
  return (
    <AuthGate>
      {({ session, onLogout, onContextChange }) => {
        const membership = session.memberships.find(
          (item) => item.organization_id === session.active_organization_id,
        );
        const legalEntity = session.active_legal_entities.find(
          (item) => item.id === session.active_legal_entity_id,
        );

        return (
          <AppShell onContextChange={onContextChange} onLogout={onLogout} session={session}>
            <section className="border-b border-[var(--color-border)] bg-white px-6 py-5">
              <p className="mb-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--color-text-muted)]">
                Phase 5
              </p>
              <div className="flex items-end justify-between gap-6">
                <div>
                  <h1 className="text-2xl font-semibold tracking-tight">
                    Core Finance Operations
                  </h1>
                  <p className="mt-1 max-w-3xl text-sm text-[var(--color-text-muted)]">
                    Day-to-day finance workflows for vendors, expenses, income, transfers,
                    founder funding, reimbursements, approvals, and supporting documents,
                    all backed by the Phase 4 double-entry ledger.
                  </p>
                </div>
                <div className="border border-[var(--color-border)] bg-[var(--color-surface-subtle)] px-3 py-2 text-xs">
                  Role: <strong>{membership?.role ?? "Unscoped"}</strong>
                </div>
              </div>
            </section>

            <section className="grid grid-cols-4 border-b border-[var(--color-border)] bg-white">
              {operationItems.map(([label, value]) => (
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
                  <h2 className="text-sm font-semibold">Active finance context</h2>
                </div>
                <dl className="grid grid-cols-[160px_1fr] text-sm">
                  <dt className="border-b border-r border-[var(--color-border)] bg-[var(--color-surface-subtle)] px-4 py-3 font-semibold">
                    Legal entity
                  </dt>
                  <dd className="border-b border-[var(--color-border)] px-4 py-3">
                    {legalEntity?.name ?? "Select a legal entity"}
                  </dd>
                  <dt className="border-r border-[var(--color-border)] bg-[var(--color-surface-subtle)] px-4 py-3 font-semibold">
                    Base currency
                  </dt>
                  <dd className="px-4 py-3">{legalEntity?.base_currency ?? "—"}</dd>
                </dl>
              </div>

              <div className="border border-[var(--color-border)] bg-white">
                <div className="border-b border-[var(--color-border)] px-4 py-3">
                  <h2 className="text-sm font-semibold">Ledger integration</h2>
                </div>
                <div className="px-4 py-4 text-sm leading-6 text-[var(--color-text-muted)]">
                  Operational finance records do not maintain a second accounting balance.
                  Approved and posted events create balanced Phase 4 journals, so fiscal-period
                  controls, legal-entity scope, immutable postings, reversals, and financial
                  reports continue to use one ledger truth.
                </div>
              </div>
            </section>

            <section className="px-6 pb-6">
              <div className="border border-[var(--color-border)] bg-white">
                <div className="border-b border-[var(--color-border)] px-4 py-3">
                  <h2 className="text-sm font-semibold">Operational workflows</h2>
                </div>
                <div className="divide-y divide-[var(--color-border)]">
                  {workflows.map(([name, flow]) => (
                    <div className="grid grid-cols-[180px_1fr] text-sm" key={name}>
                      <div className="bg-[var(--color-surface-subtle)] px-4 py-3 font-semibold">
                        {name}
                      </div>
                      <div className="px-4 py-3 text-[var(--color-text-muted)]">{flow}</div>
                    </div>
                  ))}
                </div>
              </div>
            </section>
          </AppShell>
        );
      }}
    </AuthGate>
  );
}
