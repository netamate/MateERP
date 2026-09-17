"use client";

import {
  Bell,
  ChevronDown,
  LayoutDashboard,
  Plus,
  Search,
  Settings,
  ShieldCheck,
  Users,
} from "lucide-react";
import type { ReactNode } from "react";

import type { SessionPayload } from "@/lib/api";

const navigation = [
  { label: "Overview", icon: LayoutDashboard },
  { label: "Organization", icon: Settings },
  { label: "Members", icon: Users },
  { label: "Security", icon: ShieldCheck },
];

type AppShellProps = {
  children: ReactNode;
  session: SessionPayload;
  onLogout: () => Promise<void>;
  onContextChange: (
    organizationId: string,
    legalEntityId: string | null,
  ) => Promise<void>;
};

export function AppShell({
  children,
  session,
  onLogout,
  onContextChange,
}: AppShellProps) {
  const activeOrganization = session.organizations.find(
    (organization) => organization.id === session.active_organization_id,
  );

  async function changeOrganization(organizationId: string) {
    await onContextChange(organizationId, null);
  }

  async function changeLegalEntity(legalEntityId: string) {
    if (!session.active_organization_id) return;
    await onContextChange(session.active_organization_id, legalEntityId || null);
  }

  return (
    <div className="min-h-screen bg-[var(--color-bg)]">
      <aside className="fixed inset-y-0 left-0 w-[var(--sidebar-width)] border-r border-black/30 bg-[var(--color-sidebar)] text-[var(--color-sidebar-text)]">
        <div className="flex h-[var(--header-height)] items-center border-b border-white/10 px-4">
          <div>
            <div className="text-base font-bold tracking-wide text-white">MateERP</div>
            <div className="text-[10px] uppercase tracking-[0.16em] text-slate-400">
              NetaMate Solutions
            </div>
          </div>
        </div>

        <nav className="p-2" aria-label="Primary navigation">
          <div className="px-2 pb-2 pt-3 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500">
            Identity & Security
          </div>
          {navigation.map(({ label, icon: Icon }, index) => (
            <button
              className={`mb-1 flex w-full items-center gap-3 border px-3 py-2 text-left text-sm ${
                index === 0
                  ? "border-white/10 bg-white/10 text-white"
                  : "border-transparent text-slate-300 hover:border-white/10 hover:bg-white/5"
              }`}
              key={label}
              type="button"
            >
              <Icon size={16} strokeWidth={1.75} />
              {label}
            </button>
          ))}
        </nav>
      </aside>

      <div className="pl-[var(--sidebar-width)]">
        <header className="sticky top-0 z-10 flex h-[var(--header-height)] items-center justify-between border-b border-[var(--color-border)] bg-white px-5">
          <div className="flex items-center gap-2">
            <button
              className="flex h-8 min-w-64 items-center gap-2 border border-[var(--color-border)] bg-[var(--color-surface-subtle)] px-3 text-left text-sm text-[var(--color-text-muted)]"
              type="button"
            >
              <Search size={15} />
              Search MateERP
              <span className="ml-auto border border-[var(--color-border)] bg-white px-1.5 py-0.5 text-[10px]">
                Ctrl K
              </span>
            </button>

            <select
              aria-label="Organization"
              className="h-8 min-w-48 border border-[var(--color-border)] bg-white px-2 text-xs"
              onChange={(event) => void changeOrganization(event.target.value)}
              value={session.active_organization_id ?? ""}
            >
              {session.organizations.map((organization) => (
                <option key={organization.id} value={organization.id}>
                  {organization.name}
                </option>
              ))}
            </select>

            <select
              aria-label="Legal entity"
              className="h-8 min-w-48 border border-[var(--color-border)] bg-white px-2 text-xs"
              disabled={!activeOrganization}
              onChange={(event) => void changeLegalEntity(event.target.value)}
              value={session.active_legal_entity_id ?? ""}
            >
              <option value="">Organization scope</option>
              {session.active_legal_entities.map((entity) => (
                <option key={entity.id} value={entity.id}>
                  {entity.name}
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-center gap-2">
            <button
              className="h-8 border border-[var(--color-border)] bg-white px-3 text-xs font-semibold"
              type="button"
            >
              <span className="flex items-center gap-1.5">
                <Plus size={14} /> Quick Add
              </span>
            </button>
            <button
              className="grid h-8 w-8 place-items-center border border-[var(--color-border)] bg-white"
              aria-label="Notifications"
              type="button"
            >
              <Bell size={15} />
            </button>
            <button
              className="flex h-8 items-center gap-2 border border-[var(--color-border)] bg-white px-2 text-xs"
              onClick={() => void onLogout()}
              title="Sign out"
              type="button"
            >
              {session.user.display_name || session.user.email}
              <ChevronDown size={13} />
            </button>
          </div>
        </header>

        <main>{children}</main>
      </div>
    </div>
  );
}
