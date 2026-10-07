"use client";

import { useQuery } from "@tanstack/react-query";
import { Download, LineChart, ReceiptText } from "lucide-react";
import { useState } from "react";

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
import type { SessionPayload } from "@/lib/api";
import {
  reportingApi,
  type AccountBalanceRow,
  type CostIntelligenceCurrency,
  type CostIntelligenceMonth,
  type CostIntelligenceSubscription,
  type CostIntelligenceVendor,
  type CurrencyExposureRow,
  type ExpenseReportRow,
  type FounderCapitalRow,
  type RevenueReportRow,
  type SpendRow,
} from "@/lib/phase8-api";

function membership(session: SessionPayload) {
  return session.memberships.find(
    (item) => item.organization_id === session.active_organization_id,
  );
}

function can(session: SessionPayload, permission: string) {
  return membership(session)?.permissions.includes(permission) ?? false;
}

function activeEntity(session: SessionPayload) {
  return session.active_legal_entities.find(
    (entity) => entity.id === session.active_legal_entity_id,
  );
}

function money(value: string | number | undefined, currency: string) {
  const amount = Number(value ?? 0);
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(Number.isFinite(amount) ? amount : 0);
}

function firstDayOfYear() {
  return `${new Date().getFullYear()}-01-01`;
}

function today() {
  return new Date().toISOString().slice(0, 10);
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "Unable to load enterprise reporting.";
}

function totalsLabel(
  rows: CostIntelligenceCurrency[],
  field:
    | "estimated_cost"
    | "current_usage"
    | "actual_billed"
    | "paid"
    | "outstanding"
    | "forecast"
    | "budget",
) {
  if (!rows.length) return "—";
  return rows.map((row) => money(row[field], row.currency)).join(" · ");
}

