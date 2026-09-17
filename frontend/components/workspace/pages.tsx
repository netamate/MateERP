"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight,
  Check,
  CreditCard,
  FileText,
  Landmark,
  Plus,
  Search,
  ShieldCheck,
  X,
} from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  useMemo,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";

import {
  DataTable,
  EmptyState,
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
  adminApi,
  financeApi,
  request,
  type Expense,
  type FinancialAccount,
  type Income,
  type JournalEntry,
  type LedgerAccount,
  type Reimbursement,
  type SessionPayload,
  type Transfer,
  type Vendor,
} from "@/lib/api";

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

function today() {
  return new Date().toISOString().slice(0, 10);
}

function firstDayOfYear() {
  return `${new Date().getFullYear()}-01-01`;
}

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

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "The request could not be completed.";
}

function PageContent({ children }: { children: ReactNode }) {
  return <div className="p-4 lg:p-6">{children}</div>;
}

function Toolbar({
  search,
  onSearch,
  filters,
  onNew,
  canCreate = true,
  newLabel = "Add",
}: {
  search: string;
  onSearch: (value: string) => void;
  filters?: ReactNode;
  onNew?: () => void;
  canCreate?: boolean;
  newLabel?: string;
}) {
  return (
    <div className="mb-3 flex flex-wrap items-center gap-2 border border-[var(--color-border)] bg-[#fbfcfd] p-2.5">
      <label className="relative min-w-56 flex-1 sm:max-w-80">
        <Search className="absolute left-2.5 top-2.5 text-[var(--color-text-muted)]" size={14} />
        <input
          aria-label="Search records"
          className="erp-field !h-8 !min-h-8 pl-8 text-xs"
          onChange={(event) => onSearch(event.target.value)}
          placeholder="Search records..."
          value={search}
        />
      </label>
      {filters}
      <div className="ml-auto" />
      {onNew ? (
        <button
          className="erp-button erp-button-primary !h-8 !min-h-8"
          disabled={!canCreate}
          onClick={onNew}
          type="button"
        >
          <Plus size={13} /> {newLabel}
        </button>
      ) : null}
    </div>
  );
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
          <button aria-label="Close" className="erp-button !h-8 !min-h-8 !w-8 !p-0" onClick={onClose} type="button">
            <X size={14} />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

function FormGrid({ children }: { children: ReactNode }) {
  return <div className="grid gap-4 p-5 sm:grid-cols-2">{children}</div>;
}

function Field({
  label,
  name,
  type = "text",
  defaultValue,
  required = false,
  children,
  full = false,
  step,
}: {
  label: string;
  name: string;
  type?: string;
  defaultValue?: string | number;
  required?: boolean;
  children?: ReactNode;
  full?: boolean;
  step?: string;
}) {
  return (
    <label className={full ? "sm:col-span-2" : undefined}>
      <span className="erp-label">{label}</span>
      {children ?? (
        <input
          className="erp-field"
          defaultValue={defaultValue}
          name={name}
          required={required}
          step={step}
          type={type}
        />
      )}
    </label>
  );
}

function FormActions({ pending, onClose }: { pending: boolean; onClose: () => void }) {
  return (
    <div className="flex justify-end gap-2 border-t border-[var(--color-border)] bg-[var(--color-surface-subtle)] px-5 py-3">
      <button className="erp-button" onClick={onClose} type="button">
        Cancel
      </button>
      <button className="erp-button erp-button-primary" disabled={pending} type="submit">
        {pending ? "Saving..." : "Save"}
      </button>
    </div>
  );
}

function useCreateModal() {
  const router = useRouter();
  const params = useSearchParams();
  const open = params.get("new") === "1";
  return {
    open,
    show: () => router.push(`${window.location.pathname}?new=1`),
    close: () => router.replace(window.location.pathname),
  };
}

export function DashboardPage({ session }: { session: SessionPayload }) {
  const entity = activeEntity(session);
  const enabled = Boolean(entity);
  const expenses = useQuery({ queryKey: ["expenses", entity?.id], queryFn: financeApi.expenses, enabled });
  const income = useQuery({ queryKey: ["income", entity?.id], queryFn: financeApi.income, enabled });
  const accounts = useQuery({ queryKey: ["financial-accounts", entity?.id], queryFn: financeApi.accounts, enabled });
  const reimbursements = useQuery({
    queryKey: ["reimbursements", entity?.id],
    queryFn: financeApi.reimbursements,
    enabled,
  });

  const expenseTotal = (expenses.data ?? []).reduce((sum, item) => sum + Number(item.amount), 0);
  const incomeTotal = (income.data ?? []).reduce((sum, item) => sum + Number(item.amount), 0);
  const openExpenses = (expenses.data ?? []).filter((item) => item.status !== "PAID").length;
  const pendingReimbursements = (reimbursements.data ?? []).filter((item) =>
    ["DRAFT", "SUBMITTED", "APPROVED", "PARTIALLY_PAID"].includes(item.status),
  ).length;

  return (
    <>
      <PageHeader
        description="Financial overview and operational health for the active legal entity, derived from live MateERP finance records."
        eyebrow="Overview"
        title="Dashboard"
      />
      <MetricStrip
        metrics={[
          { label: "Recorded Income", value: money(incomeTotal, entity?.base_currency), note: "Current dataset", tone: "good" },
          { label: "Recorded Expenses", value: money(expenseTotal, entity?.base_currency), note: `${openExpenses} not fully paid`, tone: openExpenses ? "bad" : "default" },
          { label: "Net Movement", value: money(incomeTotal - expenseTotal, entity?.base_currency), note: "Income less expense documents", tone: incomeTotal >= expenseTotal ? "good" : "bad" },
          { label: "Financial Accounts", value: String(accounts.data?.length ?? 0), note: `${pendingReimbursements} reimbursement items open` },
        ]}
      />
      <PageContent>
        {!entity ? (
          <PermissionNotice>Select a legal entity from the header to load financial data.</PermissionNotice>
        ) : expenses.isLoading || income.isLoading ? (
          <LoadingState label="Loading finance overview..." />
        ) : expenses.error || income.error ? (
          <ErrorState message={errorMessage(expenses.error ?? income.error)} />
        ) : (
          <div className="grid gap-4 xl:grid-cols-[1.5fr_1fr]">
            <div>
              <div className="mb-3 flex items-center justify-between">
                <h2 className="text-sm font-semibold">Recent Expenses</h2>
                <span className="text-xs text-[var(--color-text-muted)]">Live operational records</span>
              </div>
              <DataTable
                columns={[
                  { key: "date", label: "Date", render: (row: Expense) => shortDate(row.expense_date) },
                  { key: "description", label: "Description", render: (row: Expense) => row.description },
                  { key: "reference", label: "Reference", render: (row: Expense) => row.reference || "—" },
                  { key: "amount", label: "Amount", numeric: true, render: (row: Expense) => money(row.amount, row.currency) },
                  { key: "status", label: "Status", render: (row: Expense) => <StatusBadge value={row.status} /> },
                ]}
                rowKey={(row) => row.id}
                rows={(expenses.data ?? []).slice(0, 8)}
              />
            </div>
            <div className="space-y-4">
              <div className="erp-panel">
                <div className="erp-panel-header"><h2 className="text-sm font-semibold">Finance Controls</h2><ShieldCheck size={15} /></div>
                <div className="divide-y divide-[var(--color-border-soft)] text-sm">
                  {[
                    ["Legal entity", entity.name],
                    ["Base currency", entity.base_currency],
                    ["Role", activeMembership(session)?.role ?? "—"],
                    ["Ledger authority", "Phase 4 double-entry journals"],
                  ].map(([label, value]) => (
                    <div className="grid grid-cols-[130px_1fr]" key={label}>
                      <div className="bg-[var(--color-surface-subtle)] px-3 py-2.5 text-xs font-semibold">{label}</div>
                      <div className="px-3 py-2.5 text-xs text-[var(--color-text-muted)]">{value}</div>
                    </div>
                  ))}
                </div>
              </div>
              <div className="erp-panel">
                <div className="erp-panel-header"><h2 className="text-sm font-semibold">Next Roadmap Boundary</h2></div>
                <div className="p-4 text-sm leading-6 text-[var(--color-text-muted)]">
                  Subscriptions, domains, infrastructure, budgets, cost centers, products, projects, and cost allocation remain scheduled for Phase 7. Phase 6 exposes only capabilities already backed by production APIs.
                </div>
              </div>
            </div>
          </div>
        )}
      </PageContent>
    </>
  );
}

export function VendorsPage({ session }: { session: SessionPayload }) {
  const queryClient = useQueryClient();
  const entity = activeEntity(session);
  const modal = useCreateModal();
  const [search, setSearch] = useState("");
  const vendors = useQuery({ queryKey: ["vendors", entity?.id], queryFn: financeApi.vendors, enabled: Boolean(entity) });
  const create = useMutation({
    mutationFn: financeApi.createVendor,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["vendors", entity?.id] });
      modal.close();
    },
  });
  const rows = (vendors.data ?? []).filter((vendor) => `${vendor.code} ${vendor.name} ${vendor.email}`.toLowerCase().includes(search.toLowerCase()));

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(event.currentTarget).entries());
    create.mutate({ ...data, payment_terms_days: Number(data.payment_terms_days ?? 0) });
  }

  const columns: Array<TableColumn<Vendor>> = [
    { key: "code", label: "Code", render: (row) => <span className="font-semibold">{row.code}</span> },
    { key: "name", label: "Vendor", render: (row) => row.name },
    { key: "contact", label: "Contact", render: (row) => row.contact_name || "—" },
    { key: "email", label: "Email", render: (row) => row.email || "—" },
    { key: "terms", label: "Terms", render: (row) => `${row.payment_terms_days} days` },
    { key: "status", label: "Status", render: (row) => <StatusBadge value={row.status} /> },
  ];

  return (
    <>
      <PageHeader description="Manage vendors and their default expense/payable accounting relationships." eyebrow="Finance" title="Vendors" />
      <PageContent>
        <Toolbar canCreate={can(session, "MANAGE_FINANCE")} newLabel="Add Vendor" onNew={modal.show} onSearch={setSearch} search={search} />
        {!entity ? <PermissionNotice>Select a legal entity first.</PermissionNotice> : vendors.isLoading ? <LoadingState /> : vendors.error ? <ErrorState message={errorMessage(vendors.error)} /> : <DataTable columns={columns} rowKey={(row) => row.id} rows={rows} />}
      </PageContent>
      {modal.open ? (
        <Modal description="Create vendor master data. Accounting defaults can be configured later." onClose={modal.close} title="Add Vendor">
          <form onSubmit={submit}>
            <FormGrid>
              <Field label="Vendor code" name="code" required />
              <Field label="Vendor name" name="name" required />
              <Field label="Contact name" name="contact_name" />
              <Field label="Email" name="email" type="email" />
              <Field label="Phone" name="phone" />
              <Field defaultValue="0" label="Payment terms (days)" name="payment_terms_days" type="number" />
              {create.error ? <div className="sm:col-span-2"><ErrorState message={errorMessage(create.error)} /></div> : null}
            </FormGrid>
            <FormActions onClose={modal.close} pending={create.isPending} />
          </form>
        </Modal>
      ) : null}
    </>
  );
}

