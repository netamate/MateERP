"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileUp, Landmark, Plus, Search, ShieldCheck } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useMemo, useState, type FormEvent, type ReactNode } from "react";

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
  financeApi,
  request,
  type FinancialAccount,
  type LedgerAccount,
  type SessionPayload,
} from "@/lib/api";

type FounderFunding = {
  id: string;
  funding_date: string;
  founder_name: string;
  funding_type: "CONTRIBUTION" | "LOAN";
  amount: string;
  currency: string;
  fx_rate: string;
  financial_account: string;
  counter_account: string;
  reference: string;
  memo: string;
  status: string;
  journal_entry: string | null;
};

type FinanceTransaction = {
  id: string;
  journal_id: string;
  journal_number: string;
  date: string;
  source_type: string;
  source_id: string;
  description: string;
  debit: string;
  credit: string;
  currency: string;
  base_debit: string;
  base_credit: string;
  running_base_balance: string;
  financial_account_id: string;
  financial_account_name: string;
};

type FiscalPeriod = {
  id: string;
  legal_entity_id: string;
  name: string;
  start_date: string;
  end_date: string;
  status: string;
};

type ApprovalAction = {
  id: string;
  object_type: string;
  object_id: string;
  action: string;
  actor: string;
  actor_email: string;
  comment: string;
  created_at: string;
};

type FinanceDocument = {
  id: string;
  document_type: string;
  file: string;
  original_name: string;
  vendor: string | null;
  expense: string | null;
  income: string | null;
  reimbursement: string | null;
  transfer: string | null;
  founder_funding: string | null;
  created_at: string;
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
  }).format(new Date(value.length === 10 ? `${value}T00:00:00` : value));
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

