"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import {
  DataTable,
  ErrorState,
  LoadingState,
  MetricStrip,
  PageHeader,
  PermissionNotice,
  type TableColumn,
} from "@/components/ui/erp";
import type { SessionPayload } from "@/lib/api";
import {
  reportingApi,
  type AccountBalanceRow,
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

export function EnterpriseReportingPage({ session }: { session: SessionPayload }) {
  const entity = activeEntity(session);
  const allowed = Boolean(entity) && can(session, "VIEW_REPORTS");
  const [startDate, setStartDate] = useState(firstDayOfYear());
  const [endDate, setEndDate] = useState(today());

  const overview = useQuery({
    queryKey: ["phase8-reporting-overview", entity?.id, startDate, endDate],
    queryFn: () => reportingApi.overview(startDate, endDate),
    enabled: allowed,
  });
  const expenses = useQuery({
    queryKey: ["phase8-report-expenses", entity?.id, startDate, endDate],
    queryFn: () => reportingApi.expenses(startDate, endDate),
    enabled: allowed,
  });
  const revenue = useQuery({
    queryKey: ["phase8-report-revenue", entity?.id, startDate, endDate],
    queryFn: () => reportingApi.revenue(startDate, endDate),
    enabled: allowed,
  });
  const vendors = useQuery({
    queryKey: ["phase8-report-vendors", entity?.id, startDate, endDate],
    queryFn: () => reportingApi.vendorSpend(startDate, endDate),
    enabled: allowed,
  });
  const products = useQuery({
    queryKey: ["phase8-report-products", entity?.id, startDate, endDate],
    queryFn: () => reportingApi.productCost(startDate, endDate),
    enabled: allowed,
  });
  const costCenters = useQuery({
    queryKey: ["phase8-report-cost-centers", entity?.id, startDate, endDate],
    queryFn: () => reportingApi.costCenterSpend(startDate, endDate),
    enabled: allowed,
  });
  const balances = useQuery({
    queryKey: ["phase8-report-balances", entity?.id, endDate],
    queryFn: () => reportingApi.accountBalances(endDate),
    enabled: allowed,
  });
  const currencies = useQuery({
    queryKey: ["phase8-report-currencies", entity?.id, endDate],
    queryFn: () => reportingApi.currencyExposure(endDate),
    enabled: allowed,
  });
  const founders = useQuery({
    queryKey: ["phase8-report-founders", entity?.id, startDate, endDate],
    queryFn: () => reportingApi.founderCapital(startDate, endDate),
    enabled: allowed,
  });

  if (!entity) {
    return <PermissionNotice>Select a legal entity to view enterprise reports.</PermissionNotice>;
  }
  if (!allowed) {
    return <PermissionNotice>You do not have permission to view enterprise reports.</PermissionNotice>;
  }
  if (
    overview.isLoading ||
    expenses.isLoading ||
    revenue.isLoading ||
    vendors.isLoading ||
    products.isLoading ||
    costCenters.isLoading ||
    balances.isLoading ||
    currencies.isLoading ||
    founders.isLoading
  ) {
    return <LoadingState label="Loading enterprise reports..." />;
  }
  const failure = [overview, expenses, revenue, vendors, products, costCenters, balances, currencies, founders].find(
    (query) => query.error,
  );
  if (failure?.error) return <ErrorState message={errorMessage(failure.error)} />;

  const currency = overview.data?.base_currency ?? entity.base_currency;
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

  return (
    <>
      <PageHeader
        eyebrow="Phase 8 · Reporting"
        title="Enterprise Reports"
        description="Ledger-derived financial and management reporting for the active legal entity. No report stores an editable financial balance."
        actions={
          <div className="flex gap-2">
            <input className="erp-field !h-8" aria-label="Report start date" type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} />
            <input className="erp-field !h-8" aria-label="Report end date" type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} />
          </div>
        }
      />
      <MetricStrip
        metrics={[
          { label: "Revenue", value: money(overview.data?.revenue, currency) },
          { label: "Expenses", value: money(overview.data?.expenses, currency) },
          { label: "Net Income", value: money(overview.data?.net_income, currency), tone: Number(overview.data?.net_income ?? 0) >= 0 ? "good" : "bad" },
          { label: "Net Cash Change", value: money(overview.data?.net_cash_change, currency) },
        ]}
      />
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
    </>
  );
}
