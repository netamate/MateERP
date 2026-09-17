"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, CreditCard, Plus, Search, X } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useState, type FormEvent, type ReactNode } from "react";

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
  accountingApi,
  financeApi,
  type Expense,
  type FinancialAccount,
  type SessionPayload,
} from "@/lib/api";

type TaxCode = {
  id: string;
  code: string;
  name: string;
  rate: string;
  input_account_id: string | null;
  is_active: boolean;
};

function money(value: string | number | null | undefined, currency = "USD") {
  const amount = typeof value === "number" ? value : Number(value ?? 0);
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(Number.isFinite(amount) ? amount : 0);
}

function shortDate(value: string | null | undefined) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en-US", {
    year: "numeric",
    month: "short",
    day: "2-digit",
  }).format(new Date(`${value}T00:00:00`));
}

function activeEntity(session: SessionPayload) {
  return session.active_legal_entities.find((entity) => entity.id === session.active_legal_entity_id);
}

function activeMembership(session: SessionPayload) {
  return session.memberships.find(
    (membership) => membership.organization_id === session.active_organization_id,
  );
}

function can(session: SessionPayload, permission: string) {
  return activeMembership(session)?.permissions.includes(permission) ?? false;
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "The request could not be completed.";
}

function useCreateModal() {
  const router = useRouter();
  const params = useSearchParams();
  return {
    open: params.get("new") === "1",
    show: () => router.push(`${window.location.pathname}?new=1`),
    close: () => router.replace(window.location.pathname),
  };
}

function Modal({
  title,
  description,
  children,
  onClose,
}: {
  title: string;
  description: string;
  children: ReactNode;
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 z-[80] flex items-start justify-center overflow-y-auto bg-black/50 px-4 py-[8vh]">
      <div className="w-full max-w-2xl border border-[var(--color-border-strong)] bg-white shadow-2xl">
        <div className="flex items-start justify-between border-b border-[var(--color-border)] px-5 py-4">
          <div>
            <h2 className="text-lg font-semibold">{title}</h2>
            <p className="mt-1 text-xs text-[var(--color-text-muted)]">{description}</p>
          </div>
          <button aria-label="Close" className="erp-button !h-8 !min-h-8 !w-8 !p-0" onClick={onClose} type="button"><X size={14} /></button>
        </div>
        {children}
      </div>
    </div>
  );
}

function FormActions({ pending, onClose, label = "Save" }: { pending: boolean; onClose: () => void; label?: string }) {
  return (
    <div className="flex justify-end gap-2 border-t border-[var(--color-border)] bg-[var(--color-surface-subtle)] px-5 py-3">
      <button className="erp-button" onClick={onClose} type="button">Cancel</button>
      <button className="erp-button erp-button-primary" disabled={pending} type="submit">{pending ? "Saving..." : label}</button>
    </div>
  );
}

