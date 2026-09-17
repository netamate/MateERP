"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Plus, Search, Trash2, X } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useState, type FormEvent, type ReactNode } from "react";

import {
  DataTable,
  ErrorState,
  LoadingState,
  PageHeader,
  PermissionNotice,
  StatusBadge,
  type TableColumn,
} from "@/components/ui/erp";
import {
  accountingApi,
  request,
  type JournalEntry,
  type LedgerAccount,
  type SessionPayload,
} from "@/lib/api";

type FiscalPeriod = {
  id: string;
  legal_entity_id: string;
  name: string;
  start_date: string;
  end_date: string;
  status: string;
};

type TaxCode = {
  id: string;
  code: string;
  name: string;
  rate: string;
  input_account_id: string | null;
  output_account_id: string | null;
  is_active: boolean;
};

type ExchangeRate = {
  id: string;
  rate_date: string;
  from_currency: string;
  to_currency: string;
  rate: string;
  source: string;
};

type DraftJournalLine = {
  key: number;
  account_id: string;
  description: string;
  debit: string;
  credit: string;
  currency: string;
  fx_rate: string;
};

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

function shortDate(value: string | null | undefined) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en-US", {
    year: "numeric",
    month: "short",
    day: "2-digit",
  }).format(new Date(value.length === 10 ? `${value}T00:00:00` : value));
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
  wide = false,
}: {
  title: string;
  description: string;
  children: ReactNode;
  onClose: () => void;
  wide?: boolean;
}) {
  return (
    <div className="fixed inset-0 z-[80] flex items-start justify-center overflow-y-auto bg-black/50 px-4 py-[6vh]">
      <div className={`w-full border border-[var(--color-border-strong)] bg-white shadow-2xl ${wide ? "max-w-5xl" : "max-w-2xl"}`}>
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

export function ChartOfAccountsProductionPage({ session }: { session: SessionPayload }) {
  const entity = activeEntity(session);
  const modal = useCreateModal();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const accounts = useQuery({
    queryKey: ["ledger-accounts", entity?.id],
    queryFn: accountingApi.accounts,
    enabled: Boolean(entity),
  });
  const create = useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      request<LedgerAccount>(
        "/api/v1/accounting/accounts/",
        { method: "POST", body: JSON.stringify(body) },
        true,
      ),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["ledger-accounts", entity?.id] });
      modal.close();
    },
  });
  const rows = (accounts.data ?? []).filter((item) =>
    `${item.code} ${item.name} ${item.account_type}`.toLowerCase().includes(search.toLowerCase()),
  );

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(event.currentTarget).entries());
    create.mutate({
      code: data.code,
      name: data.name,
      account_type: data.account_type,
      normal_balance: data.normal_balance,
      parent_id: data.parent_id || null,
      system_code: data.system_code || "",
      is_control: data.is_control === "on",
      is_active: true,
    });
  }

  const columns: Array<TableColumn<LedgerAccount>> = [
    { key: "code", label: "Code", render: (row) => <span className="font-semibold">{row.code}</span> },
    { key: "name", label: "Account", render: (row) => row.name },
    { key: "type", label: "Type", render: (row) => row.account_type },
    { key: "normal", label: "Normal Balance", render: (row) => row.normal_balance },
    { key: "status", label: "Status", render: (row) => <StatusBadge value={row.is_active ? "ACTIVE" : "INACTIVE"} /> },
  ];

  return (
    <>
      <PageHeader description="Maintain the legal entity's ledger classification. Financial accounts remain a separate operational concept." eyebrow="Accounting" title="Chart of Accounts" />
      <div className="p-4 lg:p-6">
        <div className="mb-3 flex flex-wrap items-center gap-2 border border-[var(--color-border)] bg-[#fbfcfd] p-2.5">
          <label className="relative min-w-56 flex-1 sm:max-w-80"><Search className="absolute left-2.5 top-2.5 text-[var(--color-text-muted)]" size={14} /><input className="erp-field !h-8 !min-h-8 pl-8 text-xs" onChange={(event) => setSearch(event.target.value)} placeholder="Search accounts..." value={search} /></label>
          <button className="erp-button erp-button-primary ml-auto !h-8 !min-h-8" disabled={!can(session, "EDIT_CHART_OF_ACCOUNTS")} onClick={modal.show} type="button"><Plus size={13} /> Add Ledger Account</button>
        </div>
        {!entity ? <PermissionNotice>Select a legal entity first.</PermissionNotice> : accounts.isLoading ? <LoadingState /> : accounts.error ? <ErrorState message={errorMessage(accounts.error)} /> : <DataTable columns={columns} rowKey={(row) => row.id} rows={rows} />}
      </div>
      {modal.open ? (
        <Modal description="Create a ledger account within the active legal entity. Account codes are unique per legal entity." onClose={modal.close} title="Add Ledger Account">
          <form onSubmit={submit}>
            <div className="grid gap-4 p-5 sm:grid-cols-2">
              <label><span className="erp-label">Account code</span><input className="erp-field" name="code" required /></label>
              <label><span className="erp-label">Account name</span><input className="erp-field" name="name" required /></label>
              <label><span className="erp-label">Account type</span><select className="erp-field" defaultValue="ASSET" name="account_type"><option value="ASSET">Asset</option><option value="LIABILITY">Liability</option><option value="EQUITY">Equity</option><option value="REVENUE">Revenue</option><option value="EXPENSE">Expense</option></select></label>
              <label><span className="erp-label">Normal balance</span><select className="erp-field" defaultValue="DEBIT" name="normal_balance"><option value="DEBIT">Debit</option><option value="CREDIT">Credit</option></select></label>
              <label><span className="erp-label">Parent account</span><select className="erp-field" defaultValue="" name="parent_id"><option value="">No parent</option>{(accounts.data ?? []).map((account) => <option key={account.id} value={account.id}>{account.code} · {account.name}</option>)}</select></label>
              <label><span className="erp-label">System code</span><input className="erp-field" name="system_code" /></label>
              <label className="flex items-center gap-2 sm:col-span-2"><input name="is_control" type="checkbox" /><span className="text-sm">Control account</span></label>
              {create.error ? <div className="sm:col-span-2"><ErrorState message={errorMessage(create.error)} /></div> : null}
            </div>
            <FormActions onClose={modal.close} pending={create.isPending} />
          </form>
        </Modal>
      ) : null}
    </>
  );
}