function ExpenseForm({ session, onClose }: { session: SessionPayload; onClose: () => void }) {
  const queryClient = useQueryClient();
  const entity = activeEntity(session);
  const vendors = useQuery({ queryKey: ["vendors", entity?.id], queryFn: financeApi.vendors, enabled: Boolean(entity) });
  const ledger = useQuery({ queryKey: ["ledger-accounts", entity?.id], queryFn: accountingApi.accounts, enabled: Boolean(entity) });
  const create = useMutation({
    mutationFn: financeApi.createExpense,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["expenses", entity?.id] });
      onClose();
    },
  });
  const expenseAccounts = (ledger.data ?? []).filter((item) => item.account_type === "EXPENSE");
  const payableAccounts = (ledger.data ?? []).filter((item) => item.account_type === "LIABILITY");

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(event.currentTarget).entries());
    create.mutate({
      ...data,
      vendor: data.vendor || null,
      due_date: data.due_date || null,
      reference: data.reference || "",
      tax_amount: data.tax_amount || "0",
      currency: String(data.currency || entity?.base_currency || "USD").toUpperCase(),
      fx_rate: data.fx_rate || "1",
    });
  }

  return (
    <form onSubmit={submit}>
      <FormGrid>
        <Field defaultValue={today()} label="Expense date" name="expense_date" required type="date" />
        <Field label="Due date" name="due_date" type="date" />
        <Field full label="Description" name="description" required />
        <Field label="Vendor" name="vendor">
          <select className="erp-field" defaultValue="" name="vendor">
            <option value="">No vendor</option>
            {(vendors.data ?? []).map((vendor) => <option key={vendor.id} value={vendor.id}>{vendor.name}</option>)}
          </select>
        </Field>
        <Field label="Reference" name="reference" />
        <Field label="Amount" name="amount" required step="0.01" type="number" />
        <Field defaultValue="0" label="Tax amount" name="tax_amount" step="0.01" type="number" />
        <Field defaultValue={entity?.base_currency ?? "USD"} label="Currency" name="currency" required />
        <Field defaultValue="1" label="FX rate" name="fx_rate" required step="0.0000000001" type="number" />
        <Field label="Expense account" name="expense_account">
          <select className="erp-field" name="expense_account" required>
            <option value="">Select expense account</option>
            {expenseAccounts.map((account) => <option key={account.id} value={account.id}>{account.code} · {account.name}</option>)}
          </select>
        </Field>
        <Field label="Payable account" name="payable_account">
          <select className="erp-field" name="payable_account" required>
            <option value="">Select payable account</option>
            {payableAccounts.map((account) => <option key={account.id} value={account.id}>{account.code} · {account.name}</option>)}
          </select>
        </Field>
        {create.error ? <div className="sm:col-span-2"><ErrorState message={errorMessage(create.error)} /></div> : null}
      </FormGrid>
      <FormActions onClose={onClose} pending={create.isPending} />
    </form>
  );
}