function ExpenseCreateForm({ session, onClose }: { session: SessionPayload; onClose: () => void }) {
  const entity = activeEntity(session);
  const queryClient = useQueryClient();
  const [validationError, setValidationError] = useState("");
  const vendors = useQuery({ queryKey: ["vendors", entity?.id], queryFn: financeApi.vendors, enabled: Boolean(entity) });
  const ledger = useQuery({ queryKey: ["ledger-accounts", entity?.id], queryFn: accountingApi.accounts, enabled: Boolean(entity) });
  const taxCodes = useQuery({
    queryKey: ["tax-codes", entity?.id],
    queryFn: () => import("@/lib/api").then(({ request }) => request<TaxCode[]>("/api/v1/accounting/tax-codes/")),
    enabled: Boolean(entity),
  });
  const create = useMutation({
    mutationFn: financeApi.createExpense,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["expenses", entity?.id] });
      onClose();
    },
  });
  const expenseAccounts = (ledger.data ?? []).filter((item) => item.account_type === "EXPENSE");
  const payableAccounts = (ledger.data ?? []).filter((item) => item.account_type === "LIABILITY");
  const usableTaxCodes = (taxCodes.data ?? []).filter((item) => item.is_active && item.input_account_id);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setValidationError("");
    const data = Object.fromEntries(new FormData(event.currentTarget).entries());
    const taxAmount = Number(data.tax_amount ?? 0);
    if (taxAmount > 0 && !data.tax_code) {
      setValidationError("Select an input tax code when the tax amount is greater than zero.");
      return;
    }
    create.mutate({
      ...data,
      vendor: data.vendor || null,
      due_date: data.due_date || null,
      reference: data.reference || "",
      tax_amount: data.tax_amount || "0",
      tax_code: data.tax_code || null,
      currency: String(data.currency || entity?.base_currency || "USD").toUpperCase(),
      fx_rate: data.fx_rate || "1",
    });
  }

  return (
    <form onSubmit={submit}>
      <div className="grid gap-4 p-5 sm:grid-cols-2">
        <label><span className="erp-label">Expense date</span><input className="erp-field" defaultValue={new Date().toISOString().slice(0, 10)} name="expense_date" required type="date" /></label>
        <label><span className="erp-label">Due date</span><input className="erp-field" name="due_date" type="date" /></label>
        <label className="sm:col-span-2"><span className="erp-label">Description</span><input className="erp-field" name="description" required /></label>
        <label><span className="erp-label">Vendor</span><select className="erp-field" defaultValue="" name="vendor"><option value="">No vendor</option>{(vendors.data ?? []).map((vendor) => <option key={vendor.id} value={vendor.id}>{vendor.name}</option>)}</select></label>
        <label><span className="erp-label">Reference</span><input className="erp-field" name="reference" /></label>
        <label><span className="erp-label">Gross amount</span><input className="erp-field" name="amount" required step="0.01" type="number" /></label>
        <label><span className="erp-label">Tax amount</span><input className="erp-field" defaultValue="0" min="0" name="tax_amount" step="0.01" type="number" /></label>
        <label><span className="erp-label">Tax code</span><select className="erp-field" defaultValue="" name="tax_code"><option value="">No tax</option>{usableTaxCodes.map((code) => <option key={code.id} value={code.id}>{code.code} · {code.name} ({code.rate}%)</option>)}</select><span className="mt-1 block text-[11px] text-[var(--color-text-muted)]">Required for any nonzero tax amount.</span></label>
        <label><span className="erp-label">Currency</span><input className="erp-field" defaultValue={entity?.base_currency ?? "USD"} name="currency" required /></label>
        <label><span className="erp-label">FX rate</span><input className="erp-field" defaultValue="1" name="fx_rate" required step="0.0000000001" type="number" /></label>
        <label><span className="erp-label">Expense account</span><select className="erp-field" name="expense_account" required><option value="">Select expense account</option>{expenseAccounts.map((account) => <option key={account.id} value={account.id}>{account.code} · {account.name}</option>)}</select></label>
        <label><span className="erp-label">Payable account</span><select className="erp-field" name="payable_account" required><option value="">Select payable account</option>{payableAccounts.map((account) => <option key={account.id} value={account.id}>{account.code} · {account.name}</option>)}</select></label>
        {validationError ? <div className="sm:col-span-2"><ErrorState message={validationError} /></div> : null}
        {create.error ? <div className="sm:col-span-2"><ErrorState message={errorMessage(create.error)} /></div> : null}
      </div>
      <FormActions label="Create Draft" onClose={onClose} pending={create.isPending} />
    </form>
  );
}