export function FiscalPeriodsProductionPage({ session }: { session: SessionPayload }) {
  const entity = activeEntity(session);
  const modal = useCreateModal();
  const queryClient = useQueryClient();
  const periods = useQuery({ queryKey: ["fiscal-periods", entity?.id], queryFn: () => request<FiscalPeriod[]>("/api/v1/accounting/periods/"), enabled: Boolean(entity) });
  const create = useMutation({
    mutationFn: (body: Record<string, unknown>) => request<FiscalPeriod>("/api/v1/accounting/periods/", { method: "POST", body: JSON.stringify(body) }, true),
    onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: ["fiscal-periods", entity?.id] }); modal.close(); },
  });
  const close = useMutation({
    mutationFn: (id: string) => request<FiscalPeriod>(`/api/v1/accounting/periods/${id}/close/`, { method: "POST", body: JSON.stringify({ hard_close: false }) }, true),
    onSuccess: async () => queryClient.invalidateQueries({ queryKey: ["fiscal-periods", entity?.id] }),
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(event.currentTarget).entries());
    create.mutate(data);
  }

  const columns: Array<TableColumn<FiscalPeriod>> = [
    { key: "name", label: "Period", render: (row) => <span className="font-semibold">{row.name}</span> },
    { key: "start", label: "Start", render: (row) => shortDate(row.start_date) },
    { key: "end", label: "End", render: (row) => shortDate(row.end_date) },
    { key: "status", label: "Status", render: (row) => <StatusBadge value={row.status} /> },
    { key: "action", label: "Action", render: (row) => row.status === "OPEN" && can(session, "CLOSE_PERIOD") ? <button className="erp-button !h-7 !min-h-7 !px-2" disabled={close.isPending} onClick={() => close.mutate(row.id)} type="button">Close Period</button> : "—" },
  ];

  return (
    <>
      <PageHeader description="Create and close fiscal periods. Closed periods block ordinary financial posting that would alter historical accounts." eyebrow="Accounting" title="Fiscal Periods" />
      <div className="p-4 lg:p-6">
        <div className="mb-3 flex justify-end border border-[var(--color-border)] bg-[#fbfcfd] p-2.5"><button className="erp-button erp-button-primary !h-8 !min-h-8" disabled={!can(session, "CLOSE_PERIOD")} onClick={modal.show} type="button"><Plus size={13} /> Add Fiscal Period</button></div>
        {!entity ? <PermissionNotice>Select a legal entity first.</PermissionNotice> : periods.isLoading ? <LoadingState /> : periods.error ? <ErrorState message={errorMessage(periods.error)} /> : <DataTable columns={columns} rowKey={(row) => row.id} rows={periods.data ?? []} />}
        {close.error ? <div className="mt-3"><ErrorState message={errorMessage(close.error)} /></div> : null}
      </div>
      {modal.open ? <Modal description="Periods must use valid, non-overlapping dates according to backend accounting rules." onClose={modal.close} title="Add Fiscal Period"><form onSubmit={submit}><div className="grid gap-4 p-5 sm:grid-cols-2"><label className="sm:col-span-2"><span className="erp-label">Period name</span><input className="erp-field" name="name" required /></label><label><span className="erp-label">Start date</span><input className="erp-field" name="start_date" required type="date" /></label><label><span className="erp-label">End date</span><input className="erp-field" name="end_date" required type="date" /></label>{create.error ? <div className="sm:col-span-2"><ErrorState message={errorMessage(create.error)} /></div> : null}</div><FormActions onClose={modal.close} pending={create.isPending} /></form></Modal> : null}
    </>
  );
}

