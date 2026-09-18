"use client";

import {
  ArrowLeftRight,
  BarChart3,
  Bell,
  BookOpen,
  Boxes,
  Building2,
  CalendarDays,
  ChevronDown,
  CircleDollarSign,
  FileCheck2,
  FileText,
  FolderKanban,
  Landmark,
  LayoutDashboard,
  LogOut,
  Menu,
  PackageOpen,
  Plus,
  ReceiptText,
  Search,
  Settings,
  Users,
  WalletCards,
  X,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useMemo, useState, type ReactNode } from "react";

import { MateERPBrand } from "@/components/brand/mateerp-brand";
import type { SessionPayload } from "@/lib/api";

type NavItem = {
  label: string;
  href: string;
  icon: LucideIcon;
};

type NavGroup = {
  label: string;
  items: NavItem[];
};

const navGroups: NavGroup[] = [
  {
    label: "Overview",
    items: [{ label: "Dashboard", href: "/", icon: LayoutDashboard }],
  },
  {
    label: "Finance",
    items: [
      { label: "Transactions", href: "/transactions", icon: ArrowLeftRight },
      { label: "Expenses", href: "/expenses", icon: ReceiptText },
      { label: "Income", href: "/income", icon: CircleDollarSign },
      { label: "Transfers", href: "/transfers", icon: WalletCards },
      { label: "Financial Accounts", href: "/accounts", icon: Landmark },
      { label: "Reconciliation", href: "/reconciliation", icon: FileCheck2 },
      { label: "Vendors", href: "/vendors", icon: Building2 },
      { label: "Reimbursements", href: "/reimbursements", icon: ReceiptText },
      { label: "Founder Funding", href: "/founder-funding", icon: Landmark },
      { label: "Documents & Approvals", href: "/documents", icon: FileCheck2 },
    ],
  },
  {
    label: "Operations",
    items: [
      { label: "Subscriptions", href: "/operations/subscriptions", icon: PackageOpen },
      { label: "Domains", href: "/operations/domains", icon: FolderKanban },
      { label: "Infrastructure", href: "/operations/infrastructure", icon: Landmark },
      { label: "Renewals", href: "/operations/renewals", icon: CalendarDays },
    ],
  },
  {
    label: "Planning",
    items: [
      { label: "Budgets", href: "/planning/budgets", icon: BarChart3 },
      { label: "Cost Centers", href: "/planning/cost-centers", icon: Building2 },
      { label: "Products", href: "/planning/products", icon: Boxes },
      { label: "Projects", href: "/planning/projects", icon: FileText },
      { label: "Expense Allocations", href: "/planning/allocations", icon: ArrowLeftRight },
    ],
  },
  {
    label: "Accounting & Reporting",
    items: [
      { label: "Chart of Accounts", href: "/accounting/accounts", icon: BookOpen },
      { label: "Journal Entries", href: "/accounting/journals", icon: FileText },
      { label: "Fiscal Periods", href: "/accounting/periods", icon: CalendarDays },
      { label: "Tax & FX", href: "/accounting/configuration", icon: Settings },
      { label: "Financial Statements", href: "/reports", icon: BarChart3 },
      { label: "Enterprise Reports", href: "/reporting", icon: BarChart3 },
    ],
  },
  {
    label: "Administration",
    items: [
      { label: "Members & Access", href: "/administration/members", icon: Users },
      { label: "Audit Log", href: "/administration/audit", icon: FileText },
      { label: "Notifications", href: "/administration/notifications", icon: Bell },
      {
        label: "Document Integrity",
        href: "/administration/document-integrity",
        icon: FileCheck2,
      },
      { label: "Settings", href: "/administration/settings", icon: Settings },
    ],
  },
];

const commandItems: NavItem[] = navGroups.flatMap((group) => group.items);

