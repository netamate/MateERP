import { AppShell } from "@/components/layout/app-shell";

const foundationItems = [
  ["Backend", "Django REST API foundation"],
  ["Frontend", "Next.js App Router foundation"],
  ["Database", "PostgreSQL development service"],
  ["API contract", "OpenAPI schema baseline"],
];

export default function Home() {
  return (
    <AppShell>
      <section className="border-b border-[var(--color-border)] bg-white px-6 py-5">
        <p className="mb-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--color-text-muted)]">
          Phase 2
        </p>
        <div className="flex items-end justify-between gap-6">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Engineering Foundation</h1>
            <p className="mt-1 max-w-3xl text-sm text-[var(--color-text-muted)]">
              Production monorepo bootstrap for MateERP. Business modules are intentionally not implemented in this phase.
            </p>
          </div>
          <div className="border border-[var(--color-border)] bg-[var(--color-surface-subtle)] px-3 py-2 text-xs">
            Status: <strong>Bootstrap</strong>
          </div>
        </div>
      </section>

      <section className="grid grid-cols-4 border-b border-[var(--color-border)] bg-white">
        {foundationItems.map(([label, value]) => (
          <div className="border-r border-[var(--color-border)] px-5 py-4 last:border-r-0" key={label}>
            <div className="text-[10px] font-semibold uppercase tracking-[0.1em] text-[var(--color-text-muted)]">{label}</div>
            <div className="mt-1 text-sm font-semibold">{value}</div>
          </div>
        ))}
      </section>

      <section className="p-6">
        <div className="border border-[var(--color-border)] bg-white">
          <div className="border-b border-[var(--color-border)] px-4 py-3">
            <h2 className="text-sm font-semibold">Phase boundary</h2>
          </div>
          <div className="px-4 py-4 text-sm leading-6 text-[var(--color-text-muted)]">
            The application shell, design system baseline, API infrastructure, database wiring, testing, linting, and CI belong here. Organization, security roles, accounting, expenses, income, payments, transfers, reporting, and operational modules begin only in their scheduled phases.
          </div>
        </div>
      </section>
    </AppShell>
  );
}