function PaymentDialog({
  session,
  record,
  type,
  onClose,
}: {
  session: SessionPayload;
  record: Expense | Reimbursement;
  type: "expense" | "reimbursement";
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const entity = activeEntity(session);
  const accounts = useQuery({ queryKey: ["financial-accounts", entity?.id], queryFn: financeApi.accounts, enabled: Boolean(entity) });
  const mutation = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      type === "expense"
        ? financeApi.payExpense(record.id, body)
        : request(
            `/api/v1/finance/reimbursements/${record.id}/payments/`,
            { method: "POST", body: JSON.stringify(body) },
            true,
          ),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: [type === "expense" ? "expenses" : "reimbursements", entity?.id] });
      onClose();
    },
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(event.currentTarget).entries());
    mutation.mutate({ ...data, fx_rate: data.fx_rate || "1" });
  }

  return (
    <Modal description="Payments create a separate posted journal and reduce the outstanding payable." onClose={onClose} title={type === "expense" ? "Pay Expense" : "Pay Reimbursement"}>
      <form onSubmit={submit}>
        <FormGrid>
          <Field label="Financial account" name="financial_account">
            <select className="erp-field" name="financial_account" required>
              <option value="">Select financial account</option>
              {(accounts.data ?? []).filter((account) => account.is_active).map((account) => <option key={account.id} value={account.id}>{account.name} · {account.currency}</option>)}
            </select>
          </Field>
          <Field defaultValue={today()} label="Payment date" name="payment_date" required type="date" />
          <Field defaultValue={record.amount} label="Amount" name="amount" required step="0.01" type="number" />
          <Field defaultValue={record.currency} label="Currency" name="currency" required />
          <Field defaultValue="1" label="FX rate" name="fx_rate" required step="0.0000000001" type="number" />
          <Field label="Reference" name="reference" />
          {mutation.error ? <div className="sm:col-span-2"><ErrorState message={errorMessage(mutation.error)} /></div> : null}
        </FormGrid>
        <FormActions onClose={onClose} pending={mutation.isPending} />
      </form>
    </Modal>
  );
}

export function ExpensesPage({ session }: { session: SessionPayload }) {
  const queryClient = useQueryClient();
  const entity = activeEntity(session);
  const modal = useCreateModal();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [paying, setPaying] = useState<Expense | null>(null);
  const expenses = useQuery({ queryKey: ["expenses", entity?.id], queryFn: financeApi.expenses, enabled: Boolean(entity) });
  const vendors = useQuery({ queryKey: ["vendors", entity?.id], queryFn: financeApi.vendors, enabled: Boolean(entity) });
  const vendorMap = new Map((vendors.data ?? []).map((vendor) => [vendor.id, vendor.name]));
  const workflow = useMutation({
    mutationFn: ({ id, action }: { id: string; action: "submit" | "approve" | "reject" }) =>
      financeApi.expenseWorkflow(id, action, action === "reject" ? "Rejected from Phase 6 workspace" : ""),
    onSuccess: async () => queryClient.invalidateQueries({ queryKey: ["expenses", entity?.id] }),
  });

  const rows = (expenses.data ?? []).filter((expense) => {
    const matchesSearch = `${expense.description} ${expense.reference} ${vendorMap.get(expense.vendor ?? "") ?? ""}`.toLowerCase().includes(search.toLowerCase());
    return matchesSearch && (statusFilter === "ALL" || expense.status === statusFilter);
  });

  const columns: Array<TableColumn<Expense>> = [
    { key: "date", label: "Date", render: (row) => shortDate(row.expense_date) },
    { key: "vendor", label: "Vendor", render: (row) => vendorMap.get(row.vendor ?? "") ?? "—" },
    { key: "description", label: "Description", render: (row) => <span className="font-medium">{row.description}</span> },
    { key: "reference", label: "Reference", render: (row) => row.reference || "—" },
    { key: "amount", label: "Amount", numeric: true, render: (row) => money(row.amount, row.currency) },
    { key: "status", label: "Status", render: (row) => <StatusBadge value={row.status} /> },
    {
      key: "actions",
      label: "Actions",
      render: (row) => (
        <div className="flex gap-1">
          {row.status === "DRAFT" && can(session, "SUBMIT_FINANCE") ? <button className="erp-button !h-7 !min-h-7 !px-2" onClick={() => workflow.mutate({ id: row.id, action: "submit" })} type="button">Submit</button> : null}
          {row.status === "SUBMITTED" && can(session, "APPROVE_FINANCE") ? <><button className="erp-button !h-7 !min-h-7 !px-2" onClick={() => workflow.mutate({ id: row.id, action: "approve" })} type="button"><Check size={11} /> Approve</button><button className="erp-button erp-button-danger !h-7 !min-h-7 !px-2" onClick={() => workflow.mutate({ id: row.id, action: "reject" })} type="button">Reject</button></> : null}
          {["APPROVED", "PARTIALLY_PAID"].includes(row.status) && can(session, "PAY_FINANCE") ? <button className="erp-button !h-7 !min-h-7 !px-2" onClick={() => setPaying(row)} type="button"><CreditCard size={11} /> Pay</button> : null}
        </div>
      ),
    },
  ];

  const total = (expenses.data ?? []).reduce((sum, item) => sum + Number(item.amount), 0);
  const outstanding = (expenses.data ?? []).filter((item) => item.status !== "PAID").reduce((sum, item) => sum + Number(item.amount), 0);

  return (
    <>
      <PageHeader description="Track, approve, accrue, and settle company expenses without collapsing expense documents into payments." eyebrow="Finance" title="Expenses" />
      <MetricStrip metrics={[{ label: "Total Recorded", value: money(total, entity?.base_currency) }, { label: "Open Face Value", value: money(outstanding, entity?.base_currency), tone: outstanding ? "bad" : "default" }, { label: "Documents", value: String(expenses.data?.length ?? 0) }, { label: "Pending Approval", value: String((expenses.data ?? []).filter((item) => item.status === "SUBMITTED").length) }]} />
      <PageContent>
        <Toolbar canCreate={can(session, "SUBMIT_FINANCE")} filters={<select className="erp-field !h-8 !min-h-8 !w-auto text-xs" onChange={(event) => setStatusFilter(event.target.value)} value={statusFilter}><option value="ALL">All statuses</option>{["DRAFT", "SUBMITTED", "APPROVED", "PARTIALLY_PAID", "PAID", "REJECTED"].map((status) => <option key={status} value={status}>{status.replaceAll("_", " ")}</option>)}</select>} newLabel="Add Expense" onNew={modal.show} onSearch={setSearch} search={search} />
        {!entity ? <PermissionNotice>Select a legal entity first.</PermissionNotice> : expenses.isLoading ? <LoadingState /> : expenses.error ? <ErrorState message={errorMessage(expenses.error)} /> : <DataTable columns={columns} rowKey={(row) => row.id} rows={rows} />}
        {workflow.error ? <div className="mt-3"><ErrorState message={errorMessage(workflow.error)} /></div> : null}
      </PageContent>
      {modal.open ? <Modal description="Create the operational expense document. Submit and approval remain explicit actions." onClose={modal.close} title="Add Expense"><ExpenseForm onClose={modal.close} session={session} /></Modal> : null}
      {paying ? <PaymentDialog onClose={() => setPaying(null)} record={paying} session={session} type="expense" /> : null}
    </>
  );
}