export function JournalsProductionPage({ session }: { session: SessionPayload }) {
  const entity = activeEntity(session);
  const modal = useCreateModal();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [validationError, setValidationError] = useState("");
  const [lines, setLines] = useState<DraftJournalLine[]>([
    { key: 1, account_id: "", description: "", debit: "", credit: "", currency: entity?.base_currency ?? "USD", fx_rate: "1" },
    { key: 2, account_id: "", description: "", debit: "", credit: "", currency: entity?.base_currency ?? "USD", fx_rate: "1" },
  ]);
  const journals = useQuery({ queryKey: ["journals", entity?.id], queryFn: accountingApi.journals, enabled: Boolean(entity) });
  const accounts = useQuery({ queryKey: ["ledger-accounts", entity?.id], queryFn: accountingApi.accounts, enabled: Boolean(entity) });
  const create = useMutation({
    mutationFn: (body: Record<string, unknown>) => request<JournalEntry>("/api/v1/accounting/journals/", { method: "POST", body: JSON.stringify(body) }, true),
    onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: ["journals", entity?.id] }); modal.close(); },
  });
  const post = useMutation({ mutationFn: (id: string) => request<JournalEntry>(`/api/v1/accounting/journals/${id}/post/`, { method: "POST", body: JSON.stringify({}) }, true), onSuccess: async () => queryClient.invalidateQueries({ queryKey: ["journals", entity?.id] }) });
  const reverse = useMutation({ mutationFn: (id: string) => request<JournalEntry>(`/api/v1/accounting/journals/${id}/reverse/`, { method: "POST", body: JSON.stringify({ reversal_date: new Date().toISOString().slice(0, 10), memo: "Reversal from Phase 6 production workspace" }) }, true), onSuccess: async () => queryClient.invalidateQueries({ queryKey: ["journals", entity?.id] }) });
  const rows = (journals.data ?? []).filter((item) => `${item.number} ${item.memo} ${item.source_type}`.toLowerCase().includes(search.toLowerCase()));

  function updateLine(key: number, field: keyof DraftJournalLine, value: string) {
    setLines((current) => current.map((line) => line.key === key ? { ...line, [field]: value } : line));
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setValidationError("");
    const form = Object.fromEntries(new FormData(event.currentTarget).entries());
    const debit = lines.reduce((sum, line) => sum + Number(line.debit || 0) * Number(line.fx_rate || 1), 0);
    const credit = lines.reduce((sum, line) => sum + Number(line.credit || 0) * Number(line.fx_rate || 1), 0);
    if (Math.abs(debit - credit) > 0.005) {
      setValidationError("Manual journal debits and credits must balance in base currency before submission.");
      return;
    }
    create.mutate({
      entry_date: form.entry_date,
      memo: form.memo || "",
      source_type: "MANUAL",
      source_id: "",
      lines: lines.map(({ key: _key, ...line }) => ({ ...line, debit: line.debit || "0", credit: line.credit || "0" })),
    });
  }

  const columns: Array<TableColumn<JournalEntry>> = [
    { key: "number", label: "Journal", render: (row) => <span className="font-semibold">{row.number}</span> },
    { key: "date", label: "Date", render: (row) => shortDate(row.entry_date) },
    { key: "memo", label: "Memo", render: (row) => row.memo || "—" },
    { key: "source", label: "Source", render: (row) => row.source_type || "MANUAL" },
    { key: "lines", label: "Lines", numeric: true, render: (row) => String(row.lines?.length ?? 0) },
    { key: "status", label: "Status", render: (row) => <StatusBadge value={row.status} /> },
    { key: "actions", label: "Actions", render: (row) => <div className="flex gap-1">{row.status === "DRAFT" && can(session, "POST_JOURNAL") ? <button className="erp-button !h-7 !min-h-7 !px-2" onClick={() => post.mutate(row.id)} type="button"><Check size={11} /> Post</button> : null}{row.status === "POSTED" && can(session, "REVERSE_JOURNAL") ? <button className="erp-button erp-button-danger !h-7 !min-h-7 !px-2" onClick={() => reverse.mutate(row.id)} type="button">Reverse</button> : null}</div> },
  ];

  return (
    <>
      <PageHeader description="Create manual journals where necessary, post balanced drafts, and correct posted accounting facts only through reversal." eyebrow="Accounting" title="Journal Entries" />
      <div className="p-4 lg:p-6">
        <div className="mb-3 flex flex-wrap items-center gap-2 border border-[var(--color-border)] bg-[#fbfcfd] p-2.5"><label className="relative min-w-56 flex-1 sm:max-w-80"><Search className="absolute left-2.5 top-2.5 text-[var(--color-text-muted)]" size={14} /><input className="erp-field !h-8 !min-h-8 pl-8 text-xs" onChange={(event) => setSearch(event.target.value)} placeholder="Search journals..." value={search} /></label><button className="erp-button erp-button-primary ml-auto !h-8 !min-h-8" disabled={!can(session, "POST_JOURNAL")} onClick={modal.show} type="button"><Plus size={13} /> Manual Journal</button></div>
        {!entity ? <PermissionNotice>Select a legal entity first.</PermissionNotice> : journals.isLoading ? <LoadingState /> : journals.error ? <ErrorState message={errorMessage(journals.error)} /> : <DataTable columns={columns} rowKey={(row) => row.id} rows={rows} />}
        {post.error || reverse.error ? <div className="mt-3"><ErrorState message={errorMessage(post.error ?? reverse.error)} /></div> : null}
      </div>
      {modal.open ? (
        <Modal description="Draft journal lines are validated again transactionally by the backend before posting." onClose={modal.close} title="Create Manual Journal" wide>
          <form onSubmit={submit}>
            <div className="grid gap-4 border-b border-[var(--color-border)] p-5 sm:grid-cols-2"><label><span className="erp-label">Entry date</span><input className="erp-field" defaultValue={new Date().toISOString().slice(0, 10)} name="entry_date" required type="date" /></label><label><span className="erp-label">Memo</span><input className="erp-field" name="memo" /></label></div>
            <div className="p-5">
              <div className="mb-2 flex items-center justify-between"><h3 className="text-sm font-semibold">Journal Lines</h3><button className="erp-button !h-8 !min-h-8" onClick={() => setLines((current) => [...current, { key: Date.now(), account_id: "", description: "", debit: "", credit: "", currency: entity?.base_currency ?? "USD", fx_rate: "1" }])} type="button"><Plus size={12} /> Add Line</button></div>
              <div className="overflow-auto border border-[var(--color-border)]"><table className="erp-table min-w-[1050px]"><thead><tr><th>Account</th><th>Description</th><th>Debit</th><th>Credit</th><th>Currency</th><th>FX Rate</th><th></th></tr></thead><tbody>{lines.map((line) => <tr key={line.key}><td><select className="erp-field !min-h-8" onChange={(event) => updateLine(line.key, "account_id", event.target.value)} required value={line.account_id}><option value="">Select account</option>{(accounts.data ?? []).filter((account) => account.is_active).map((account) => <option key={account.id} value={account.id}>{account.code} · {account.name}</option>)}</select></td><td><input className="erp-field !min-h-8" onChange={(event) => updateLine(line.key, "description", event.target.value)} value={line.description} /></td><td><input className="erp-field !min-h-8" min="0" onChange={(event) => updateLine(line.key, "debit", event.target.value)} step="0.01" type="number" value={line.debit} /></td><td><input className="erp-field !min-h-8" min="0" onChange={(event) => updateLine(line.key, "credit", event.target.value)} step="0.01" type="number" value={line.credit} /></td><td><input className="erp-field !min-h-8" onChange={(event) => updateLine(line.key, "currency", event.target.value.toUpperCase())} value={line.currency} /></td><td><input className="erp-field !min-h-8" min="0.0000000001" onChange={(event) => updateLine(line.key, "fx_rate", event.target.value)} step="0.0000000001" type="number" value={line.fx_rate} /></td><td>{lines.length > 2 ? <button aria-label="Remove line" className="erp-button erp-button-danger !h-8 !min-h-8 !w-8 !p-0" onClick={() => setLines((current) => current.filter((item) => item.key !== line.key))} type="button"><Trash2 size={12} /></button> : null}</td></tr>)}</tbody></table></div>
              {validationError ? <div className="mt-3"><ErrorState message={validationError} /></div> : null}
              {create.error ? <div className="mt-3"><ErrorState message={errorMessage(create.error)} /></div> : null}
            </div>
            <FormActions label="Create Draft Journal" onClose={modal.close} pending={create.isPending} />
          </form>
        </Modal>
      ) : null}
    </>
  );
}