export function EnterpriseReportingPage({ session }: { session: SessionPayload }) {
  const entity = activeEntity(session);
  const allowed = Boolean(entity) && can(session, "VIEW_REPORTS");
  const [startDate, setStartDate] = useState(firstDayOfYear());
  const [endDate, setEndDate] = useState(today());
  const [mode, setMode] = useState<"financial" | "cost">("financial");

  const overview = useQuery({
    queryKey: ["phase8-reporting-overview", entity?.id, startDate, endDate],
    queryFn: () => reportingApi.overview(startDate, endDate),
    enabled: allowed,
  });
  const expenses = useQuery({
    queryKey: ["phase8-report-expenses", entity?.id, startDate, endDate],
    queryFn: () => reportingApi.expenses(startDate, endDate),
    enabled: allowed && mode === "financial",
  });
  const revenue = useQuery({
    queryKey: ["phase8-report-revenue", entity?.id, startDate, endDate],
    queryFn: () => reportingApi.revenue(startDate, endDate),
    enabled: allowed && mode === "financial",
  });
  const vendors = useQuery({
    queryKey: ["phase8-report-vendors", entity?.id, startDate, endDate],
    queryFn: () => reportingApi.vendorSpend(startDate, endDate),
    enabled: allowed && mode === "financial",
  });
  const products = useQuery({
    queryKey: ["phase8-report-products", entity?.id, startDate, endDate],
    queryFn: () => reportingApi.productCost(startDate, endDate),
    enabled: allowed && mode === "financial",
  });
  const costCenters = useQuery({
    queryKey: ["phase8-report-cost-centers", entity?.id, startDate, endDate],
    queryFn: () => reportingApi.costCenterSpend(startDate, endDate),
    enabled: allowed && mode === "financial",
  });
  const balances = useQuery({
    queryKey: ["phase8-report-balances", entity?.id, endDate],
    queryFn: () => reportingApi.accountBalances(endDate),
    enabled: allowed && mode === "financial",
  });
  const currencies = useQuery({
    queryKey: ["phase8-report-currencies", entity?.id, endDate],
    queryFn: () => reportingApi.currencyExposure(endDate),
    enabled: allowed && mode === "financial",
  });
  const founders = useQuery({
    queryKey: ["phase8-report-founders", entity?.id, startDate, endDate],
    queryFn: () => reportingApi.founderCapital(startDate, endDate),
    enabled: allowed && mode === "financial",
  });
  const cost = useQuery({
    queryKey: ["phase6-cost-intelligence", entity?.id, startDate, endDate],
    queryFn: () => reportingApi.costIntelligence(startDate, endDate),
    enabled: allowed && mode === "cost",
  });

  if (!entity) {
    return <PermissionNotice>Select a legal entity to view enterprise reports.</PermissionNotice>;
  }
  if (!allowed) {
    return <PermissionNotice>You do not have permission to view enterprise reports.</PermissionNotice>;
  }

  const financialQueries = [
    overview,
    expenses,
    revenue,
    vendors,
    products,
    costCenters,
    balances,
    currencies,
    founders,
  ];
  if (
    overview.isLoading
    || (mode === "financial" && financialQueries.some((query) => query.isLoading))
    || (mode === "cost" && cost.isLoading)
  ) {
    return <LoadingState label="Loading enterprise reports..." />;
  }
  const failure =
    mode === "financial"
      ? financialQueries.find((query) => query.error)
      : [overview, cost].find((query) => query.error);
  if (failure?.error) return <ErrorState message={errorMessage(failure.error)} />;

  const currency = overview.data?.base_currency ?? entity.base_currency;
  const costRows = cost.data?.currency_totals ?? [];
  const reconciliation = cost.data?.reconciliation_health;
  const integrationHealth = cost.data?.integration_health;
  const automationHealth = cost.data?.automation_health;

  const expenseColumns: Array<TableColumn<ExpenseReportRow>> = [
    { key: "date", label: "Date", render: (row) => row.date },
    { key: "description", label: "Expense", render: (row) => row.description },
    { key: "vendor", label: "Vendor", render: (row) => row.vendor_name ?? "Unattributed" },
    { key: "account", label: "Account", render: (row) => `${row.account_code} ${row.account_name}` },
    { key: "amount", label: `Base (${currency})`, numeric: true, render: (row) => money(row.base_amount, currency) },
  ];
  const revenueColumns: Array<TableColumn<RevenueReportRow>> = [
    { key: "date", label: "Date", render: (row) => row.date },
    { key: "payer", label: "Payer", render: (row) => row.payer_name || "Unspecified" },
    { key: "description", label: "Revenue", render: (row) => row.description },
    { key: "account", label: "Account", render: (row) => `${row.account_code} ${row.account_name}` },
    { key: "amount", label: `Base (${currency})`, numeric: true, render: (row) => money(row.base_amount, currency) },
  ];
  const vendorColumns: Array<TableColumn<SpendRow>> = [
    { key: "name", label: "Vendor", render: (row) => row.vendor_name ?? "Unknown" },
    { key: "amount", label: `Spend (${currency})`, numeric: true, render: (row) => money(row.base_amount, currency) },
  ];
  const productColumns: Array<TableColumn<SpendRow>> = [
    { key: "name", label: "Product", render: (row) => row.product_name ?? "Unknown" },
    { key: "amount", label: `Allocated Cost (${currency})`, numeric: true, render: (row) => money(row.base_amount, currency) },
  ];
  const costCenterColumns: Array<TableColumn<SpendRow>> = [
    { key: "name", label: "Cost Center", render: (row) => row.cost_center_name ?? "Unknown" },
    { key: "amount", label: `Allocated Spend (${currency})`, numeric: true, render: (row) => money(row.base_amount, currency) },
  ];
  const balanceColumns: Array<TableColumn<AccountBalanceRow>> = [
    { key: "code", label: "Code", render: (row) => row.account_code },
    { key: "name", label: "Account", render: (row) => row.account_name },
    { key: "type", label: "Type", render: (row) => row.account_type },
    { key: "balance", label: `Balance (${currency})`, numeric: true, render: (row) => money(row.natural_balance, currency) },
  ];
  const currencyColumns: Array<TableColumn<CurrencyExposureRow>> = [
    { key: "currency", label: "Currency", render: (row) => row.currency },
    { key: "transaction", label: "Transaction Net", numeric: true, render: (row) => row.transaction_net },
    { key: "base", label: `Base Net (${currency})`, numeric: true, render: (row) => money(row.base_net, currency) },
  ];
  const founderColumns: Array<TableColumn<FounderCapitalRow>> = [
    { key: "founder", label: "Founder", render: (row) => row.founder_name },
    { key: "type", label: "Funding Type", render: (row) => row.funding_type.replaceAll("_", " ") },
    { key: "amount", label: `Base Amount (${currency})`, numeric: true, render: (row) => money(row.base_amount, currency) },
  ];

  const costCurrencyColumns: Array<TableColumn<CostIntelligenceCurrency>> = [
    { key: "currency", label: "Currency", render: (row) => row.currency },
    { key: "estimate", label: "Estimated", numeric: true, render: (row) => money(row.estimated_cost, row.currency) },
    { key: "usage", label: "Current Usage", numeric: true, render: (row) => money(row.current_usage, row.currency) },
    { key: "billed", label: "Actual Billed", numeric: true, render: (row) => money(row.actual_billed, row.currency) },
    { key: "paid", label: "Paid", numeric: true, render: (row) => money(row.paid, row.currency) },
    { key: "outstanding", label: "Outstanding", numeric: true, render: (row) => money(row.outstanding, row.currency) },
    { key: "forecast", label: "Forecast", numeric: true, render: (row) => money(row.forecast, row.currency) },
    { key: "budget", label: "Budget", numeric: true, render: (row) => money(row.budget, row.currency) },
  ];
  const subscriptionColumns: Array<TableColumn<CostIntelligenceSubscription>> = [
    {
      key: "subscription",
      label: "Subscription",
      render: (row) => (
        <div>
          <div className="font-semibold">{row.subscription_name}</div>
          <div className="mt-0.5 text-[11px] text-[var(--color-text-muted)]">
            {row.vendor_name ?? "No vendor"} · {row.subscription_code}
          </div>
        </div>
      ),
    },
    { key: "mode", label: "Mode", render: (row) => <StatusBadge value={row.billing_mode} /> },
    { key: "estimate", label: "Estimated", numeric: true, render: (row) => money(row.estimated_cost, row.currency) },
    { key: "usage", label: "Usage", numeric: true, render: (row) => money(row.current_usage, row.currency) },
    { key: "actual", label: "Billed", numeric: true, render: (row) => money(row.actual_billed, row.currency) },
    { key: "forecast", label: "Forecast", numeric: true, render: (row) => money(row.forecast, row.currency) },
    {
      key: "budget",
      label: "Forecast vs Budget",
      render: (row) => (
        <div>
          <div>{row.budget !== "0" ? money(row.budget, row.currency) : "—"}</div>
          {row.over_budget_forecast ? (
            <div className="text-[11px] font-semibold text-[var(--color-danger)]">
              {money(row.forecast_variance, row.currency)} over
            </div>
          ) : (
            <div className="text-[11px] text-[var(--color-text-muted)]">Within forecast</div>
          )}
        </div>
      ),
    },
  ];
  const costVendorColumns: Array<TableColumn<CostIntelligenceVendor>> = [
    { key: "vendor", label: "Vendor", render: (row) => row.vendor_name },
    { key: "currency", label: "Currency", render: (row) => row.currency },
    { key: "tracked", label: "Tracked Cost", numeric: true, render: (row) => money(row.tracked_cost, row.currency) },
    { key: "billed", label: "Actual Billed", numeric: true, render: (row) => money(row.actual_billed, row.currency) },
    { key: "forecast", label: "Forecast", numeric: true, render: (row) => money(row.forecast, row.currency) },
  ];
  const monthColumns: Array<TableColumn<CostIntelligenceMonth>> = [
    { key: "month", label: "Month", render: (row) => row.month },
    { key: "currency", label: "Currency", render: (row) => row.currency },
    { key: "estimated", label: "Estimated", numeric: true, render: (row) => money(row.estimated_cost, row.currency) },
    { key: "usage", label: "Usage", numeric: true, render: (row) => money(row.current_usage, row.currency) },
    { key: "billed", label: "Billed", numeric: true, render: (row) => money(row.actual_billed, row.currency) },
    { key: "paid", label: "Paid", numeric: true, render: (row) => money(row.paid, row.currency) },
    { key: "forecast", label: "Forecast", numeric: true, render: (row) => money(row.forecast, row.currency) },
  ];

  return (
    <>
      <PageHeader
        eyebrow="Enterprise Intelligence"
        title="Reports"
        description={
          mode === "financial"
            ? "Ledger-derived financial and management reporting for the active legal entity."
            : "Operational cost intelligence across PAYG billing, vendor sync, forecast, reconciliation and automation health."
        }
        actions={
          <div className="flex flex-wrap gap-2">
            <button
              className={`erp-button ${mode === "financial" ? "erp-button-primary" : ""}`}
              onClick={() => setMode("financial")}
              type="button"
            >
              <ReceiptText size={13} /> Financial
            </button>
            <button
              className={`erp-button ${mode === "cost" ? "erp-button-primary" : ""}`}
              onClick={() => setMode("cost")}
              type="button"
            >
              <LineChart size={13} /> Cost Intelligence
            </button>
            <input
              className="erp-field !h-8 !w-auto"
              aria-label="Report start date"
              type="date"
              value={startDate}
              onChange={(event) => setStartDate(event.target.value)}
            />
            <input
              className="erp-field !h-8 !w-auto"
              aria-label="Report end date"
              type="date"
              value={endDate}
              onChange={(event) => setEndDate(event.target.value)}
            />
          </div>
        }
      />

      {mode === "financial" ? (
        <MetricStrip
          metrics={[
            { label: "Revenue", value: money(overview.data?.revenue, currency) },
            { label: "Expenses", value: money(overview.data?.expenses, currency) },
            {
              label: "Net Income",
              value: money(overview.data?.net_income, currency),
              tone: Number(overview.data?.net_income ?? 0) >= 0 ? "good" : "bad",
            },
            { label: "Net Cash Change", value: money(overview.data?.net_cash_change, currency) },
          ]}
        />
      ) : (
        <MetricStrip
          metrics={[
            { label: "Forecast", value: totalsLabel(costRows, "forecast") },
            { label: "Actual Billed", value: totalsLabel(costRows, "actual_billed") },
            { label: "Outstanding", value: totalsLabel(costRows, "outstanding") },
            {
              label: "Operational Health",
              value: String(
                (integrationHealth?.failed ?? 0)
                + (integrationHealth?.stale ?? 0)
                + (automationHealth?.failed_runs_24h ?? 0),
              ),
              note: "Failed/stale integrations + failed automation runs",
              tone:
                (integrationHealth?.failed ?? 0)
                + (integrationHealth?.stale ?? 0)
                + (automationHealth?.failed_runs_24h ?? 0)
                  ? "bad"
                  : "good",
            },
          ]}
        />
      )}

      {mode === "financial" ? (
        <div className="space-y-5 p-4 lg:p-6">
          <section>
            <h2 className="mb-2 text-sm font-semibold">Expense detail</h2>
            <DataTable columns={expenseColumns} rows={expenses.data?.rows ?? []} rowKey={(row) => row.id} />
          </section>
          <section>
            <h2 className="mb-2 text-sm font-semibold">Revenue detail</h2>
            <DataTable columns={revenueColumns} rows={revenue.data?.rows ?? []} rowKey={(row) => row.id} />
          </section>
          <div className="grid gap-5 xl:grid-cols-3">
            <section><h2 className="mb-2 text-sm font-semibold">Vendor spend</h2><DataTable columns={vendorColumns} rows={vendors.data?.rows ?? []} rowKey={(row) => row.vendor_id ?? row.vendor_name ?? row.base_amount} /></section>
            <section><h2 className="mb-2 text-sm font-semibold">Product cost</h2><DataTable columns={productColumns} rows={products.data?.rows ?? []} rowKey={(row) => row.product_id ?? row.product_name ?? row.base_amount} /></section>
            <section><h2 className="mb-2 text-sm font-semibold">Cost center spend</h2><DataTable columns={costCenterColumns} rows={costCenters.data?.rows ?? []} rowKey={(row) => row.cost_center_id ?? row.cost_center_name ?? row.base_amount} /></section>
          </div>
          <section><h2 className="mb-2 text-sm font-semibold">Account balances as of {endDate}</h2><DataTable columns={balanceColumns} rows={balances.data?.rows ?? []} rowKey={(row) => row.account_id} /></section>
          <div className="grid gap-5 xl:grid-cols-2">
            <section><h2 className="mb-2 text-sm font-semibold">Currency exposure</h2><DataTable columns={currencyColumns} rows={currencies.data?.rows ?? []} rowKey={(row) => row.currency} /></section>
            <section><h2 className="mb-2 text-sm font-semibold">Founder capital and loans</h2><DataTable columns={founderColumns} rows={founders.data?.rows ?? []} rowKey={(row) => `${row.founder_name}-${row.funding_type}`} /></section>
          </div>
        </div>
      ) : (
        <div className="space-y-5 p-4 lg:p-6">
          <div className="flex flex-wrap justify-end gap-2">
            {(["subscriptions", "vendors", "monthly"] as const).map((section) => (
              <a
                className="erp-button"
                href={reportingApi.costIntelligenceExportUrl(section, startDate, endDate)}
                key={section}
              >
                <Download size={13} /> {section.replaceAll("_", " ")} CSV
              </a>
            ))}
          </div>

          <section>
            <h2 className="mb-2 text-sm font-semibold">Currency-safe cost position</h2>
            <DataTable
              columns={costCurrencyColumns}
              rows={costRows}
              rowKey={(row) => row.currency}
              emptyTitle="No billing-period cost data in this range"
            />
          </section>

          <div className="grid gap-px border border-[var(--color-border)] bg-[var(--color-border)] md:grid-cols-3">
            <div className="bg-white p-4">
              <div className="erp-label">Invoice Reconciliation</div>
              <div className="mt-2 text-xl font-semibold">
                {reconciliation?.invoice_matched ?? 0}/{reconciliation?.invoice_total ?? 0}
              </div>
              <div className="mt-1 text-xs text-[var(--color-text-muted)]">
                {reconciliation?.invoice_unmatched ?? 0} unmatched · {reconciliation?.invoice_mismatch ?? 0} mismatch
              </div>
            </div>
            <div className="bg-white p-4">
              <div className="erp-label">Payment Reconciliation</div>
              <div className="mt-2 text-xl font-semibold">
                {reconciliation?.payment_matched ?? 0}/{reconciliation?.payment_total ?? 0}
              </div>
              <div className="mt-1 text-xs text-[var(--color-text-muted)]">
                {reconciliation?.payment_unmatched ?? 0} unmatched
              </div>
            </div>
            <div className="bg-white p-4">
              <div className="erp-label">Vendor API Health</div>
              <div className="mt-2 text-xl font-semibold">{integrationHealth?.active ?? 0} active</div>
              <div className="mt-1 text-xs text-[var(--color-text-muted)]">
                {integrationHealth?.failed ?? 0} failed · {integrationHealth?.stale ?? 0} stale · {integrationHealth?.never_synced ?? 0} never synced
              </div>
            </div>
          </div>

          <section>
            <h2 className="mb-2 text-sm font-semibold">Subscription forecast & budget risk</h2>
            <DataTable
              columns={subscriptionColumns}
              rows={cost.data?.subscriptions ?? []}
              rowKey={(row) => row.subscription_id}
              emptyTitle="No subscription billing data in this range"
            />
          </section>
          <div className="grid gap-5 xl:grid-cols-2">
            <section>
              <h2 className="mb-2 text-sm font-semibold">Vendor concentration</h2>
              <DataTable
                columns={costVendorColumns}
                rows={cost.data?.vendors ?? []}
                rowKey={(row) => `${row.vendor_id}-${row.currency}`}
                emptyTitle="No vendor cost data"
              />
            </section>
            <section>
              <h2 className="mb-2 text-sm font-semibold">Monthly cost trend</h2>
              <DataTable
                columns={monthColumns}
                rows={cost.data?.monthly_trend ?? []}
                rowKey={(row) => `${row.month}-${row.currency}`}
                emptyTitle="No monthly cost trend"
              />
            </section>
          </div>
        </div>
      )}
    </>
  );
}