export function IncomePage({ session }: { session: SessionPayload }) {
  const queryClient = useQueryClient();
  const entity = activeEntity(session);
  const modal = useCreateModal();
  const [search, setSearch] = useState("");
  const rowsQuery = useQuery({ queryKey: ["income", entity?.id], queryFn: financeApi.income, enabled: Boolean(entity) });
  const ledger = useQuery({ queryKey: ["ledger-accounts", entity?.id], queryFn: accountingApi.accounts, enabled: Boolean(entity) });
  const financial = useQuery({ queryKey: ["financial-accounts", entity?.id], queryFn: financeApi.accounts, enabled: Boolean(entity) });
  const create = useMutation({ mutationFn: financeApi.createIncome, onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: ["income", entity?.id] }); modal.close(); } });
  const rows = (rowsQuery.data ?? []).filter((item) => `${item.payer_name} ${item.description} ${item.reference}`.toLowerCase().includes(search.toLowerCase()));

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(event.currentTarget).entries());
    create.mutate({ ...data, reference: data.reference || "", currency: String(data.currency || entity?.base_currency || "USD").toUpperCase(), fx_rate: data.fx_rate || "1" });
  }

  const columns: Array<TableColumn<Income>> = [
    { key: "date", label: "Date", render: (row) => shortDate(row.income_date) },
    { key: "payer", label: "Payer", render: (row) => row.payer_name || "—" },
    { key: "description", label: "Description", render: (row) => row.description },
    { key: "reference", label: "Reference", render: (row) => row.reference || "—" },
    { key: "amount", label: "Amount", numeric: true, render: (row) => money(row.amount, row.currency) },
    { key: "status", label: "Status", render: (row) => <StatusBadge value={row.status} /> },
  ];

  return (
    <>
      <PageHeader description="Record company income directly into the selected financial account and revenue ledger account." eyebrow="Finance" title="Income" />
      <PageContent>
        <Toolbar canCreate={can(session, "MANAGE_FINANCE")} newLabel="Record Income" onNew={modal.show} onSearch={setSearch} search={search} />
        {!entity ? <PermissionNotice>Select a legal entity first.</PermissionNotice> : rowsQuery.isLoading ? <LoadingState /> : rowsQuery.error ? <ErrorState message={errorMessage(rowsQuery.error)} /> : <DataTable columns={columns} rowKey={(row) => row.id} rows={rows} />}
      </PageContent>
      {modal.open ? <Modal description="Recording income posts a balanced journal immediately through the Phase 4 accounting engine." onClose={modal.close} title="Record Income"><form onSubmit={submit}><FormGrid><Field defaultValue={today()} label="Income date" name="income_date" required type="date" /><Field label="Payer" name="payer_name" /><Field full label="Description" name="description" required /><Field label="Reference" name="reference" /><Field label="Amount" name="amount" required step="0.01" type="number" /><Field defaultValue={entity?.base_currency ?? "USD"} label="Currency" name="currency" required /><Field defaultValue="1" label="FX rate" name="fx_rate" required step="0.0000000001" type="number" /><Field label="Revenue account" name="revenue_account"><select className="erp-field" name="revenue_account" required><option value="">Select revenue account</option>{(ledger.data ?? []).filter((item) => item.account_type === "REVENUE").map((account) => <option key={account.id} value={account.id}>{account.code} · {account.name}</option>)}</select></Field><Field label="Financial account" name="financial_account"><select className="erp-field" name="financial_account" required><option value="">Select receiving account</option>{(financial.data ?? []).filter((item) => item.is_active).map((account) => <option key={account.id} value={account.id}>{account.name} · {account.currency}</option>)}</select></Field>{create.error ? <div className="sm:col-span-2"><ErrorState message={errorMessage(create.error)} /></div> : null}</FormGrid><FormActions onClose={modal.close} pending={create.isPending} /></form></Modal> : null}
    </>
  );
}