function PageContent({ children }: { children: ReactNode }) {
  return <div className="p-4 lg:p-6">{children}</div>;
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
          <button aria-label="Close" className="erp-button !h-8 !min-h-8 !w-8 !p-0" onClick={onClose} type="button">×</button>
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

export function TransactionsPage({ session }: { session: SessionPayload }) {
  const entity = activeEntity(session);
  const [search, setSearch] = useState("");
  const accounts = useQuery({
    queryKey: ["financial-accounts", entity?.id],
    queryFn: financeApi.accounts,
    enabled: Boolean(entity),
  });
  const transactions = useQuery({
    queryKey: ["financial-transactions", entity?.id, accounts.data?.map((item) => item.id).join(",")],
    enabled: Boolean(entity && accounts.data),
    queryFn: async () => {
      const groups = await Promise.all(
        (accounts.data ?? []).map(async (account) => {
          const rows = await request<Omit<FinanceTransaction, "financial_account_id" | "financial_account_name">[]>(
            `/api/v1/finance/accounts/${account.id}/transactions/`,
          );
          return rows.map((row) => ({
            ...row,
            financial_account_id: account.id,
            financial_account_name: account.name,
          }));
        }),
      );
      return groups.flat().sort((a, b) => b.date.localeCompare(a.date));
    },
  });
  const rows = (transactions.data ?? []).filter((item) =>
    `${item.journal_number} ${item.description} ${item.source_type} ${item.financial_account_name}`
      .toLowerCase()
      .includes(search.toLowerCase()),
  );
  const base = entity?.base_currency ?? "USD";
  const inflow = rows.reduce((sum, item) => sum + Number(item.base_debit), 0);
  const outflow = rows.reduce((sum, item) => sum + Number(item.base_credit), 0);

  const columns: Array<TableColumn<FinanceTransaction>> = [
    { key: "date", label: "Date", render: (row) => shortDate(row.date) },
    { key: "journal", label: "Journal", render: (row) => <span className="font-semibold">{row.journal_number}</span> },
    { key: "account", label: "Financial Account", render: (row) => row.financial_account_name },
    { key: "description", label: "Description", render: (row) => row.description || "—" },
    { key: "source", label: "Source", render: (row) => row.source_type || "MANUAL" },
    { key: "debit", label: "Debit", numeric: true, render: (row) => money(row.base_debit, base) },
    { key: "credit", label: "Credit", numeric: true, render: (row) => money(row.base_credit, base) },
    { key: "balance", label: "Running Balance", numeric: true, render: (row) => money(row.running_base_balance, base) },
  ];

  return (
    <>
      <PageHeader
        description="Central account transaction view derived from posted journal lines. No editable current-balance field is used."
        eyebrow="Finance"
        title="Transactions"
      />
      <MetricStrip metrics={[{ label: "Base Debit", value: money(inflow, base) }, { label: "Base Credit", value: money(outflow, base) }, { label: "Net Movement", value: money(inflow - outflow, base) }, { label: "Transactions", value: String(rows.length) }]} />
      <PageContent>
        <div className="mb-3 flex items-center border border-[var(--color-border)] bg-[#fbfcfd] p-2.5">
          <label className="relative w-full max-w-80">
            <Search className="absolute left-2.5 top-2.5 text-[var(--color-text-muted)]" size={14} />
            <input className="erp-field !h-8 !min-h-8 pl-8 text-xs" onChange={(event) => setSearch(event.target.value)} placeholder="Search transactions..." value={search} />
          </label>
        </div>
        {!entity ? <PermissionNotice>Select a legal entity first.</PermissionNotice> : accounts.isLoading || transactions.isLoading ? <LoadingState label="Loading ledger-derived transactions..." /> : accounts.error || transactions.error ? <ErrorState message={errorMessage(accounts.error ?? transactions.error)} /> : <DataTable columns={columns} emptyDescription="Posted finance activity will appear here automatically." emptyTitle="No posted transactions" rowKey={(row) => `${row.financial_account_id}-${row.id}`} rows={rows} />}
      </PageContent>
    </>
  );
}

export function FounderFundingPage({ session }: { session: SessionPayload }) {
  const entity = activeEntity(session);
  const modal = useCreateModal();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const rowsQuery = useQuery({
    queryKey: ["founder-funding", entity?.id],
    queryFn: () => request<FounderFunding[]>("/api/v1/finance/founder-funding/"),
    enabled: Boolean(entity),
  });
  const financialAccounts = useQuery({
    queryKey: ["financial-accounts", entity?.id],
    queryFn: financeApi.accounts,
    enabled: Boolean(entity),
  });
  const ledger = useQuery({
    queryKey: ["ledger-accounts", entity?.id],
    queryFn: accountingApi.accounts,
    enabled: Boolean(entity),
  });
  const create = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      request<FounderFunding>(
        "/api/v1/finance/founder-funding/",
        { method: "POST", body: JSON.stringify(body) },
        true,
      ),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["founder-funding", entity?.id] });
      modal.close();
    },
  });
  const rows = (rowsQuery.data ?? []).filter((item) =>
    `${item.founder_name} ${item.reference} ${item.memo} ${item.funding_type}`
      .toLowerCase()
      .includes(search.toLowerCase()),
  );
  const accountMap = new Map((financialAccounts.data ?? []).map((item) => [item.id, item.name]));

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(event.currentTarget).entries());
    create.mutate({
      ...data,
      currency: String(data.currency || entity?.base_currency || "USD").toUpperCase(),
      fx_rate: data.fx_rate || "1",
      reference: data.reference || "",
      memo: data.memo || "",
    });
  }

  const columns: Array<TableColumn<FounderFunding>> = [
    { key: "date", label: "Date", render: (row) => shortDate(row.funding_date) },
    { key: "founder", label: "Founder", render: (row) => row.founder_name },
    { key: "type", label: "Funding Type", render: (row) => row.funding_type.replaceAll("_", " ") },
    { key: "account", label: "Financial Account", render: (row) => accountMap.get(row.financial_account) ?? row.financial_account },
    { key: "reference", label: "Reference", render: (row) => row.reference || "—" },
    { key: "amount", label: "Amount", numeric: true, render: (row) => money(row.amount, row.currency) },
    { key: "status", label: "Status", render: (row) => <StatusBadge value={row.status} /> },
  ];

  return (
    <>
      <PageHeader description="Track founder contributions and founder loans separately. Contributions post to equity and loans post to liabilities." eyebrow="Capital" title="Founder Funding" />
      <PageContent>
        <div className="mb-3 flex flex-wrap items-center gap-2 border border-[var(--color-border)] bg-[#fbfcfd] p-2.5">
          <label className="relative min-w-56 flex-1 sm:max-w-80"><Search className="absolute left-2.5 top-2.5 text-[var(--color-text-muted)]" size={14} /><input className="erp-field !h-8 !min-h-8 pl-8 text-xs" onChange={(event) => setSearch(event.target.value)} placeholder="Search founder funding..." value={search} /></label>
          <button className="erp-button erp-button-primary ml-auto !h-8 !min-h-8" disabled={!can(session, "MANAGE_FINANCE")} onClick={modal.show} type="button"><Plus size={13} /> Record Funding</button>
        </div>
        {!entity ? <PermissionNotice>Select a legal entity first.</PermissionNotice> : rowsQuery.isLoading ? <LoadingState /> : rowsQuery.error ? <ErrorState message={errorMessage(rowsQuery.error)} /> : <DataTable columns={columns} rowKey={(row) => row.id} rows={rows} />}
      </PageContent>
      {modal.open ? (
        <Modal description="Recording founder funding immediately creates a balanced posted journal through the accounting engine." onClose={modal.close} title="Record Founder Funding">
          <form onSubmit={submit}>
            <div className="grid gap-4 p-5 sm:grid-cols-2">
              <label><span className="erp-label">Funding date</span><input className="erp-field" defaultValue={new Date().toISOString().slice(0, 10)} name="funding_date" required type="date" /></label>
              <label><span className="erp-label">Founder name</span><input className="erp-field" name="founder_name" required /></label>
              <label><span className="erp-label">Funding type</span><select className="erp-field" defaultValue="CONTRIBUTION" name="funding_type"><option value="CONTRIBUTION">Founder contribution</option><option value="LOAN">Founder loan</option></select></label>
              <label><span className="erp-label">Amount</span><input className="erp-field" name="amount" required step="0.01" type="number" /></label>
              <label><span className="erp-label">Currency</span><input className="erp-field" defaultValue={entity?.base_currency ?? "USD"} name="currency" required /></label>
              <label><span className="erp-label">FX rate</span><input className="erp-field" defaultValue="1" name="fx_rate" required step="0.0000000001" type="number" /></label>
              <label><span className="erp-label">Financial account</span><select className="erp-field" name="financial_account" required><option value="">Select receiving account</option>{(financialAccounts.data ?? []).filter((item) => item.is_active).map((item) => <option key={item.id} value={item.id}>{item.name} · {item.currency}</option>)}</select></label>
              <label><span className="erp-label">Equity / liability account</span><select className="erp-field" name="counter_account" required><option value="">Select counter account</option>{(ledger.data ?? []).filter((item) => ["EQUITY", "LIABILITY"].includes(item.account_type)).map((item) => <option key={item.id} value={item.id}>{item.code} · {item.name} ({item.account_type})</option>)}</select></label>
              <label><span className="erp-label">Reference</span><input className="erp-field" name="reference" /></label>
              <label><span className="erp-label">Memo</span><input className="erp-field" name="memo" /></label>
              {create.error ? <div className="sm:col-span-2"><ErrorState message={errorMessage(create.error)} /></div> : null}
            </div>
            <FormActions label="Record & Post" onClose={modal.close} pending={create.isPending} />
          </form>
        </Modal>
      ) : null}
    </>
  );
}

