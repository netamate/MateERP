"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Archive, History, Plus, RefreshCw } from "lucide-react";
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
  operationsApi,
  planningApi,
  type Budget,
  type BudgetActualLine,
  type CostCenter,
  type DomainRecord,
  type DomainRenewal,
  type Expense,
  type ExpenseAllocation,
  type InfrastructureAsset,
  type Product,
  type Project,
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

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "The request could not be completed.";
}

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

function nullable(form: FormData, name: string) {
  const value = String(form.get(name) ?? "").trim();
  return value || null;
}

function PageBody({ children }: { children: ReactNode }) {
  return <div className="p-4 lg:p-6">{children}</div>;
}

function Field({
  label,
  name,
  type = "text",
  required = false,
  defaultValue,
  step,
  children,
  full = false,
}: {
  label: string;
  name: string;
  type?: string;
  required?: boolean;
  defaultValue?: string | number;
  step?: string;
  children?: ReactNode;
  full?: boolean;
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

function Select({
  name,
  children,
  required = false,
  defaultValue = "",
}: {
  name: string;
  children: ReactNode;
  required?: boolean;
  defaultValue?: string;
}) {
  return (
    <select className="erp-field" defaultValue={defaultValue} name={name} required={required}>
      {children}
    </select>
  );
}

function CreatePanel({
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
    <section className="mb-4 border border-[var(--color-border-strong)] bg-white">
      <div className="flex items-start justify-between border-b border-[var(--color-border)] px-4 py-3">
        <div>
          <h2 className="text-sm font-semibold">{title}</h2>
          <p className="mt-0.5 text-xs text-[var(--color-text-muted)]">{description}</p>
        </div>
        <button className="erp-button !h-8 !min-h-8" onClick={onClose} type="button">
          Close
        </button>
      </div>
      {children}
    </section>
  );
}

function SubmitRow({ pending }: { pending: boolean }) {
  return (
    <div className="flex justify-end border-t border-[var(--color-border)] bg-[var(--color-surface-subtle)] px-4 py-3 sm:col-span-2">
      <button className="erp-button erp-button-primary" disabled={pending} type="submit">
        {pending ? "Saving..." : "Save"}
      </button>
    </div>
  );
}

function MutationError({ error }: { error: unknown }) {
  return error ? <div className="mb-3"><ErrorState message={errorMessage(error)} /></div> : null;
}

function ScopeGate({ session, permission, children }: { session: SessionPayload; permission: string; children: ReactNode }) {
  if (!activeEntity(session)) {
    return <PageBody><PermissionNotice>Select a legal entity to use this workspace.</PermissionNotice></PageBody>;
  }
  if (!can(session, permission)) {
    return <PageBody><PermissionNotice>Your role does not include {permission.replaceAll("_", " ").toLowerCase()}.</PermissionNotice></PageBody>;
  }
  return children;
}

type MasterRecord = CostCenter | Product;

type MasterPageProps = {
  session: SessionPayload;
  title: string;
  description: string;
  queryKey: string;
  queryFn: () => Promise<MasterRecord[]>;
  createFn: (body: Record<string, unknown>) => Promise<MasterRecord>;
  updateFn: (id: string, body: Record<string, unknown>) => Promise<MasterRecord>;
  codePlaceholder: string;
};

function MasterDataPage({
  session,
  title,
  description,
  queryKey,
  queryFn,
  createFn,
  updateFn,
  codePlaceholder,
}: MasterPageProps) {
  const queryClient = useQueryClient();
  const [creating, setCreating] = useState(false);
  const [search, setSearch] = useState("");
  const entity = activeEntity(session);
  const viewAllowed = can(session, "VIEW_PLANNING");
  const manageAllowed = can(session, "MANAGE_PLANNING");
  const query = useQuery({ queryKey: [queryKey, entity?.id], queryFn, enabled: Boolean(entity && viewAllowed) });
  const create = useMutation({
    mutationFn: createFn,
    onSuccess: async () => {
      setCreating(false);
      await queryClient.invalidateQueries({ queryKey: [queryKey, entity?.id] });
    },
  });
  const archive = useMutation({
    mutationFn: (id: string) => updateFn(id, { status: "ARCHIVED" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: [queryKey, entity?.id] }),
  });

  const rows = useMemo(() => {
    const normalized = search.trim().toLowerCase();
    if (!normalized) return query.data ?? [];
    return (query.data ?? []).filter((item) =>
      [item.code, item.name, item.description].some((value) => value.toLowerCase().includes(normalized)),
    );
  }, [query.data, search]);

  const columns: TableColumn<MasterRecord>[] = [
    { key: "code", label: "Code", render: (row) => <strong>{row.code}</strong> },
    { key: "name", label: "Name", render: (row) => row.name },
    { key: "description", label: "Description", render: (row) => row.description || "—" },
    { key: "status", label: "Status", render: (row) => <StatusBadge value={row.status} /> },
    {
      key: "actions",
      label: "Actions",
      render: (row) => row.status === "ACTIVE" && manageAllowed ? (
        <button className="erp-button !h-7 !min-h-7 text-[11px]" disabled={archive.isPending} onClick={() => archive.mutate(row.id)} type="button">
          <Archive size={12} /> Archive
        </button>
      ) : "—",
    },
  ];

  return (
    <>
      <PageHeader
        actions={manageAllowed ? <button className="erp-button erp-button-primary" onClick={() => setCreating(true)} type="button"><Plus size={13} /> Add</button> : undefined}
        description={description}
        eyebrow="Planning"
        title={title}
      />
      <ScopeGate permission="VIEW_PLANNING" session={session}>
        <PageBody>
          {creating ? (
            <CreatePanel description={`Create a legal-entity scoped ${title.toLowerCase()} record.`} onClose={() => setCreating(false)} title={`Add ${title.replace(/s$/, "")}`}>
              <form
                className="grid gap-4 p-4 sm:grid-cols-2"
                onSubmit={(event) => {
                  event.preventDefault();
                  const data = new FormData(event.currentTarget);
                  create.mutate({
                    code: String(data.get("code") ?? ""),
                    name: String(data.get("name") ?? ""),
                    description: String(data.get("description") ?? ""),
                  });
                }}
              >
                <Field label="Code" name="code" required><input className="erp-field" name="code" placeholder={codePlaceholder} required /></Field>
                <Field label="Name" name="name" required />
                <Field full label="Description" name="description" />
                <SubmitRow pending={create.isPending} />
              </form>
            </CreatePanel>
          ) : null}
          <MutationError error={create.error ?? archive.error} />
          <div className="mb-3 border border-[var(--color-border)] bg-white p-2.5">
            <input className="erp-field !h-8 !min-h-8 max-w-sm" onChange={(event) => setSearch(event.target.value)} placeholder="Search code or name..." value={search} />
          </div>
          {query.isLoading ? <LoadingState /> : query.error ? <ErrorState message={errorMessage(query.error)} /> : <DataTable columns={columns} rowKey={(row) => row.id} rows={rows} />}
        </PageBody>
      </ScopeGate>
    </>
  );
}

export function CostCentersPage({ session }: { session: SessionPayload }) {
  return <MasterDataPage codePlaceholder="INFRA" createFn={planningApi.createCostCenter} description="Define organizational areas that incur company costs and support allocation and budget analysis." queryFn={planningApi.costCenters} queryKey="cost-centers" session={session} title="Cost Centers" updateFn={planningApi.updateCostCenter} />;
}

export function ProductsPage({ session }: { session: SessionPayload }) {
  return <MasterDataPage codePlaceholder="MATEDESK" createFn={planningApi.createProduct} description="Track long-lived products and services independently from finite projects." queryFn={planningApi.products} queryKey="products" session={session} title="Products" updateFn={planningApi.updateProduct} />;
}

export function ProjectsPage({ session }: { session: SessionPayload }) {
  const queryClient = useQueryClient();
  const [creating, setCreating] = useState(false);
  const entity = activeEntity(session);
  const viewAllowed = can(session, "VIEW_PLANNING");
  const manageAllowed = can(session, "MANAGE_PLANNING");
  const projects = useQuery({ queryKey: ["projects", entity?.id], queryFn: planningApi.projects, enabled: Boolean(entity && viewAllowed) });
  const products = useQuery({ queryKey: ["products", entity?.id], queryFn: planningApi.products, enabled: Boolean(entity && viewAllowed) });
  const create = useMutation({
    mutationFn: planningApi.createProject,
    onSuccess: async () => {
      setCreating(false);
      await queryClient.invalidateQueries({ queryKey: ["projects", entity?.id] });
    },
  });
  const archive = useMutation({
    mutationFn: (id: string) => planningApi.updateProject(id, { status: "ARCHIVED" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["projects", entity?.id] }),
  });
  const productMap = new Map((products.data ?? []).map((item) => [item.id, item.name]));
  const columns: TableColumn<Project>[] = [
    { key: "code", label: "Code", render: (row) => <strong>{row.code}</strong> },
    { key: "name", label: "Project", render: (row) => row.name },
    { key: "client", label: "Client", render: (row) => row.client_name || "Internal" },
    { key: "product", label: "Product", render: (row) => row.product ? productMap.get(row.product) ?? "—" : "—" },
    { key: "dates", label: "Period", render: (row) => `${shortDate(row.start_date)} → ${shortDate(row.end_date)}` },
    { key: "status", label: "Status", render: (row) => <StatusBadge value={row.status} /> },
    { key: "actions", label: "Actions", render: (row) => row.status !== "ARCHIVED" && manageAllowed ? <button className="erp-button !h-7 !min-h-7 text-[11px]" onClick={() => archive.mutate(row.id)} type="button"><Archive size={12} /> Archive</button> : "—" },
  ];

  return (
    <>
      <PageHeader actions={manageAllowed ? <button className="erp-button erp-button-primary" onClick={() => setCreating(true)} type="button"><Plus size={13} /> Add Project</button> : undefined} description="Track finite internal and client initiatives separately from long-lived products." eyebrow="Planning" title="Projects" />
      <ScopeGate permission="VIEW_PLANNING" session={session}>
        <PageBody>
          {creating ? (
            <CreatePanel description="Create a finite project and optionally associate it with a product." onClose={() => setCreating(false)} title="Add Project">
              <form className="grid gap-4 p-4 sm:grid-cols-2" onSubmit={(event) => {
                event.preventDefault();
                const data = new FormData(event.currentTarget);
                create.mutate({ code: String(data.get("code")), name: String(data.get("name")), client_name: String(data.get("client_name") ?? ""), product: nullable(data, "product"), start_date: nullable(data, "start_date"), end_date: nullable(data, "end_date"), description: String(data.get("description") ?? ""), status: "PLANNED" });
              }}>
                <Field label="Code" name="code" required />
                <Field label="Project name" name="name" required />
                <Field label="Client / owner" name="client_name" />
                <Field label="Related product" name="product"><Select name="product"><option value="">No product</option>{(products.data ?? []).filter((item) => item.status === "ACTIVE").map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</Select></Field>
                <Field label="Start date" name="start_date" type="date" />
                <Field label="End date" name="end_date" type="date" />
                <Field full label="Description" name="description" />
                <SubmitRow pending={create.isPending} />
              </form>
            </CreatePanel>
          ) : null}
          <MutationError error={create.error ?? archive.error} />
          {projects.isLoading ? <LoadingState /> : projects.error ? <ErrorState message={errorMessage(projects.error)} /> : <DataTable columns={columns} rowKey={(row) => row.id} rows={projects.data ?? []} />}
        </PageBody>
      </ScopeGate>
    </>
  );
}

function OperationalDependencies({ session }: { session: SessionPayload }) {
  void session;
  return null;
}

export function SubscriptionsPage({ session }: { session: SessionPayload }) {
  const queryClient = useQueryClient();
  const [creating, setCreating] = useState(false);
  const entity = activeEntity(session);
  const viewAllowed = can(session, "VIEW_OPERATIONS");
  const manageAllowed = can(session, "MANAGE_OPERATIONS");
  const subscriptions = useQuery({ queryKey: ["subscriptions", entity?.id], queryFn: operationsApi.subscriptions, enabled: Boolean(entity && viewAllowed) });
  const vendors = useQuery({ queryKey: ["vendors", entity?.id], queryFn: financeApi.vendors, enabled: Boolean(entity && viewAllowed) });
  const products = useQuery({ queryKey: ["products", entity?.id], queryFn: planningApi.products, enabled: Boolean(entity && viewAllowed) });
  const costCenters = useQuery({ queryKey: ["cost-centers", entity?.id], queryFn: planningApi.costCenters, enabled: Boolean(entity && viewAllowed) });
  const create = useMutation({ mutationFn: operationsApi.createSubscription, onSuccess: async () => { setCreating(false); await queryClient.invalidateQueries({ queryKey: ["subscriptions", entity?.id] }); await queryClient.invalidateQueries({ queryKey: ["renewals", entity?.id] }); } });
  const archive = useMutation({ mutationFn: (id: string) => operationsApi.updateSubscription(id, { status: "ARCHIVED" }), onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["subscriptions", entity?.id] }); queryClient.invalidateQueries({ queryKey: ["renewals", entity?.id] }); } });
  const columns: TableColumn<Subscription>[] = [
    { key: "name", label: "Subscription", render: (row) => <div><strong>{row.name}</strong><div className="text-[11px] text-[var(--color-text-muted)]">{row.category || "Uncategorized"}</div></div> },
    { key: "vendor", label: "Vendor", render: (row) => row.vendor_name || "—" },
    { key: "dimension", label: "Allocation", render: (row) => row.product_name || row.cost_center_name || "—" },
    { key: "cycle", label: "Billing", render: (row) => row.billing_cycle.replaceAll("_", " ") },
    { key: "renewal", label: "Next Renewal", render: (row) => shortDate(row.next_renewal_date) },
    { key: "amount", label: "Amount", numeric: true, render: (row) => money(row.amount, row.currency) },
    { key: "status", label: "Status", render: (row) => <StatusBadge value={row.status} /> },
    { key: "actions", label: "Actions", render: (row) => row.status === "ACTIVE" && manageAllowed ? <button className="erp-button !h-7 !min-h-7 text-[11px]" onClick={() => archive.mutate(row.id)} type="button"><Archive size={12} /> Archive</button> : "—" },
  ];

  return (
    <>
      <OperationalDependencies session={session} />
      <PageHeader actions={manageAllowed ? <button className="erp-button erp-button-primary" onClick={() => setCreating(true)} type="button"><Plus size={13} /> Add Subscription</button> : undefined} description="Manage recurring software, platform, service, and business obligations without turning subscriptions into accounting journals." eyebrow="Operations" title="Subscriptions" />
      <ScopeGate permission="VIEW_OPERATIONS" session={session}>
        <PageBody>
          {creating ? (
            <CreatePanel description="Record the operational contract. Financial expenses remain separate accounting documents." onClose={() => setCreating(false)} title="Add Subscription">
              <form className="grid gap-4 p-4 sm:grid-cols-2" onSubmit={(event) => {
                event.preventDefault(); const data = new FormData(event.currentTarget);
                create.mutate({ name: String(data.get("name")), category: String(data.get("category") ?? ""), vendor: nullable(data, "vendor"), product: nullable(data, "product"), cost_center: nullable(data, "cost_center"), amount: String(data.get("amount")), currency: String(data.get("currency")), billing_cycle: String(data.get("billing_cycle")), started_on: nullable(data, "started_on"), next_renewal_date: nullable(data, "next_renewal_date"), auto_renew: data.get("auto_renew") === "on", description: String(data.get("description") ?? ""), status: "ACTIVE" });
              }}>
                <Field label="Name" name="name" required />
                <Field label="Category" name="category" />
                <Field label="Vendor" name="vendor"><Select name="vendor"><option value="">No vendor</option>{(vendors.data ?? []).filter((item) => item.status === "ACTIVE").map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</Select></Field>
                <Field label="Product" name="product"><Select name="product"><option value="">No product</option>{(products.data ?? []).filter((item) => item.status === "ACTIVE").map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</Select></Field>
                <Field label="Cost center" name="cost_center"><Select name="cost_center"><option value="">No cost center</option>{(costCenters.data ?? []).filter((item) => item.status === "ACTIVE").map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</Select></Field>
                <Field label="Billing cycle" name="billing_cycle"><Select defaultValue="MONTHLY" name="billing_cycle"><option value="MONTHLY">Monthly</option><option value="QUARTERLY">Quarterly</option><option value="SEMIANNUAL">Semiannual</option><option value="ANNUAL">Annual</option><option value="CUSTOM">Custom</option></Select></Field>
                <Field label="Amount" name="amount" required step="0.01" type="number" />
                <Field defaultValue={entity?.base_currency ?? "USD"} label="Currency" name="currency" required />
                <Field label="Started on" name="started_on" type="date" />
                <Field label="Next renewal" name="next_renewal_date" type="date" />
                <label className="flex items-center gap-2 pt-6 text-sm"><input defaultChecked name="auto_renew" type="checkbox" /> Auto renew</label>
                <Field full label="Description" name="description" />
                <SubmitRow pending={create.isPending} />
              </form>
            </CreatePanel>
          ) : null}
          <MutationError error={create.error ?? archive.error} />
          {subscriptions.isLoading ? <LoadingState /> : subscriptions.error ? <ErrorState message={errorMessage(subscriptions.error)} /> : <DataTable columns={columns} rowKey={(row) => row.id} rows={subscriptions.data ?? []} />}
        </PageBody>
      </ScopeGate>
    </>
  );
}

export function DomainsPage({ session }: { session: SessionPayload }) {
  const queryClient = useQueryClient();
  const [creating, setCreating] = useState(false);
  const [renewing, setRenewing] = useState<DomainRecord | null>(null);
  const [historyDomain, setHistoryDomain] = useState<DomainRecord | null>(null);
  const entity = activeEntity(session);
  const viewAllowed = can(session, "VIEW_OPERATIONS");
  const manageAllowed = can(session, "MANAGE_OPERATIONS");
  const domains = useQuery({ queryKey: ["domains", entity?.id], queryFn: operationsApi.domains, enabled: Boolean(entity && viewAllowed) });
  const products = useQuery({ queryKey: ["products", entity?.id], queryFn: planningApi.products, enabled: Boolean(entity && viewAllowed) });
  const ledger = useQuery({ queryKey: ["ledger-accounts", entity?.id], queryFn: accountingApi.accounts, enabled: Boolean(entity && viewAllowed) });
  const history = useQuery({ queryKey: ["domain-renewals", historyDomain?.id], queryFn: () => operationsApi.domainRenewals(historyDomain!.id), enabled: Boolean(historyDomain) });
  const create = useMutation({ mutationFn: operationsApi.createDomain, onSuccess: async () => { setCreating(false); await queryClient.invalidateQueries({ queryKey: ["domains", entity?.id] }); await queryClient.invalidateQueries({ queryKey: ["renewals", entity?.id] }); } });
  const renew = useMutation({ mutationFn: ({ id, body }: { id: string; body: Record<string, unknown> }) => operationsApi.renewDomain(id, body), onSuccess: async (_, variables) => { setRenewing(null); await queryClient.invalidateQueries({ queryKey: ["domains", entity?.id] }); await queryClient.invalidateQueries({ queryKey: ["renewals", entity?.id] }); await queryClient.invalidateQueries({ queryKey: ["domain-renewals", variables.id] }); await queryClient.invalidateQueries({ queryKey: ["expenses", entity?.id] }); } });
  const archive = useMutation({ mutationFn: (id: string) => operationsApi.updateDomain(id, { status: "ARCHIVED" }), onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["domains", entity?.id] }); queryClient.invalidateQueries({ queryKey: ["renewals", entity?.id] }); } });
  const columns: TableColumn<DomainRecord>[] = [
    { key: "domain", label: "Domain", render: (row) => <strong>{row.domain_name}</strong> },
    { key: "registrar", label: "Registrar / DNS", render: (row) => <div>{row.registrar || "—"}<div className="text-[11px] text-[var(--color-text-muted)]">{row.dns_provider || "No DNS provider"}</div></div> },
    { key: "product", label: "Product", render: (row) => row.product_name || "—" },
    { key: "expiry", label: "Expiry", render: (row) => shortDate(row.expiry_date) },
    { key: "amount", label: "Renewal", numeric: true, render: (row) => money(row.renewal_amount, row.currency) },
    { key: "status", label: "Status", render: (row) => <StatusBadge value={row.status} /> },
    { key: "history", label: "History", render: (row) => <button className="erp-button !h-7 !min-h-7 text-[11px]" onClick={() => setHistoryDomain(row)} type="button"><History size={12} /> {row.renewal_count}</button> },
    { key: "actions", label: "Actions", render: (row) => manageAllowed && row.status === "ACTIVE" ? <div className="flex gap-1"><button className="erp-button !h-7 !min-h-7 text-[11px]" onClick={() => setRenewing(row)} type="button"><RefreshCw size={12} /> Renew</button><button aria-label={`Archive ${row.domain_name}`} className="erp-button !h-7 !min-h-7 !w-7 !p-0" onClick={() => archive.mutate(row.id)} type="button"><Archive size={12} /></button></div> : "—" },
  ];
  const historyColumns: TableColumn<DomainRenewal>[] = [
    { key: "date", label: "Renewed", render: (row) => shortDate(row.renewed_on) },
    { key: "period", label: "Expiry Change", render: (row) => `${shortDate(row.previous_expiry_date)} → ${shortDate(row.new_expiry_date)}` },
    { key: "amount", label: "Amount", numeric: true, render: (row) => money(row.amount, row.currency) },
    { key: "expense", label: "Expense", render: (row) => row.expense ? "Generated" : "Not generated" },
    { key: "notes", label: "Notes", render: (row) => row.notes || "—" },
  ];
  const expenseAccounts = (ledger.data ?? []).filter((account) => account.account_type === "EXPENSE" && account.is_active);
  const payableAccounts = (ledger.data ?? []).filter((account) => account.account_type === "LIABILITY" && account.is_active);

  return (
    <>
      <PageHeader actions={manageAllowed ? <button className="erp-button erp-button-primary" onClick={() => setCreating(true)} type="button"><Plus size={13} /> Add Domain</button> : undefined} description="Track ownership, registrar, DNS, product relationship, expiry, renewal cost, auto-renew, and immutable renewal history." eyebrow="Operations" title="Domains" />
      <ScopeGate permission="VIEW_OPERATIONS" session={session}>
        <PageBody>
          {creating ? (
            <CreatePanel description="Expense/payable accounts enable one-click draft expense generation when a renewal is recorded." onClose={() => setCreating(false)} title="Add Domain">
              <form className="grid gap-4 p-4 sm:grid-cols-2" onSubmit={(event) => { event.preventDefault(); const data = new FormData(event.currentTarget); create.mutate({ domain_name: String(data.get("domain_name")), registrar: String(data.get("registrar") ?? ""), dns_provider: String(data.get("dns_provider") ?? ""), purpose: String(data.get("purpose") ?? ""), purchase_date: nullable(data, "purchase_date"), expiry_date: String(data.get("expiry_date")), renewal_amount: String(data.get("renewal_amount")), currency: String(data.get("currency")), product: nullable(data, "product"), expense_account: nullable(data, "expense_account"), payable_account: nullable(data, "payable_account"), auto_renew: data.get("auto_renew") === "on", status: "ACTIVE" }); }}>
                <Field label="Domain name" name="domain_name" required />
                <Field label="Registrar" name="registrar" />
                <Field label="DNS provider" name="dns_provider" />
                <Field label="Purpose" name="purpose" />
                <Field label="Purchase date" name="purchase_date" type="date" />
                <Field label="Expiry date" name="expiry_date" required type="date" />
                <Field label="Renewal amount" name="renewal_amount" required step="0.01" type="number" />
                <Field defaultValue={entity?.base_currency ?? "USD"} label="Currency" name="currency" required />
                <Field label="Product" name="product"><Select name="product"><option value="">No product</option>{(products.data ?? []).filter((item) => item.status === "ACTIVE").map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</Select></Field>
                <Field label="Expense account" name="expense_account"><Select name="expense_account"><option value="">Not configured</option>{expenseAccounts.map((item) => <option key={item.id} value={item.id}>{item.code} · {item.name}</option>)}</Select></Field>
                <Field label="Payable account" name="payable_account"><Select name="payable_account"><option value="">Not configured</option>{payableAccounts.map((item) => <option key={item.id} value={item.id}>{item.code} · {item.name}</option>)}</Select></Field>
                <label className="flex items-center gap-2 pt-6 text-sm"><input defaultChecked name="auto_renew" type="checkbox" /> Auto renew</label>
                <SubmitRow pending={create.isPending} />
              </form>
            </CreatePanel>
          ) : null}
          {renewing ? (
            <CreatePanel description={`Current expiry: ${shortDate(renewing.expiry_date)}. Recording this action preserves the old expiry in renewal history.`} onClose={() => setRenewing(null)} title={`Renew ${renewing.domain_name}`}>
              <form className="grid gap-4 p-4 sm:grid-cols-2" onSubmit={(event) => { event.preventDefault(); const data = new FormData(event.currentTarget); renew.mutate({ id: renewing.id, body: { renewed_on: String(data.get("renewed_on")), new_expiry_date: String(data.get("new_expiry_date")), amount: String(data.get("amount")), currency: String(data.get("currency")), fx_rate: String(data.get("fx_rate")), notes: String(data.get("notes") ?? ""), generate_expense: data.get("generate_expense") === "on" } }); }}>
                <Field defaultValue={today()} label="Renewed on" name="renewed_on" required type="date" />
                <Field label="New expiry date" name="new_expiry_date" required type="date" />
                <Field defaultValue={renewing.renewal_amount} label="Amount" name="amount" required step="0.01" type="number" />
                <Field defaultValue={renewing.currency} label="Currency" name="currency" required />
                <Field defaultValue="1" label="FX rate" name="fx_rate" required step="0.0000000001" type="number" />
                <Field label="Notes" name="notes" />
                <label className="flex items-center gap-2 text-sm sm:col-span-2"><input name="generate_expense" type="checkbox" /> Generate a draft Expense for this renewal</label>
                <SubmitRow pending={renew.isPending} />
              </form>
            </CreatePanel>
          ) : null}
          <MutationError error={create.error ?? renew.error ?? archive.error} />
          {domains.isLoading ? <LoadingState /> : domains.error ? <ErrorState message={errorMessage(domains.error)} /> : <DataTable columns={columns} rowKey={(row) => row.id} rows={domains.data ?? []} />}
          {historyDomain ? <section className="mt-4 border border-[var(--color-border)] bg-white"><div className="flex items-center justify-between border-b border-[var(--color-border)] px-4 py-3"><div><h2 className="text-sm font-semibold">{historyDomain.domain_name} renewal history</h2><p className="text-xs text-[var(--color-text-muted)]">Historical renewal events are preserved when current expiry changes.</p></div><button className="erp-button !h-8 !min-h-8" onClick={() => setHistoryDomain(null)} type="button">Close</button></div><div className="p-3">{history.isLoading ? <LoadingState /> : history.error ? <ErrorState message={errorMessage(history.error)} /> : <DataTable columns={historyColumns} emptyDescription="Record the first domain renewal to create immutable history." emptyTitle="No renewal history" rowKey={(row) => row.id} rows={history.data ?? []} />}</div></section> : null}
        </PageBody>
      </ScopeGate>
    </>
  );
}

export function InfrastructurePage({ session }: { session: SessionPayload }) {
  const queryClient = useQueryClient();
  const [creating, setCreating] = useState(false);
  const entity = activeEntity(session);
  const viewAllowed = can(session, "VIEW_OPERATIONS");
  const manageAllowed = can(session, "MANAGE_OPERATIONS");
  const assets = useQuery({ queryKey: ["infrastructure", entity?.id], queryFn: operationsApi.infrastructure, enabled: Boolean(entity && viewAllowed) });
  const vendors = useQuery({ queryKey: ["vendors", entity?.id], queryFn: financeApi.vendors, enabled: Boolean(entity && viewAllowed) });
  const products = useQuery({ queryKey: ["products", entity?.id], queryFn: planningApi.products, enabled: Boolean(entity && viewAllowed) });
  const costCenters = useQuery({ queryKey: ["cost-centers", entity?.id], queryFn: planningApi.costCenters, enabled: Boolean(entity && viewAllowed) });
  const create = useMutation({ mutationFn: operationsApi.createInfrastructure, onSuccess: async () => { setCreating(false); await queryClient.invalidateQueries({ queryKey: ["infrastructure", entity?.id] }); await queryClient.invalidateQueries({ queryKey: ["renewals", entity?.id] }); } });
  const archive = useMutation({ mutationFn: (id: string) => operationsApi.updateInfrastructure(id, { status: "ARCHIVED" }), onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["infrastructure", entity?.id] }); queryClient.invalidateQueries({ queryKey: ["renewals", entity?.id] }); } });
  const columns: TableColumn<InfrastructureAsset>[] = [
    { key: "name", label: "Asset", render: (row) => <div><strong>{row.name}</strong><div className="text-[11px] text-[var(--color-text-muted)]">{row.provider_reference || row.purpose || "—"}</div></div> },
    { key: "type", label: "Type", render: (row) => row.asset_type.replaceAll("_", " ") },
    { key: "vendor", label: "Vendor", render: (row) => row.vendor_name || "—" },
    { key: "allocation", label: "Product / Cost Center", render: (row) => [row.product_name, row.cost_center_name].filter(Boolean).join(" / ") || "—" },
    { key: "renewal", label: "Next Renewal", render: (row) => shortDate(row.next_renewal_date) },
    { key: "amount", label: "Renewal Cost", numeric: true, render: (row) => money(row.renewal_amount, row.currency) },
    { key: "status", label: "Status", render: (row) => <StatusBadge value={row.status} /> },
    { key: "actions", label: "Actions", render: (row) => row.status === "ACTIVE" && manageAllowed ? <button className="erp-button !h-7 !min-h-7 text-[11px]" onClick={() => archive.mutate(row.id)} type="button"><Archive size={12} /> Archive</button> : "—" },
  ];

  return (
    <>
      <PageHeader actions={manageAllowed ? <button className="erp-button erp-button-primary" onClick={() => setCreating(true)} type="button"><Plus size={13} /> Add Asset</button> : undefined} description="Track VPS, hosting, cloud, storage, CDN, backup, email, monitoring, and other operational infrastructure." eyebrow="Operations" title="Infrastructure" />
      <ScopeGate permission="VIEW_OPERATIONS" session={session}>
        <PageBody>
          {creating ? <CreatePanel description="Record the operational asset and its recurring renewal commitment." onClose={() => setCreating(false)} title="Add Infrastructure Asset"><form className="grid gap-4 p-4 sm:grid-cols-2" onSubmit={(event) => { event.preventDefault(); const data = new FormData(event.currentTarget); create.mutate({ name: String(data.get("name")), asset_type: String(data.get("asset_type")), provider_reference: String(data.get("provider_reference") ?? ""), purpose: String(data.get("purpose") ?? ""), vendor: nullable(data, "vendor"), product: nullable(data, "product"), cost_center: nullable(data, "cost_center"), started_on: nullable(data, "started_on"), next_renewal_date: nullable(data, "next_renewal_date"), renewal_amount: String(data.get("renewal_amount")), currency: String(data.get("currency")), billing_cycle: String(data.get("billing_cycle")), auto_renew: data.get("auto_renew") === "on", status: "ACTIVE" }); }}>
            <Field label="Asset name" name="name" required />
            <Field label="Asset type" name="asset_type"><Select name="asset_type" required><option value="VPS">VPS</option><option value="HOSTING">Hosting</option><option value="CLOUD">Cloud</option><option value="STORAGE">Storage</option><option value="CDN">CDN</option><option value="BACKUP">Backup</option><option value="EMAIL">Email Infrastructure</option><option value="MONITORING">Monitoring</option><option value="OTHER">Other</option></Select></Field>
            <Field label="Provider reference" name="provider_reference" />
            <Field label="Purpose" name="purpose" />
            <Field label="Vendor" name="vendor"><Select name="vendor"><option value="">No vendor</option>{(vendors.data ?? []).filter((item) => item.status === "ACTIVE").map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</Select></Field>
            <Field label="Product" name="product"><Select name="product"><option value="">No product</option>{(products.data ?? []).filter((item) => item.status === "ACTIVE").map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</Select></Field>
            <Field label="Cost center" name="cost_center"><Select name="cost_center"><option value="">No cost center</option>{(costCenters.data ?? []).filter((item) => item.status === "ACTIVE").map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</Select></Field>
            <Field label="Billing cycle" name="billing_cycle"><Select defaultValue="MONTHLY" name="billing_cycle"><option value="MONTHLY">Monthly</option><option value="QUARTERLY">Quarterly</option><option value="SEMIANNUAL">Semiannual</option><option value="ANNUAL">Annual</option><option value="CUSTOM">Custom</option></Select></Field>
            <Field label="Started on" name="started_on" type="date" />
            <Field label="Next renewal" name="next_renewal_date" type="date" />
            <Field label="Renewal amount" name="renewal_amount" required step="0.01" type="number" />
            <Field defaultValue={entity?.base_currency ?? "USD"} label="Currency" name="currency" required />
            <label className="flex items-center gap-2 text-sm sm:col-span-2"><input defaultChecked name="auto_renew" type="checkbox" /> Auto renew</label>
            <SubmitRow pending={create.isPending} />
          </form></CreatePanel> : null}
          <MutationError error={create.error ?? archive.error} />
          {assets.isLoading ? <LoadingState /> : assets.error ? <ErrorState message={errorMessage(assets.error)} /> : <DataTable columns={columns} rowKey={(row) => row.id} rows={assets.data ?? []} />}
        </PageBody>
      </ScopeGate>
    </>
  );
}

export function RenewalsPage({ session }: { session: SessionPayload }) {
  const entity = activeEntity(session);
  const viewAllowed = can(session, "VIEW_OPERATIONS");
  const [startDate, setStartDate] = useState(today());
  const [endDate, setEndDate] = useState(() => {
    const next = new Date(); next.setDate(next.getDate() + 90); return next.toISOString().slice(0, 10);
  });
  const renewals = useQuery({ queryKey: ["renewals", entity?.id, startDate, endDate], queryFn: () => operationsApi.renewals(startDate, endDate), enabled: Boolean(entity && viewAllowed) });
  const rows = renewals.data ?? [];
  const next30 = new Date(); next30.setDate(next30.getDate() + 30);
  const next30String = next30.toISOString().slice(0, 10);
  const dueSoon = rows.filter((row) => row.renewal_date <= next30String).length;
  const autoRenew = rows.filter((row) => row.auto_renew).length;
  const columns: TableColumn<RenewalItem>[] = [
    { key: "date", label: "Renewal Date", render: (row) => shortDate(row.renewal_date) },
    { key: "type", label: "Source", render: (row) => <StatusBadge value={row.source_type} /> },
    { key: "name", label: "Obligation", render: (row) => <strong>{row.name}</strong> },
    { key: "vendor", label: "Vendor / Registrar", render: (row) => row.vendor_name || "—" },
    { key: "allocation", label: "Product / Cost Center", render: (row) => [row.product_name, row.cost_center_name].filter(Boolean).join(" / ") || "—" },
    { key: "amount", label: "Amount", numeric: true, render: (row) => money(row.amount, row.currency) },
    { key: "auto", label: "Auto Renew", render: (row) => row.auto_renew ? "Yes" : "No" },
  ];
  return (
    <>
      <PageHeader description="Aggregated renewal calendar derived from subscriptions, domains, and infrastructure. This view does not duplicate operational source records." eyebrow="Operations" title="Renewals" />
      <ScopeGate permission="VIEW_OPERATIONS" session={session}>
        <MetricStrip metrics={[{ label: "Upcoming", value: String(rows.length), note: "Selected period" }, { label: "Next 30 Days", value: String(dueSoon), note: "Near-term commitments" }, { label: "Auto Renew", value: String(autoRenew), note: "Enabled source records" }, { label: "Manual Renewal", value: String(rows.length - autoRenew), note: "Requires attention" }]} />
        <PageBody>
          <div className="mb-3 flex flex-wrap gap-3 border border-[var(--color-border)] bg-white p-3"><Field label="From" name="start"><input className="erp-field !h-8 !min-h-8" onChange={(event) => setStartDate(event.target.value)} type="date" value={startDate} /></Field><Field label="Through" name="end"><input className="erp-field !h-8 !min-h-8" onChange={(event) => setEndDate(event.target.value)} type="date" value={endDate} /></Field></div>
          {renewals.isLoading ? <LoadingState /> : renewals.error ? <ErrorState message={errorMessage(renewals.error)} /> : <DataTable columns={columns} emptyDescription="No active subscription, domain, or infrastructure renewal falls inside this date window." emptyTitle="No renewals in this period" rowKey={(row) => `${row.source_type}-${row.source_id}`} rows={rows} />}
        </PageBody>
      </ScopeGate>
    </>
  );
}

export function BudgetsPage({ session }: { session: SessionPayload }) {
  const queryClient = useQueryClient();
  const [creating, setCreating] = useState(false);
  const [selectedBudgetId, setSelectedBudgetId] = useState<string | null>(null);
  const [addingLine, setAddingLine] = useState(false);
  const entity = activeEntity(session);
  const viewAllowed = can(session, "VIEW_PLANNING");
  const manageAllowed = can(session, "MANAGE_PLANNING");
  const budgets = useQuery({ queryKey: ["budgets", entity?.id], queryFn: planningApi.budgets, enabled: Boolean(entity && viewAllowed) });
  const actuals = useQuery({ queryKey: ["budget-actuals", selectedBudgetId], queryFn: () => planningApi.budgetActuals(selectedBudgetId!), enabled: Boolean(selectedBudgetId) });
  const accounts = useQuery({ queryKey: ["ledger-accounts", entity?.id], queryFn: accountingApi.accounts, enabled: Boolean(entity && viewAllowed) });
  const costCenters = useQuery({ queryKey: ["cost-centers", entity?.id], queryFn: planningApi.costCenters, enabled: Boolean(entity && viewAllowed) });
  const products = useQuery({ queryKey: ["products", entity?.id], queryFn: planningApi.products, enabled: Boolean(entity && viewAllowed) });
  const projects = useQuery({ queryKey: ["projects", entity?.id], queryFn: planningApi.projects, enabled: Boolean(entity && viewAllowed) });
  const create = useMutation({ mutationFn: planningApi.createBudget, onSuccess: async () => { setCreating(false); await queryClient.invalidateQueries({ queryKey: ["budgets", entity?.id] }); } });
  const lifecycle = useMutation({ mutationFn: ({ id, status }: { id: string; status: string }) => planningApi.updateBudget(id, { status }), onSuccess: () => queryClient.invalidateQueries({ queryKey: ["budgets", entity?.id] }) });
  const createLine = useMutation({ mutationFn: ({ budgetId, body }: { budgetId: string; body: Record<string, unknown> }) => planningApi.createBudgetLine(budgetId, body), onSuccess: async (_, variables) => { setAddingLine(false); await queryClient.invalidateQueries({ queryKey: ["budget-actuals", variables.budgetId] }); await queryClient.invalidateQueries({ queryKey: ["budgets", entity?.id] }); } });
  const columns: TableColumn<Budget>[] = [
    { key: "name", label: "Budget", render: (row) => <strong>{row.name}</strong> },
    { key: "period", label: "Period", render: (row) => `${shortDate(row.start_date)} → ${shortDate(row.end_date)}` },
    { key: "lines", label: "Lines", numeric: true, render: (row) => row.line_count },
    { key: "status", label: "Status", render: (row) => <StatusBadge value={row.status} /> },
    { key: "actions", label: "Actions", render: (row) => <div className="flex flex-wrap gap-1"><button className="erp-button !h-7 !min-h-7 text-[11px]" onClick={() => { setSelectedBudgetId(row.id); setAddingLine(false); }} type="button">Review Actuals</button>{manageAllowed && row.status === "DRAFT" ? <button className="erp-button !h-7 !min-h-7 text-[11px]" onClick={() => lifecycle.mutate({ id: row.id, status: "ACTIVE" })} type="button">Activate</button> : null}{manageAllowed && row.status === "ACTIVE" ? <button className="erp-button !h-7 !min-h-7 text-[11px]" onClick={() => lifecycle.mutate({ id: row.id, status: "CLOSED" })} type="button">Close</button> : null}</div> },
  ];
  const actualColumns: TableColumn<BudgetActualLine>[] = [
    { key: "target", label: "Target", render: (row) => [row.expense_account_name, row.cost_center_name, row.product_name, row.project_name].filter(Boolean).join(" / ") || "—" },
    { key: "budget", label: "Budget", numeric: true, render: (row) => money(row.budget_amount, actuals.data?.base_currency) },
    { key: "actual", label: "Actual", numeric: true, render: (row) => money(row.actual_amount, actuals.data?.base_currency) },
    { key: "variance", label: "Variance", numeric: true, render: (row) => money(row.variance, actuals.data?.base_currency) },
    { key: "util", label: "Utilization", numeric: true, render: (row) => `${row.utilization_percent}%` },
  ];
  const expenseAccounts = (accounts.data ?? []).filter((item) => item.account_type === "EXPENSE" && item.is_active);

  return (
    <>
      <PageHeader actions={manageAllowed ? <button className="erp-button erp-button-primary" onClick={() => setCreating(true)} type="button"><Plus size={13} /> Add Budget</button> : undefined} description="Plan spend by account, cost center, product, or project. Actual values are always calculated from posted financial data." eyebrow="Planning" title="Budgets" />
      <ScopeGate permission="VIEW_PLANNING" session={session}>
        <PageBody>
          {creating ? <CreatePanel description="Create the budget period first, then add target lines." onClose={() => setCreating(false)} title="Add Budget"><form className="grid gap-4 p-4 sm:grid-cols-2" onSubmit={(event) => { event.preventDefault(); const data = new FormData(event.currentTarget); create.mutate({ name: String(data.get("name")), start_date: String(data.get("start_date")), end_date: String(data.get("end_date")), status: "DRAFT", notes: String(data.get("notes") ?? "") }); }}><Field label="Budget name" name="name" required /><Field label="Start date" name="start_date" required type="date" /><Field label="End date" name="end_date" required type="date" /><Field label="Notes" name="notes" /><SubmitRow pending={create.isPending} /></form></CreatePanel> : null}
          <MutationError error={create.error ?? lifecycle.error ?? createLine.error} />
          {budgets.isLoading ? <LoadingState /> : budgets.error ? <ErrorState message={errorMessage(budgets.error)} /> : <DataTable columns={columns} rowKey={(row) => row.id} rows={budgets.data ?? []} />}
          {selectedBudgetId ? <section className="mt-4 border border-[var(--color-border)] bg-white"><div className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--color-border)] px-4 py-3"><div><h2 className="text-sm font-semibold">Budget vs Actual</h2><p className="text-xs text-[var(--color-text-muted)]">Actuals are derived from posted journal lines and authoritative expense allocations.</p></div><div className="flex gap-2">{manageAllowed ? <button className="erp-button erp-button-primary !h-8 !min-h-8" onClick={() => setAddingLine((value) => !value)} type="button"><Plus size={12} /> Add Line</button> : null}<button className="erp-button !h-8 !min-h-8" onClick={() => setSelectedBudgetId(null)} type="button">Close</button></div></div>
            {addingLine ? <form className="grid gap-3 border-b border-[var(--color-border)] bg-[var(--color-surface-subtle)] p-4 sm:grid-cols-3" onSubmit={(event) => { event.preventDefault(); const data = new FormData(event.currentTarget); createLine.mutate({ budgetId: selectedBudgetId, body: { expense_account: nullable(data, "expense_account"), cost_center: nullable(data, "cost_center"), product: nullable(data, "product"), project: nullable(data, "project"), amount: String(data.get("amount")), notes: String(data.get("notes") ?? "") } }); }}><Field label="Expense account" name="expense_account"><Select name="expense_account"><option value="">No account target</option>{expenseAccounts.map((item) => <option key={item.id} value={item.id}>{item.code} · {item.name}</option>)}</Select></Field><Field label="Cost center" name="cost_center"><Select name="cost_center"><option value="">No cost center</option>{(costCenters.data ?? []).filter((item) => item.status === "ACTIVE").map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</Select></Field><Field label="Product" name="product"><Select name="product"><option value="">No product</option>{(products.data ?? []).filter((item) => item.status === "ACTIVE").map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</Select></Field><Field label="Project" name="project"><Select name="project"><option value="">No project</option>{(projects.data ?? []).filter((item) => item.status !== "ARCHIVED").map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</Select></Field><Field label="Budget amount" name="amount" required step="0.01" type="number" /><Field label="Notes" name="notes" /><div className="flex justify-end sm:col-span-3"><button className="erp-button erp-button-primary" disabled={createLine.isPending} type="submit">{createLine.isPending ? "Saving..." : "Save Line"}</button></div></form> : null}
            <div className="p-3">{actuals.isLoading ? <LoadingState /> : actuals.error ? <ErrorState message={errorMessage(actuals.error)} /> : actuals.data ? <><MetricStrip metrics={[{ label: "Budget", value: money(actuals.data.total_budget, actuals.data.base_currency) }, { label: "Actual", value: money(actuals.data.total_actual, actuals.data.base_currency) }, { label: "Variance", value: money(actuals.data.total_variance, actuals.data.base_currency), tone: Number(actuals.data.total_variance) >= 0 ? "good" : "bad" }, { label: "Lines", value: String(actuals.data.lines.length) }]} /><div className="mt-3"><DataTable columns={actualColumns} emptyDescription="Add a budget line to begin budget-versus-actual tracking." emptyTitle="No budget lines" rowKey={(row) => row.id} rows={actuals.data.lines} /></div></> : null}</div>
          </section> : null}
        </PageBody>
      </ScopeGate>
    </>
  );
}

type AllocationDraft = {
  key: string;
  cost_center: string;
  product: string;
  project: string;
  amount: string;
  note: string;
};

function emptyAllocation(key = "initial"): AllocationDraft {
  return { key, cost_center: "", product: "", project: "", amount: "", note: "" };
}

export function ExpenseAllocationsPage({ session }: { session: SessionPayload }) {
  const queryClient = useQueryClient();
  const entity = activeEntity(session);
  const viewAllowed = can(session, "VIEW_PLANNING");
  const manageAllowed = can(session, "MANAGE_PLANNING");
  const [selectedExpenseId, setSelectedExpenseId] = useState("");
  const [rows, setRows] = useState<AllocationDraft[]>([emptyAllocation()]);
  const [clientError, setClientError] = useState("");
  const expenses = useQuery({ queryKey: ["expenses", entity?.id], queryFn: financeApi.expenses, enabled: Boolean(entity && viewAllowed) });
  const costCenters = useQuery({ queryKey: ["cost-centers", entity?.id], queryFn: planningApi.costCenters, enabled: Boolean(entity && viewAllowed) });
  const products = useQuery({ queryKey: ["products", entity?.id], queryFn: planningApi.products, enabled: Boolean(entity && viewAllowed) });
  const projects = useQuery({ queryKey: ["projects", entity?.id], queryFn: planningApi.projects, enabled: Boolean(entity && viewAllowed) });
  const existing = useQuery({ queryKey: ["expense-allocations", selectedExpenseId], queryFn: () => planningApi.expenseAllocations(selectedExpenseId), enabled: Boolean(selectedExpenseId && viewAllowed) });
  const save = useMutation({ mutationFn: ({ expenseId, allocations }: { expenseId: string; allocations: Array<Record<string, unknown>> }) => planningApi.replaceExpenseAllocations(expenseId, allocations), onSuccess: async (_, variables) => { setClientError(""); await queryClient.invalidateQueries({ queryKey: ["expense-allocations", variables.expenseId] }); } });
  const selectedExpense = (expenses.data ?? []).find((expense) => expense.id === selectedExpenseId);
  const currentColumns: TableColumn<ExpenseAllocation>[] = [
    { key: "dimension", label: "Dimensions", render: (row) => [costCenters.data?.find((item) => item.id === row.cost_center)?.name, products.data?.find((item) => item.id === row.product)?.name, projects.data?.find((item) => item.id === row.project)?.name].filter(Boolean).join(" / ") || "—" },
    { key: "amount", label: "Amount", numeric: true, render: (row) => money(row.amount, selectedExpense?.currency) },
    { key: "base", label: "Base Amount", numeric: true, render: (row) => money(row.base_amount, entity?.base_currency) },
    { key: "note", label: "Note", render: (row) => row.note || "—" },
  ];
  function updateRow(key: string, field: keyof Omit<AllocationDraft, "key">, value: string) {
    setRows((current) => current.map((row) => row.key === key ? { ...row, [field]: value } : row));
  }
  function loadCurrent() {
    const data = existing.data ?? [];
    setRows(data.length ? data.map((row, index) => ({ key: `${row.id}-${index}`, cost_center: row.cost_center ?? "", product: row.product ?? "", project: row.project ?? "", amount: row.amount, note: row.note })) : [emptyAllocation(`empty-${Date.now()}`)]);
  }
  function saveRows() {
    if (!selectedExpense) return;
    const usable = rows.filter((row) => Number(row.amount) > 0);
    if (!usable.length) { setClientError("Add at least one allocation amount before saving."); return; }
    if (usable.some((row) => !row.cost_center && !row.product && !row.project)) { setClientError("Every allocation requires a cost center, product, or project."); return; }
    const total = usable.reduce((sum, row) => sum + Number(row.amount), 0);
    if (total > Number(selectedExpense.amount)) { setClientError("Allocated amount cannot exceed the expense amount."); return; }
    setClientError("");
    save.mutate({ expenseId: selectedExpense.id, allocations: usable.map((row) => ({ cost_center: row.cost_center || null, product: row.product || null, project: row.project || null, amount: row.amount, note: row.note })) });
  }

  return (
    <>
      <PageHeader description="Split draft expenses across cost centers, products, and projects using authoritative amounts. Percentages remain derived presentation only." eyebrow="Planning" title="Expense Allocations" />
      <ScopeGate permission="VIEW_PLANNING" session={session}>
        <PageBody>
          <div className="mb-4 border border-[var(--color-border)] bg-white p-4"><label><span className="erp-label">Draft expense</span><select className="erp-field max-w-2xl" onChange={(event) => { setSelectedExpenseId(event.target.value); setRows([emptyAllocation(`select-${Date.now()}`)]); setClientError(""); }} value={selectedExpenseId}><option value="">Select a draft expense</option>{(expenses.data ?? []).filter((expense) => expense.status === "DRAFT").map((expense: Expense) => <option key={expense.id} value={expense.id}>{shortDate(expense.expense_date)} · {expense.description} · {money(expense.amount, expense.currency)}</option>)}</select></label></div>
          {expenses.isLoading ? <LoadingState /> : expenses.error ? <ErrorState message={errorMessage(expenses.error)} /> : !selectedExpense ? <EmptyState description="Only draft expenses can be allocated or reallocated. Select one above to begin." title="Select an expense" /> : <>
            <MetricStrip metrics={[{ label: "Expense", value: money(selectedExpense.amount, selectedExpense.currency), note: selectedExpense.description }, { label: "Current Allocated", value: money((existing.data ?? []).reduce((sum, row) => sum + Number(row.amount), 0), selectedExpense.currency) }, { label: "Draft Lines", value: String(rows.length) }, { label: "FX Rate", value: selectedExpense.fx_rate }]} />
            <section className="mt-4 border border-[var(--color-border)] bg-white"><div className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--color-border)] px-4 py-3"><div><h2 className="text-sm font-semibold">Allocation editor</h2><p className="text-xs text-[var(--color-text-muted)]">Saving replaces the draft expense allocation set atomically.</p></div><div className="flex gap-2"><button className="erp-button !h-8 !min-h-8" disabled={existing.isLoading} onClick={loadCurrent} type="button">Load Current</button>{manageAllowed ? <button className="erp-button !h-8 !min-h-8" onClick={() => setRows((current) => [...current, emptyAllocation(`row-${Date.now()}-${current.length}`)])} type="button"><Plus size={12} /> Add Line</button> : null}</div></div>
              <div className="overflow-x-auto"><table className="erp-table"><thead><tr><th>Cost Center</th><th>Product</th><th>Project</th><th className="erp-num">Amount</th><th>Note</th><th /></tr></thead><tbody>{rows.map((row) => <tr key={row.key}><td><select className="erp-field !h-8 !min-h-8 min-w-40" onChange={(event) => updateRow(row.key, "cost_center", event.target.value)} value={row.cost_center}><option value="">—</option>{(costCenters.data ?? []).filter((item) => item.status === "ACTIVE").map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></td><td><select className="erp-field !h-8 !min-h-8 min-w-40" onChange={(event) => updateRow(row.key, "product", event.target.value)} value={row.product}><option value="">—</option>{(products.data ?? []).filter((item) => item.status === "ACTIVE").map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></td><td><select className="erp-field !h-8 !min-h-8 min-w-40" onChange={(event) => updateRow(row.key, "project", event.target.value)} value={row.project}><option value="">—</option>{(projects.data ?? []).filter((item) => item.status !== "ARCHIVED").map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></td><td><input className="erp-field !h-8 !min-h-8 w-28 text-right" min="0.01" onChange={(event) => updateRow(row.key, "amount", event.target.value)} step="0.01" type="number" value={row.amount} /></td><td><input className="erp-field !h-8 !min-h-8 min-w-40" onChange={(event) => updateRow(row.key, "note", event.target.value)} value={row.note} /></td><td>{rows.length > 1 ? <button aria-label="Remove allocation line" className="erp-button !h-7 !min-h-7" onClick={() => setRows((current) => current.filter((item) => item.key !== row.key))} type="button">Remove</button> : null}</td></tr>)}</tbody></table></div>
              {clientError ? <div className="border-t border-[#e0a8a8] bg-[#fff6f6] px-4 py-3 text-xs text-[var(--color-danger)]">{clientError}</div> : null}<MutationError error={save.error} />
              <div className="flex justify-end border-t border-[var(--color-border)] bg-[var(--color-surface-subtle)] p-3"><button className="erp-button erp-button-primary" disabled={!manageAllowed || save.isPending} onClick={saveRows} type="button">{save.isPending ? "Saving..." : "Replace Allocations"}</button></div>
            </section>
            <section className="mt-4"><h2 className="mb-2 text-sm font-semibold">Current saved allocations</h2>{existing.isLoading ? <LoadingState /> : existing.error ? <ErrorState message={errorMessage(existing.error)} /> : <DataTable columns={currentColumns} emptyDescription="This draft expense has not been allocated to planning dimensions yet." emptyTitle="No saved allocations" rowKey={(row) => row.id} rows={existing.data ?? []} />}</section>
          </>}
        </PageBody>
      </ScopeGate>
    </>
  );
}