export function TransfersPage({ session }: { session: SessionPayload }) {
  const queryClient = useQueryClient();
  const entity = activeEntity(session);
  const modal = useCreateModal();
  const [search, setSearch] = useState("");
  const rowsQuery = useQuery({ queryKey: ["transfers", entity?.id], queryFn: financeApi.transfers, enabled: Boolean(entity) });
  const accounts = useQuery({ queryKey: ["financial-accounts", entity?.id], queryFn: financeApi.accounts, enabled: Boolean(entity) });
  const create = useMutation({ mutationFn: financeApi.createTransfer, onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: ["transfers", entity?.id] }); modal.close(); } });
  const accountMap = new Map((accounts.data ?? []).map((account) => [account.id, account.name]));
  const rows = (rowsQuery.data ?? []).filter((item) => `${item.reference} ${item.memo} ${accountMap.get(item.from_account) ?? ""} ${accountMap.get(item.to_account) ?? ""}`.toLowerCase().includes(search.toLowerCase()));

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(event.currentTarget).entries());
    create.mutate({ ...data, source_fx_rate: data.source_fx_rate || "1", destination_fx_rate: data.destination_fx_rate || "1", reference: data.reference || "", memo: data.memo || "" });
  }

  const columns: Array<TableColumn<Transfer>> = [
    { key: "date", label: "Date", render: (row) => shortDate(row.transfer_date) },
    { key: "from", label: "From", render: (row) => accountMap.get(row.from_account) ?? row.from_account },
    { key: "to", label: "To", render: (row) => accountMap.get(row.to_account) ?? row.to_account },
    { key: "source", label: "Source Amount", numeric: true, render: (row) => row.source_amount },
    { key: "destination", label: "Destination Amount", numeric: true, render: (row) => row.destination_amount },
    { key: "reference", label: "Reference", render: (row) => row.reference || "—" },
    { key: "status", label: "Status", render: (row) => <StatusBadge value={row.status} /> },
  ];

  return (
    <>
      <PageHeader description="Move funds between internal financial accounts. Cross-currency transfers must balance in base currency." eyebrow="Finance" title="Transfers" />
      <PageContent><Toolbar canCreate={can(session, "MANAGE_FINANCE")} newLabel="New Transfer" onNew={modal.show} onSearch={setSearch} search={search} />{!entity ? <PermissionNotice>Select a legal entity first.</PermissionNotice> : rowsQuery.isLoading ? <LoadingState /> : rowsQuery.error ? <ErrorState message={errorMessage(rowsQuery.error)} /> : <DataTable columns={columns} rowKey={(row) => row.id} rows={rows} />}</PageContent>
      {modal.open ? <Modal description="The source and destination legs must resolve to the same base-currency value." onClose={modal.close} title="New Transfer"><form onSubmit={submit}><FormGrid><Field defaultValue={today()} label="Transfer date" name="transfer_date" required type="date" /><Field label="Reference" name="reference" /><Field label="From account" name="from_account"><select className="erp-field" name="from_account" required><option value="">Select source</option>{(accounts.data ?? []).filter((item) => item.is_active).map((account) => <option key={account.id} value={account.id}>{account.name} · {account.currency}</option>)}</select></Field><Field label="To account" name="to_account"><select className="erp-field" name="to_account" required><option value="">Select destination</option>{(accounts.data ?? []).filter((item) => item.is_active).map((account) => <option key={account.id} value={account.id}>{account.name} · {account.currency}</option>)}</select></Field><Field label="Source amount" name="source_amount" required step="0.01" type="number" /><Field label="Destination amount" name="destination_amount" required step="0.01" type="number" /><Field defaultValue="1" label="Source FX rate" name="source_fx_rate" required step="0.0000000001" type="number" /><Field defaultValue="1" label="Destination FX rate" name="destination_fx_rate" required step="0.0000000001" type="number" /><Field full label="Memo" name="memo" />{create.error ? <div className="sm:col-span-2"><ErrorState message={errorMessage(create.error)} /></div> : null}</FormGrid><FormActions onClose={modal.close} pending={create.isPending} /></form></Modal> : null}
    </>
  );
}

export function FinancialAccountsPage({ session }: { session: SessionPayload }) {
  const queryClient = useQueryClient();
  const entity = activeEntity(session);
  const modal = useCreateModal();
  const [search, setSearch] = useState("");
  const rowsQuery = useQuery({ queryKey: ["financial-accounts", entity?.id], queryFn: financeApi.accounts, enabled: Boolean(entity) });
  const ledger = useQuery({ queryKey: ["ledger-accounts", entity?.id], queryFn: accountingApi.accounts, enabled: Boolean(entity) });
  const create = useMutation({
    mutationFn: (body: Record<string, unknown>) => request<FinancialAccount>("/api/v1/finance/accounts/", { method: "POST", body: JSON.stringify(body) }, true),
    onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: ["financial-accounts", entity?.id] }); modal.close(); },
  });
  const rows = (rowsQuery.data ?? []).filter((item) => `${item.name} ${item.institution_name} ${item.currency}`.toLowerCase().includes(search.toLowerCase()));

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(event.currentTarget).entries());
    create.mutate({ ...data, is_active: true, institution_name: data.institution_name || "", last_four: data.last_four || "" });
  }

  const columns: Array<TableColumn<FinancialAccount>> = [
    { key: "name", label: "Account", render: (row) => <span className="font-semibold">{row.name}</span> },
    { key: "type", label: "Type", render: (row) => row.account_type.replaceAll("_", " ") },
    { key: "institution", label: "Institution", render: (row) => row.institution_name || "—" },
    { key: "currency", label: "Currency", render: (row) => row.currency },
    { key: "last_four", label: "Last Four", render: (row) => row.last_four ? `•••• ${row.last_four}` : "—" },
    { key: "status", label: "Status", render: (row) => <StatusBadge value={row.is_active ? "ACTIVE" : "INACTIVE"} /> },
  ];

  return (
    <>
      <PageHeader description="Represent where company money exists or moves. Authoritative balances remain ledger-derived." eyebrow="Finance" title="Financial Accounts" />
      <PageContent><Toolbar canCreate={can(session, "MANAGE_FINANCE")} newLabel="Add Account" onNew={modal.show} onSearch={setSearch} search={search} />{!entity ? <PermissionNotice>Select a legal entity first.</PermissionNotice> : rowsQuery.isLoading ? <LoadingState /> : rowsQuery.error ? <ErrorState message={errorMessage(rowsQuery.error)} /> : <DataTable columns={columns} rowKey={(row) => row.id} rows={rows} />}</PageContent>
      {modal.open ? <Modal description="Map the operational financial account to an appropriate Chart of Accounts ledger account." onClose={modal.close} title="Add Financial Account"><form onSubmit={submit}><FormGrid><Field label="Account name" name="name" required /><Field label="Account type" name="account_type"><select className="erp-field" defaultValue="BANK" name="account_type"><option value="BANK">Bank</option><option value="CASH">Cash</option><option value="CREDIT_CARD">Credit card</option><option value="WALLET">Wallet</option><option value="PAYMENT_PROCESSOR">Payment processor</option></select></Field><Field defaultValue={entity?.base_currency ?? "USD"} label="Currency" name="currency" required /><Field label="Ledger account" name="ledger_account"><select className="erp-field" name="ledger_account" required><option value="">Select ledger account</option>{(ledger.data ?? []).map((account) => <option key={account.id} value={account.id}>{account.code} · {account.name} ({account.account_type})</option>)}</select></Field><Field label="Institution" name="institution_name" /><Field label="Last four" name="last_four" />{create.error ? <div className="sm:col-span-2"><ErrorState message={errorMessage(create.error)} /></div> : null}</FormGrid><FormActions onClose={modal.close} pending={create.isPending} /></form></Modal> : null}
    </>
  );
}

