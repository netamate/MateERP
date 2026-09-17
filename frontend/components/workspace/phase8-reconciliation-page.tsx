"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Plus } from "lucide-react";
import { useMemo, useState, type FormEvent } from "react";

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
import { financeApi, type SessionPayload } from "@/lib/api";
import {
  reconciliationApi,
  type Reconciliation,
  type ReconciliationCandidate,
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

function today() {
  return new Date().toISOString().slice(0, 10);
}

function firstDayOfMonth() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-01`;
}

function money(value: string | number, currency: string) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(Number(value));
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "The reconciliation request failed.";
}

export function ReconciliationPage({ session }: { session: SessionPayload }) {
  const queryClient = useQueryClient();
  const entity = activeEntity(session);
  const mayView = Boolean(entity) && can(session, "VIEW_RECONCILIATION");
  const mayManage = Boolean(entity) && can(session, "MANAGE_RECONCILIATION");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectionOverrides, setSelectionOverrides] = useState<Record<string, boolean>>({});
  const [createOpen, setCreateOpen] = useState(false);

  const reconciliations = useQuery({
    queryKey: ["reconciliations", entity?.id],
    queryFn: reconciliationApi.list,
    enabled: mayView,
  });
  const accounts = useQuery({
    queryKey: ["financial-accounts", entity?.id],
    queryFn: financeApi.accounts,
    enabled: mayView,
  });
  const selected = (reconciliations.data ?? []).find((item) => item.id === selectedId) ?? null;
  const candidates = useQuery({
    queryKey: ["reconciliation-candidates", entity?.id, selectedId],
    queryFn: () => reconciliationApi.candidates(selectedId!),
    enabled: mayView && Boolean(selectedId) && selected?.status === "DRAFT",
  });

  const createMutation = useMutation({
    mutationFn: reconciliationApi.create,
    onSuccess: async (item) => {
      await queryClient.invalidateQueries({ queryKey: ["reconciliations", entity?.id] });
      setSelectedId(item.id);
      setSelectionOverrides({});
      setCreateOpen(false);
    },
  });
  const saveItemsMutation = useMutation({
    mutationFn: ({ id, lineIds }: { id: string; lineIds: string[] }) =>
      reconciliationApi.replaceItems(id, lineIds),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["reconciliations", entity?.id] });
      await queryClient.invalidateQueries({ queryKey: ["reconciliation-candidates", entity?.id, selectedId] });
      setSelectionOverrides({});
    },
  });
  const completeMutation = useMutation({
    mutationFn: reconciliationApi.complete,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["reconciliations", entity?.id] });
      setSelectionOverrides({});
    },
  });

  const selectedLineIds = useMemo(() => {
    return (candidates.data ?? [])
      .filter((item) => selectionOverrides[item.id] ?? item.selected)
      .map((item) => item.id);
  }, [candidates.data, selectionOverrides]);

  if (!entity) return <PermissionNotice>Select a legal entity to reconcile accounts.</PermissionNotice>;
  if (!mayView) return <PermissionNotice>You do not have permission to view reconciliations.</PermissionNotice>;
  if (reconciliations.isLoading || accounts.isLoading) {
    return <LoadingState label="Loading reconciliation workspace..." />;
  }
  if (reconciliations.error || accounts.error) {
    return <ErrorState message={errorMessage(reconciliations.error ?? accounts.error)} />;
  }

  const columns: Array<TableColumn<Reconciliation>> = [
    { key: "account", label: "Account", render: (row) => row.financial_account_name },
    { key: "period", label: "Statement Period", render: (row) => `${row.start_date} → ${row.end_date}` },
    { key: "status", label: "Status", render: (row) => <StatusBadge value={row.status} /> },
    { key: "statement", label: "Statement Ending", numeric: true, render: (row) => money(row.statement_ending_balance, row.currency) },
    { key: "difference", label: "Difference", numeric: true, render: (row) => money(row.summary.difference, row.currency) },
    {
      key: "open",
      label: "",
      render: (row) => (
        <button
          className="erp-button !h-7 !min-h-7"
          onClick={() => {
            setSelectedId(row.id);
            setSelectionOverrides({});
          }}
          type="button"
        >
          Review
        </button>
      ),
    },
  ];

  const candidateColumns: Array<TableColumn<ReconciliationCandidate>> = [
    {
      key: "select",
      label: "Clear",
      render: (row) => (
        <input
          aria-label={`Clear ${row.journal_number}`}
          checked={selectionOverrides[row.id] ?? row.selected}
          disabled={!mayManage || selected?.status !== "DRAFT"}
          onChange={(event) =>
            setSelectionOverrides((current) => ({ ...current, [row.id]: event.target.checked }))
          }
          type="checkbox"
        />
      ),
    },
    { key: "date", label: "Date", render: (row) => row.date },
    { key: "journal", label: "Journal", render: (row) => row.journal_number },
    { key: "description", label: "Description", render: (row) => row.description || row.source_type },
    { key: "debit", label: "Debit", numeric: true, render: (row) => row.debit },
    { key: "credit", label: "Credit", numeric: true, render: (row) => row.credit },
    { key: "movement", label: `Movement (${selected?.currency ?? entity.base_currency})`, numeric: true, render: (row) => row.signed_amount },
  ];

  function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    createMutation.mutate({
      financial_account: String(form.get("financial_account")),
      start_date: String(form.get("start_date")),
      end_date: String(form.get("end_date")),
      statement_ending_balance: String(form.get("statement_ending_balance")),
      notes: String(form.get("notes") ?? ""),
    });
  }

  return (
    <>
      <PageHeader
        eyebrow="Phase 8 · Finance Control"
        title="Account Reconciliation"
        description="Clear posted ledger activity against financial account statements. Completed reconciliations are immutable and require an exact zero difference."
        actions={
          <button className="erp-button erp-button-primary" disabled={!mayManage} onClick={() => setCreateOpen((value) => !value)} type="button">
            <Plus size={14} /> New Reconciliation
          </button>
        }
      />
      <MetricStrip
        metrics={[
          { label: "Total", value: String(reconciliations.data?.length ?? 0) },
          { label: "Draft", value: String((reconciliations.data ?? []).filter((item) => item.status === "DRAFT").length) },
          { label: "Completed", value: String((reconciliations.data ?? []).filter((item) => item.status === "COMPLETED").length) },
          { label: "Accounts", value: String(accounts.data?.length ?? 0) },
        ]}
      />
      <div className="space-y-5 p-4 lg:p-6">
        {createOpen ? (
          <form className="border border-[var(--color-border)] bg-white" onSubmit={create}>
            <div className="grid gap-4 p-4 md:grid-cols-2 xl:grid-cols-5">
              <label><span className="erp-label">Financial Account</span><select className="erp-field" name="financial_account" required><option value="">Select account</option>{(accounts.data ?? []).filter((account) => account.is_active).map((account) => <option key={account.id} value={account.id}>{account.name} · {account.currency}</option>)}</select></label>
              <label><span className="erp-label">Start Date</span><input className="erp-field" defaultValue={firstDayOfMonth()} name="start_date" required type="date" /></label>
              <label><span className="erp-label">End Date</span><input className="erp-field" defaultValue={today()} name="end_date" required type="date" /></label>
              <label><span className="erp-label">Statement Ending Balance</span><input className="erp-field" name="statement_ending_balance" required step="0.01" type="number" /></label>
              <label><span className="erp-label">Notes</span><input className="erp-field" name="notes" /></label>
            </div>
            {createMutation.error ? <div className="px-4 pb-3 text-xs text-[var(--color-danger)]">{errorMessage(createMutation.error)}</div> : null}
            <div className="flex justify-end border-t border-[var(--color-border)] p-3"><button className="erp-button erp-button-primary" disabled={createMutation.isPending} type="submit">Create</button></div>
          </form>
        ) : null}
        <DataTable columns={columns} rows={reconciliations.data ?? []} rowKey={(row) => row.id} />
        {selected ? (
          <section className="border border-[var(--color-border)] bg-white">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--color-border)] px-4 py-3">
              <div>
                <h2 className="text-sm font-semibold">{selected.financial_account_name} · {selected.start_date} to {selected.end_date}</h2>
                <p className="mt-1 text-xs text-[var(--color-text-muted)]">Calculated {money(selected.summary.calculated_ending_balance, selected.currency)} · Statement {money(selected.statement_ending_balance, selected.currency)} · Difference {money(selected.summary.difference, selected.currency)}</p>
              </div>
              <div className="flex gap-2">
                {selected.status === "DRAFT" ? (
                  <>
                    <button className="erp-button" disabled={!mayManage || saveItemsMutation.isPending} onClick={() => saveItemsMutation.mutate({ id: selected.id, lineIds: selectedLineIds })} type="button">Save Cleared Items</button>
                    <button className="erp-button erp-button-primary" disabled={!mayManage || completeMutation.isPending || Number(selected.summary.difference) !== 0} onClick={() => completeMutation.mutate(selected.id)} type="button"><CheckCircle2 size={14} /> Complete</button>
                  </>
                ) : <StatusBadge value={selected.status} />}
              </div>
            </div>
            {saveItemsMutation.error || completeMutation.error ? <div className="border-b border-[var(--color-border)] px-4 py-3 text-xs text-[var(--color-danger)]">{errorMessage(saveItemsMutation.error ?? completeMutation.error)}</div> : null}
            {selected.status === "DRAFT" ? (
              candidates.isLoading ? <LoadingState label="Loading eligible ledger lines..." /> : candidates.error ? <ErrorState message={errorMessage(candidates.error)} /> : <DataTable columns={candidateColumns} rows={candidates.data ?? []} rowKey={(row) => row.id} emptyTitle="No eligible ledger lines" emptyDescription="There are no unreconciled posted lines for this account up to the statement date." />
            ) : <div className="p-4 text-sm text-[var(--color-text-muted)]">This reconciliation is completed and immutable.</div>}
          </section>
        ) : null}
      </div>
    </>
  );
}
