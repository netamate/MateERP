"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CheckCircle2,
  Pencil,
  Play,
  PlugZap,
  Plus,
  RefreshCw,
  Workflow,
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
  type SessionPayload,
  type Subscription,
} from "@/lib/api";
import {
  automationApi,
  type AutomationPolicy,
  type AutomationRun,
  type VendorIntegration,
  type VendorSyncRun,
} from "@/lib/phase8-api";

type IntegrationDraft = {
  id?: string;
  name: string;
  vendor: string;
  subscription: string;
  endpoint_url: string;
  auth_type: "NONE" | "BEARER" | "API_KEY_HEADER" | "BASIC";
  auth_username: string;
  secret: string;
  api_key_header: string;
  custom_headers: string;
  cost_json_path: string;
  usage_quantity_json_path: string;
  currency_json_path: string;
  usage_unit_json_path: string;
  timeout_seconds: number;
  auto_create_period: boolean;
  enabled: boolean;
  secret_configured: boolean;
};

type PolicyEditor = {
  policy: AutomationPolicy;
  createOverride: boolean;
} | null;

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

function timestamp(value: string | null | undefined) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function money(value: string | number | null | undefined, currency: string) {
  const amount = Number(value ?? 0);
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(Number.isFinite(amount) ? amount : 0);
}

function blankIntegration(payg: Subscription[]): IntegrationDraft {
  const subscription = payg[0];
  return {
    name: "",
    vendor: subscription?.vendor ?? "",
    subscription: subscription?.id ?? "",
    endpoint_url: "",
    auth_type: "NONE",
    auth_username: "",
    secret: "",
    api_key_header: "X-API-Key",
    custom_headers: "{}",
    cost_json_path: "",
    usage_quantity_json_path: "",
    currency_json_path: "",
    usage_unit_json_path: "",
    timeout_seconds: 15,
    auto_create_period: true,
    enabled: true,
    secret_configured: false,
  };
}

function editIntegration(row: VendorIntegration): IntegrationDraft {
  return {
    id: row.id,
    name: row.name,
    vendor: row.vendor,
    subscription: row.subscription,
    endpoint_url: row.endpoint_url,
    auth_type: row.auth_type,
    auth_username: row.auth_username,
    secret: "",
    api_key_header: row.api_key_header,
    custom_headers: JSON.stringify(row.custom_headers ?? {}, null, 2),
    cost_json_path: row.cost_json_path,
    usage_quantity_json_path: row.usage_quantity_json_path,
    currency_json_path: row.currency_json_path,
    usage_unit_json_path: row.usage_unit_json_path,
    timeout_seconds: row.timeout_seconds,
    auto_create_period: row.auto_create_period,
    enabled: row.enabled,
    secret_configured: row.secret_configured,
  };
}