export function ReimbursementsPage({ session }: { session: SessionPayload }) {
  const queryClient = useQueryClient();
  const entity = activeEntity(session);
  const modal = useCreateModal();
  const [search, setSearch] = useState("");
  const [paying, setPaying] = useState<Reimbursement | null>(null);
  const rowsQuery = useQuery({ queryKey: ["reimbursements", entity?.id], queryFn: financeApi.reimbursements, enabled: Boolean(entity) });
  const ledger = useQuery({ queryKey: ["ledger-accounts", entity?.id], queryFn: accountingApi.accounts, enabled: Boolean(entity) });
  const workflow = useMutation({ mutationFn: ({ id, action }: { id: string; action: "submit" | "approve" | "reject" }) => financeApi.reimbursementWorkflow(id, action, action === "reject" ? "Rejected from Phase 6 workspace" : ""), onSuccess: async () => queryClient.invalidateQueries({ queryKey: ["reimbursements", entity?.id] }) });
  const create = useMutation({ mutationFn: financeApi.createReimbursement, onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: ["reimbursements", entity?.id] }); modal.close(); } });
  const rows = (rowsQuery.data ?? []).filter((item) => item.description.toLowerCase().includes(search.toLowerCase()));

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(event.currentTarget).entries());
    create.mutate({ ...data, claimant: session.user.id, currency: String(data.currency || entity?.base_currency || "USD").toUpperCase(), fx_rate: data.fx_rate || "1" });
  }

  const columns: Array<TableColumn<Reimbursement>> = [
    { key: "date", label: "Expense Date", render: (row) => shortDate(row.expense_date) },
    { key: "description", label: "Description", render: (row) => row.description },
    { key: "amount", label: "Amount", numeric: true, render: (row) => money(row.amount, row.currency) },
    { key: "status", label: "Status", render: (row) => <StatusBadge value={row.status} /> },
    { key: "actions", label: "Actions", render: (row) => <div className="flex gap-1">{row.status === "DRAFT" && can(session, "SUBMIT_FINANCE") ? <button className="erp-button !h-7 !min-h-7 !px-2" onClick={() => workflow.mutate({ id: row.id, action: "submit" })} type="button">Submit</button> : null}{row.status === "SUBMITTED" && can(session, "APPROVE_FINANCE") ? <><button className="erp-button !h-7 !min-h-7 !px-2" onClick={() => workflow.mutate({ id: row.id, action: "approve" })} type="button">Approve</button><button className="erp-button erp-button-danger !h-7 !min-h-7 !px-2" onClick={() => workflow.mutate({ id: row.id, action: "reject" })} type="button">Reject</button></> : null}{["APPROVED", "PARTIALLY_PAID"].includes(row.status) && can(session, "PAY_FINANCE") ? <button className="erp-button !h-7 !min-h-7 !px-2" onClick={() => setPaying(row)} type="button">Pay</button> : null}</div> },
  ];

  return (
    <>
      <PageHeader description="Manage company costs paid personally by an active organization member, with approval and settlement separated." eyebrow="Finance" title="Reimbursements" />
      <PageContent><Toolbar canCreate={can(session, "SUBMIT_FINANCE")} newLabel="New Reimbursement" onNew={modal.show} onSearch={setSearch} search={search} />{!entity ? <PermissionNotice>Select a legal entity first.</PermissionNotice> : rowsQuery.isLoading ? <LoadingState /> : rowsQuery.error ? <ErrorState message={errorMessage(rowsQuery.error)} /> : <DataTable columns={columns} rowKey={(row) => row.id} rows={rows} />}{workflow.error ? <div className="mt-3"><ErrorState message={errorMessage(workflow.error)} /></div> : null}</PageContent>
      {modal.open ? <Modal description="The claimant defaults to the signed-in member for this core workflow." onClose={modal.close} title="New Reimbursement"><form onSubmit={submit}><FormGrid><Field defaultValue={today()} label="Expense date" name="expense_date" required type="date" /><Field label="Amount" name="amount" required step="0.01" type="number" /><Field full label="Description" name="description" required /><Field defaultValue={entity?.base_currency ?? "USD"} label="Currency" name="currency" required /><Field defaultValue="1" label="FX rate" name="fx_rate" required step="0.0000000001" type="number" /><Field label="Expense account" name="expense_account"><select className="erp-field" name="expense_account" required><option value="">Select expense account</option>{(ledger.data ?? []).filter((item) => item.account_type === "EXPENSE").map((account) => <option key={account.id} value={account.id}>{account.code} · {account.name}</option>)}</select></Field><Field label="Payable account" name="payable_account"><select className="erp-field" name="payable_account" required><option value="">Select liability account</option>{(ledger.data ?? []).filter((item) => item.account_type === "LIABILITY").map((account) => <option key={account.id} value={account.id}>{account.code} · {account.name}</option>)}</select></Field>{create.error ? <div className="sm:col-span-2"><ErrorState message={errorMessage(create.error)} /></div> : null}</FormGrid><FormActions onClose={modal.close} pending={create.isPending} /></form></Modal> : null}
      {paying ? <PaymentDialog onClose={() => setPaying(null)} record={paying} session={session} type="reimbursement" /> : null}
    </>
  );
}

