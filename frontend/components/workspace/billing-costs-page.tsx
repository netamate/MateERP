"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  Ban,
  CircleDollarSign,
  Gauge,
  Link2,
  Pencil,
  Plus,
  ReceiptText,
  WalletCards,
  X,
} from "lucide-react";
import { useSearchParams } from "next/navigation";
import { useMemo, useState, type FormEvent, type ReactNode } from "react";

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
  financeApi,
  operationsApi,
  request,
  type BillingPayment,
  type BillingPeriod,
  type Expense,
  type SessionPayload,
  type SubscriptionInvoice,
} from "@/lib/api";

type DocumentOption = {
  id: string;
  document_type: string;
  document_date: string;
  standardized_name: string;
  vendor: string | null;
  subscription: string | null;
  expense: string | null;
};

type Editor =
  | { kind: "period"; current?: BillingPeriod }
  | { kind: "invoice"; current?: SubscriptionInvoice }
  | { kind: "payment"; current?: BillingPayment }
  | { kind: "allocate"; current: BillingPayment }
  | null;

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
    (item) => item.id === session.active_legal_entity_id,
  );
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "The request could not be completed.";
}

function money(value: string | number | null | undefined, currency: string) {
  const amount = Number(value ?? 0);
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(Number.isFinite(amount) ? amount : 0);
}

function shortDate(value: string | null | undefined) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en-US", { dateStyle: "medium" }).format(
    new Date(`${value}T00:00:00`),
  );
}

function today() {
  return new Date().toISOString().slice(0, 10);
}

function monthBounds() {
  const now = new Date();
  const start = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), 1));
  const end = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() + 1, 0));
  return {
    start: start.toISOString().slice(0, 10),
    end: end.toISOString().slice(0, 10),
  };
}

function Overlay({
  title,
  description,
  onClose,
  children,
}: {
  title: string;
  description: string;
  onClose: () => void;
  children: ReactNode;
}) {
  return (
    <div className="fixed inset-0 z-[90] flex items-start justify-center overflow-y-auto bg-black/55 px-3 py-[6vh]">
      <section className="w-full max-w-4xl border border-[var(--color-border-strong)] bg-white shadow-2xl">
        <header className="flex items-start justify-between gap-4 border-b border-[var(--color-border)] px-5 py-4">
          <div>
            <h2 className="text-lg font-semibold">{title}</h2>
            <p className="mt-1 text-xs text-[var(--color-text-muted)]">{description}</p>
          </div>
          <button
            aria-label="Close"
            className="erp-button !h-8 !min-h-8 !w-8 !p-0"
            onClick={onClose}
            type="button"
          >
            <X size={14} />
          </button>
        </header>
        {children}
      </section>
    </div>
  );
}

function Field({
  label,
  name,
  defaultValue,
  type = "text",
  required = false,
  step,
  readOnly = false,
}: {
  label: string;
  name: string;
  defaultValue?: string | number | null;
  type?: string;
  required?: boolean;
  step?: string;
  readOnly?: boolean;
}) {
  return (
    <label className="block text-xs font-medium">
      <span className="mb-1 block text-[var(--color-text-muted)]">{label}</span>
      <input
        className="erp-field"
        defaultValue={defaultValue ?? ""}
        name={name}
        readOnly={readOnly}
        required={required}
        step={step}
        type={type}
      />
    </label>
  );
}

function formatCurrencyTotals(
  rows: Array<{ currency: string; [key: string]: string }>,
  field: string,
) {
  if (!rows.length) return "—";
  return rows
    .map((row) => money(row[field], row.currency))
    .join(" · ");
}

