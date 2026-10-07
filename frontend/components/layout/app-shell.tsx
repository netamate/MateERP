"use client";

import {
  Bell,
  Building2,
  CalendarDays,
  ChevronDown,
  LayoutDashboard,
  LogOut,
  Mail,
  Menu,
  PackageOpen,
  Plus,
  Search,
  Settings,
  Users,
  X,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useMemo, useState, type ReactNode } from "react";

import { MateERPLogoMark } from "@/components/brand/mateerp-brand";
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
    label: "Management",
    items: [
      { label: "Subscriptions", href: "/operations/subscriptions", icon: PackageOpen },
      { label: "Vendors", href: "/vendors", icon: Building2 },
      { label: "Renewals", href: "/operations/renewals", icon: CalendarDays },
    ],
  },
  {
    label: "Alerts & Settings",
    items: [
      { label: "Alerts", href: "/administration/notifications", icon: Bell },
      { label: "Email Notifications", href: "/administration/email-notifications", icon: Mail },
      { label: "Members & Access", href: "/administration/members", icon: Users },
      { label: "Settings", href: "/administration/settings", icon: Settings },
    ],
  },
];

const commandItems: NavItem[] = navGroups.flatMap((group) => group.items);

const quickActions: Array<[string, string]> = [
  ["Subscription", "/operations/subscriptions"],
  ["Vendor", "/vendors?new=1"],
  ["Email Notification", "/administration/email-notifications"],
];

type AppShellProps = {
  children: ReactNode;
  session: SessionPayload;
  onLogout: () => Promise<void>;
};

export function AppShell({ children, session, onLogout }: AppShellProps) {
  const pathname = usePathname();
  const router = useRouter();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [commandOpen, setCommandOpen] = useState(false);
  const [quickOpen, setQuickOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [query, setQuery] = useState("");

  const activeOrganization = session.organizations.find(
    (organization) => organization.id === session.active_organization_id,
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

  function isActive(href: string) {
    if (href === "/") return pathname === "/";
    return pathname === href || pathname.startsWith(`${href}/`);
  }

  function closeNavigationUi() {
    setMobileOpen(false);
    setQuickOpen(false);
    setUserMenuOpen(false);
  }

  const sidebar = (collapsed: boolean) => (
    <aside className="erp-scrollbar flex h-full w-full flex-col overflow-hidden border-r border-[#1C2739] bg-[#0D1523] text-white">
      <div className={`flex h-14 shrink-0 items-center gap-2.5 border-b border-[#1C2739] ${collapsed ? "justify-center px-2" : "px-3.5"}`}>
        <div className="flex h-7 w-7 shrink-0 items-center justify-center border border-[#2A3A54] bg-[#16243B]">
          <MateERPLogoMark className="h-[18px] w-[18px]" />
        </div>
        {!collapsed ? (
          <div className="mateerp-wordmark truncate text-[18px] tracking-[0.04em] text-white">
            MateERP
          </div>
        ) : null}
      </div>

      <nav className="erp-scrollbar min-h-0 flex-1 overflow-y-auto px-2 py-2.5" aria-label="Primary navigation">
        {navGroups.map((group) => (
          <div className="mb-3" key={group.label}>
            {!collapsed ? (
              <div className="px-2 py-1.5 text-[9.5px] font-semibold uppercase tracking-[0.15em] text-[#5C6F8E]">
                {group.label}
              </div>
            ) : null}
            {group.items.map(({ label, href, icon: Icon }) => (
              <Link
                aria-label={label}
                className={`relative mb-px flex h-9 items-center gap-2.5 px-2 text-[12.5px] transition-colors ${isActive(href)
                  ? "bg-[#182437] text-white before:absolute before:inset-y-0 before:left-0 before:w-[3px] before:bg-[#4B85E8]"
                  : "text-[#9FB0CA] hover:bg-[#18243A] hover:text-white"
                }`}
                href={href}
                key={href}
                onClick={closeNavigationUi}
                title={label}
              >
                <Icon className="shrink-0" size={16} strokeWidth={1.7} />
                {!collapsed ? <span className="min-w-0 flex-1 truncate">{label}</span> : null}
              </Link>
            ))}
          </div>
        ))}
      </nav>

      <div className="shrink-0 border-t border-[#1C2739] p-2.5">
        <div className="flex items-center gap-2.5 p-1.5">
          <div className="flex h-7 w-7 shrink-0 items-center justify-center bg-[#1B4DB1] text-[10.5px] font-semibold text-white" aria-hidden="true">
            {(session.user.display_name || session.user.email).trim().charAt(0).toUpperCase()}
          </div>
          {!collapsed ? (
            <div className="min-w-0">
              <div className="truncate text-[12px] font-semibold text-[#E8EDF5]">
                {session.user.display_name || session.user.email}
              </div>
              <div className="truncate text-[10px] uppercase tracking-[0.1em] text-[#6F84A6]">
                {activeMembership?.role ?? "Member"}
              </div>
            </div>
          ) : null}
        </div>
        {!collapsed ? (
          <div className="mt-2 grid grid-cols-2 gap-1">
            <Link
              className="border border-[#27344A] py-1.5 text-center text-[11px] text-[#A8B7CE] hover:text-white"
              href="/administration/settings"
              onClick={closeNavigationUi}
            >
              Settings
            </Link>
            <button
              className="border border-[#27344A] py-1.5 text-center text-[11px] text-[#A8B7CE] hover:text-white"
              onClick={() => void onLogout()}
              type="button"
            >
              Sign out
            </button>
          </div>
        ) : null}
      </div>
    </aside>
  );

  return (
    <div className="min-h-screen bg-[var(--color-bg)]">
      <div className={`fixed inset-y-0 left-0 z-30 hidden lg:block ${sidebarCollapsed ? "w-[60px]" : "w-[232px]"}`}>
        {sidebar(sidebarCollapsed)}
      </div>

      {mobileOpen ? (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            aria-label="Close navigation"
            className="absolute inset-0 bg-black/50"
            onClick={() => setMobileOpen(false)}
            type="button"
          />
          <div className="relative h-full w-[232px]">{sidebar(false)}</div>
        </div>
      ) : null}

      <div className={sidebarCollapsed ? "lg:pl-[60px]" : "lg:pl-[232px]"}>
        <header className="sticky top-0 z-20 flex h-14 min-h-[var(--header-height)] items-center gap-2 border-b border-[#E2E5EB] bg-white px-3 lg:px-4">
          <button
            aria-label="Open navigation"
            className="erp-button !h-8 !min-h-8 !w-8 !p-0 lg:hidden"
            onClick={() => setMobileOpen(true)}
            type="button"
          >
            <Menu size={16} />
          </button>

          <button
            aria-label="Toggle sidebar"
            aria-expanded={!sidebarCollapsed}
            className="hidden h-7 w-7 shrink-0 items-center justify-center border border-[#E2E5EB] text-[#5B6472] lg:flex"
            onClick={() => setSidebarCollapsed((collapsed) => !collapsed)}
            type="button"
          >
            <Menu size={15} />
          </button>
          <div className="hidden min-w-0 items-center gap-1.5 text-[12.5px] lg:flex">
            <span className="hidden text-[#7B8494] xl:inline">MateERP</span>
            <span className="hidden text-[#C3C9D3] xl:inline">/</span>
            <span className="truncate font-semibold">
              {commandItems.find((item) => isActive(item.href))?.label ?? "Dashboard"}
            </span>
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