export function LedgerAccountsPage({ session }: { session: SessionPayload }) {
  const entity = activeEntity(session);
  const [search, setSearch] = useState("");
  const query = useQuery({ queryKey: ["ledger-accounts", entity?.id], queryFn: accountingApi.accounts, enabled: Boolean(entity) });
  const rows = (query.data ?? []).filter((item) => `${item.code} ${item.name} ${item.account_type}`.toLowerCase().includes(search.toLowerCase()));
  const columns: Array<TableColumn<LedgerAccount>> = [
    { key: "code", label: "Code", render: (row) => <span className="font-semibold">{row.code}</span> },
    { key: "name", label: "Account", render: (row) => row.name },
    { key: "type", label: "Type", render: (row) => row.account_type },
    { key: "normal", label: "Normal Balance", render: (row) => row.normal_balance },
    { key: "status", label: "Status", render: (row) => <StatusBadge value={row.is_active ? "ACTIVE" : "INACTIVE"} /> },
  ];
  return <><PageHeader description="Ledger accounts define financial classification and remain separate from operational financial accounts." eyebrow="Accounting" title="Chart of Accounts" /><PageContent><Toolbar canCreate={false} onSearch={setSearch} search={search} />{!entity ? <PermissionNotice>Select a legal entity first.</PermissionNotice> : query.isLoading ? <LoadingState /> : query.error ? <ErrorState message={errorMessage(query.error)} /> : <DataTable columns={columns} rowKey={(row) => row.id} rows={rows} />}</PageContent></>;
}

export function JournalsPage({ session }: { session: SessionPayload }) {
  const queryClient = useQueryClient();
  const entity = activeEntity(session);
  const [search, setSearch] = useState("");
  const query = useQuery({ queryKey: ["journals", entity?.id], queryFn: accountingApi.journals, enabled: Boolean(entity) });
  const post = useMutation({ mutationFn: (id: string) => request(`/api/v1/accounting/journals/${id}/post/`, { method: "POST", body: JSON.stringify({}) }, true), onSuccess: async () => queryClient.invalidateQueries({ queryKey: ["journals", entity?.id] }) });
  const reverse = useMutation({ mutationFn: (id: string) => request(`/api/v1/accounting/journals/${id}/reverse/`, { method: "POST", body: JSON.stringify({ reason: "Reversed from Phase 6 workspace" }) }, true), onSuccess: async () => queryClient.invalidateQueries({ queryKey: ["journals", entity?.id] }) });
  const rows = (query.data ?? []).filter((item) => `${item.number} ${item.memo} ${item.source_type}`.toLowerCase().includes(search.toLowerCase()));
  const columns: Array<TableColumn<JournalEntry>> = [
    { key: "number", label: "Journal", render: (row) => <span className="font-semibold">{row.number}</span> },
    { key: "date", label: "Date", render: (row) => shortDate(row.entry_date) },
    { key: "memo", label: "Memo", render: (row) => row.memo || "—" },
    { key: "source", label: "Source", render: (row) => row.source_type || "MANUAL" },
    { key: "lines", label: "Lines", numeric: true, render: (row) => String(row.lines?.length ?? 0) },
    { key: "status", label: "Status", render: (row) => <StatusBadge value={row.status} /> },
    { key: "actions", label: "Actions", render: (row) => <div className="flex gap-1">{row.status === "DRAFT" && can(session, "POST_JOURNAL") ? <button className="erp-button !h-7 !min-h-7 !px-2" onClick={() => post.mutate(row.id)} type="button">Post</button> : null}{row.status === "POSTED" && can(session, "REVERSE_JOURNAL") ? <button className="erp-button erp-button-danger !h-7 !min-h-7 !px-2" onClick={() => reverse.mutate(row.id)} type="button">Reverse</button> : null}</div> },
  ];
  return <><PageHeader description="Review operational and manual journal entries. Posted accounting facts remain immutable and corrections use reversal." eyebrow="Accounting" title="Journal Entries" /><PageContent><Toolbar canCreate={false} onSearch={setSearch} search={search} />{!entity ? <PermissionNotice>Select a legal entity first.</PermissionNotice> : query.isLoading ? <LoadingState /> : query.error ? <ErrorState message={errorMessage(query.error)} /> : <DataTable columns={columns} rowKey={(row) => row.id} rows={rows} />}{post.error || reverse.error ? <div className="mt-3"><ErrorState message={errorMessage(post.error ?? reverse.error)} /></div> : null}</PageContent></>;
}

function ReportCard({ title, value, icon }: { title: string; value: string; icon: ReactNode }) {
  return <div className="erp-panel p-4"><div className="flex items-center justify-between text-[10px] font-bold uppercase tracking-[0.1em] text-[var(--color-text-muted)]"><span>{title}</span>{icon}</div><div className="mt-2 text-2xl font-bold tabular-nums">{value}</div></div>;
}

