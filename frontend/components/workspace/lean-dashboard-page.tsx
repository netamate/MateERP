"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import {
  DataTable,
  ErrorState,
  LoadingState,
  MetricStrip,
  PageHeader,
  PermissionNotice,
  StatusBadge,
  type TableColumn,
} from "@/components/ui/erp";
import {
  operationsApi,
  type RenewalItem,
  type SessionPayload,
  type Subscription,
} from "@/lib/api";

function activeMembership(session: SessionPayload) {
  return session.memberships.find(
    (membership) => membership.organization_id === session.active_organization_id,
  );
}

function can(session: SessionPayload, permission: string) {
  return activeMembership(session)?.permissions.includes(permission) ?? false;
}

function activeEntity(session: SessionPayload) {
  return session.active_legal_entities.find(
    (entity) => entity.id === session.active_legal_entity_id,
  );
}

function dateString(date: Date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function shortDate(value: string) {
  return new Intl.DateTimeFormat("en-US", {
    year: "numeric",
    month: "short",
    day: "2-digit",
  }).format(new Date(`${value}T00:00:00`));
}

function money(value: string, currency: string) {
  const amount = Number(value);
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(Number.isFinite(amount) ? amount : 0);
}

function monthlyEquivalent(subscription: Subscription) {
  const amount = Number(subscription.amount);
  if (!Number.isFinite(amount)) return 0;
  switch (subscription.billing_cycle) {
    case "MONTHLY":
      return amount;
    case "QUARTERLY":
      return amount / 3;
    case "SEMIANNUAL":
      return amount / 6;
    case "ANNUAL":
      return amount / 12;
    default:
      return 0;
  }
}

function spendSummary(subscriptions: Subscription[]) {
  const totals = new Map<string, number>();
  for (const subscription of subscriptions) {
    if (subscription.status !== "ACTIVE") continue;
    const monthly = monthlyEquivalent(subscription);
    if (!monthly) continue;
    totals.set(subscription.currency, (totals.get(subscription.currency) ?? 0) + monthly);
  }
  if (!totals.size) return "—";
  return Array.from(totals.entries())
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([currency, value]) => money(String(value), currency))
    .join(" · ");
}

export function LeanDashboardPage({ session }: { session: SessionPayload }) {
  const entity = activeEntity(session);
  const allowed = can(session, "VIEW_OPERATIONS");

  const today = new Date();
  const end = new Date(today);
  end.setDate(end.getDate() + 30);

  const subscriptions = useQuery({
    queryKey: ["subscriptions", entity?.id],
    queryFn: operationsApi.subscriptions,
    enabled: Boolean(entity && allowed),
  });
  const renewals = useQuery({
    queryKey: ["renewals", entity?.id, "dashboard-30"],
    queryFn: () => operationsApi.renewals(dateString(today), dateString(end)),
    enabled: Boolean(entity && allowed),
  });

  if (!entity) {
    return <PermissionNotice>Select a legal entity to view the subscription dashboard.</PermissionNotice>;
  }
  if (!allowed) {
    return <PermissionNotice>You do not have permission to view subscriptions and renewals.</PermissionNotice>;
  }
  if (subscriptions.isLoading || renewals.isLoading) {
    return <LoadingState label="Loading subscription overview..." />;
  }
  if (subscriptions.error || renewals.error) {
    const error = subscriptions.error ?? renewals.error;
    return <ErrorState message={error instanceof Error ? error.message : "Unable to load dashboard."} />;
  }

  const activeSubscriptions = (subscriptions.data ?? []).filter((item) => item.status === "ACTIVE");
  const autoRenew = activeSubscriptions.filter((item) => item.auto_renew).length;
  const vendorCount = new Set(activeSubscriptions.map((item) => item.vendor_name).filter(Boolean)).size;
  const upcoming = renewals.data ?? [];

  const columns: Array<TableColumn<RenewalItem>> = [
    {
      key: "name",
      label: "Subscription",
      render: (row) => (
        <div>
          <div className="font-semibold">{row.name}</div>
          <div className="text-[11px] text-[var(--color-text-muted)]">
            {row.vendor_name || "No vendor"} · {row.source_type.toLowerCase()}
          </div>
        </div>
      ),
    },
    { key: "date", label: "Next Payment", render: (row) => shortDate(row.renewal_date) },
    {
      key: "renew",
      label: "Auto Renew",
      render: (row) => <StatusBadge value={row.auto_renew ? "ON" : "OFF"} />,
    },
    {
      key: "amount",
      label: "Amount",
      numeric: true,
      render: (row) => money(row.amount, row.currency),
    },
  ];

  return (
    <>
      <PageHeader
        eyebrow="Overview"
        title="Dashboard"
        description="A focused view of NetaMate subscriptions, recurring costs, and upcoming renewal dates."
        actions={
          <Link className="erp-button erp-button-primary" href="/operations/subscriptions">
            Manage Subscriptions
          </Link>
        }
      />
      <MetricStrip
        metrics={[
          { label: "Active Subscriptions", value: String(activeSubscriptions.length) },
          { label: "Monthly Estimate", value: spendSummary(activeSubscriptions), note: "Grouped by currency" },
          { label: "Due in 30 Days", value: String(upcoming.length), tone: upcoming.length ? "bad" : "good" },
          { label: "Auto Renew", value: String(autoRenew), note: `${vendorCount} vendors in use` },
        ]}
      />
      <div className="space-y-4 p-4 lg:p-6">
        <section>
          <div className="mb-3 flex items-center justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold">Upcoming Payments & Renewals</h2>
              <p className="mt-0.5 text-xs text-[var(--color-text-muted)]">
                Next 30 days from the existing renewal records.
              </p>
            </div>
            <Link className="erp-button" href="/operations/renewals">View All</Link>
          </div>
          <DataTable
            columns={columns}
            rows={upcoming.slice(0, 8)}
            rowKey={(row) => `${row.source_type}:${row.source_id}:${row.renewal_date}`}
            emptyTitle="Nothing due in the next 30 days"
            emptyDescription="Upcoming subscription payments and renewals will appear here."
          />
        </section>
      </div>
    </>
  );
}
