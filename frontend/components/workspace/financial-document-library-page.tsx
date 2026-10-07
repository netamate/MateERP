"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CalendarDays,
  Download,
  Eye,
  FileArchive,
  FileText,
  FolderOpen,
  Image as ImageIcon,
  Plus,
  Search,
  ShieldCheck,
  UploadCloud,
  X,
} from "lucide-react";
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
  type Expense,
  type ServiceAccount,
  type SessionPayload,
  type Subscription,
  type Vendor,
  type VendorService,
} from "@/lib/api";

type FinanceDocument = {
  id: string;
  document_type: string;
  document_date: string;
  reference: string;
  original_name: string;
  standardized_name: string;
  vendor: string | null;
  vendor_name: string | null;
  service: string | null;
  service_name: string | null;
  service_account: string | null;
  account_alias: string | null;
  account_code: string | null;
  subscription: string | null;
  subscription_name: string | null;
  subscription_code: string | null;
  expense: string | null;
  income: string | null;
  reimbursement: string | null;
  transfer: string | null;
  founder_funding: string | null;
  uploaded_by_email: string;
  mime_type: string | null;
  size_bytes: number | null;
  checksum_sha256: string | null;
  folder_year: number;
  folder_month: number;
  content_url: string;
  created_at: string;
};

type ApprovalAction = {
  id: string;
  object_type: string;
  object_id: string;
  action: string;
  actor_email: string;
  comment: string;
  created_at: string;
};

const monthNames = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

const documentTypes = [
  ["INVOICE", "Invoice"],
  ["RECEIPT", "Receipt"],
  ["BILL", "Bill"],
  ["STATEMENT", "Statement"],
  ["PAYSLIP", "Payslip"],
  ["PAYMENT_CONFIRMATION", "Payment confirmation"],
  ["CREDIT_NOTE", "Credit note"],
  ["OTHER", "Other"],
] as const;

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

function shortDate(value: string) {
  return new Intl.DateTimeFormat("en-US", {
    year: "numeric",
    month: "short",
    day: "2-digit",
  }).format(new Date(`${value}T00:00:00`));
}