const quickActions: Array<[string, string]> = [
  ["Expense", "/expenses?new=1"],
  ["Income", "/income?new=1"],
  ["Transfer", "/transfers?new=1"],
  ["Vendor", "/vendors?new=1"],
  ["Reimbursement", "/reimbursements?new=1"],
  ["Founder Funding", "/founder-funding?new=1"],
  ["Finance Document", "/documents?new=1"],
  ["Subscription", "/operations/subscriptions"],
  ["Domain", "/operations/domains"],
  ["Infrastructure Asset", "/operations/infrastructure"],
  ["Budget", "/planning/budgets"],
  ["Reconciliation", "/reconciliation"],
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

export function AppShell({ children, session, onLogout, onContextChange }: AppShellProps) {
  const pathname = usePathname();
  const router = useRouter();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [commandOpen, setCommandOpen] = useState(false);
  const [quickOpen, setQuickOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [query, setQuery] = useState("");

  const activeOrganization = session.organizations.find(
    (organization) => organization.id === session.active_organization_id,
  );
  const activeEntity = session.active_legal_entities.find(
    (entity) => entity.id === session.active_legal_entity_id,
  );
  const activeMembership = session.memberships.find(
    (membership) => membership.organization_id === session.active_organization_id,
  );

  const filteredCommands = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return commandItems;
    return commandItems.filter((item) => item.label.toLowerCase().includes(normalized));
  }, [query]);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setCommandOpen(true);
      }
      if (event.key === "Escape") {
        setCommandOpen(false);
        setQuickOpen(false);
        setUserMenuOpen(false);
        setMobileOpen(false);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  async function changeOrganization(organizationId: string) {
    await onContextChange(organizationId, null);
  }

  async function changeLegalEntity(legalEntityId: string) {
    if (!session.active_organization_id) return;
    await onContextChange(session.active_organization_id, legalEntityId || null);
  }

  function isActive(href: string) {
    if (href === "/") return pathname === "/";
    return pathname === href || pathname.startsWith(`${href}/`);
  }

  function closeNavigationUi() {
    setMobileOpen(false);
    setQuickOpen(false);
    setUserMenuOpen(false);
  }

  const sidebar = (
    <aside className="erp-scrollbar flex h-full w-[var(--sidebar-width)] flex-col overflow-y-auto border-r border-[#202938] bg-[var(--color-sidebar)] text-[var(--color-sidebar-text)]">
      <div className="flex h-[76px] shrink-0 items-center border-b border-[#253044] px-[18px]">
        <MateERPBrand
          className="text-white"
          logoClassName="h-8 w-9 shrink-0"
          subtitle="NetaMate Solutions"
          wordmarkClassName="text-[22px] tracking-[0.04em]"
        />
      </div>

      <div className="border-b border-[#253044] p-3">
        <div className="border border-[#2c374a] bg-[#0d1524] px-3 py-2">
          <div className="truncate text-xs font-semibold text-white">
            {activeOrganization?.name ?? "Select organization"}
          </div>
          <div className="mt-1 truncate text-[10px] uppercase tracking-[0.08em] text-slate-400">
            {activeEntity?.name ?? "Organization scope"}
          </div>
        </div>
      </div>

      <nav className="pb-6" aria-label="Primary navigation">
        {navGroups.map((group) => (
          <div className="pt-3" key={group.label}>
            <div className="px-[17px] pb-1.5 text-[10px] font-bold uppercase tracking-[0.14em] text-[#7f8ba3]">
              {group.label}
            </div>
            {group.items.map(({ label, href, icon: Icon }) => (
              <Link
                className={`flex min-h-9 items-center gap-2.5 border-l-[3px] px-4 py-2 text-[13px] transition-colors ${
                  isActive(href)
                    ? "border-[#2e78ff] bg-[var(--color-sidebar-active)] text-white"
                    : "border-transparent text-[#c5cedd] hover:bg-[#172133] hover:text-white"
                }`}
                href={href}
                key={href}
                onClick={closeNavigationUi}
              >
                <Icon className="shrink-0 text-[#9fb1ca]" size={16} strokeWidth={1.75} />
                {label}
              </Link>
            ))}
          </div>
        ))}
      </nav>
    </aside>
  );

  return (
    <div className="min-h-screen bg-[var(--color-bg)]">
      <div className="fixed inset-y-0 left-0 z-30 hidden lg:block">{sidebar}</div>

      {mobileOpen ? (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            aria-label="Close navigation"
            className="absolute inset-0 bg-black/50"
            onClick={() => setMobileOpen(false)}
            type="button"
          />
          <div className="relative h-full w-[var(--sidebar-width)]">{sidebar}</div>
        </div>
      ) : null}

      <div className="lg:pl-[var(--sidebar-width)]">
        <header className="sticky top-0 z-20 flex min-h-[var(--header-height)] items-center gap-2 border-b border-[var(--color-border)] bg-white px-3 lg:px-[18px]">
          <button
            aria-label="Open navigation"
            className="erp-button !h-8 !min-h-8 !w-8 !p-0 lg:hidden"
            onClick={() => setMobileOpen(true)}
            type="button"
          >
            <Menu size={16} />
          </button>

          <div className="hidden min-w-32 text-xs text-[var(--color-text-muted)] xl:block">
            MateERP / {commandItems.find((item) => isActive(item.href))?.label ?? "Dashboard"}
          </div>

          <button
            className="ml-auto flex h-8 min-w-0 flex-1 items-center gap-2 border border-[var(--color-border)] bg-[#fbfcfd] px-3 text-left text-xs text-[var(--color-text-muted)] sm:max-w-[330px]"
            onClick={() => setCommandOpen(true)}
            type="button"
          >
            <Search size={14} />
            <span className="truncate">Search MateERP...</span>
            <span className="ml-auto hidden border border-[var(--color-border)] bg-white px-1.5 py-0.5 text-[9px] sm:inline">Ctrl K</span>
          </button>

          <select
            aria-label="Organization"
            className="hidden h-8 max-w-48 border border-[var(--color-border)] bg-white px-2 text-xs md:block"
            onChange={(event) => void changeOrganization(event.target.value)}
            value={session.active_organization_id ?? ""}
          >
            {session.organizations.map((organization) => (
              <option key={organization.id} value={organization.id}>{organization.name}</option>
            ))}
          </select>

          <select
            aria-label="Legal entity"
            className="hidden h-8 max-w-48 border border-[var(--color-border)] bg-white px-2 text-xs md:block"
            disabled={!activeOrganization}
            onChange={(event) => void changeLegalEntity(event.target.value)}
            value={session.active_legal_entity_id ?? ""}
          >
            <option value="">Organization scope</option>
            {session.active_legal_entities.map((entity) => (
              <option key={entity.id} value={entity.id}>{entity.name}</option>
            ))}
          </select>

          <div className="relative">
            <button
              className="erp-button erp-button-primary !h-8 !min-h-8"
              onClick={() => setQuickOpen((value) => !value)}
              type="button"
            >
              <Plus size={14} />
              <span className="hidden sm:inline">Add</span>
            </button>
            {quickOpen ? (
              <div className="absolute right-0 top-10 z-40 w-56 border border-[var(--color-border-strong)] bg-white shadow-lg">
                <div className="border-b border-[var(--color-border)] px-3 py-2 text-[10px] font-bold uppercase tracking-[0.1em] text-[var(--color-text-muted)]">Quick Add</div>
                {quickActions.map(([label, href]) => (
                  <Link
                    className="flex items-center gap-2 border-b border-[var(--color-border-soft)] px-3 py-2.5 text-sm last:border-b-0 hover:bg-[var(--color-surface-subtle)]"
                    href={href}
                    key={label}
                    onClick={closeNavigationUi}
                  >
                    <Plus size={13} /> {label}
                  </Link>
                ))}
              </div>
            ) : null}
          </div>

          <Link
            aria-label="Notifications"
            className="erp-button !h-8 !min-h-8 !w-8 !p-0"
            href="/administration/notifications"
          >
            <Bell size={14} />
          </Link>
          <div className="relative">
            <button
              aria-expanded={userMenuOpen}
              aria-haspopup="menu"
              className="erp-button !h-8 !min-h-8 max-w-44"
              onClick={() => {
                setUserMenuOpen((value) => !value);
                setQuickOpen(false);
              }}
              type="button"
            >
              <span className="truncate">{session.user.display_name || session.user.email}</span>
              <ChevronDown
                className={`shrink-0 transition-transform ${userMenuOpen ? "rotate-180" : ""}`}
                size={12}
              />
            </button>

            {userMenuOpen ? (
              <div
                className="absolute right-0 top-10 z-50 w-64 border border-[var(--color-border-strong)] bg-white shadow-lg"
                role="menu"
              >
                <div className="border-b border-[var(--color-border)] px-4 py-3">
                  <div className="truncate text-sm font-semibold text-[var(--color-text)]">
                    {session.user.display_name || "MateERP User"}
                  </div>
                  <div className="mt-1 truncate text-xs text-[var(--color-text-muted)]">
                    {session.user.email}
                  </div>
                  <div className="mt-2 flex items-center gap-2 text-[10px] font-bold uppercase tracking-[0.08em] text-[var(--color-text-muted)]">
                    <span>{activeOrganization?.name ?? "Organization"}</span>
                    {activeMembership?.role ? (
                      <>
                        <span aria-hidden="true">•</span>
                        <span>{activeMembership.role}</span>
                      </>
                    ) : null}
                  </div>
                </div>

                <Link
                  className="flex items-center px-4 py-2.5 text-sm hover:bg-[var(--color-surface-subtle)]"
                  href="/administration/settings"
                  onClick={() => setUserMenuOpen(false)}
                  role="menuitem"
                >
                  <Settings className="mr-2.5 text-[var(--color-text-muted)]" size={15} />
                  Organization settings
                </Link>

                <button
                  className="flex w-full items-center border-t border-[var(--color-border)] px-4 py-2.5 text-left text-sm text-[var(--color-danger)] hover:bg-[#fff6f6]"
                  onClick={() => void onLogout()}
                  role="menuitem"
                  type="button"
                >
                  <LogOut className="mr-2.5" size={15} />
                  Sign out
                </button>
              </div>
            ) : null}
          </div>
        </header>

        <main>{children}</main>
      </div>

      {commandOpen ? (
        <div className="fixed inset-0 z-[70] bg-black/50 px-4 pt-[12vh]" role="presentation">
          <div className="mx-auto max-w-2xl border border-[var(--color-border-strong)] bg-white shadow-2xl">
            <div className="flex items-center border-b border-[var(--color-border)]">
              <Search className="ml-4 text-[var(--color-text-muted)]" size={17} />
              <input
                autoFocus
                className="h-12 flex-1 border-0 px-3 outline-none"
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search pages and actions..."
                value={query}
              />
              <button aria-label="Close search" className="grid h-12 w-12 place-items-center border-l border-[var(--color-border)]" onClick={() => setCommandOpen(false)} type="button"><X size={16} /></button>
            </div>
            <div className="max-h-[55vh] overflow-y-auto py-2">
              <div className="px-4 py-1.5 text-[10px] font-bold uppercase tracking-[0.1em] text-[var(--color-text-muted)]">Navigation</div>
              {filteredCommands.length ? filteredCommands.map((item) => (
                <button
                  className="flex w-full items-center justify-between px-4 py-2.5 text-left text-sm hover:bg-[var(--color-surface-subtle)]"
                  key={item.href}
                  onClick={() => {
                    router.push(item.href);
                    setCommandOpen(false);
                    closeNavigationUi();
                  }}
                  type="button"
                >
                  <span>{item.label}</span>
                  <span className="text-xs text-[var(--color-text-muted)]">Open</span>
                </button>
              )) : (
                <div className="px-4 py-8 text-center text-sm text-[var(--color-text-muted)]">No matching MateERP page.</div>
              )}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