function PaymentForm({ session, expense, onClose }: { session: SessionPayload; expense: Expense; onClose: () => void }) {
  const entity = activeEntity(session);
  const queryClient = useQueryClient();
  const accounts = useQuery({ queryKey: ["financial-accounts", entity?.id], queryFn: financeApi.accounts, enabled: Boolean(entity) });
  const mutation = useMutation({
    mutationFn: (body: Record<string, unknown>) => financeApi.payExpense(expense.id, body),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["expenses", entity?.id] });
      onClose();
    },
  });
  const paidBase = expense.payments.reduce((sum, payment) => sum + Number(payment.base_amount), 0);
  const totalBase = Number(expense.amount) * Number(expense.fx_rate);
  const outstandingBase = Math.max(totalBase - paidBase, 0);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(event.currentTarget).entries());
    mutation.mutate({ ...data, fx_rate: data.fx_rate || "1" });
  }

  return (
    <form onSubmit={submit}>
      <div className="grid gap-4 p-5 sm:grid-cols-2">
        <div className="sm:col-span-2 border border-[var(--color-border)] bg-[var(--color-surface-subtle)] px-3 py-2 text-xs">Outstanding in base currency: <strong>{money(outstandingBase, entity?.base_currency)}</strong></div>
        <label><span className="erp-label">Financial account</span><select className="erp-field" name="financial_account" required><option value="">Select payment account</option>{(accounts.data ?? []).filter((account: FinancialAccount) => account.is_active).map((account) => <option key={account.id} value={account.id}>{account.name} · {account.currency}</option>)}</select></label>
        <label><span className="erp-label">Payment date</span><input className="erp-field" defaultValue={new Date().toISOString().slice(0, 10)} name="payment_date" required type="date" /></label>
        <label><span className="erp-label">Payment amount</span><input className="erp-field" name="amount" required step="0.01" type="number" /></label>
        <label><span className="erp-label">Currency</span><input className="erp-field" defaultValue={expense.currency} name="currency" required /></label>
        <label><span className="erp-label">FX rate</span><input className="erp-field" defaultValue="1" name="fx_rate" required step="0.0000000001" type="number" /></label>
        <label><span className="erp-label">Reference</span><input className="erp-field" name="reference" /></label>
        {mutation.error ? <div className="sm:col-span-2"><ErrorState message={errorMessage(mutation.error)} /></div> : null}
      </div>
      <FormActions label="Post Payment" onClose={onClose} pending={mutation.isPending} />
    </form>
  );
}