function draftFingerprint(draft: IntegrationDraft) {
  return JSON.stringify({
    ...draft,
    secret_configured: undefined,
  });
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
    <div className="fixed inset-0 z-[90] flex items-start justify-center overflow-y-auto bg-black/55 px-3 py-[5vh]">
      <section className="w-full max-w-5xl border border-[var(--color-border-strong)] bg-white shadow-2xl">
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

export function AutomationIntegrationsPage({ session }: { session: SessionPayload }) {
  const entity = activeEntity(session);
  const allowed = Boolean(entity) && can(session, "VIEW_AUTOMATION");
  const manageAllowed = Boolean(entity) && can(session, "MANAGE_AUTOMATION");
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<"integrations" | "automation" | "history">("integrations");
  const [integrationDraft, setIntegrationDraft] = useState<IntegrationDraft | null>(null);
  const [verifiedFingerprint, setVerifiedFingerprint] = useState("");
  const [testResult, setTestResult] = useState<{
    cost_amount: string;
    usage_quantity: string | null;
    currency: string;
    usage_unit: string;
  } | null>(null);
  const [policyEditor, setPolicyEditor] = useState<PolicyEditor>(null);

  const overview = useQuery({
    queryKey: ["automation-overview", entity?.id],
    queryFn: automationApi.overview,
    enabled: allowed,
  });
  const integrations = useQuery({
    queryKey: ["vendor-integrations", entity?.id],
    queryFn: automationApi.integrations,
    enabled: allowed,
  });
  const policies = useQuery({
    queryKey: ["automation-policies", entity?.id],
    queryFn: automationApi.policies,
    enabled: allowed,
  });
  const automationRuns = useQuery({
    queryKey: ["automation-runs", entity?.id],
    queryFn: automationApi.runs,
    enabled: allowed,
  });
  const syncRuns = useQuery({
    queryKey: ["vendor-sync-runs", entity?.id],
    queryFn: automationApi.syncRuns,
    enabled: allowed,
  });
  const vendors = useQuery({
    queryKey: ["vendors", entity?.id],
    queryFn: financeApi.vendors,
    enabled: allowed,
  });
  const subscriptions = useQuery({
    queryKey: ["subscriptions", entity?.id],
    queryFn: operationsApi.subscriptions,
    enabled: allowed,
  });

  const refresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["automation-overview"] }),
      queryClient.invalidateQueries({ queryKey: ["vendor-integrations"] }),
      queryClient.invalidateQueries({ queryKey: ["automation-policies"] }),
      queryClient.invalidateQueries({ queryKey: ["automation-runs"] }),
      queryClient.invalidateQueries({ queryKey: ["vendor-sync-runs"] }),
      queryClient.invalidateQueries({ queryKey: ["billing-periods"] }),
      queryClient.invalidateQueries({ queryKey: ["billing-summary"] }),
    ]);
  };

  const createIntegration = useMutation({
    mutationFn: automationApi.createIntegration,
    onSuccess: async () => {
      setIntegrationDraft(null);
      setVerifiedFingerprint("");
      setTestResult(null);
      await refresh();
    },
  });
  const updateIntegration = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Record<string, unknown> }) =>
      automationApi.updateIntegration(id, body),
    onSuccess: async () => {
      setIntegrationDraft(null);
      setVerifiedFingerprint("");
      setTestResult(null);
      await refresh();
    },
  });
  const testIntegration = useMutation({
    mutationFn: automationApi.testIntegration,
    onSuccess: (result) => {
      if (integrationDraft) setVerifiedFingerprint(draftFingerprint(integrationDraft));
      setTestResult(result);
    },
  });
  const syncIntegration = useMutation({
    mutationFn: automationApi.syncIntegration,
    onSuccess: refresh,
  });
  const runPolicy = useMutation({
    mutationFn: automationApi.runPolicy,
    onSuccess: refresh,
  });
  const updatePolicy = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Record<string, unknown> }) =>
      automationApi.updatePolicy(id, body),
    onSuccess: async () => {
      setPolicyEditor(null);
      await refresh();
    },
  });
  const createPolicy = useMutation({
    mutationFn: automationApi.createPolicy,
    onSuccess: async () => {
      setPolicyEditor(null);
      await refresh();
    },
  });

  const paygSubscriptions = useMemo(
    () =>
      (subscriptions.data ?? []).filter(
        (item) => item.status === "ACTIVE" && item.billing_mode === "PAYG",
      ),
    [subscriptions.data],
  );

  if (!entity) {
    return <PermissionNotice>Select a legal entity to manage automation.</PermissionNotice>;
  }
  if (!allowed) {
    return <PermissionNotice>You do not have permission to view automation.</PermissionNotice>;
  }

  const loading =
    overview.isLoading
    || integrations.isLoading
    || policies.isLoading
    || automationRuns.isLoading
    || syncRuns.isLoading
    || vendors.isLoading
    || subscriptions.isLoading;
  const loadError =
    overview.error
    ?? integrations.error
    ?? policies.error
    ?? automationRuns.error
    ?? syncRuns.error
    ?? vendors.error
    ?? subscriptions.error;
  if (loading) return <LoadingState label="Loading automation and integrations..." />;
  if (loadError) return <ErrorState message={errorMessage(loadError)} />;

  const integrationColumns: Array<TableColumn<VendorIntegration>> = [
    {
      key: "integration",
      label: "Integration",
      render: (row) => (
        <div>
          <div className="font-semibold">{row.name}</div>
          <div className="mt-0.5 text-[11px] text-[var(--color-text-muted)]">
            {row.vendor_name} · {row.subscription_name}
          </div>
          <div className="mt-0.5 font-mono text-[10px] text-[var(--color-text-muted)]">
            {row.subscription_code}
          </div>
        </div>
      ),
    },
    {
      key: "endpoint",
      label: "Endpoint",
      render: (row) => {
        try {
          return new URL(row.endpoint_url).hostname;
        } catch {
          return row.endpoint_url;
        }
      },
    },
    { key: "auth", label: "Auth", render: (row) => <StatusBadge value={row.auth_type} /> },
    {
      key: "test",
      label: "Test",
      render: (row) => (
        <div>
          <StatusBadge value={row.last_test_status} />
          <div className="mt-1 text-[10px] text-[var(--color-text-muted)]">
            {timestamp(row.last_test_at)}
          </div>
        </div>
      ),
    },
    {
      key: "sync",
      label: "Last Sync",
      render: (row) => (
        <div>
          <StatusBadge value={row.last_sync_status} />
          <div className="mt-1 text-[10px] text-[var(--color-text-muted)]">
            {timestamp(row.last_sync_at)}
          </div>
          {row.last_sync_error ? (
            <div className="mt-1 max-w-xs text-[10px] text-[var(--color-danger)]">
              {row.last_sync_error}
            </div>
          ) : null}
        </div>
      ),
    },
    {
      key: "state",
      label: "State",
      render: (row) => <StatusBadge value={row.enabled ? "ENABLED" : "DISABLED"} />,
    },
    {
      key: "actions",
      label: "Actions",
      render: (row) =>
        manageAllowed ? (
          <div className="flex flex-wrap gap-1">
            <button
              className="erp-button !h-7 !min-h-7 text-[11px]"
              onClick={() => {
                setIntegrationDraft(editIntegration(row));
                setVerifiedFingerprint("");
                setTestResult(null);
              }}
              type="button"
            >
              <Pencil size={12} /> Edit
            </button>
            <button
              className="erp-button !h-7 !min-h-7 text-[11px]"
              disabled={!row.enabled || syncIntegration.isPending}
              onClick={() => syncIntegration.mutate(row.id)}
              type="button"
            >
              <RefreshCw size={12} /> Sync
            </button>
          </div>
        ) : "—",
    },
  ];

  const policyColumns: Array<TableColumn<AutomationPolicy>> = [
    {
      key: "policy",
      label: "Automation",
      render: (row) => (
        <div>
          <div className="font-semibold">{row.name}</div>
          <div className="mt-0.5 text-[11px] text-[var(--color-text-muted)]">
            {row.legal_entity_name ?? "Organization default"} · {row.kind.replaceAll("_", " ")}
          </div>
        </div>
      ),
    },
    {
      key: "state",
      label: "State",
      render: (row) => <StatusBadge value={row.enabled ? "ENABLED" : "DISABLED"} />,
    },
    {
      key: "schedule",
      label: "Schedule",
      render: (row) => (
        <div>
          <div>
            {row.frequency === "HOURLY"
              ? "Hourly"
              : "Daily · " + String(row.schedule_hour).padStart(2, "0") + ":00"}
          </div>
          <div className="text-[10px] text-[var(--color-text-muted)]">
            {row.schedule_timezone}
          </div>
        </div>
      ),
    },
    {
      key: "last",
      label: "Last Run",
      render: (row) => (
        <div>
          <StatusBadge value={row.last_status} />
          <div className="mt-1 text-[10px] text-[var(--color-text-muted)]">
            {timestamp(row.last_run_at)}
          </div>
          {row.last_error ? (
            <div className="mt-1 max-w-xs text-[10px] text-[var(--color-danger)]">
              {row.last_error}
            </div>
          ) : null}
        </div>
      ),
    },
    {
      key: "actions",
      label: "Actions",
      render: (row) =>
        manageAllowed ? (
          <div className="flex flex-wrap gap-1">
            <button
              className="erp-button !h-7 !min-h-7 text-[11px]"
              onClick={() => setPolicyEditor({ policy: row, createOverride: false })}
              type="button"
            >
              <Pencil size={12} /> Configure
            </button>
            <button
              className="erp-button !h-7 !min-h-7 text-[11px]"
              disabled={runPolicy.isPending}
              onClick={() => runPolicy.mutate(row.id)}
              type="button"
            >
              <Play size={12} /> Run Now
            </button>
            {!row.legal_entity
            && !(policies.data ?? []).some(
              (candidate) =>
                candidate.legal_entity === entity.id && candidate.kind === row.kind,
            ) ? (
              <button
                className="erp-button !h-7 !min-h-7 text-[11px]"
                onClick={() => setPolicyEditor({ policy: row, createOverride: true })}
                type="button"
              >
                Entity Override
              </button>
            ) : null}
          </div>
        ) : "—",
    },
  ];

  const automationRunColumns: Array<TableColumn<AutomationRun>> = [
    { key: "policy", label: "Automation", render: (row) => row.policy_name },
    { key: "kind", label: "Kind", render: (row) => row.policy_kind.replaceAll("_", " ") },
    { key: "trigger", label: "Trigger", render: (row) => <StatusBadge value={row.trigger} /> },
    { key: "status", label: "Status", render: (row) => <StatusBadge value={row.status} /> },
    {
      key: "summary",
      label: "Summary",
      render: (row) =>
        Object.keys(row.summary).length ? (
          <span className="font-mono text-[10px]">{JSON.stringify(row.summary)}</span>
        ) : row.error || "—",
    },
    { key: "started", label: "Started", render: (row) => timestamp(row.started_at) },
  ];

  const syncRunColumns: Array<TableColumn<VendorSyncRun>> = [
    {
      key: "source",
      label: "Vendor Sync",
      render: (row) => (
        <div>
          <div className="font-semibold">{row.integration_name}</div>
          <div className="text-[11px] text-[var(--color-text-muted)]">
            {row.vendor_name} · {row.subscription_name}
          </div>
        </div>
      ),
    },
    { key: "trigger", label: "Trigger", render: (row) => <StatusBadge value={row.trigger} /> },
    { key: "status", label: "Status", render: (row) => <StatusBadge value={row.status} /> },
    {
      key: "cost",
      label: "Synced Cost",
      numeric: true,
      render: (row) => row.cost_amount ? money(row.cost_amount, row.currency || "USD") : "—",
    },
    {
      key: "usage",
      label: "Usage",
      render: (row) =>
        row.usage_quantity ? row.usage_quantity + (row.usage_unit ? " " + row.usage_unit : "") : "—",
    },
    { key: "started", label: "Started", render: (row) => timestamp(row.started_at) },
    {
      key: "error",
      label: "Error",
      render: (row) => row.error ? <span className="text-[var(--color-danger)]">{row.error}</span> : "—",
    },
  ];

  const mutationError =
    createIntegration.error
    ?? updateIntegration.error
    ?? testIntegration.error
    ?? syncIntegration.error
    ?? runPolicy.error
    ?? updatePolicy.error
    ?? createPolicy.error;

  function integrationPayload(draft: IntegrationDraft, includeSecret = true) {
    let customHeaders: Record<string, string> = {};
    try {
      customHeaders = JSON.parse(draft.custom_headers || "{}") as Record<string, string>;
    } catch {
      throw new Error("Custom Headers must be valid JSON.");
    }
    return {
      integration_id: draft.id ?? null,
      name: draft.name,
      vendor: draft.vendor,
      subscription: draft.subscription,
      connector_type: "GENERIC_JSON",
      enabled: draft.enabled,
      endpoint_url: draft.endpoint_url,
      auth_type: draft.auth_type,
      auth_username: draft.auth_username,
      ...(includeSecret ? { secret: draft.secret } : {}),
      api_key_header: draft.api_key_header,
      custom_headers: customHeaders,
      cost_json_path: draft.cost_json_path,
      usage_quantity_json_path: draft.usage_quantity_json_path,
      currency_json_path: draft.currency_json_path,
      usage_unit_json_path: draft.usage_unit_json_path,
      timeout_seconds: draft.timeout_seconds,
      auto_create_period: draft.auto_create_period,
    };
  }

  function testCurrentDraft() {
    if (!integrationDraft) return;
    try {
      testIntegration.mutate(integrationPayload(integrationDraft));
    } catch (error) {
      testIntegration.reset();
      setTestResult(null);
      setVerifiedFingerprint("");
      // Surface through a local thrown error is awkward; browser validation is enough for JSON.
      window.alert(errorMessage(error));
    }
  }

  function saveCurrentDraft() {
    if (!integrationDraft) return;
    const body = integrationPayload(integrationDraft);
    delete body.integration_id;
    if (!integrationDraft.secret) delete body.secret;
    if (integrationDraft.id) {
      updateIntegration.mutate({ id: integrationDraft.id, body });
    } else {
      createIntegration.mutate(body);
    }
  }

  function submitPolicy(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!policyEditor) return;
    const data = new FormData(event.currentTarget);
    const body = {
      name: String(data.get("name") ?? policyEditor.policy.name),
      kind: policyEditor.policy.kind,
      legal_entity: policyEditor.createOverride ? entity.id : policyEditor.policy.legal_entity,
      enabled: data.get("enabled") === "on",
      frequency: String(data.get("frequency") ?? "DAILY"),
      schedule_hour: Number(data.get("schedule_hour") ?? 0),
      schedule_timezone: String(data.get("schedule_timezone") ?? "UTC"),
    };
    if (policyEditor.createOverride) createPolicy.mutate(body);
    else updatePolicy.mutate({ id: policyEditor.policy.id, body });
  }

  const verified =
    Boolean(integrationDraft)
    && verifiedFingerprint === draftFingerprint(integrationDraft!);
  const saveAllowed = Boolean(integrationDraft) && (!integrationDraft!.enabled || verified);

  return (
    <>
      <PageHeader
        eyebrow="Phase 6 · Operations Automation"
        title="Automation & Integrations"
        description="Connect vendor usage APIs, automate safe operational routines, and keep a complete run history without auto-posting financial transactions."
        actions={
          manageAllowed && tab === "integrations" ? (
            <button
              className="erp-button erp-button-primary"
              disabled={!paygSubscriptions.length}
              onClick={() => {
                setIntegrationDraft(blankIntegration(paygSubscriptions));
                setVerifiedFingerprint("");
                setTestResult(null);
              }}
              type="button"
            >
              <Plus size={14} /> Vendor Integration
            </button>
          ) : undefined
        }
      />
      <MetricStrip
        metrics={[
          {
            label: "Active Integrations",
            value: String(overview.data?.active_integrations ?? 0),
          },
          {
            label: "Integration Failures",
            value: String(overview.data?.failed_integrations ?? 0),
            tone: overview.data?.failed_integrations ? "bad" : "good",
          },
          {
            label: "Enabled Automations",
            value: String(overview.data?.enabled_policies ?? 0),
          },
          {
            label: "Failed Runs · 24h",
            value: String(overview.data?.failed_runs_24h ?? 0),
            tone: overview.data?.failed_runs_24h ? "bad" : "good",
            note: "Last vendor sync: " + timestamp(overview.data?.last_vendor_sync_at),
          },
        ]}
      />

      <div className="space-y-4 p-4 lg:p-6">
        {mutationError ? <ErrorState message={errorMessage(mutationError)} /> : null}
        <div className="flex flex-wrap gap-1 border-b border-[var(--color-border)]">
          {[
            ["integrations", "Vendor Integrations", PlugZap],
            ["automation", "Automation Policies", Workflow],
            ["history", "Run History", RefreshCw],
          ].map(([value, label, Icon]) => (
            <button
              className={
                "flex items-center gap-2 px-4 py-2 text-sm font-semibold "
                + (tab === value
                  ? "border-b-2 border-[var(--color-primary)] text-[var(--color-primary)]"
                  : "text-[var(--color-text-muted)]")
              }
              key={String(value)}
              onClick={() => setTab(value as typeof tab)}
              type="button"
            >
              <Icon size={13} /> {String(label)}
            </button>
          ))}
        </div>

        {tab === "integrations" ? (
          <>
            {!paygSubscriptions.length ? (
              <div className="border border-[var(--color-border)] bg-white p-4 text-sm">
                Create an active PAYG subscription before adding a vendor usage integration.
              </div>
            ) : null}
            <DataTable
              columns={integrationColumns}
              rows={integrations.data ?? []}
              rowKey={(row) => row.id}
              emptyTitle="No vendor integrations"
              emptyDescription="Connect a vendor HTTPS JSON API to keep PAYG current usage synchronized."
            />
          </>
        ) : null}

        {tab === "automation" ? (
          <>
            <div className="border border-[var(--color-border)] bg-white px-4 py-3 text-xs text-[var(--color-text-muted)]">
              Automations intentionally avoid payments, invoice creation, approvals and ledger posting.
              Organization defaults can be overridden for the active legal entity.
            </div>
            <DataTable
              columns={policyColumns}
              rows={policies.data ?? []}
              rowKey={(row) => row.id}
              emptyTitle="No automation policies"
              emptyDescription="Safe default policies are created automatically."
            />
          </>
        ) : null}

        {tab === "history" ? (
          <div className="space-y-6">
            <section>
              <h2 className="mb-2 text-sm font-semibold">Automation Runs</h2>
              <DataTable
                columns={automationRunColumns}
                rows={automationRuns.data?.results ?? []}
                rowKey={(row) => row.id}
                emptyTitle="No automation runs"
              />
            </section>
            <section>
              <h2 className="mb-2 text-sm font-semibold">Vendor Sync Runs</h2>
              <DataTable
                columns={syncRunColumns}
                rows={syncRuns.data?.results ?? []}
                rowKey={(row) => row.id}
                emptyTitle="No vendor sync runs"
              />
            </section>
          </div>
        ) : null}
      </div>

      {integrationDraft ? (
        <Overlay
          title={integrationDraft.id ? "Edit Vendor Integration" : "New Vendor Integration"}
          description="Configure the current draft, test it without saving, then save only the verified configuration."
          onClose={() => setIntegrationDraft(null)}
        >
          <div className="grid gap-4 p-5 sm:grid-cols-2">
            <label className="sm:col-span-2">
              <span className="erp-label">Integration Name</span>
              <input
                className="erp-field"
                value={integrationDraft.name}
                onChange={(event) => {
                  setIntegrationDraft({ ...integrationDraft, name: event.target.value });
                  setVerifiedFingerprint("");
                }}
              />
            </label>

            <label>
              <span className="erp-label">PAYG Subscription</span>
              <select
                className="erp-field"
                value={integrationDraft.subscription}
                onChange={(event) => {
                  const sub = paygSubscriptions.find((item) => item.id === event.target.value);
                  setIntegrationDraft({
                    ...integrationDraft,
                    subscription: event.target.value,
                    vendor: sub?.vendor ?? "",
                  });
                  setVerifiedFingerprint("");
                }}
              >
                <option value="">Select subscription</option>
                {paygSubscriptions.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name} · {item.vendor_name ?? "No vendor"} · {item.currency}
                  </option>
                ))}
              </select>
            </label>

            <label>
              <span className="erp-label">Vendor</span>
              <select
                className="erp-field"
                value={integrationDraft.vendor}
                onChange={(event) => {
                  setIntegrationDraft({ ...integrationDraft, vendor: event.target.value });
                  setVerifiedFingerprint("");
                }}
              >
                <option value="">Select vendor</option>
                {(vendors.data ?? []).map((item) => (
                  <option key={item.id} value={item.id}>{item.name}</option>
                ))}
              </select>
            </label>

            <label className="sm:col-span-2">
              <span className="erp-label">HTTPS JSON Endpoint</span>
              <input
                className="erp-field font-mono text-xs"
                placeholder="https://api.vendor.com/v1/usage/current"
                value={integrationDraft.endpoint_url}
                onChange={(event) => {
                  setIntegrationDraft({ ...integrationDraft, endpoint_url: event.target.value });
                  setVerifiedFingerprint("");
                }}
              />
              <span className="mt-1 block text-[10px] text-[var(--color-text-muted)]">
                Redirects and private/local network targets are blocked server-side.
              </span>
            </label>

            <label>
              <span className="erp-label">Authentication</span>
              <select
                className="erp-field"
                value={integrationDraft.auth_type}
                onChange={(event) => {
                  setIntegrationDraft({
                    ...integrationDraft,
                    auth_type: event.target.value as IntegrationDraft["auth_type"],
                  });
                  setVerifiedFingerprint("");
                }}
              >
                <option value="NONE">None</option>
                <option value="BEARER">Bearer Token</option>
                <option value="API_KEY_HEADER">API Key Header</option>
                <option value="BASIC">Basic Auth</option>
              </select>
            </label>

            <label>
              <span className="erp-label">Secret</span>
              <input
                className="erp-field"
                placeholder={integrationDraft.secret_configured ? "Saved secret — blank reuses it" : "Token / API key / password"}
                type="password"
                value={integrationDraft.secret}
                onChange={(event) => {
                  setIntegrationDraft({ ...integrationDraft, secret: event.target.value });
                  setVerifiedFingerprint("");
                }}
              />
            </label>

            {integrationDraft.auth_type === "BASIC" ? (
              <label>
                <span className="erp-label">Username</span>
                <input
                  className="erp-field"
                  value={integrationDraft.auth_username}
                  onChange={(event) => {
                    setIntegrationDraft({ ...integrationDraft, auth_username: event.target.value });
                    setVerifiedFingerprint("");
                  }}
                />
              </label>
            ) : null}

            {integrationDraft.auth_type === "API_KEY_HEADER" ? (
              <label>
                <span className="erp-label">API Key Header</span>
                <input
                  className="erp-field"
                  value={integrationDraft.api_key_header}
                  onChange={(event) => {
                    setIntegrationDraft({ ...integrationDraft, api_key_header: event.target.value });
                    setVerifiedFingerprint("");
                  }}
                />
              </label>
            ) : null}

            <label>
              <span className="erp-label">Cost JSON Path</span>
              <input
                className="erp-field font-mono text-xs"
                placeholder="data.current_cost"
                value={integrationDraft.cost_json_path}
                onChange={(event) => {
                  setIntegrationDraft({ ...integrationDraft, cost_json_path: event.target.value });
                  setVerifiedFingerprint("");
                }}
              />
            </label>
            <label>
              <span className="erp-label">Usage Quantity Path (optional)</span>
              <input
                className="erp-field font-mono text-xs"
                placeholder="data.usage.quantity"
                value={integrationDraft.usage_quantity_json_path}
                onChange={(event) => {
                  setIntegrationDraft({
                    ...integrationDraft,
                    usage_quantity_json_path: event.target.value,
                  });
                  setVerifiedFingerprint("");
                }}
              />
            </label>
            <label>
              <span className="erp-label">Currency Path (optional)</span>
              <input
                className="erp-field font-mono text-xs"
                placeholder="data.currency"
                value={integrationDraft.currency_json_path}
                onChange={(event) => {
                  setIntegrationDraft({ ...integrationDraft, currency_json_path: event.target.value });
                  setVerifiedFingerprint("");
                }}
              />
            </label>
            <label>
              <span className="erp-label">Usage Unit Path (optional)</span>
              <input
                className="erp-field font-mono text-xs"
                placeholder="data.usage.unit"
                value={integrationDraft.usage_unit_json_path}
                onChange={(event) => {
                  setIntegrationDraft({ ...integrationDraft, usage_unit_json_path: event.target.value });
                  setVerifiedFingerprint("");
                }}
              />
            </label>

            <label>
              <span className="erp-label">Timeout · seconds</span>
              <input
                className="erp-field"
                max={60}
                min={3}
                type="number"
                value={integrationDraft.timeout_seconds}
                onChange={(event) => {
                  setIntegrationDraft({
                    ...integrationDraft,
                    timeout_seconds: Number(event.target.value),
                  });
                  setVerifiedFingerprint("");
                }}
              />
            </label>

            <label className="sm:col-span-2">
              <span className="erp-label">Custom Headers · JSON</span>
              <textarea
                className="erp-field min-h-24 font-mono text-xs"
                value={integrationDraft.custom_headers}
                onChange={(event) => {
                  setIntegrationDraft({ ...integrationDraft, custom_headers: event.target.value });
                  setVerifiedFingerprint("");
                }}
              />
            </label>

            <div className="flex flex-wrap gap-5 sm:col-span-2">
              <label className="flex items-center gap-2 text-xs">
                <input
                  checked={integrationDraft.enabled}
                  onChange={(event) => {
                    setIntegrationDraft({ ...integrationDraft, enabled: event.target.checked });
                    setVerifiedFingerprint("");
                  }}
                  type="checkbox"
                />
                Integration enabled
              </label>
              <label className="flex items-center gap-2 text-xs">
                <input
                  checked={integrationDraft.auto_create_period}
                  onChange={(event) => {
                    setIntegrationDraft({
                      ...integrationDraft,
                      auto_create_period: event.target.checked,
                    });
                    setVerifiedFingerprint("");
                  }}
                  type="checkbox"
                />
                Auto-create current PAYG period when missing
              </label>
            </div>

            {testResult ? (
              <div className="flex items-center gap-3 border border-[var(--color-success)] bg-[#f3fbf6] p-3 text-sm sm:col-span-2">
                <CheckCircle2 size={16} />
                <div>
                  <strong>Verified draft.</strong>{" "}
                  {money(testResult.cost_amount, testResult.currency)}
                  {testResult.usage_quantity
                    ? " · " + testResult.usage_quantity + " " + testResult.usage_unit
                    : ""}
                </div>
              </div>
            ) : null}
          </div>
          <div className="flex justify-end gap-2 border-t border-[var(--color-border)] px-5 py-3">
            <button className="erp-button" onClick={() => setIntegrationDraft(null)} type="button">
              Cancel
            </button>
            <button
              className="erp-button"
              disabled={testIntegration.isPending}
              onClick={testCurrentDraft}
              type="button"
            >
              {testIntegration.isPending ? "Testing..." : "Test Current Draft"}
            </button>
            <button
              className="erp-button erp-button-primary"
              disabled={!manageAllowed || !saveAllowed || createIntegration.isPending || updateIntegration.isPending}
              onClick={saveCurrentDraft}
              type="button"
            >
              {createIntegration.isPending || updateIntegration.isPending
                ? "Saving..."
                : "Save Verified Integration"}
            </button>
          </div>
        </Overlay>
      ) : null}

      {policyEditor ? (
        <Overlay
          title={
            policyEditor.createOverride
              ? "Create " + entity.name + " Override"
              : "Configure · " + policyEditor.policy.name
          }
          description="Safe operational automation only; financial posting remains an explicit user action."
          onClose={() => setPolicyEditor(null)}
        >
          <form onSubmit={submitPolicy}>
            <div className="grid gap-4 p-5 sm:grid-cols-2">
              <label className="sm:col-span-2">
                <span className="erp-label">Name</span>
                <input
                  className="erp-field"
                  defaultValue={
                    policyEditor.createOverride
                      ? policyEditor.policy.name + " · " + entity.name
                      : policyEditor.policy.name
                  }
                  name="name"
                  required
                />
              </label>
              <label>
                <span className="erp-label">Frequency</span>
                <select className="erp-field" defaultValue={policyEditor.policy.frequency} name="frequency">
                  <option value="HOURLY">Hourly</option>
                  <option value="DAILY">Daily</option>
                </select>
              </label>
              <label>
                <span className="erp-label">Daily Schedule Hour</span>
                <input
                  className="erp-field"
                  defaultValue={policyEditor.policy.schedule_hour}
                  max={23}
                  min={0}
                  name="schedule_hour"
                  type="number"
                />
              </label>
              <label className="sm:col-span-2">
                <span className="erp-label">Timezone</span>
                <input
                  className="erp-field"
                  defaultValue={policyEditor.policy.schedule_timezone}
                  name="schedule_timezone"
                  placeholder="Asia/Dhaka"
                />
              </label>
              <label className="flex items-center gap-2 text-sm sm:col-span-2">
                <input
                  defaultChecked={policyEditor.policy.enabled}
                  name="enabled"
                  type="checkbox"
                />
                Automation enabled
              </label>
            </div>
            <div className="flex justify-end gap-2 border-t border-[var(--color-border)] px-5 py-3">
              <button className="erp-button" onClick={() => setPolicyEditor(null)} type="button">
                Cancel
              </button>
              <button
                className="erp-button erp-button-primary"
                disabled={updatePolicy.isPending || createPolicy.isPending}
                type="submit"
              >
                {updatePolicy.isPending || createPolicy.isPending
                  ? "Saving..."
                  : policyEditor.createOverride
                    ? "Create Override"
                    : "Save Policy"}
              </button>
            </div>
          </form>
        </Overlay>
      ) : null}
    </>
  );
}