export function ReportsPage({ session }: { session: SessionPayload }) {
  const entity = activeEntity(session);
  const [startDate, setStartDate] = useState(firstDayOfYear());
  const [endDate, setEndDate] = useState(today());
  const enabled = Boolean(entity && startDate && endDate);
  const pnl = useQuery({ queryKey: ["report-pnl", entity?.id, startDate, endDate], queryFn: () => request<Record<string, string>>(`/api/v1/accounting/reports/profit-loss/?start_date=${startDate}&end_date=${endDate}`), enabled });
  const cash = useQuery({ queryKey: ["report-cash", entity?.id, startDate, endDate], queryFn: () => request<Record<string, string>>(`/api/v1/accounting/reports/cash-flow/?start_date=${startDate}&end_date=${endDate}`), enabled });
  const balance = useQuery({ queryKey: ["report-balance", entity?.id, endDate], queryFn: () => request<Record<string, string>>(`/api/v1/accounting/reports/balance-sheet/?as_of=${endDate}`), enabled });
  const trial = useQuery({ queryKey: ["report-trial", entity?.id, startDate, endDate], queryFn: () => request<Array<Record<string, string>>>(`/api/v1/accounting/reports/trial-balance/?start_date=${startDate}&end_date=${endDate}`), enabled });
  const base = entity?.base_currency ?? "USD";
  return <><PageHeader description="Ledger-derived financial reports. Values are read-only outputs from posted accounting data." eyebrow="Reporting" title="Financial Reports" /><PageContent><div className="mb-4 flex flex-wrap items-end gap-3 border border-[var(--color-border)] bg-white p-3"><label><span className="erp-label">From</span><input className="erp-field !w-auto" onChange={(event) => setStartDate(event.target.value)} type="date" value={startDate} /></label><label><span className="erp-label">To / As of</span><input className="erp-field !w-auto" onChange={(event) => setEndDate(event.target.value)} type="date" value={endDate} /></label><span className="pb-2 text-xs text-[var(--color-text-muted)]">Base currency: {base}</span></div>{!entity ? <PermissionNotice>Select a legal entity first.</PermissionNotice> : pnl.isLoading || cash.isLoading || balance.isLoading ? <LoadingState label="Calculating reports from posted journals..." /> : pnl.error || cash.error || balance.error ? <ErrorState message={errorMessage(pnl.error ?? cash.error ?? balance.error)} /> : <><div className="mb-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4"><ReportCard icon={<Landmark size={15} />} title="Revenue" value={money(pnl.data?.revenue, base)} /><ReportCard icon={<FileText size={15} />} title="Expenses" value={money(pnl.data?.expenses, base)} /><ReportCard icon={<ArrowRight size={15} />} title="Net Income" value={money(pnl.data?.net_income, base)} /><ReportCard icon={<Landmark size={15} />} title="Net Cash Change" value={money(cash.data?.net_cash_change, base)} /></div><div className="grid gap-4 xl:grid-cols-[1fr_1.4fr]"><div className="erp-panel"><div className="erp-panel-header"><h2 className="text-sm font-semibold">Balance Sheet Summary</h2></div><div className="divide-y divide-[var(--color-border-soft)]">{[["Assets", balance.data?.assets], ["Liabilities", balance.data?.liabilities], ["Equity", balance.data?.equity], ["Retained earnings", balance.data?.retained_earnings], ["Liabilities + equity", balance.data?.liabilities_and_equity]].map(([label, value]) => <div className="flex justify-between px-4 py-3 text-sm" key={label}><span>{label}</span><strong className="tabular-nums">{money(value, base)}</strong></div>)}</div></div><div>{trial.isLoading ? <LoadingState /> : trial.error ? <ErrorState message={errorMessage(trial.error)} /> : <DataTable columns={[{ key: "code", label: "Code", render: (row: Record<string, string>) => row.account__code ?? "—" }, { key: "name", label: "Account", render: (row: Record<string, string>) => row.account__name ?? "—" }, { key: "debit", label: "Debit", numeric: true, render: (row: Record<string, string>) => money(row.debit, base) }, { key: "credit", label: "Credit", numeric: true, render: (row: Record<string, string>) => money(row.credit, base) }, { key: "balance", label: "Balance", numeric: true, render: (row: Record<string, string>) => money(row.balance, base) }]} emptyDescription="Posted journals will populate the trial balance." emptyTitle="No posted balances" rowKey={(row) => String(row.account_id)} rows={trial.data ?? []} />}</div></div></>}</PageContent></>;
}

export function MembersPage({ session }: { session: SessionPayload }) {
  const entity = activeEntity(session);
  const query = useQuery({ queryKey: ["members", session.active_organization_id], queryFn: adminApi.members, enabled: Boolean(session.active_organization_id) });
  const rows = query.data ?? [];
  return <><PageHeader description="Organization membership, role, status, and legal-entity scope. Backend RBAC remains authoritative." eyebrow="Administration" title="Members & Access" /><PageContent>{query.isLoading ? <LoadingState /> : query.error ? <ErrorState message={errorMessage(query.error)} /> : rows.length ? <DataTable columns={[{ key: "user", label: "User", render: (row: Record<string, unknown>) => { const user = row.user as Record<string, unknown> | undefined; return String(user?.display_name || user?.email || "—"); } }, { key: "role", label: "Role", render: (row: Record<string, unknown>) => String(row.role ?? "—") }, { key: "scope", label: "Entity Scope", render: (row: Record<string, unknown>) => row.all_legal_entities ? "All legal entities" : `${(row.legal_entity_ids as unknown[] | undefined)?.length ?? 0} selected` }, { key: "status", label: "Status", render: (row: Record<string, unknown>) => <StatusBadge value={String(row.status ?? "UNKNOWN")} /> }]} rowKey={(row) => String(row.id)} rows={rows} /> : <EmptyState description="Membership records will appear here once additional users are added through the identity API." title="No additional members" />}{entity ? <div className="mt-4"><PermissionNotice>Active legal entity: {entity.name}. Role and scope changes continue to be enforced by the Phase 3 backend policy layer.</PermissionNotice></div> : null}</PageContent></>;
}

export function SettingsPage({ session }: { session: SessionPayload }) {
  const organization = session.organizations.find((item) => item.id === session.active_organization_id);
  const entity = activeEntity(session);
  const membership = activeMembership(session);
  return <><PageHeader description="Read the active organization, legal entity, fiscal, currency, timezone, and security context." eyebrow="Administration" title="Settings" /><PageContent><div className="grid gap-4 xl:grid-cols-[220px_1fr]"><div className="erp-panel h-fit"><div className="border-b border-[var(--color-border)] px-3 py-2.5 text-sm font-semibold text-[var(--color-brand)]">Organization</div><div className="border-b border-[var(--color-border-soft)] px-3 py-2.5 text-sm">Legal Entity</div><div className="border-b border-[var(--color-border-soft)] px-3 py-2.5 text-sm">Fiscal & Currency</div><div className="px-3 py-2.5 text-sm">Security</div></div><div className="space-y-4"><div className="erp-panel"><div className="erp-panel-header"><h2 className="text-sm font-semibold">Organization Context</h2></div><div className="grid sm:grid-cols-2">{[["Organization", organization?.name ?? "—"], ["Organization timezone", organization?.timezone ?? "—"], ["Legal entity", entity?.name ?? "Organization scope"], ["Base currency", entity?.base_currency ?? "—"], ["Entity timezone", entity?.timezone ?? "—"], ["Fiscal year starts", entity ? `${entity.fiscal_year_start_month}/${entity.fiscal_year_start_day}` : "—"]].map(([label, value]) => <div className="border-b border-r border-[var(--color-border-soft)] p-4" key={label}><div className="text-[10px] font-bold uppercase tracking-[0.08em] text-[var(--color-text-muted)]">{label}</div><div className="mt-1 text-sm font-semibold">{value}</div></div>)}</div></div><div className="erp-panel"><div className="erp-panel-header"><h2 className="text-sm font-semibold">Security Context</h2><ShieldCheck size={15} /></div><div className="p-4"><div className="mb-3 text-sm">Signed in as <strong>{session.user.display_name || session.user.email}</strong> with role <strong>{membership?.role ?? "—"}</strong>.</div><div className="flex flex-wrap gap-1.5">{(membership?.permissions ?? []).map((permission) => <span className="erp-status erp-status-muted" key={permission}>{permission.replaceAll("_", " ")}</span>)}</div></div></div></div></div></PageContent></>;
}
