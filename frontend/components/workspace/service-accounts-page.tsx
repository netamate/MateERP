"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Archive, Boxes, Layers3, Pencil, Plus, Search, UsersRound, X } from "lucide-react";
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
import {
  financeApi,
  operationsApi,
  type ServiceAccount,
  type SessionPayload,
  type VendorService,
} from "@/lib/api";

function can(session: SessionPayload, permission: string) {
  return session.memberships.find(
    (item) => item.organization_id === session.active_organization_id,
  )?.permissions.includes(permission) ?? false;
}

function problem(error: unknown) {
  return error instanceof Error ? error.message : "Unable to complete the request.";
}

type Editor =
  | { kind: "service"; current?: VendorService }
  | { kind: "account"; current?: ServiceAccount }
  | null;

function Popup({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}) {
  return (
    <section className="mb-4 border border-[var(--color-border-strong)] bg-white">
      <div className="flex items-start justify-between border-b border-[var(--color-border)] px-4 py-3">
        <div>
          <h2 className="text-sm font-semibold">{title}</h2>
          <p className="mt-1 text-xs text-[var(--color-text-muted)]">
            Edit your catalogue without changing existing subscription or invoice history.
          </p>
        </div>
        <button aria-label="Close editor" className="erp-button !h-8 !min-h-8 !w-8 !p-0"
          onClick={onClose} type="button"><X size={14} /></button>
      </div>
      {children}
    </section>
  );
}

const serviceTypes: Array<[string, string]> = [
  ["SAAS", "SaaS / Software"],
  ["API", "API / Usage Service"],
  ["CLOUD", "Cloud"],
  ["DOMAIN", "Domain"],
  ["VPS", "VPS / Server"],
  ["HOSTING", "Hosting"],
  ["EMAIL", "Email"],
  ["AI", "AI"],
  ["STORAGE", "Storage"],
  ["OTHER", "Other"],
];