export function BillingCostsPage({ session }: { session: SessionPayload }) {
  const params = useSearchParams();
  const entity = activeEntity(session);
  const canView = can(session, "VIEW_OPERATIONS");
  const canManage = can(session, "MANAGE_OPERATIONS");
  const queryClient = useQueryClient();
  const initialSubscription = params.get("subscription") ?? "";

  const [tab, setTab] = useState<"periods" | "invoices" | "payments" | "trend">("periods");
  const [editor, setEditor] = useState<Editor>(null);
  const [subscriptionFilter, setSubscriptionFilter] = useState(initialSubscription);
  const [statusFilter, setStatusFilter] = useState("");
  const [invoicePeriodId, setInvoicePeriodId] = useState("");
  const [paymentSubscriptionId, setPaymentSubscriptionId] = useState("");
  const [invoiceSubtotal, setInvoiceSubtotal] = useState("0");
  const [invoiceTax, setInvoiceTax] = useState("0");

  const summary = useQuery({
    queryKey: ["billing-summary", entity?.id],
    queryFn: operationsApi.billingSummary,
    enabled: Boolean(entity && canView),
  });
  const periods = useQuery({
    queryKey: ["billing-periods", entity?.id],
    queryFn: operationsApi.billingPeriods,
    enabled: Boolean(entity && canView),
  });
  const invoices = useQuery({
    queryKey: ["billing-invoices", entity?.id],
    queryFn: operationsApi.billingInvoices,
    enabled: Boolean(entity && canView),
  });
  const payments = useQuery({
    queryKey: ["billing-payments", entity?.id],
    queryFn: operationsApi.billingPayments,
    enabled: Boolean(entity && canView),
  });
  const subscriptions = useQuery({
    queryKey: ["subscriptions", entity?.id],
    queryFn: operationsApi.subscriptions,
    enabled: Boolean(entity && canView),
  });
  const accounts = useQuery({
    queryKey: ["financial-accounts", entity?.id],
    queryFn: financeApi.accounts,
    enabled: Boolean(entity && canView),
  });
  const expenses = useQuery({
    queryKey: ["expenses", entity?.id],
    queryFn: financeApi.expenses,
    enabled: Boolean(entity && canView),
  });
  const documents = useQuery({
    queryKey: ["billing-document-options", entity?.id],
    queryFn: () => request<DocumentOption[]>("/api/v1/finance/documents/"),
    enabled: Boolean(entity && canView),
  });

  const refresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["billing-summary", entity?.id] }),
      queryClient.invalidateQueries({ queryKey: ["billing-periods", entity?.id] }),
      queryClient.invalidateQueries({ queryKey: ["billing-invoices", entity?.id] }),
      queryClient.invalidateQueries({ queryKey: ["billing-payments", entity?.id] }),
    ]);
  };

  const savePeriod = useMutation({
    mutationFn: ({ id, body }: { id?: string; body: Record<string, unknown> }) =>
      id
        ? operationsApi.updateBillingPeriod(id, body)
        : operationsApi.createBillingPeriod(body),
    onSuccess: async () => {
      setEditor(null);
      await refresh();
    },
  });

  const saveInvoice = useMutation({
    mutationFn: ({ id, body }: { id?: string; body: Record<string, unknown> }) =>
      id
        ? operationsApi.updateBillingInvoice(id, body)
        : operationsApi.createBillingInvoice(body),
    onSuccess: async () => {
      setEditor(null);
      await refresh();
    },
  });

  const voidInvoice = useMutation({
    mutationFn: operationsApi.voidBillingInvoice,
    onSuccess: refresh,
  });

  const savePayment = useMutation({
    mutationFn: operationsApi.createBillingPayment,
    onSuccess: async () => {
      setEditor(null);
      await refresh();
    },
  });

  const saveAllocations = useMutation({
    mutationFn: ({
      id,
      allocations,
    }: {
      id: string;
      allocations: Array<{ invoice: string; amount: string }>;
    }) => operationsApi.replaceBillingAllocations(id, allocations),
    onSuccess: async () => {
      setEditor(null);
      await refresh();
    },
  });

  const paygSubscriptions = (subscriptions.data ?? []).filter(
    (item) => item.status === "ACTIVE" && item.billing_mode === "PAYG",
  );

  const filteredPeriods = useMemo(
    () =>
      (periods.data ?? []).filter(
        (row) =>
          (!subscriptionFilter || row.subscription === subscriptionFilter)
          && (!statusFilter || row.status === statusFilter),
      ),
    [periods.data, subscriptionFilter, statusFilter],
  );

  const filteredInvoices = useMemo(
    () =>
      (invoices.data ?? []).filter(
        (row) =>
          (!subscriptionFilter || row.subscription === subscriptionFilter)
          && (!statusFilter || row.status === statusFilter),
      ),
    [invoices.data, subscriptionFilter, statusFilter],
  );

  const filteredPayments = useMemo(
    () =>
      (payments.data ?? []).filter(
        (row) =>
          (!subscriptionFilter || row.subscription === subscriptionFilter)
          && (!statusFilter || row.reconciliation_status === statusFilter),
      ),
    [payments.data, subscriptionFilter, statusFilter],
  );

  const selectedInvoicePeriod = (periods.data ?? []).find(
    (item) => item.id === invoicePeriodId,
  );
  const selectedPaymentSubscription = (subscriptions.data ?? []).find(
    (item) => item.id === paymentSubscriptionId,
  );

  const invoiceDocuments = (documents.data ?? []).filter(
    (item) =>
      item.document_type === "INVOICE"
      && !item.expense
      && (
        !selectedInvoicePeriod
        || !item.subscription
        || item.subscription === selectedInvoicePeriod.subscription
      ),
  );
  const invoiceExpenses = (expenses.data ?? []).filter((item) => {
    if (!selectedInvoicePeriod) return true;
    const subscription = (subscriptions.data ?? []).find(
      (candidate) => candidate.id === selectedInvoicePeriod.subscription,
    );
    return (
      item.currency === selectedInvoicePeriod.currency
      && (!subscription?.vendor || !item.vendor || item.vendor === subscription.vendor)
    );
  });

  const expensePaymentOptions = (expenses.data ?? []).flatMap((expense: Expense) =>
    expense.payments.map((payment) => ({
      ...payment,
      expense_description: expense.description,
    })),
  );

  if (!entity) {
    return <PermissionNotice>Select a legal entity to manage billing.</PermissionNotice>;
  }
  if (!canView) {
    return <PermissionNotice>You do not have permission to view billing data.</PermissionNotice>;
  }

  const loading = summary.isLoading
    || periods.isLoading
    || invoices.isLoading
    || payments.isLoading
    || subscriptions.isLoading
    || accounts.isLoading
    || expenses.isLoading
    || documents.isLoading;
  const loadError = summary.error
    ?? periods.error
    ?? invoices.error
    ?? payments.error
    ?? subscriptions.error
    ?? accounts.error
    ?? expenses.error
    ?? documents.error;

  function openPeriod(period?: BillingPeriod) {
    setEditor({ kind: "period", current: period });
  }

  function openInvoice(invoice?: SubscriptionInvoice) {
    const period = invoice?.billing_period ?? "";
    setInvoicePeriodId(period);
    setInvoiceSubtotal(invoice?.subtotal ?? "0");
    setInvoiceTax(invoice?.tax_amount ?? "0");
    setEditor({ kind: "invoice", current: invoice });
  }

  function openPayment() {
    setPaymentSubscriptionId(subscriptionFilter || paygSubscriptions[0]?.id || "");
    setEditor({ kind: "payment" });
  }

  function submitPeriod(event: FormEvent<HTMLFormElement>, current?: BillingPeriod) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const body: Record<string, unknown> = {
      period_start: String(data.get("period_start")),
      period_end: String(data.get("period_end")),
      estimated_cost: String(data.get("estimated_cost") ?? "0"),
      current_usage_amount: String(data.get("current_usage_amount") ?? "0"),
      usage_quantity: String(data.get("usage_quantity") ?? "") || null,
      usage_unit: String(data.get("usage_unit") ?? ""),
      notes: String(data.get("notes") ?? ""),
    };
    if (current) {
      body.is_closed = data.get("is_closed") === "on";
      savePeriod.mutate({ id: current.id, body });
    } else {
      body.subscription = String(data.get("subscription"));
      savePeriod.mutate({ body });
    }
  }

  function submitInvoice(event: FormEvent<HTMLFormElement>, current?: SubscriptionInvoice) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const subtotal = Number(invoiceSubtotal || 0);
    const tax = Number(invoiceTax || 0);
    const body: Record<string, unknown> = {
      invoice_number: String(data.get("invoice_number") ?? ""),
      invoice_date: String(data.get("invoice_date") ?? ""),
      due_date: String(data.get("due_date") ?? "") || null,
      currency: String(data.get("currency") ?? ""),
      subtotal: subtotal.toFixed(2),
      tax_amount: tax.toFixed(2),
      total_amount: (subtotal + tax).toFixed(2),
      document: String(data.get("document") ?? "") || null,
      expense: String(data.get("expense") ?? "") || null,
      notes: String(data.get("notes") ?? ""),
    };
    if (current) {
      saveInvoice.mutate({ id: current.id, body });
    } else {
      body.billing_period = String(data.get("billing_period"));
      saveInvoice.mutate({ body });
    }
  }

  function submitPayment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const subscription = (subscriptions.data ?? []).find(
      (item) => item.id === String(data.get("subscription")),
    );
    savePayment.mutate({
      subscription: String(data.get("subscription")),
      paid_on: String(data.get("paid_on")),
      amount: String(data.get("amount")),
      currency: subscription?.currency ?? entity?.base_currency ?? "USD",
      reference: String(data.get("reference") ?? ""),
      financial_account: String(data.get("financial_account") ?? "") || null,
      expense_payment: String(data.get("expense_payment") ?? "") || null,
      notes: String(data.get("notes") ?? ""),
    });
  }

  function submitAllocations(event: FormEvent<HTMLFormElement>, payment: BillingPayment) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const allocationRows = (invoices.data ?? [])
      .filter(
        (invoice) =>
          invoice.subscription === payment.subscription
          && invoice.status !== "VOID",
      )
      .map((invoice) => ({
        invoice: invoice.id,
        amount: String(data.get(`invoice:${invoice.id}`) ?? "0"),
      }))
      .filter((item) => Number(item.amount) > 0);
    saveAllocations.mutate({ id: payment.id, allocations: allocationRows });
  }

  const periodColumns: Array<TableColumn<BillingPeriod>> = [
    {
      key: "period",
      label: "Billing Period",
      render: (row) => (
        <div>
          <div className="font-semibold">{row.subscription_name}</div>
          <div className="mt-0.5 text-[11px] text-[var(--color-text-muted)]">
            {shortDate(row.period_start)} → {shortDate(row.period_end)}
          </div>
          <div className="mt-0.5 font-mono text-[10px] text-[var(--color-text-muted)]">
            {row.subscription_code}
          </div>
        </div>
      ),
    },
    {
      key: "costs",
      label: "Estimate / Usage",
      numeric: true,
      render: (row) => (
        <div>
          <div>{money(row.estimated_cost, row.currency)} est.</div>
          <div className="text-[11px] text-[var(--color-text-muted)]">
            {money(row.current_usage_amount, row.currency)} usage
          </div>
        </div>
      ),
    },
    {
      key: "actual",
      label: "Billed / Paid",
      numeric: true,
      render: (row) => (
        <div>
          <div>{money(row.actual_billed_amount, row.currency)} billed</div>
          <div className="text-[11px] text-[var(--color-text-muted)]">
            {money(row.paid_amount, row.currency)} paid
          </div>
        </div>
      ),
    },
    {
      key: "budget",
      label: "Budget",
      render: (row) => row.monthly_budget ? (
        <div>
          <div>{money(row.monthly_budget, row.currency)}</div>
          <div className={`text-[11px] ${row.over_budget ? "font-semibold text-red-700" : "text-[var(--color-text-muted)]"}`}>
            {row.budget_percent ?? "0"}% used
          </div>
        </div>
      ) : "—",
    },
    {
      key: "health",
      label: "Health",
      render: (row) => (
        <div className="space-y-1">
          <StatusBadge value={row.status} />
          {row.missing_invoice ? (
            <div className="flex items-center gap-1 text-[11px] text-amber-700">
              <AlertTriangle size={11} /> Missing invoice
            </div>
          ) : null}
          {row.over_budget ? (
            <div className="flex items-center gap-1 text-[11px] text-red-700">
              <AlertTriangle size={11} /> Over budget
            </div>
          ) : null}
        </div>
      ),
    },
    {
      key: "actions",
      label: "Actions",
      render: (row) => canManage ? (
        <div className="flex flex-wrap gap-1">
          <button className="erp-button !h-7 !min-h-7 text-[11px]"
            type="button" onClick={() => openPeriod(row)}>
            <Pencil size={12} /> Usage
          </button>
          <button className="erp-button !h-7 !min-h-7 text-[11px]"
            type="button" onClick={() => {
              setInvoicePeriodId(row.id);
              setInvoiceSubtotal("0");
              setInvoiceTax("0");
              setEditor({ kind: "invoice" });
            }}>
            <ReceiptText size={12} /> Invoice
          </button>
        </div>
      ) : "—",
    },
  ];

  const invoiceColumns: Array<TableColumn<SubscriptionInvoice>> = [
    {
      key: "invoice",
      label: "Invoice",
      render: (row) => (
        <div>
          <div className="font-semibold">{row.invoice_number}</div>
          <div className="mt-0.5 text-[11px] text-[var(--color-text-muted)]">
            {row.vendor_name} · {row.subscription_name}
          </div>
        </div>
      ),
    },
    { key: "date", label: "Invoice Date", render: (row) => shortDate(row.invoice_date) },
    {
      key: "amount",
      label: "Billed / Outstanding",
      numeric: true,
      render: (row) => (
        <div>
          <div>{money(row.total_amount, row.currency)}</div>
          <div className="text-[11px] text-[var(--color-text-muted)]">
            {money(row.outstanding_amount, row.currency)} outstanding
          </div>
        </div>
      ),
    },
    {
      key: "expense",
      label: "Expense Reconciliation",
      render: (row) => (
        <div>
          <StatusBadge value={row.expense_reconciliation_status} />
          <div className="mt-1 text-[11px] text-[var(--color-text-muted)]">
            {row.document_name ? "Document linked" : "No document"}
          </div>
        </div>
      ),
    },
    { key: "status", label: "Payment", render: (row) => <StatusBadge value={row.status} /> },
    {
      key: "actions",
      label: "Actions",
      render: (row) => canManage ? (
        <div className="flex flex-wrap gap-1">
          <button className="erp-button !h-7 !min-h-7 text-[11px]"
            type="button" onClick={() => openInvoice(row)}>
            <Link2 size={12} /> Reconcile
          </button>
          {row.status === "OPEN" ? (
            <button className="erp-button !h-7 !min-h-7 text-[11px]"
              type="button" disabled={voidInvoice.isPending}
              onClick={() => voidInvoice.mutate(row.id)}>
              <Ban size={12} /> Void
            </button>
          ) : null}
        </div>
      ) : "—",
    },
  ];

  const paymentColumns: Array<TableColumn<BillingPayment>> = [
    {
      key: "payment",
      label: "Payment",
      render: (row) => (
        <div>
          <div className="font-semibold">{row.payment_code}</div>
          <div className="mt-0.5 text-[11px] text-[var(--color-text-muted)]">
            {row.subscription_name} · {shortDate(row.paid_on)}
          </div>
        </div>
      ),
    },
    { key: "amount", label: "Amount", numeric: true, render: (row) => money(row.amount, row.currency) },
    {
      key: "allocation",
      label: "Allocated",
      numeric: true,
      render: (row) => (
        <div>
          <div>{money(row.allocated_amount, row.currency)}</div>
          <div className="text-[11px] text-[var(--color-text-muted)]">
            {money(row.unallocated_amount, row.currency)} unallocated
          </div>
        </div>
      ),
    },
    {
      key: "reconciliation",
      label: "Payment Reconciliation",
      render: (row) => (
        <div>
          <StatusBadge value={row.reconciliation_status} />
          <div className="mt-1 text-[11px] text-[var(--color-text-muted)]">
            {row.financial_account_name || "No payment account"}
          </div>
        </div>
      ),
    },
    {
      key: "actions",
      label: "Actions",
      render: (row) => canManage ? (
        <button className="erp-button !h-7 !min-h-7 text-[11px]"
          type="button" onClick={() => setEditor({ kind: "allocate", current: row })}>
          <Link2 size={12} /> Allocate
        </button>
      ) : "—",
    },
  ];

  const mutationError = savePeriod.error
    ?? saveInvoice.error
    ?? voidInvoice.error
    ?? savePayment.error
    ?? saveAllocations.error;

  const bounds = monthBounds();

  return (
    <>
      <PageHeader
        eyebrow="Management"
        title="Billing & Costs"
        description="Track PAYG estimates, current usage, actual vendor invoices and payments without treating uncertain costs as fixed subscription amounts."
        actions={canManage ? (
          <div className="flex gap-2">
            <button className="erp-button" type="button" onClick={() => openPayment()}>
              <WalletCards size={14} /> Record Payment
            </button>
            <button className="erp-button erp-button-primary" type="button" onClick={() => openPeriod()}>
              <Plus size={14} /> Billing Period
            </button>
          </div>
        ) : undefined}
      />

      <MetricStrip metrics={[
        {
          label: "Missing Invoices",
          value: String(summary.data?.missing_invoice_count ?? 0),
          note: "Ended periods without an invoice",
        },
        {
          label: "Over Budget",
          value: String(summary.data?.over_budget_period_count ?? 0),
          note: "Usage or actual bill exceeds budget",
        },
        {
          label: "Unpaid Invoices",
          value: String(summary.data?.unpaid_invoice_count ?? 0),
        },
        {
          label: "Needs Reconciliation",
          value: String(summary.data?.unreconciled_invoice_count ?? 0),
          note: "Invoice ↔ expense mismatch or missing link",
        },
      ]} />

      <div className="space-y-4 p-4 lg:p-6">
        {summary.data?.totals_by_currency.length ? (
          <section className="border border-[var(--color-border)] bg-white">
            <div className="border-b border-[var(--color-border)] px-4 py-3">
              <h2 className="text-sm font-semibold">Cost Position by Currency</h2>
              <p className="mt-1 text-[11px] text-[var(--color-text-muted)]">
                Currency-safe totals; MateERP never adds unlike currencies together.
              </p>
            </div>
            <div className="grid gap-px bg-[var(--color-border)] md:grid-cols-5">
              {[
                ["Estimated", "estimated_cost"],
                ["Current Usage", "current_usage_amount"],
                ["Actual Billed", "actual_billed_amount"],
                ["Paid", "paid_amount"],
                ["Outstanding", "outstanding_amount"],
              ].map(([label, field]) => (
                <div key={field} className="bg-white p-3">
                  <div className="text-[10px] font-semibold uppercase tracking-[0.08em] text-[var(--color-text-muted)]">{label}</div>
                  <div className="mt-1 text-sm font-semibold">
                    {formatCurrencyTotals(summary.data?.totals_by_currency ?? [], field)}
                  </div>
                </div>
              ))}
            </div>
          </section>
        ) : null}

        <div className="flex flex-wrap items-center gap-2 border border-[var(--color-border)] bg-white p-2.5">
          {[
            ["periods", "Billing Periods", Gauge],
            ["invoices", "Invoices", ReceiptText],
            ["payments", "Payments", WalletCards],
            ["trend", "Cost Trend", CircleDollarSign],
          ].map(([value, label, Icon]) => (
            <button
              key={String(value)}
              className={`erp-button !h-8 !min-h-8 ${tab === value ? "erp-button-primary" : ""}`}
              type="button"
              onClick={() => {
                setTab(value as typeof tab);
                setStatusFilter("");
              }}
            >
              <Icon size={13} /> {String(label)}
            </button>
          ))}
          <select className="erp-field ml-auto !h-8 !w-auto text-xs"
            value={subscriptionFilter} onChange={(event) => setSubscriptionFilter(event.target.value)}>
            <option value="">All subscriptions</option>
            {(subscriptions.data ?? []).map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}{item.account_alias ? ` · ${item.account_alias}` : ""}
              </option>
            ))}
          </select>
          {tab !== "trend" ? (
            <select className="erp-field !h-8 !w-auto text-xs"
              value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
              <option value="">All statuses</option>
              {tab === "periods" ? (
                <>
                  <option value="OPEN">Open</option>
                  <option value="AWAITING_INVOICE">Awaiting invoice</option>
                  <option value="INVOICED">Invoiced</option>
                  <option value="PARTIALLY_PAID">Partially paid</option>
                  <option value="PAID">Paid</option>
                  <option value="CLOSED">Closed</option>
                </>
              ) : tab === "invoices" ? (
                <>
                  <option value="OPEN">Open</option>
                  <option value="PARTIALLY_PAID">Partially paid</option>
                  <option value="PAID">Paid</option>
                  <option value="VOID">Void</option>
                </>
              ) : (
                <>
                  <option value="UNMATCHED">Unmatched</option>
                  <option value="ACCOUNT_IDENTIFIED">Account identified</option>
                  <option value="MATCHED">Matched</option>
                </>
              )}
            </select>
          ) : null}
          {canManage && tab === "invoices" ? (
            <button className="erp-button erp-button-primary !h-8 !min-h-8"
              type="button" onClick={() => openInvoice()}>
              <Plus size={13} /> Record Invoice
            </button>
          ) : null}
        </div>

        {mutationError ? <ErrorState message={errorMessage(mutationError)} /> : null}

        {loading ? (
          <LoadingState label="Loading billing and reconciliation data..." />
        ) : loadError ? (
          <ErrorState message={errorMessage(loadError)} />
        ) : tab === "periods" ? (
          <DataTable
            columns={periodColumns}
            rows={filteredPeriods}
            rowKey={(row) => row.id}
            emptyTitle="No billing periods"
            emptyDescription="Create a period to track estimate, usage, actual invoice and paid amount separately."
          />
        ) : tab === "invoices" ? (
          <DataTable
            columns={invoiceColumns}
            rows={filteredInvoices}
            rowKey={(row) => row.id}
            emptyTitle="No vendor invoices"
            emptyDescription="Record an invoice against a billing period, then link its PDF and accounting expense."
          />
        ) : tab === "payments" ? (
          <DataTable
            columns={paymentColumns}
            rows={filteredPayments}
            rowKey={(row) => row.id}
            emptyTitle="No billing payments"
            emptyDescription="Record a vendor payment and allocate it across one or more invoices."
          />
        ) : (
          <section className="border border-[var(--color-border)] bg-white">
            <div className="border-b border-[var(--color-border)] px-4 py-3">
              <h2 className="text-sm font-semibold">Monthly Cost Trend</h2>
              <p className="mt-1 text-[11px] text-[var(--color-text-muted)]">
                Estimate → current usage → actual bill → paid, grouped by month and currency.
              </p>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[760px] text-xs">
                <thead>
                  <tr className="border-b border-[var(--color-border)] bg-[var(--color-surface-subtle)] text-left">
                    {["Period", "Currency", "Budget", "Estimated", "Usage", "Actual", "Paid"].map((label) => (
                      <th key={label} className="px-3 py-2 font-semibold">{label}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {(summary.data?.trend ?? []).map((row) => (
                    <tr key={`${row.period}:${row.currency}`} className="border-b border-[var(--color-border-soft)]">
                      <td className="px-3 py-2 font-semibold">{row.period}</td>
                      <td className="px-3 py-2">{row.currency}</td>
                      <td className="px-3 py-2">{money(row.budget, row.currency)}</td>
                      <td className="px-3 py-2">{money(row.estimated_cost, row.currency)}</td>
                      <td className="px-3 py-2">{money(row.current_usage_amount, row.currency)}</td>
                      <td className="px-3 py-2">{money(row.actual_billed_amount, row.currency)}</td>
                      <td className="px-3 py-2">{money(row.paid_amount, row.currency)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}
      </div>

      {editor?.kind === "period" ? (
        <Overlay
          title={editor.current ? `Update Usage · ${editor.current.subscription_name}` : "Create Billing Period"}
          description="A billing period keeps estimate, live usage, actual invoices and payments as separate facts."
          onClose={() => setEditor(null)}
        >
          <form onSubmit={(event) => submitPeriod(event, editor.current)}>
            <div className="grid gap-4 p-5 sm:grid-cols-2">
              {editor.current ? (
                <div className="sm:col-span-2 border border-[var(--color-border)] bg-[var(--color-surface-subtle)] p-3 text-sm font-semibold">
                  {editor.current.subscription_name} · {editor.current.subscription_code}
                </div>
              ) : (
                <label className="block text-xs font-medium sm:col-span-2">
                  <span className="mb-1 block text-[var(--color-text-muted)]">Subscription</span>
                  <select className="erp-field" name="subscription" required
                    defaultValue={subscriptionFilter || ""}>
                    <option value="">Select PAYG subscription</option>
                    {paygSubscriptions.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.name}{item.account_alias ? ` · ${item.account_alias}` : ""}
                      </option>
                    ))}
                  </select>
                </label>
              )}
              <Field label="Period Start" name="period_start" type="date" required
                defaultValue={editor.current?.period_start ?? bounds.start} />
              <Field label="Period End" name="period_end" type="date" required
                defaultValue={editor.current?.period_end ?? bounds.end} />
              <Field label="Estimated Cost" name="estimated_cost" type="number" step="0.01"
                defaultValue={editor.current?.estimated_cost ?? ""} />
              <Field label="Current Usage Cost" name="current_usage_amount" type="number" step="0.01"
                defaultValue={editor.current?.current_usage_amount ?? "0"} />
              <Field label="Usage Quantity (optional)" name="usage_quantity" type="number" step="0.0001"
                defaultValue={editor.current?.usage_quantity} />
              <Field label="Usage Unit (optional)" name="usage_unit"
                defaultValue={editor.current?.usage_unit} />
              <label className="block text-xs font-medium sm:col-span-2">
                <span className="mb-1 block text-[var(--color-text-muted)]">Notes</span>
                <textarea className="erp-field" name="notes" rows={2}
                  defaultValue={editor.current?.notes} />
              </label>
              {editor.current ? (
                <label className="flex items-center gap-2 text-xs sm:col-span-2">
                  <input type="checkbox" name="is_closed" defaultChecked={editor.current.is_closed} />
                  Close this billing period after final reconciliation
                </label>
              ) : null}
            </div>
            <div className="flex justify-end gap-2 border-t border-[var(--color-border)] px-5 py-3">
              <button className="erp-button" type="button" onClick={() => setEditor(null)}>Cancel</button>
              <button className="erp-button erp-button-primary" type="submit" disabled={savePeriod.isPending}>
                {savePeriod.isPending ? "Saving..." : "Save Billing Period"}
              </button>
            </div>
          </form>
        </Overlay>
      ) : null}

      {editor?.kind === "invoice" ? (
        <Overlay
          title={editor.current ? `Reconcile Invoice · ${editor.current.invoice_number}` : "Record Vendor Invoice"}
          description="Invoice total becomes Actual Billed Amount. Link the invoice PDF and accounting expense to reconcile without duplicate expenses."
          onClose={() => setEditor(null)}
        >
          <form onSubmit={(event) => submitInvoice(event, editor.current)}>
            <div className="grid gap-4 p-5 sm:grid-cols-2">
              <label className="block text-xs font-medium sm:col-span-2">
                <span className="mb-1 block text-[var(--color-text-muted)]">Billing Period</span>
                <select className="erp-field" name="billing_period" required
                  disabled={Boolean(editor.current)}
                  value={editor.current?.billing_period ?? invoicePeriodId}
                  onChange={(event) => setInvoicePeriodId(event.target.value)}>
                  <option value="">Select billing period</option>
                  {(periods.data ?? []).map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.subscription_name} · {item.period_start} → {item.period_end}
                    </option>
                  ))}
                </select>
              </label>
              <Field label="Invoice Number" name="invoice_number" required
                defaultValue={editor.current?.invoice_number} />
              <Field label="Invoice Date" name="invoice_date" type="date" required
                defaultValue={editor.current?.invoice_date ?? today()} />
              <Field label="Due Date" name="due_date" type="date"
                defaultValue={editor.current?.due_date} />
              <Field label="Currency" name="currency" required readOnly
                defaultValue={editor.current?.currency ?? selectedInvoicePeriod?.currency ?? entity.base_currency} />
              <label className="block text-xs font-medium">
                <span className="mb-1 block text-[var(--color-text-muted)]">Subtotal</span>
                <input className="erp-field" type="number" step="0.01" required
                  value={invoiceSubtotal} onChange={(event) => setInvoiceSubtotal(event.target.value)} />
              </label>
              <label className="block text-xs font-medium">
                <span className="mb-1 block text-[var(--color-text-muted)]">Tax</span>
                <input className="erp-field" type="number" step="0.01" required
                  value={invoiceTax} onChange={(event) => setInvoiceTax(event.target.value)} />
              </label>
              <div className="border border-[var(--color-border)] bg-[var(--color-surface-subtle)] p-3 sm:col-span-2">
                <span className="text-[10px] font-semibold uppercase tracking-[0.08em] text-[var(--color-text-muted)]">Actual Billed Amount</span>
                <div className="mt-1 text-lg font-semibold">
                  {money(Number(invoiceSubtotal || 0) + Number(invoiceTax || 0), editor.current?.currency ?? selectedInvoicePeriod?.currency ?? entity.base_currency)}
                </div>
              </div>
              <label className="block text-xs font-medium">
                <span className="mb-1 block text-[var(--color-text-muted)]">Invoice PDF</span>
                <select className="erp-field" name="document" defaultValue={editor.current?.document ?? ""}>
                  <option value="">No document link</option>
                  {invoiceDocuments.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.standardized_name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block text-xs font-medium">
                <span className="mb-1 block text-[var(--color-text-muted)]">Accounting Expense</span>
                <select className="erp-field" name="expense" defaultValue={editor.current?.expense ?? ""}>
                  <option value="">Unmatched expense</option>
                  {invoiceExpenses.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.description} · {money(item.amount, item.currency)}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block text-xs font-medium sm:col-span-2">
                <span className="mb-1 block text-[var(--color-text-muted)]">Notes</span>
                <textarea className="erp-field" name="notes" rows={2}
                  defaultValue={editor.current?.notes} />
              </label>
            </div>
            <div className="flex justify-end gap-2 border-t border-[var(--color-border)] px-5 py-3">
              <button className="erp-button" type="button" onClick={() => setEditor(null)}>Cancel</button>
              <button className="erp-button erp-button-primary" type="submit" disabled={saveInvoice.isPending}>
                {saveInvoice.isPending ? "Saving..." : editor.current ? "Save Reconciliation" : "Record Invoice"}
              </button>
            </div>
          </form>
        </Overlay>
      ) : null}

      {editor?.kind === "payment" ? (
        <Overlay
          title="Record Billing Payment"
          description="Record the actual vendor payment, optionally match it to the accounting payment, then allocate it across invoices."
          onClose={() => setEditor(null)}
        >
          <form onSubmit={submitPayment}>
            <div className="grid gap-4 p-5 sm:grid-cols-2">
              <label className="block text-xs font-medium sm:col-span-2">
                <span className="mb-1 block text-[var(--color-text-muted)]">Subscription</span>
                <select className="erp-field" name="subscription" required
                  value={paymentSubscriptionId}
                  onChange={(event) => setPaymentSubscriptionId(event.target.value)}>
                  <option value="">Select subscription</option>
                  {(subscriptions.data ?? []).filter((item) => item.status === "ACTIVE").map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name}{item.account_alias ? ` · ${item.account_alias}` : ""}
                    </option>
                  ))}
                </select>
              </label>
              <Field label="Paid On" name="paid_on" type="date" required defaultValue={today()} />
              <Field label="Amount" name="amount" type="number" step="0.01" required />
              <Field label="Currency" name="currency" readOnly
                defaultValue={selectedPaymentSubscription?.currency ?? entity.base_currency} />
              <label className="block text-xs font-medium">
                <span className="mb-1 block text-[var(--color-text-muted)]">Financial Account (optional)</span>
                <select className="erp-field" name="financial_account" defaultValue="">
                  <option value="">Not identified yet</option>
                  {(accounts.data ?? []).filter(
                    (item) => !selectedPaymentSubscription || item.currency === selectedPaymentSubscription.currency,
                  ).map((item) => (
                    <option key={item.id} value={item.id}>{item.name}</option>
                  ))}
                </select>
              </label>
              <label className="block text-xs font-medium sm:col-span-2">
                <span className="mb-1 block text-[var(--color-text-muted)]">Accounting Expense Payment (optional)</span>
                <select className="erp-field" name="expense_payment" defaultValue="">
                  <option value="">Unmatched payment</option>
                  {expensePaymentOptions.filter(
                    (item) => !selectedPaymentSubscription || item.currency === selectedPaymentSubscription.currency,
                  ).map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.expense_description} · {shortDate(item.payment_date)} · {money(item.amount, item.currency)}
                    </option>
                  ))}
                </select>
              </label>
              <Field label="Reference" name="reference" />
              <Field label="Notes" name="notes" />
            </div>
            <div className="flex justify-end gap-2 border-t border-[var(--color-border)] px-5 py-3">
              <button className="erp-button" type="button" onClick={() => setEditor(null)}>Cancel</button>
              <button className="erp-button erp-button-primary" type="submit" disabled={savePayment.isPending}>
                {savePayment.isPending ? "Recording..." : "Record Payment"}
              </button>
            </div>
          </form>
        </Overlay>
      ) : null}

      {editor?.kind === "allocate" ? (
        <Overlay
          title={`Allocate Payment · ${editor.current.payment_code}`}
          description="One payment can settle multiple invoices. Partial allocations are supported; over-allocation is blocked."
          onClose={() => setEditor(null)}
        >
          <form onSubmit={(event) => submitAllocations(event, editor.current)}>
            <div className="p-5">
              <div className="mb-4 grid gap-px border border-[var(--color-border)] bg-[var(--color-border)] sm:grid-cols-3">
                <div className="bg-white p-3">
                  <div className="erp-label">Payment</div>
                  <div className="mt-1 font-semibold">{money(editor.current.amount, editor.current.currency)}</div>
                </div>
                <div className="bg-white p-3">
                  <div className="erp-label">Allocated</div>
                  <div className="mt-1 font-semibold">{money(editor.current.allocated_amount, editor.current.currency)}</div>
                </div>
                <div className="bg-white p-3">
                  <div className="erp-label">Unallocated</div>
                  <div className="mt-1 font-semibold">{money(editor.current.unallocated_amount, editor.current.currency)}</div>
                </div>
              </div>
              <div className="space-y-2">
                {(invoices.data ?? []).filter(
                  (invoice) => invoice.subscription === editor.current.subscription && invoice.status !== "VOID",
                ).map((invoice) => {
                  const existing = editor.current.allocations.find(
                    (allocation) => allocation.invoice === invoice.id,
                  );
                  return (
                    <div key={invoice.id}
                      className="grid items-center gap-3 border border-[var(--color-border)] p-3 sm:grid-cols-[minmax(0,1fr)_140px]">
                      <div>
                        <div className="font-semibold">{invoice.invoice_number}</div>
                        <div className="mt-0.5 text-[11px] text-[var(--color-text-muted)]">
                          {shortDate(invoice.invoice_date)} · {money(invoice.total_amount, invoice.currency)}
                          {" · "}{money(invoice.outstanding_amount, invoice.currency)} outstanding
                        </div>
                      </div>
                      <input
                        className="erp-field text-right"
                        min="0"
                        name={`invoice:${invoice.id}`}
                        step="0.01"
                        type="number"
                        defaultValue={existing?.amount ?? "0"}
                      />
                    </div>
                  );
                })}
              </div>
            </div>
            <div className="flex justify-end gap-2 border-t border-[var(--color-border)] px-5 py-3">
              <button className="erp-button" type="button" onClick={() => setEditor(null)}>Cancel</button>
              <button className="erp-button erp-button-primary" type="submit" disabled={saveAllocations.isPending}>
                {saveAllocations.isPending ? "Saving..." : "Save Allocations"}
              </button>
            </div>
          </form>
        </Overlay>
      ) : null}
    </>
  );
}