export function ExpensesProductionPage({ session }: { session: SessionPayload }) {
  const entity = activeEntity(session);
  const modal = useCreateModal();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [paying, setPaying] = useState<Expense | null>(null);
  const expenses = useQuery({ queryKey: ["expenses", entity?.id], queryFn: financeApi.expenses, enabled: Boolean(entity) });
  const vendors = useQuery({ queryKey: ["vendors", entity?.id], queryFn: financeApi.vendors, enabled: Boolean(entity) });
  const vendorMap = new Map((vendors.data ?? []).map((vendor) => [vendor.id, vendor.name]));
  const workflow = useMutation({
    mutationFn: ({ id, action }: { id: string; action: "submit" | "approve" | "reject" }) =>
      financeApi.expenseWorkflow(
        id,
        action,
        action === "reject" ? "Rejected from Phase 6 production workspace" : "",
      ),
    onSuccess: async () => queryClient.invalidateQueries({ queryKey: ["expenses", entity?.id] }),
  });

  const rows = (expenses.data ?? []).filter((expense) => {
    const text = `${expense.description} ${expense.reference} ${vendorMap.get(expense.vendor ?? "") ?? ""}`.toLowerCase();
    return text.includes(search.toLowerCase()) && (statusFilter === "ALL" || expense.status === statusFilter);
  });
  const total = (expenses.data ?? []).reduce((sum, item) => sum + Number(item.amount), 0);
  const outstanding = (expenses.data ?? []).filter((item) => item.status !== "PAID").reduce((sum, item) => sum + Number(item.amount), 0);

  const columns: Array<TableColumn<Expense>> = [
    { key: "date", label: "Date", render: (row) => shortDate(row.expense_date) },
    { key: "vendor", label: "Vendor", render: (row) => vendorMap.get(row.vendor ?? "") ?? "—" },
    { key: "description", label: "Description", render: (row) => <span className="font-medium">{row.description}</span> },
    { key: "reference", label: "Reference", render: (row) => row.reference || "—" },
    { key: "tax", label: "Tax", numeric: true, render: (row) => money(row.tax_amount, row.currency) },
    { key: "amount", label: "Amount", numeric: true, render: (row) => money(row.amount, row.currency) },
    { key: "status", label: "Status", render: (row) => <StatusBadge value={row.status} /> },
    {
      key: "actions",
      label: "Actions",
      render: (row) => (
        <div className="flex gap-1">
          {row.status === "DRAFT" && can(session, "SUBMIT_FINANCE") ? <button className="erp-button !h-7 !min-h-7 !px-2" disabled={workflow.isPending} onClick={() => workflow.mutate({ id: row.id, action: "submit" })} type="button">Submit</button> : null}
          {row.status === "SUBMITTED" && can(session, "APPROVE_FINANCE") ? <><button className="erp-button !h-7 !min-h-7 !px-2" disabled={workflow.isPending} onClick={() => workflow.mutate({ id: row.id, action: "approve" })} type="button"><Check size={11} /> Approve</button><button className="erp-button erp-button-danger !h-7 !min-h-7 !px-2" disabled={workflow.isPending} onClick={() => workflow.mutate({ id: row.id, action: "reject" })} type="button">Reject</button></> : null}
          {["APPROVED", "PARTIALLY_PAID"].includes(row.status) && can(session, "PAY_FINANCE") ? <button className="erp-button !h-7 !min-h-7 !px-2" onClick={() => setPaying(row)} type="button"><CreditCard size={11} /> Pay</button> : null}
        </div>
      ),
    },
  ];

  return (
    <>
      <PageHeader description="Track, tax-code, approve, accrue, and settle company expenses while keeping expense documents separate from payments." eyebrow="Finance" title="Expenses" />
      <MetricStrip metrics={[{ label: "Total Recorded", value: money(total, entity?.base_currency) }, { label: "Open Face Value", value: money(outstanding, entity?.base_currency), tone: outstanding ? "bad" : "default" }, { label: "Documents", value: String(expenses.data?.length ?? 0) }, { label: "Pending Approval", value: String((expenses.data ?? []).filter((item) => item.status === "SUBMITTED").length) }]} />
      <div className="p-4 lg:p-6">
        <div className="mb-3 flex flex-wrap items-center gap-2 border border-[var(--color-border)] bg-[#fbfcfd] p-2.5">
          <label className="relative min-w-56 flex-1 sm:max-w-80"><Search className="absolute left-2.5 top-2.5 text-[var(--color-text-muted)]" size={14} /><input className="erp-field !h-8 !min-h-8 pl-8 text-xs" onChange={(event) => setSearch(event.target.value)} placeholder="Search expenses..." value={search} /></label>
          <select className="erp-field !h-8 !min-h-8 !w-auto text-xs" onChange={(event) => setStatusFilter(event.target.value)} value={statusFilter}><option value="ALL">All statuses</option>{["DRAFT", "SUBMITTED", "APPROVED", "PARTIALLY_PAID", "PAID", "REJECTED"].map((status) => <option key={status} value={status}>{status.replaceAll("_", " ")}</option>)}</select>
          <button className="erp-button erp-button-primary ml-auto !h-8 !min-h-8" disabled={!can(session, "SUBMIT_FINANCE")} onClick={modal.show} type="button"><Plus size={13} /> Add Expense</button>
        </div>
        {!entity ? <PermissionNotice>Select a legal entity first.</PermissionNotice> : expenses.isLoading ? <LoadingState /> : expenses.error ? <ErrorState message={errorMessage(expenses.error)} /> : <DataTable columns={columns} rowKey={(row) => row.id} rows={rows} />}
        {workflow.error ? <div className="mt-3"><ErrorState message={errorMessage(workflow.error)} /></div> : null}
      </div>
      {modal.open ? <Modal description="Create a draft expense. Nonzero tax requires an active input tax code before the record can be created." onClose={modal.close} title="Add Expense"><ExpenseCreateForm onClose={modal.close} session={session} /></Modal> : null}
      {paying ? <Modal description="Payment is a separate financial event and posts its own journal entry." onClose={() => setPaying(null)} title="Pay Expense"><PaymentForm expense={paying} onClose={() => setPaying(null)} session={session} /></Modal> : null}
    </>
  );
}