export function ServiceAccountsPage({ session }: { session: SessionPayload }) {
  const entity = session.active_legal_entities.find(
    (item) => item.id === session.active_legal_entity_id,
  );
  const canView = can(session, "VIEW_OPERATIONS");
  const canManage = can(session, "MANAGE_OPERATIONS");
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<"services" | "accounts">("services");
  const [editor, setEditor] = useState<Editor>(null);
  const [search, setSearch] = useState("");
  const [vendorFilter, setVendorFilter] = useState("");
  const [serviceFilter, setServiceFilter] = useState("");

  const vendors = useQuery({
    queryKey: ["vendors", entity?.id],
    queryFn: financeApi.vendors,
    enabled: Boolean(entity && canView),
  });
  const services = useQuery({
    queryKey: ["vendor-services", entity?.id],
    queryFn: operationsApi.vendorServices,
    enabled: Boolean(entity && canView),
  });
  const accounts = useQuery({
    queryKey: ["service-accounts", entity?.id],
    queryFn: operationsApi.serviceAccounts,
    enabled: Boolean(entity && canView),
  });
  const subscriptions = useQuery({
    queryKey: ["subscriptions", entity?.id],
    queryFn: operationsApi.subscriptions,
    enabled: Boolean(entity && canView),
  });

  const refresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["vendor-services", entity?.id] }),
      queryClient.invalidateQueries({ queryKey: ["service-accounts", entity?.id] }),
      queryClient.invalidateQueries({ queryKey: ["subscriptions", entity?.id] }),
    ]);
  };

  const saveService = useMutation({
    mutationFn: ({ id, body }: { id?: string; body: Record<string, unknown> }) =>
      id ? operationsApi.updateVendorService(id, body) : operationsApi.createVendorService(body),
    onSuccess: async () => {
      setEditor(null);
      await refresh();
    },
  });
  const saveAccount = useMutation({
    mutationFn: ({ id, body }: { id?: string; body: Record<string, unknown> }) =>
      id ? operationsApi.updateServiceAccount(id, body) : operationsApi.createServiceAccount(body),
    onSuccess: async () => {
      setEditor(null);
      await refresh();
    },
  });

  const serviceRows = useMemo(() => {
    const term = search.trim().toLowerCase();
    return (services.data ?? []).filter(
      (item) => (!vendorFilter || item.vendor === vendorFilter)
        && (!term || [item.name, item.code, item.vendor_name].some(
          (value) => value.toLowerCase().includes(term),
        )),
    );
  }, [services.data, search, vendorFilter]);
  const accountRows = useMemo(() => {
    const term = search.trim().toLowerCase();
    return (accounts.data ?? []).filter(
      (item) => (!vendorFilter || item.vendor_id === vendorFilter)
        && (!serviceFilter || item.service === serviceFilter)
        && (!term || [item.alias, item.code, item.service_name, item.vendor_name].some(
          (value) => value.toLowerCase().includes(term),
        )),
    );
  }, [accounts.data, search, vendorFilter, serviceFilter]);

  if (!entity) return <PermissionNotice>Choose an active legal entity first.</PermissionNotice>;
  if (!canView) return <PermissionNotice>You cannot view operational service accounts.</PermissionNotice>;

  const busy = saveService.isPending || saveAccount.isPending;
  const error = saveService.error ?? saveAccount.error;
  const serviceColumns: Array<TableColumn<VendorService>> = [
    { key: "name", label: "Service", render: (item) => (
      <div><div className="font-semibold">{item.name}</div>
        <div className="mt-0.5 text-[11px] text-[var(--color-text-muted)]">{item.code} · {item.service_type}</div>
      </div>
    ) },
    { key: "vendor", label: "Vendor", render: (item) => item.vendor_name },
    { key: "accounts", label: "Accounts", numeric: true, render: (item) => String(item.account_count) },
    { key: "status", label: "Status", render: (item) => <StatusBadge value={item.status} /> },
    { key: "actions", label: "Actions", render: (item) => canManage ? (
      <div className="flex flex-wrap gap-1">
        <button className="erp-button !h-7 !min-h-7 text-[11px]" type="button"
          onClick={() => setEditor({ kind: "service", current: item })}>
          <Pencil size={12} /> Edit
        </button>
        <button className="erp-button !h-7 !min-h-7 text-[11px]" type="button"
          disabled={busy}
          onClick={() => saveService.mutate({
            id: item.id,
            body: { status: item.status === "ACTIVE" ? "ARCHIVED" : "ACTIVE" },
          })}>
          <Archive size={12} /> {item.status === "ACTIVE" ? "Archive" : "Restore"}
        </button>
      </div>
    ) : "—" },
  ];
  const accountColumns: Array<TableColumn<ServiceAccount>> = [
    { key: "alias", label: "Account Alias", render: (item) => (
      <div><div className="font-semibold">{item.alias}</div>
        <div className="mt-0.5 text-[11px] text-[var(--color-text-muted)]">{item.code}</div>
      </div>
    ) },
    { key: "service", label: "Service", render: (item) => (
      <div>{item.service_name}<div className="text-[11px] text-[var(--color-text-muted)]">{item.vendor_name}</div></div>
    ) },
    { key: "subscriptions", label: "Subscriptions", numeric: true, render: (item) => String(item.subscription_count) },
    { key: "status", label: "Status", render: (item) => <StatusBadge value={item.status} /> },
    { key: "actions", label: "Actions", render: (item) => canManage ? (
      <div className="flex flex-wrap gap-1">
        <button className="erp-button !h-7 !min-h-7 text-[11px]" type="button"
          onClick={() => setEditor({ kind: "account", current: item })}>
          <Pencil size={12} /> Edit
        </button>
        <button className="erp-button !h-7 !min-h-7 text-[11px]" type="button"
          disabled={busy}
          onClick={() => saveAccount.mutate({
            id: item.id,
            body: { status: item.status === "ACTIVE" ? "ARCHIVED" : "ACTIVE" },
          })}>
          <Archive size={12} /> {item.status === "ACTIVE" ? "Archive" : "Restore"}
        </button>
      </div>
    ) : "—" },
  ];

  function submitService(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    saveService.mutate({
      id: editor?.kind === "service" ? editor.current?.id : undefined,
      body: {
        vendor: String(data.get("vendor") ?? ""),
        name: String(data.get("name") ?? "").trim(),
        code: String(data.get("code") ?? "").trim(),
        service_type: String(data.get("service_type") ?? "OTHER"),
        description: String(data.get("description") ?? ""),
        status: String(data.get("status") ?? "ACTIVE"),
      },
    });
  }
  function submitAccount(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    saveAccount.mutate({
      id: editor?.kind === "account" ? editor.current?.id : undefined,
      body: {
        service: String(data.get("service") ?? ""),
        alias: String(data.get("alias") ?? "").trim(),
        reference: String(data.get("reference") ?? "").trim(),
        notes: String(data.get("notes") ?? ""),
        status: String(data.get("status") ?? "ACTIVE"),
      },
    });
  }

  const selectedService = editor?.kind === "service" ? editor.current : undefined;
  const selectedAccount = editor?.kind === "account" ? editor.current : undefined;

  return (
    <>
      <PageHeader eyebrow="Management" title="Services & Accounts"
        description="Organize vendor services, billing identities and their subscriptions. Codes stay stable as names evolve."
        actions={canManage ? (
          <button className="erp-button erp-button-primary" type="button"
            onClick={() => setEditor({ kind: tab === "services" ? "service" : "account" })}>
            <Plus size={14} /> Add {tab === "services" ? "Service" : "Account"}
          </button>
        ) : undefined}
      />
      <div className="space-y-4 p-4 lg:p-6">
        <MetricStrip metrics={[
          { label: "Vendor Services", value: String(services.data?.length ?? 0) },
          { label: "Service Accounts", value: String(accounts.data?.length ?? 0) },
          { label: "Linked Subscriptions", value: String(
            (subscriptions.data ?? []).filter((s) => s.service_account).length,
          ) },
          { label: "Needs Assignment", value: String(
            (subscriptions.data ?? []).filter((s) => !s.service_account).length,
          ), note: "Assign existing records as needed" },
        ]} />

        {editor?.kind === "service" ? (
          <Popup title={selectedService ? `Edit Service · ${selectedService.name}` : "Add Vendor Service"}
            onClose={() => setEditor(null)}>
            <form className="grid gap-4 p-4 sm:grid-cols-2" onSubmit={submitService}>
              <label className="block"><span className="erp-label">Vendor</span>
                <select name="vendor" className="erp-field" required
                  defaultValue={selectedService?.vendor ?? ""} disabled={Boolean(selectedService?.id)}>
                  <option value="">Select vendor</option>
                  {(vendors.data ?? []).filter((v) => v.status === "ACTIVE" || v.id === selectedService?.vendor)
                    .map((v) => <option key={v.id} value={v.id}>{v.name}</option>)}
                </select>
              </label>
              <label><span className="erp-label">Service Code</span>
                <input className="erp-field" name="code" required maxLength={40}
                  placeholder="CHATGPT" defaultValue={selectedService?.code} />
              </label>
              <label><span className="erp-label">Service Name</span>
                <input className="erp-field" name="name" required
                  placeholder="ChatGPT" defaultValue={selectedService?.name} />
              </label>
              <label><span className="erp-label">Service Category</span>
                <select className="erp-field" name="service_type" defaultValue={selectedService?.service_type ?? "SAAS"}>
                  {serviceTypes.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                </select>
              </label>
              <label className="sm:col-span-2"><span className="erp-label">Description</span>
                <textarea className="erp-field" name="description" rows={2} defaultValue={selectedService?.description} />
              </label>
              <input type="hidden" name="status" value={selectedService?.status ?? "ACTIVE"} />
              <div className="flex justify-end sm:col-span-2">
                <button className="erp-button erp-button-primary" disabled={busy} type="submit">
                  {busy ? "Saving..." : "Save Service"}
                </button>
              </div>
            </form>
          </Popup>
        ) : null}

        {editor?.kind === "account" ? (
          <Popup title={selectedAccount ? `Edit Account · ${selectedAccount.alias}` : "Add Service Account"}
            onClose={() => setEditor(null)}>
            <form className="grid gap-4 p-4 sm:grid-cols-2" onSubmit={submitAccount}>
              <label><span className="erp-label">Vendor Service</span>
                <select className="erp-field" name="service" required
                  defaultValue={selectedAccount?.service ?? ""} disabled={Boolean(selectedAccount?.id)}>
                  <option value="">Select service</option>
                  {(services.data ?? []).filter((s) => s.status === "ACTIVE" || s.id === selectedAccount?.service)
                    .map((s) => (
                      <option key={s.id} value={s.id}>{s.vendor_name} · {s.name}</option>
                    ))}
                </select>
              </label>
              <label><span className="erp-label">Account Alias</span>
                <input className="erp-field" name="alias" required maxLength={120}
                  placeholder="Rizwan-01" defaultValue={selectedAccount?.alias} />
              </label>
              <label><span className="erp-label">Non-sensitive Reference (optional)</span>
                <input className="erp-field" name="reference" maxLength={180}
                  placeholder="Internal label only" defaultValue={selectedAccount?.reference} />
              </label>
              <label><span className="erp-label">Notes</span>
                <input className="erp-field" name="notes" defaultValue={selectedAccount?.notes} />
              </label>
              <input type="hidden" name="status" value={selectedAccount?.status ?? "ACTIVE"} />
              <p className="sm:col-span-2 text-[11px] text-[var(--color-text-muted)]">
                A permanent account code is assigned automatically. Never paste passwords, tokens or full payment card details into these fields.
              </p>
              <div className="flex justify-end sm:col-span-2">
                <button className="erp-button erp-button-primary" disabled={busy} type="submit">
                  {busy ? "Saving..." : "Save Account"}
                </button>
              </div>
            </form>
          </Popup>
        ) : null}

        {error ? <ErrorState message={problem(error)} /> : null}
        <div className="flex flex-wrap items-center justify-between gap-3 border border-[var(--color-border)] bg-white p-3">
          <div className="flex items-center gap-1">
            <button type="button" onClick={() => { setTab("services"); setEditor(null); setServiceFilter(""); }}
              className={`erp-button !min-h-8 ${tab === "services" ? "erp-button-primary" : ""}`}>
              <Layers3 size={14} /> Services
            </button>
            <button type="button" onClick={() => { setTab("accounts"); setEditor(null); }}
              className={`erp-button !min-h-8 ${tab === "accounts" ? "erp-button-primary" : ""}`}>
              <UsersRound size={14} /> Accounts
            </button>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <label className="flex items-center gap-2 border border-[var(--color-border)] px-2">
              <Search size={13} className="text-[var(--color-text-muted)]" />
              <input type="search" className="h-8 w-40 bg-transparent text-xs outline-none"
                placeholder="Search..." value={search} onChange={(e) => setSearch(e.target.value)} />
            </label>
            <select className="erp-field !h-8 !w-auto text-xs" aria-label="Filter vendor"
              value={vendorFilter} onChange={(e) => { setVendorFilter(e.target.value); setServiceFilter(""); }}>
              <option value="">All vendors</option>
              {(vendors.data ?? []).map((v) => <option key={v.id} value={v.id}>{v.name}</option>)}
            </select>
            {tab === "accounts" ? (
              <select className="erp-field !h-8 !w-auto text-xs" aria-label="Filter service"
                value={serviceFilter} onChange={(e) => setServiceFilter(e.target.value)}>
                <option value="">All services</option>
                {(services.data ?? []).filter((s) => !vendorFilter || s.vendor === vendorFilter)
                  .map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            ) : null}
          </div>
        </div>
        {services.isLoading || accounts.isLoading || vendors.isLoading || subscriptions.isLoading
          ? <LoadingState label="Loading service catalogue..." />
          : services.error || accounts.error || vendors.error || subscriptions.error
            ? <ErrorState message={problem(
                services.error ?? accounts.error ?? vendors.error ?? subscriptions.error,
              )} />
            : tab === "services"
              ? <DataTable columns={serviceColumns} rows={serviceRows} rowKey={(item) => item.id}
                  emptyTitle="No vendor services" emptyDescription="Add ChatGPT, VPS, domains, API services or other vendor offerings." />
              : <DataTable columns={accountColumns} rows={accountRows} rowKey={(item) => item.id}
                  emptyTitle="No service accounts" emptyDescription="Add identities such as Rizwan-01 or Shahbaj-01 under an existing service." />}
        <div className="flex items-center gap-2 border border-[var(--color-border)] bg-white p-3 text-xs text-[var(--color-text-muted)]">
          <Boxes size={14} />
          Existing subscriptions without an account are preserved. Assign them from the Subscriptions page when ready.
        </div>
      </div>
    </>
  );
}