export function FiscalPeriodsPage({ session }: { session: SessionPayload }) {
  const entity = activeEntity(session);
  const queryClient = useQueryClient();
  const periods = useQuery({
    queryKey: ["fiscal-periods", entity?.id],
    queryFn: () => request<FiscalPeriod[]>("/api/v1/accounting/periods/"),
    enabled: Boolean(entity),
  });
  const close = useMutation({
    mutationFn: (id: string) =>
      request<FiscalPeriod>(
        `/api/v1/accounting/periods/${id}/close/`,
        { method: "POST", body: JSON.stringify({ hard_close: false }) },
        true,
      ),
    onSuccess: async () => queryClient.invalidateQueries({ queryKey: ["fiscal-periods", entity?.id] }),
  });
  const columns: Array<TableColumn<FiscalPeriod>> = [
    { key: "name", label: "Period", render: (row) => <span className="font-semibold">{row.name}</span> },
    { key: "start", label: "Start", render: (row) => shortDate(row.start_date) },
    { key: "end", label: "End", render: (row) => shortDate(row.end_date) },
    { key: "status", label: "Status", render: (row) => <StatusBadge value={row.status} /> },
    { key: "action", label: "Action", render: (row) => row.status === "OPEN" && can(session, "CLOSE_PERIOD") ? <button className="erp-button !h-7 !min-h-7 !px-2" disabled={close.isPending} onClick={() => close.mutate(row.id)} type="button">Close Period</button> : "—" },
  ];
  return (
    <>
      <PageHeader description="Accounting periods protect historical financial truth. Closing blocks ordinary posting into the period." eyebrow="Accounting" title="Fiscal Periods" />
      <PageContent>
        {!entity ? <PermissionNotice>Select a legal entity first.</PermissionNotice> : periods.isLoading ? <LoadingState /> : periods.error ? <ErrorState message={errorMessage(periods.error)} /> : <DataTable columns={columns} emptyDescription="Fiscal periods can be created through the accounting API when the legal entity's calendar is initialized." emptyTitle="No fiscal periods" rowKey={(row) => row.id} rows={periods.data ?? []} />}
        {close.error ? <div className="mt-3"><ErrorState message={errorMessage(close.error)} /></div> : null}
      </PageContent>
    </>
  );
}