function timestamp(value: string) {
  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function bytes(value: number | null) {
  if (value === null) return "—";
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function token(value: string | null | undefined, fallback = "") {
  const compact = String(value ?? "").trim().replaceAll(" ", "-");
  const safe = compact.replace(/[^A-Za-z0-9.-]+/g, "-").replace(/-{2,}/g, "-");
  return safe.replace(/^[-._]+|[-._]+$/g, "") || fallback;
}

function Overlay({
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
    <div className="fixed inset-0 z-[90] flex items-start justify-center overflow-y-auto bg-black/55 px-3 py-[5vh]">
      <section className={`w-full border border-[var(--color-border-strong)] bg-white shadow-2xl ${wide ? "max-w-6xl" : "max-w-3xl"}`}>
        <header className="flex items-start justify-between gap-4 border-b border-[var(--color-border)] px-5 py-4">
          <div>
            <h2 className="text-lg font-semibold">{title}</h2>
            <p className="mt-1 text-xs text-[var(--color-text-muted)]">{description}</p>
          </div>
          <button className="erp-button !h-8 !min-h-8 !w-8 !p-0" type="button"
            aria-label="Close" onClick={onClose}><X size={14} /></button>
        </header>
        {children}
      </section>
    </div>
  );
}

function hierarchyLabel(document: FinanceDocument) {
  return [
    document.vendor_name,
    document.service_name,
    document.account_alias,
    document.subscription_name,
  ].filter(Boolean).join(" → ") || "Unassigned";
}

function filenamePreview({
  vendor,
  service,
  account,
  subscription,
  documentType,
  documentDate,
  reference,
}: {
  vendor?: Vendor;
  service?: VendorService;
  account?: ServiceAccount;
  subscription?: Subscription;
  documentType: string;
  documentDate: string;
  reference: string;
}) {
  const parts = [token(vendor?.name, "Unassigned")];
  if (service) parts.push(token(service.name, "Service"));
  if (account) parts.push(token(account.alias, "Account"));
  if (subscription) parts.push(token(subscription.subscription_code, "Subscription"));
  parts.push(token(documentType, "DOCUMENT"));
  parts.push(documentDate || "YYYY-MM-DD");
  parts.push(token(reference, "AUTO-ID"));
  return `${parts.join("_")}.pdf`;
}

export function FinancialDocumentLibraryPage({ session }: { session: SessionPayload }) {
  const entity = activeEntity(session);
  const canView = can(session, "VIEW_FINANCE");
  const canManage = can(session, "MANAGE_FINANCE_DOCUMENTS");
  const queryClient = useQueryClient();

  const [tab, setTab] = useState<"library" | "approvals">("library");
  const [uploadOpen, setUploadOpen] = useState(false);
  const [selected, setSelected] = useState<FinanceDocument | null>(null);
  const [search, setSearch] = useState("");
  const [year, setYear] = useState<number | null>(null);
  const [month, setMonth] = useState<number | null>(null);
  const [vendorFilter, setVendorFilter] = useState("");
  const [serviceFilter, setServiceFilter] = useState("");
  const [accountFilter, setAccountFilter] = useState("");
  const [subscriptionFilter, setSubscriptionFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState("");

  const [uploadVendor, setUploadVendor] = useState("");
  const [uploadService, setUploadService] = useState("");
  const [uploadAccount, setUploadAccount] = useState("");
  const [uploadSubscription, setUploadSubscription] = useState("");
  const [uploadType, setUploadType] = useState("INVOICE");
  const [uploadDate, setUploadDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [uploadReference, setUploadReference] = useState("");

  const documents = useQuery({
    queryKey: ["finance-document-library", entity?.id],
    queryFn: () => request<FinanceDocument[]>("/api/v1/finance/documents/"),
    enabled: Boolean(entity && canView),
  });
  const approvals = useQuery({
    queryKey: ["finance-approvals", entity?.id],
    queryFn: () => request<ApprovalAction[]>("/api/v1/finance/approvals/"),
    enabled: Boolean(entity && canView && tab === "approvals"),
  });
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
  const expenses = useQuery({
    queryKey: ["expenses", entity?.id],
    queryFn: financeApi.expenses,
    enabled: Boolean(entity && canView && uploadOpen),
  });
  const reimbursements = useQuery({
    queryKey: ["reimbursements", entity?.id],
    queryFn: financeApi.reimbursements,
    enabled: Boolean(entity && canView && uploadOpen),
  });

  const upload = useMutation({
    mutationFn: (body: FormData) =>
      request<FinanceDocument>(
        "/api/v1/finance/documents/",
        { method: "POST", body },
        true,
      ),
    onSuccess: async (document) => {
      setUploadOpen(false);
      setSelected(document);
      setUploadReference("");
      await queryClient.invalidateQueries({
        queryKey: ["finance-document-library", entity?.id],
      });
    },
  });

  const folderTree = useMemo(() => {
    const tree = new Map<number, Map<number, number>>();
    for (const document of documents.data ?? []) {
      const months = tree.get(document.folder_year) ?? new Map<number, number>();
      months.set(document.folder_month, (months.get(document.folder_month) ?? 0) + 1);
      tree.set(document.folder_year, months);
    }
    return [...tree.entries()]
      .sort(([a], [b]) => b - a)
      .map(([folderYear, months]) => ({
        year: folderYear,
        months: [...months.entries()].sort(([a], [b]) => b - a),
      }));
  }, [documents.data]);

  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase();
    return (documents.data ?? []).filter((document) => {
      if (year !== null && document.folder_year !== year) return false;
      if (month !== null && document.folder_month !== month) return false;
      if (vendorFilter && document.vendor !== vendorFilter) return false;
      if (serviceFilter && document.service !== serviceFilter) return false;
      if (accountFilter && document.service_account !== accountFilter) return false;
      if (subscriptionFilter && document.subscription !== subscriptionFilter) return false;
      if (typeFilter && document.document_type !== typeFilter) return false;
      if (!term) return true;
      return [
        document.original_name,
        document.standardized_name,
        document.reference,
        document.vendor_name,
        document.service_name,
        document.account_alias,
        document.subscription_name,
        document.subscription_code,
      ].some((value) => String(value ?? "").toLowerCase().includes(term));
    });
  }, [
    documents.data,
    year,
    month,
    vendorFilter,
    serviceFilter,
    accountFilter,
    subscriptionFilter,
    typeFilter,
    search,
  ]);

  const availableFilterServices = (services.data ?? []).filter(
    (item) => !vendorFilter || item.vendor === vendorFilter,
  );
  const availableFilterAccounts = (accounts.data ?? []).filter(
    (item) => (!vendorFilter || item.vendor_id === vendorFilter)
      && (!serviceFilter || item.service === serviceFilter),
  );
  const availableFilterSubscriptions = (subscriptions.data ?? []).filter(
    (item) => (!vendorFilter || item.vendor === vendorFilter)
      && (!serviceFilter || item.service === serviceFilter)
      && (!accountFilter || item.service_account === accountFilter),
  );

  const uploadServices = (services.data ?? []).filter(
    (item) => item.status === "ACTIVE" && (!uploadVendor || item.vendor === uploadVendor),
  );
  const uploadAccounts = (accounts.data ?? []).filter(
    (item) => item.status === "ACTIVE" && (!uploadService || item.service === uploadService),
  );
  const uploadSubscriptions = (subscriptions.data ?? []).filter(
    (item) => item.status === "ACTIVE"
      && (!uploadVendor || item.vendor === uploadVendor)
      && (!uploadService || item.service === uploadService)
      && (!uploadAccount || item.service_account === uploadAccount),
  );

  const previewVendor = (vendors.data ?? []).find((item) => item.id === uploadVendor);
  const previewService = (services.data ?? []).find((item) => item.id === uploadService);
  const previewAccount = (accounts.data ?? []).find((item) => item.id === uploadAccount);
  const previewSubscription = (subscriptions.data ?? []).find(
    (item) => item.id === uploadSubscription,
  );
  const proposedName = filenamePreview({
    vendor: previewVendor,
    service: previewService,
    account: previewAccount,
    subscription: previewSubscription,
    documentType: uploadType,
    documentDate: uploadDate,
    reference: uploadReference,
  });

  if (!entity) {
    return <PermissionNotice>Select a legal entity to use the document library.</PermissionNotice>;
  }
  if (!canView) {
    return <PermissionNotice>You do not have permission to view finance documents.</PermissionNotice>;
  }

  function clearFilters() {
    setYear(null);
    setMonth(null);
    setVendorFilter("");
    setServiceFilter("");
    setAccountFilter("");
    setSubscriptionFilter("");
    setTypeFilter("");
    setSearch("");
  }

  function submitUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const body = new FormData(event.currentTarget);
    if (uploadVendor) body.set("vendor", uploadVendor);
    else body.delete("vendor");
    if (uploadService) body.set("service", uploadService);
    else body.delete("service");
    if (uploadAccount) body.set("service_account", uploadAccount);
    else body.delete("service_account");
    if (uploadSubscription) body.set("subscription", uploadSubscription);
    else body.delete("subscription");

    const financeTarget = String(body.get("finance_target") ?? "");
    body.delete("finance_target");
    const [targetType, targetId] = financeTarget.split(":");
    if (targetType && targetId) body.set(targetType, targetId);
    upload.mutate(body);
  }

  const columns: Array<TableColumn<FinanceDocument>> = [
    {
      key: "file",
      label: "Document",
      render: (document) => (
        <button className="text-left" type="button" onClick={() => setSelected(document)}>
          <div className="flex items-center gap-2 font-semibold">
            {document.mime_type === "application/pdf"
              ? <FileText size={15} />
              : <ImageIcon size={15} />}
            <span>{document.standardized_name}</span>
          </div>
          <div className="mt-1 text-[11px] text-[var(--color-text-muted)]">
            Original: {document.original_name}
          </div>
        </button>
      ),
    },
    { key: "date", label: "Document Date", render: (row) => shortDate(row.document_date) },
    {
      key: "hierarchy",
      label: "Linked To",
      render: (row) => (
        <div className="max-w-72">
          <div className="text-xs">{hierarchyLabel(row)}</div>
          {row.reference ? (
            <div className="mt-0.5 text-[11px] text-[var(--color-text-muted)]">
              Ref: {row.reference}
            </div>
          ) : null}
        </div>
      ),
    },
    { key: "type", label: "Type", render: (row) => <StatusBadge value={row.document_type} /> },
    { key: "size", label: "Size", numeric: true, render: (row) => bytes(row.size_bytes) },
    {
      key: "actions",
      label: "Actions",
      render: (row) => (
        <div className="flex gap-1">
          <button className="erp-button !h-7 !min-h-7 text-[11px]" type="button"
            onClick={() => setSelected(row)}><Eye size={12} /> View</button>
          <a className="erp-button !h-7 !min-h-7 text-[11px]"
            href={`${row.content_url}?disposition=attachment&name=standard`}>
            <Download size={12} /> Download
          </a>
        </div>
      ),
    },
  ];

  const approvalColumns: Array<TableColumn<ApprovalAction>> = [
    { key: "date", label: "Timestamp", render: (row) => timestamp(row.created_at) },
    { key: "object", label: "Object", render: (row) => row.object_type },
    { key: "action", label: "Action", render: (row) => <StatusBadge value={row.action} /> },
    { key: "actor", label: "Actor", render: (row) => row.actor_email },
    { key: "comment", label: "Comment", render: (row) => row.comment || "—" },
  ];

  const unassigned = (documents.data ?? []).filter((item) =>
    !item.vendor && !item.subscription && !item.expense && !item.income
    && !item.reimbursement && !item.transfer && !item.founder_funding
  ).length;

  return (
    <>
      <PageHeader
        eyebrow="Finance"
        title="Financial Document Library"
        description="Store invoices, receipts, statements and payslips with canonical filenames, virtual folders, private preview and traceable downloads."
        actions={canManage ? (
          <button className="erp-button erp-button-primary" type="button"
            onClick={() => setUploadOpen(true)}>
            <Plus size={14} /> Upload Document
          </button>
        ) : undefined}
      />

      <MetricStrip metrics={[
        { label: "Documents", value: String(documents.data?.length ?? 0) },
        { label: "PDFs", value: String((documents.data ?? []).filter((item) => item.mime_type === "application/pdf").length) },
        { label: "Virtual Years", value: String(folderTree.length) },
        { label: "Unassigned", value: String(unassigned), note: unassigned ? "Ready for later assignment" : "Everything linked" },
      ]} />

      <div className="p-4 lg:p-6">
        <div className="mb-3 flex flex-wrap items-center gap-2 border border-[var(--color-border)] bg-white p-2.5">
          <button className={`erp-button !h-8 !min-h-8 ${tab === "library" ? "erp-button-primary" : ""}`}
            type="button" onClick={() => setTab("library")}>
            <FileArchive size={13} /> Library
          </button>
          <button className={`erp-button !h-8 !min-h-8 ${tab === "approvals" ? "erp-button-primary" : ""}`}
            type="button" onClick={() => setTab("approvals")}>
            <ShieldCheck size={13} /> Approval History
          </button>
        </div>

        {tab === "library" ? (
          documents.isLoading || vendors.isLoading || services.isLoading
            || accounts.isLoading || subscriptions.isLoading ? (
              <LoadingState label="Loading financial document library..." />
            ) : documents.error || vendors.error || services.error
              || accounts.error || subscriptions.error ? (
                <ErrorState message={errorMessage(
                  documents.error ?? vendors.error ?? services.error
                  ?? accounts.error ?? subscriptions.error,
                )} />
              ) : (
                <div className="grid gap-3 xl:grid-cols-[220px_minmax(0,1fr)]">
                  <aside className="border border-[var(--color-border)] bg-white">
                    <div className="flex items-center gap-2 border-b border-[var(--color-border)] px-3 py-3 text-xs font-semibold">
                      <FolderOpen size={14} /> Virtual Folders
                    </div>
                    <button className={`flex w-full items-center justify-between px-3 py-2 text-left text-xs ${year === null ? "bg-[var(--color-surface-subtle)] font-semibold" : ""}`}
                      type="button" onClick={() => { setYear(null); setMonth(null); }}>
                      <span>All Documents</span><span>{documents.data?.length ?? 0}</span>
                    </button>
                    {folderTree.map((folder) => (
                      <div key={folder.year} className="border-t border-[var(--color-border-soft)]">
                        <button className={`flex w-full items-center justify-between px-3 py-2 text-xs ${year === folder.year && month === null ? "bg-[var(--color-surface-subtle)] font-semibold" : ""}`}
                          type="button" onClick={() => { setYear(folder.year); setMonth(null); }}>
                          <span className="flex items-center gap-2"><CalendarDays size={13} /> {folder.year}</span>
                          <span>{folder.months.reduce((sum, [, count]) => sum + count, 0)}</span>
                        </button>
                        {folder.months.map(([folderMonth, count]) => (
                          <button key={folderMonth}
                            className={`flex w-full items-center justify-between py-1.5 pl-8 pr-3 text-[11px] ${year === folder.year && month === folderMonth ? "bg-[#eef4ff] font-semibold" : "text-[var(--color-text-muted)]"}`}
                            type="button"
                            onClick={() => { setYear(folder.year); setMonth(folderMonth); }}>
                            <span>{monthNames[folderMonth - 1]}</span><span>{count}</span>
                          </button>
                        ))}
                      </div>
                    ))}
                  </aside>

                  <section className="min-w-0 space-y-3">
                    <div className="border border-[var(--color-border)] bg-white p-3">
                      <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-6">
                        <label className="flex items-center gap-2 border border-[var(--color-border)] px-2 xl:col-span-2">
                          <Search size={13} className="shrink-0 text-[var(--color-text-muted)]" />
                          <input className="h-9 min-w-0 flex-1 bg-transparent text-xs outline-none"
                            type="search" placeholder="Search file, vendor, account, reference..."
                            value={search} onChange={(event) => setSearch(event.target.value)} />
                        </label>
                        <select className="erp-field !h-9 text-xs" value={vendorFilter}
                          onChange={(event) => {
                            setVendorFilter(event.target.value);
                            setServiceFilter("");
                            setAccountFilter("");
                            setSubscriptionFilter("");
                          }}>
                          <option value="">All vendors</option>
                          {(vendors.data ?? []).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                        </select>
                        <select className="erp-field !h-9 text-xs" value={serviceFilter}
                          onChange={(event) => {
                            setServiceFilter(event.target.value);
                            setAccountFilter("");
                            setSubscriptionFilter("");
                          }}>
                          <option value="">All services</option>
                          {availableFilterServices.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                        </select>
                        <select className="erp-field !h-9 text-xs" value={accountFilter}
                          onChange={(event) => {
                            setAccountFilter(event.target.value);
                            setSubscriptionFilter("");
                          }}>
                          <option value="">All accounts</option>
                          {availableFilterAccounts.map((item) => <option key={item.id} value={item.id}>{item.alias}</option>)}
                        </select>
                        <select className="erp-field !h-9 text-xs" value={typeFilter}
                          onChange={(event) => setTypeFilter(event.target.value)}>
                          <option value="">All types</option>
                          {documentTypes.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                        </select>
                      </div>
                      <div className="mt-2 flex flex-wrap items-center gap-2">
                        <select className="erp-field !h-8 !w-auto text-xs" value={subscriptionFilter}
                          onChange={(event) => setSubscriptionFilter(event.target.value)}>
                          <option value="">All subscriptions</option>
                          {availableFilterSubscriptions.map((item) => (
                            <option key={item.id} value={item.id}>
                              {item.name} · {item.subscription_code}
                            </option>
                          ))}
                        </select>
                        <span className="text-[11px] text-[var(--color-text-muted)]">
                          Showing {filtered.length} document{filtered.length === 1 ? "" : "s"}
                        </span>
                        <button className="erp-button ml-auto !h-8 !min-h-8 text-[11px]" type="button"
                          onClick={clearFilters}>Clear filters</button>
                      </div>
                    </div>
                    <DataTable columns={columns} rows={filtered} rowKey={(row) => row.id}
                      emptyTitle="No matching documents"
                      emptyDescription="Upload a document or clear the current virtual folder and filters." />
                  </section>
                </div>
              )
        ) : approvals.isLoading ? (
          <LoadingState label="Loading approval history..." />
        ) : approvals.error ? (
          <ErrorState message={errorMessage(approvals.error)} />
        ) : (
          <DataTable columns={approvalColumns} rows={approvals.data ?? []}
            rowKey={(row) => row.id}
            emptyTitle="No approval actions"
            emptyDescription="Expense and reimbursement workflow actions will appear here." />
        )}
      </div>

      {uploadOpen ? (
        <Overlay title="Upload Financial Document"
          description="Choose optional hierarchy links. MateERP generates the canonical filename and virtual folder from the document date."
          onClose={() => setUploadOpen(false)}>
          <form onSubmit={submitUpload}>
            <div className="grid gap-4 p-5 sm:grid-cols-2">
              <label><span className="erp-label">Document Type</span>
                <select className="erp-field" name="document_type" value={uploadType}
                  onChange={(event) => setUploadType(event.target.value)}>
                  {documentTypes.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                </select>
              </label>
              <label><span className="erp-label">Document Date</span>
                <input className="erp-field" type="date" name="document_date" required
                  value={uploadDate} onChange={(event) => setUploadDate(event.target.value)} />
              </label>
              <label><span className="erp-label">Vendor</span>
                <select className="erp-field" value={uploadVendor}
                  onChange={(event) => {
                    setUploadVendor(event.target.value);
                    setUploadService("");
                    setUploadAccount("");
                    setUploadSubscription("");
                  }}>
                  <option value="">Unassigned / no vendor</option>
                  {(vendors.data ?? []).filter((item) => item.status === "ACTIVE")
                    .map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                </select>
              </label>
              <label><span className="erp-label">Service</span>
                <select className="erp-field" value={uploadService} disabled={!uploadVendor}
                  onChange={(event) => {
                    setUploadService(event.target.value);
                    setUploadAccount("");
                    setUploadSubscription("");
                  }}>
                  <option value="">No service</option>
                  {uploadServices.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                </select>
              </label>
              <label><span className="erp-label">Account</span>
                <select className="erp-field" value={uploadAccount} disabled={!uploadService}
                  onChange={(event) => {
                    setUploadAccount(event.target.value);
                    setUploadSubscription("");
                  }}>
                  <option value="">No account</option>
                  {uploadAccounts.map((item) => <option key={item.id} value={item.id}>{item.alias}</option>)}
                </select>
              </label>
              <label><span className="erp-label">Subscription</span>
                <select className="erp-field" value={uploadSubscription}
                  disabled={!uploadVendor}
                  onChange={(event) => {
                    const id = event.target.value;
                    setUploadSubscription(id);
                    const item = (subscriptions.data ?? []).find((subscription) => subscription.id === id);
                    if (item) {
                      setUploadVendor(item.vendor ?? "");
                      setUploadService(item.service ?? "");
                      setUploadAccount(item.service_account ?? "");
                    }
                  }}>
                  <option value="">No subscription</option>
                  {uploadSubscriptions.map((item) => (
                    <option key={item.id} value={item.id}>{item.name} · {item.subscription_code}</option>
                  ))}
                </select>
              </label>
              <label><span className="erp-label">Invoice / Reference No. (optional)</span>
                <input className="erp-field" name="reference" value={uploadReference}
                  maxLength={180} placeholder="INV-12345"
                  onChange={(event) => setUploadReference(event.target.value)} />
              </label>
              <label><span className="erp-label">Finance Record (optional)</span>
                <select className="erp-field" name="finance_target" defaultValue="">
                  <option value="">No finance transaction link</option>
                  {(expenses.data ?? []).map((item: Expense) => (
                    <option key={item.id} value={`expense:${item.id}`}>
                      Expense · {item.description}
                    </option>
                  ))}
                  {(reimbursements.data ?? []).map((item) => (
                    <option key={item.id} value={`reimbursement:${item.id}`}>
                      Reimbursement · {item.description}
                    </option>
                  ))}
                </select>
              </label>
              <label className="sm:col-span-2"><span className="erp-label">PDF / Image</span>
                <input className="erp-field" type="file" name="file" required
                  accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg" />
                <span className="mt-1 block text-[11px] text-[var(--color-text-muted)]">
                  PDF, PNG or JPEG · maximum 25 MB. Exact duplicate files are blocked.
                </span>
              </label>

              <div className="border border-[var(--color-border)] bg-[var(--color-surface-subtle)] p-3 sm:col-span-2">
                <div className="text-[10px] font-bold uppercase tracking-[0.08em] text-[var(--color-text-muted)]">
                  Canonical filename preview
                </div>
                <code className="mt-1 block break-all text-xs">{proposedName}</code>
                <p className="mt-2 text-[11px] text-[var(--color-text-muted)]">
                  The server verifies the hierarchy and generates the final filename. Original filename is preserved separately.
                </p>
              </div>
              {upload.error ? <div className="sm:col-span-2"><ErrorState message={errorMessage(upload.error)} /></div> : null}
            </div>
            <div className="flex justify-end gap-2 border-t border-[var(--color-border)] bg-[var(--color-surface-subtle)] px-5 py-3">
              <button className="erp-button" type="button" onClick={() => setUploadOpen(false)}>Cancel</button>
              <button className="erp-button erp-button-primary" disabled={upload.isPending} type="submit">
                <UploadCloud size={14} /> {upload.isPending ? "Uploading..." : "Upload to Library"}
              </button>
            </div>
          </form>
        </Overlay>
      ) : null}

      {selected ? (
        <Overlay wide title={selected.standardized_name}
          description={`${hierarchyLabel(selected)} · ${shortDate(selected.document_date)} · ${bytes(selected.size_bytes)}`}
          onClose={() => setSelected(null)}>
          <div className="grid min-h-[70vh] lg:grid-cols-[minmax(0,1fr)_300px]">
            <div className="min-h-[65vh] border-r border-[var(--color-border)] bg-[#eef1f5] p-3">
              {selected.mime_type === "application/pdf" ? (
                <iframe title={selected.standardized_name} className="h-[68vh] w-full border border-[var(--color-border)] bg-white"
                  src={selected.content_url} />
              ) : selected.mime_type?.startsWith("image/") ? (
                <div className="grid h-[68vh] place-items-center overflow-auto border border-[var(--color-border)] bg-white p-4">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={selected.content_url} alt={selected.standardized_name} className="max-h-full max-w-full" />
                </div>
              ) : (
                <div className="grid h-[68vh] place-items-center bg-white text-sm text-[var(--color-text-muted)]">
                  Preview is not available for this file type.
                </div>
              )}
            </div>
            <aside className="space-y-4 p-4 text-xs">
              <div>
                <div className="erp-label">Document Type</div>
                <div className="mt-1"><StatusBadge value={selected.document_type} /></div>
              </div>
              <div><div className="erp-label">Document Date</div><div className="mt-1 font-semibold">{shortDate(selected.document_date)}</div></div>
              <div><div className="erp-label">Virtual Folder</div><div className="mt-1 font-semibold">{selected.folder_year} / {monthNames[selected.folder_month - 1]}</div></div>
              <div><div className="erp-label">Linked Hierarchy</div><div className="mt-1 leading-relaxed">{hierarchyLabel(selected)}</div></div>
              <div><div className="erp-label">Reference</div><div className="mt-1">{selected.reference || "—"}</div></div>
              <div><div className="erp-label">Original Filename</div><div className="mt-1 break-all">{selected.original_name}</div></div>
              <div><div className="erp-label">SHA-256</div><code className="mt-1 block break-all text-[10px]">{selected.checksum_sha256 || "—"}</code></div>
              <div><div className="erp-label">Uploaded By</div><div className="mt-1">{selected.uploaded_by_email}</div></div>
              <div className="grid gap-2 border-t border-[var(--color-border)] pt-4">
                <a className="erp-button erp-button-primary justify-center"
                  href={`${selected.content_url}?disposition=attachment&name=standard`}>
                  <Download size={13} /> Download Standardized
                </a>
                <a className="erp-button justify-center"
                  href={`${selected.content_url}?disposition=attachment&name=original`}>
                  <Download size={13} /> Download Original
                </a>
              </div>
            </aside>
          </div>
        </Overlay>
      ) : null}
    </>
  );
}