export function AccountingConfigurationPage({ session }: { session: SessionPayload }) {
  const entity = activeEntity(session);
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<"tax" | "fx">("tax");
  const [taxOpen, setTaxOpen] = useState(false);
  const [fxOpen, setFxOpen] = useState(false);
  const accounts = useQuery({ queryKey: ["ledger-accounts", entity?.id], queryFn: accountingApi.accounts, enabled: Boolean(entity) });
  const taxCodes = useQuery({ queryKey: ["tax-codes", entity?.id], queryFn: () => request<TaxCode[]>("/api/v1/accounting/tax-codes/"), enabled: Boolean(entity) });
  const fxRates = useQuery({ queryKey: ["fx-rates", entity?.id], queryFn: () => request<ExchangeRate[]>("/api/v1/accounting/fx-rates/"), enabled: Boolean(entity) });
  const createTax = useMutation({ mutationFn: (body: Record<string, unknown>) => request<TaxCode>("/api/v1/accounting/tax-codes/", { method: "POST", body: JSON.stringify(body) }, true), onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: ["tax-codes", entity?.id] }); setTaxOpen(false); } });
  const createFx = useMutation({ mutationFn: (body: Record<string, unknown>) => request<ExchangeRate>("/api/v1/accounting/fx-rates/", { method: "POST", body: JSON.stringify(body) }, true), onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: ["fx-rates", entity?.id] }); setFxOpen(false); } });

  function submitTax(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(event.currentTarget).entries());
    createTax.mutate({ ...data, input_account_id: data.input_account_id || null, output_account_id: data.output_account_id || null, is_active: true });
  }

  function submitFx(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(event.currentTarget).entries());
    createFx.mutate({ ...data, from_currency: String(data.from_currency).toUpperCase(), to_currency: String(data.to_currency).toUpperCase() });
  }

  const taxColumns: Array<TableColumn<TaxCode>> = [
    { key: "code", label: "Code", render: (row) => <span className="font-semibold">{row.code}</span> },
    { key: "name", label: "Tax", render: (row) => row.name },
    { key: "rate", label: "Rate", numeric: true, render: (row) => `${row.rate}%` },
    { key: "input", label: "Input Account", render: (row) => (accounts.data ?? []).find((item) => item.id === row.input_account_id)?.name ?? "—" },
    { key: "output", label: "Output Account", render: (row) => (accounts.data ?? []).find((item) => item.id === row.output_account_id)?.name ?? "—" },
    { key: "status", label: "Status", render: (row) => <StatusBadge value={row.is_active ? "ACTIVE" : "INACTIVE"} /> },
  ];
  const fxColumns: Array<TableColumn<ExchangeRate>> = [
    { key: "date", label: "Rate Date", render: (row) => shortDate(row.rate_date) },
    { key: "pair", label: "Currency Pair", render: (row) => <span className="font-semibold">{row.from_currency} → {row.to_currency}</span> },
    { key: "rate", label: "Rate", numeric: true, render: (row) => row.rate },
    { key: "source", label: "Source", render: (row) => row.source || "—" },
  ];

  return (
    <>
      <PageHeader description="Configure tax-code mappings and dated exchange rates used by financial posting. Historical posted rates remain immutable." eyebrow="Accounting" title="Tax & FX Configuration" />
      <div className="p-4 lg:p-6">
        <div className="mb-3 flex flex-wrap gap-2 border border-[var(--color-border)] bg-white p-2.5"><button className={`erp-button !h-8 !min-h-8 ${tab === "tax" ? "erp-button-primary" : ""}`} onClick={() => setTab("tax")} type="button">Tax Codes</button><button className={`erp-button !h-8 !min-h-8 ${tab === "fx" ? "erp-button-primary" : ""}`} onClick={() => setTab("fx")} type="button">Exchange Rates</button>{tab === "tax" ? <button className="erp-button erp-button-primary ml-auto !h-8 !min-h-8" disabled={!can(session, "MANAGE_TAX_CONFIG")} onClick={() => setTaxOpen(true)} type="button"><Plus size={13} /> Add Tax Code</button> : <button className="erp-button erp-button-primary ml-auto !h-8 !min-h-8" disabled={!can(session, "MANAGE_FX_RATES")} onClick={() => setFxOpen(true)} type="button"><Plus size={13} /> Add FX Rate</button>}</div>
        {!entity ? <PermissionNotice>Select a legal entity first.</PermissionNotice> : tab === "tax" ? taxCodes.isLoading ? <LoadingState /> : taxCodes.error ? <ErrorState message={errorMessage(taxCodes.error)} /> : <DataTable columns={taxColumns} rowKey={(row) => row.id} rows={taxCodes.data ?? []} /> : fxRates.isLoading ? <LoadingState /> : fxRates.error ? <ErrorState message={errorMessage(fxRates.error)} /> : <DataTable columns={fxColumns} rowKey={(row) => row.id} rows={fxRates.data ?? []} />}
      </div>
      {taxOpen ? <Modal description="Map input/output tax to ledger accounts for this legal entity." onClose={() => setTaxOpen(false)} title="Add Tax Code"><form onSubmit={submitTax}><div className="grid gap-4 p-5 sm:grid-cols-2"><label><span className="erp-label">Code</span><input className="erp-field" name="code" required /></label><label><span className="erp-label">Name</span><input className="erp-field" name="name" required /></label><label><span className="erp-label">Rate (%)</span><input className="erp-field" min="0" name="rate" required step="0.0001" type="number" /></label><div /><label><span className="erp-label">Input tax account</span><select className="erp-field" defaultValue="" name="input_account_id"><option value="">None</option>{(accounts.data ?? []).map((account) => <option key={account.id} value={account.id}>{account.code} · {account.name}</option>)}</select></label><label><span className="erp-label">Output tax account</span><select className="erp-field" defaultValue="" name="output_account_id"><option value="">None</option>{(accounts.data ?? []).map((account) => <option key={account.id} value={account.id}>{account.code} · {account.name}</option>)}</select></label>{createTax.error ? <div className="sm:col-span-2"><ErrorState message={errorMessage(createTax.error)} /></div> : null}</div><FormActions onClose={() => setTaxOpen(false)} pending={createTax.isPending} /></form></Modal> : null}
      {fxOpen ? <Modal description="Store a dated exchange rate and its source. Posted journal lines preserve the rate actually used." onClose={() => setFxOpen(false)} title="Add Exchange Rate"><form onSubmit={submitFx}><div className="grid gap-4 p-5 sm:grid-cols-2"><label><span className="erp-label">Rate date</span><input className="erp-field" defaultValue={new Date().toISOString().slice(0, 10)} name="rate_date" required type="date" /></label><label><span className="erp-label">Source</span><input className="erp-field" name="source" required /></label><label><span className="erp-label">From currency</span><input className="erp-field" name="from_currency" required /></label><label><span className="erp-label">To currency</span><input className="erp-field" defaultValue={entity?.base_currency ?? "USD"} name="to_currency" required /></label><label className="sm:col-span-2"><span className="erp-label">Rate</span><input className="erp-field" min="0.0000000001" name="rate" required step="0.0000000001" type="number" /></label>{createFx.error ? <div className="sm:col-span-2"><ErrorState message={errorMessage(createFx.error)} /></div> : null}</div><FormActions onClose={() => setFxOpen(false)} pending={createFx.isPending} /></form></Modal> : null}
    </>
  );
}