export function DocumentsApprovalsPage({ session }: { session: SessionPayload }) {
  const entity = activeEntity(session);
  const modal = useCreateModal();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<"documents" | "approvals">("documents");
  const documents = useQuery({ queryKey: ["finance-documents", entity?.id], queryFn: () => request<FinanceDocument[]>("/api/v1/finance/documents/"), enabled: Boolean(entity) });
  const approvals = useQuery({ queryKey: ["finance-approvals", entity?.id], queryFn: () => request<ApprovalAction[]>("/api/v1/finance/approvals/"), enabled: Boolean(entity) });
  const vendors = useQuery({ queryKey: ["vendors", entity?.id], queryFn: financeApi.vendors, enabled: Boolean(entity) });
  const expenses = useQuery({ queryKey: ["expenses", entity?.id], queryFn: financeApi.expenses, enabled: Boolean(entity) });
  const reimbursements = useQuery({ queryKey: ["reimbursements", entity?.id], queryFn: financeApi.reimbursements, enabled: Boolean(entity) });
  const upload = useMutation({
    mutationFn: async (formData: FormData) => request<FinanceDocument>("/api/v1/finance/documents/", { method: "POST", body: formData }, true),
    onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: ["finance-documents", entity?.id] }); modal.close(); },
  });

  const targets = useMemo(() => [
    ...(vendors.data ?? []).map((item) => ({ value: `vendor:${item.id}`, label: `Vendor · ${item.name}` })),
    ...(expenses.data ?? []).map((item) => ({ value: `expense:${item.id}`, label: `Expense · ${item.description}` })),
    ...(reimbursements.data ?? []).map((item) => ({ value: `reimbursement:${item.id}`, label: `Reimbursement · ${item.description}` })),
  ], [vendors.data, expenses.data, reimbursements.data]);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const source = new FormData(event.currentTarget);
    const target = String(source.get("target") ?? "");
    const [targetType, targetId] = target.split(":");
    source.delete("target");
    if (targetType && targetId) source.set(targetType, targetId);
    upload.mutate(source);
  }

  const documentColumns: Array<TableColumn<FinanceDocument>> = [
    { key: "date", label: "Uploaded", render: (row) => shortDate(row.created_at) },
    { key: "name", label: "File", render: (row) => <span className="font-semibold">{row.original_name}</span> },
    { key: "type", label: "Document Type", render: (row) => row.document_type },
    { key: "target", label: "Linked Record", render: (row) => row.vendor ? "Vendor" : row.expense ? "Expense" : row.reimbursement ? "Reimbursement" : row.income ? "Income" : row.transfer ? "Transfer" : row.founder_funding ? "Founder funding" : "—" },
  ];
  const approvalColumns: Array<TableColumn<ApprovalAction>> = [
    { key: "date", label: "Timestamp", render: (row) => shortDate(row.created_at) },
    { key: "object", label: "Object", render: (row) => row.object_type },
    { key: "action", label: "Action", render: (row) => <StatusBadge value={row.action} /> },
    { key: "actor", label: "Actor", render: (row) => row.actor_email },
    { key: "comment", label: "Comment", render: (row) => row.comment || "—" },
  ];

  return (
    <>
      <PageHeader description="Financial supporting documents and append-only approval history for auditable operations." eyebrow="Finance" title="Documents & Approvals" />
      <PageContent>
        <div className="mb-3 flex flex-wrap items-center gap-2 border border-[var(--color-border)] bg-white p-2.5">
          <button className={`erp-button !h-8 !min-h-8 ${tab === "documents" ? "erp-button-primary" : ""}`} onClick={() => setTab("documents")} type="button"><FileUp size={13} /> Documents</button>
          <button className={`erp-button !h-8 !min-h-8 ${tab === "approvals" ? "erp-button-primary" : ""}`} onClick={() => setTab("approvals")} type="button"><ShieldCheck size={13} /> Approval History</button>
          {tab === "documents" ? <button className="erp-button erp-button-primary ml-auto !h-8 !min-h-8" disabled={!can(session, "MANAGE_FINANCE_DOCUMENTS")} onClick={modal.show} type="button"><Plus size={13} /> Upload Document</button> : null}
        </div>
        {!entity ? <PermissionNotice>Select a legal entity first.</PermissionNotice> : tab === "documents" ? documents.isLoading ? <LoadingState /> : documents.error ? <ErrorState message={errorMessage(documents.error)} /> : <DataTable columns={documentColumns} emptyDescription="Upload receipts, invoices, bills, statements, and supporting files against finance records." emptyTitle="No finance documents" rowKey={(row) => row.id} rows={documents.data ?? []} /> : approvals.isLoading ? <LoadingState /> : approvals.error ? <ErrorState message={errorMessage(approvals.error)} /> : <DataTable columns={approvalColumns} emptyDescription="Expense and reimbursement workflow actions will appear here." emptyTitle="No approval actions" rowKey={(row) => row.id} rows={approvals.data ?? []} />}
      </PageContent>
      {modal.open ? (
        <Modal description="Documents are stored through Django's storage abstraction and linked to exactly one finance record." onClose={modal.close} title="Upload Finance Document">
          <form onSubmit={submit}>
            <div className="grid gap-4 p-5 sm:grid-cols-2">
              <label><span className="erp-label">Document type</span><select className="erp-field" defaultValue="RECEIPT" name="document_type"><option value="RECEIPT">Receipt</option><option value="INVOICE">Invoice</option><option value="BILL">Bill</option><option value="STATEMENT">Statement</option><option value="OTHER">Other</option></select></label>
              <label><span className="erp-label">Linked record</span><select className="erp-field" name="target" required><option value="">Select record</option>{targets.map((target) => <option key={target.value} value={target.value}>{target.label}</option>)}</select></label>
              <label className="sm:col-span-2"><span className="erp-label">File</span><input className="erp-field" name="file" required type="file" /></label>
              {upload.error ? <div className="sm:col-span-2"><ErrorState message={errorMessage(upload.error)} /></div> : null}
            </div>
            <FormActions label="Upload" onClose={modal.close} pending={upload.isPending} />
          </form>
        </Modal>
      ) : null}
    </>
  );
}
