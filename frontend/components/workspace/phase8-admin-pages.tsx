"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState, type FormEvent } from "react";

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
import { adminApi, type SessionPayload } from "@/lib/api";
import {
  auditApi,
  documentIntegrityApi,
  notificationApi,
  type AlertRule,
  type AuditEvent,
  type FinanceDocumentIntegrity,
  type Notification,
  type NotificationDelivery,
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

export function AuditLogPage({ session }: { session: SessionPayload }) {
  const allowed = can(session, "VIEW_AUDIT_LOG");
  const [filters, setFilters] = useState<Record<string, string>>({});
  const events = useQuery({
    queryKey: ["audit-events", session.active_organization_id, session.active_legal_entity_id, filters],
    queryFn: () => auditApi.events(filters),
    enabled: allowed && Boolean(session.active_organization_id),
  });

  if (!allowed) return <PermissionNotice>You do not have permission to view the audit log.</PermissionNotice>;
  if (events.isLoading) return <LoadingState label="Loading audit events..." />;
  if (events.error) return <ErrorState message={errorMessage(events.error)} />;

  const columns: Array<TableColumn<AuditEvent>> = [
    { key: "time", label: "Timestamp", render: (row) => timestamp(row.created_at) },
    { key: "actor", label: "Actor", render: (row) => row.actor_email ?? "System" },
    { key: "action", label: "Action", render: (row) => row.action },
    { key: "object", label: "Object", render: (row) => `${row.object_type} · ${row.object_id}` },
    { key: "entity", label: "Legal Entity", render: (row) => row.legal_entity_name ?? "Organization" },
    { key: "request", label: "Request ID", render: (row) => row.request_id || "—" },
    { key: "ip", label: "IP", render: (row) => row.ip_address ?? "—" },
  ];

  function applyFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const next: Record<string, string> = {};
    for (const key of ["search", "action", "object_type", "start_date", "end_date"]) {
      const value = String(form.get(key) ?? "").trim();
      if (value) next[key] = value;
    }
    setFilters(next);
  }

  return (
    <>
      <PageHeader
        eyebrow="Phase 8 · Administration"
        title="Audit Log"
        description="Append-only audit events with actor, request context, state changes, IP address, user agent, and legal-entity scope."
      />
      <MetricStrip metrics={[{ label: "Matching Events", value: String(events.data?.count ?? 0) }, { label: "Scope", value: activeEntity(session)?.name ?? "Organization" }, { label: "Retention", value: "Append-only" }, { label: "Page Size", value: "50" }]} />
      <div className="space-y-4 p-4 lg:p-6">
        <form className="grid gap-2 border border-[var(--color-border)] bg-white p-3 md:grid-cols-5" onSubmit={applyFilters}>
          <input className="erp-field" name="search" placeholder="Search actor, action, object..." />
          <input className="erp-field" name="action" placeholder="Action contains..." />
          <input className="erp-field" name="object_type" placeholder="Object type..." />
          <input className="erp-field" name="start_date" type="date" />
          <div className="flex gap-2"><input className="erp-field" name="end_date" type="date" /><button className="erp-button erp-button-primary" type="submit">Filter</button></div>
        </form>
        <DataTable columns={columns} rows={events.data?.results ?? []} rowKey={(row) => row.id} emptyTitle="No matching audit events" emptyDescription="No append-only events match the selected filters." />
      </div>
    </>
  );
}

export function NotificationsPage({ session }: { session: SessionPayload }) {
  const queryClient = useQueryClient();
  const allowed = can(session, "VIEW_NOTIFICATIONS");
  const manageAllowed = can(session, "MANAGE_NOTIFICATIONS");
  const entity = activeEntity(session);
  const [tab, setTab] = useState<"inbox" | "rules" | "deliveries">("inbox");
  const [includeResolved, setIncludeResolved] = useState(false);
  const [kindFilter, setKindFilter] = useState("");
  const [severityFilter, setSeverityFilter] = useState("");
  const [stateFilter, setStateFilter] = useState("");
  const [deliverySignal, setDeliverySignal] = useState("");
  const [deliveryChannel, setDeliveryChannel] = useState("");
  const [deliveryStatus, setDeliveryStatus] = useState("");
  const [ruleEditor, setRuleEditor] = useState<{
    rule: AlertRule;
    createOverride: boolean;
  } | null>(null);

  const inbox = useQuery({
    queryKey: [
      "notifications",
      session.active_organization_id,
      session.active_legal_entity_id,
      includeResolved,
      kindFilter,
      severityFilter,
      stateFilter,
    ],
    queryFn: () =>
      notificationApi.inbox(includeResolved, {
        kind: kindFilter,
        severity: severityFilter,
        state: stateFilter,
      }),
    enabled: allowed && Boolean(session.active_organization_id),
  });
  const deliveries = useQuery({
    queryKey: [
      "notification-deliveries",
      session.active_organization_id,
      session.active_legal_entity_id,
      deliverySignal,
      deliveryChannel,
      deliveryStatus,
    ],
    queryFn: () =>
      notificationApi.deliveries({
        signal: deliverySignal,
        channel: deliveryChannel,
        status: deliveryStatus,
      }),
    enabled: allowed && Boolean(session.active_organization_id),
  });
  const rules = useQuery({
    queryKey: [
      "notification-rules",
      session.active_organization_id,
      session.active_legal_entity_id,
    ],
    queryFn: notificationApi.rules,
    enabled: allowed && Boolean(session.active_organization_id),
  });
  const emailTemplates = useQuery({
    queryKey: [
      "email-templates",
      session.active_organization_id,
      session.active_legal_entity_id,
      "rules",
    ],
    queryFn: () => notificationApi.emailTemplates(false),
    enabled: allowed && Boolean(session.active_organization_id),
  });
  const members = useQuery({
    queryKey: ["notification-rule-members", session.active_organization_id],
    queryFn: adminApi.members,
    enabled: manageAllowed && Boolean(session.active_organization_id),
  });

  const refresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["notifications"] }),
      queryClient.invalidateQueries({ queryKey: ["notification-deliveries"] }),
      queryClient.invalidateQueries({ queryKey: ["notification-rules"] }),
    ]);
  };

  const readMutation = useMutation({
    mutationFn: notificationApi.markRead,
    onSuccess: refresh,
  });
  const dismissMutation = useMutation({
    mutationFn: notificationApi.dismiss,
    onSuccess: refresh,
  });
  const readAllMutation = useMutation({
    mutationFn: notificationApi.markAllRead,
    onSuccess: refresh,
  });
  const retryMutation = useMutation({
    mutationFn: notificationApi.retryDelivery,
    onSuccess: refresh,
  });
  const updateRuleMutation = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Record<string, unknown> }) =>
      notificationApi.updateRule(id, body),
    onSuccess: async () => {
      setRuleEditor(null);
      await refresh();
    },
  });
  const createRuleMutation = useMutation({
    mutationFn: notificationApi.createRule,
    onSuccess: async () => {
      setRuleEditor(null);
      await refresh();
    },
  });
  const runNowMutation = useMutation({
    mutationFn: notificationApi.runRulesNow,
    onSuccess: refresh,
  });

  if (!allowed) {
    return <PermissionNotice>You do not have permission to view notifications.</PermissionNotice>;
  }
  if (inbox.isLoading || deliveries.isLoading || rules.isLoading || emailTemplates.isLoading) {
    return <LoadingState label="Loading Notification Center..." />;
  }
  if (inbox.error || deliveries.error || rules.error || emailTemplates.error) {
    return (
      <ErrorState
        message={errorMessage(inbox.error ?? deliveries.error ?? rules.error ?? emailTemplates.error)}
      />
    );
  }

  const signalOptions = [
    ["RENEWAL_DUE", "Renewal due"],
    ["BUDGET_THRESHOLD", "Budget threshold"],
    ["MISSING_INVOICE", "Missing invoice"],
    ["INVOICE_OVERDUE", "Invoice overdue"],
    ["RECONCILIATION_NEEDED", "Reconciliation needed"],
  ] as const;

  const notificationColumns: Array<TableColumn<Notification>> = [
    {
      key: "severity",
      label: "Severity",
      render: (row) => <StatusBadge value={row.severity} />,
    },
    {
      key: "kind",
      label: "Signal",
      render: (row) => <StatusBadge value={row.kind} />,
    },
    {
      key: "title",
      label: "Alert",
      render: (row) => (
        <div>
          <div className="font-semibold">{row.title}</div>
          <div className="mt-0.5 max-w-2xl text-xs text-[var(--color-text-muted)]">
            {row.message}
          </div>
        </div>
      ),
    },
    {
      key: "due",
      label: "Relevant Date",
      render: (row) => row.due_date ?? "—",
    },
    {
      key: "state",
      label: "State",
      render: (row) =>
        row.resolved_at ? (
          <StatusBadge value="RESOLVED" />
        ) : row.read_at ? (
          <StatusBadge value="READ" />
        ) : (
          <StatusBadge value="UNREAD" />
        ),
    },
    {
      key: "created",
      label: "Detected",
      render: (row) => timestamp(row.created_at),
    },
    {
      key: "action",
      label: "Actions",
      render: (row) => (
        <div className="flex flex-wrap gap-1">
          {row.link ? (
            <Link className="erp-button !h-7 !min-h-7 text-[11px]" href={row.link}>
              Open
            </Link>
          ) : null}
          {!row.read_at && !row.resolved_at ? (
            <button
              className="erp-button !h-7 !min-h-7 text-[11px]"
              disabled={readMutation.isPending}
              onClick={() => readMutation.mutate(row.id)}
              type="button"
            >
              Mark Read
            </button>
          ) : null}
          {!row.resolved_at ? (
            <button
              className="erp-button !h-7 !min-h-7 text-[11px]"
              disabled={dismissMutation.isPending}
              onClick={() => dismissMutation.mutate(row.id)}
              type="button"
            >
              Dismiss
            </button>
          ) : null}
        </div>
      ),
    },
  ];

  const deliveryColumns: Array<TableColumn<NotificationDelivery>> = [
    {
      key: "source",
      label: "Source",
      render: (row) => (
        <div>
          <div className="font-semibold">{row.source_label}</div>
          <div className="mt-0.5 text-[10px] text-[var(--color-text-muted)]">
            {row.alert_rule_name ?? "Legacy subscription reminder"}
          </div>
          {row.email_template_name ? (
            <div className="mt-0.5 text-[10px] text-[var(--color-text-muted)]">
              {row.email_template_name} · v{row.email_template_version}
            </div>
          ) : null}
        </div>
      ),
    },
    {
      key: "signal",
      label: "Signal",
      render: (row) => <StatusBadge value={row.signal} />,
    },
    {
      key: "channel",
      label: "Channel",
      render: (row) => <StatusBadge value={row.channel} />,
    },
    {
      key: "destination",
      label: "Destination",
      render: (row) => row.destination || "Default",
    },
    {
      key: "due",
      label: "Relevant Date",
      render: (row) => row.due_date ?? "—",
    },
    {
      key: "status",
      label: "Status",
      render: (row) => <StatusBadge value={row.status} />,
    },
    {
      key: "attempts",
      label: "Attempts",
      numeric: true,
      render: (row) => String(row.attempt_count),
    },
    {
      key: "sent",
      label: "Sent / Attempted",
      render: (row) => timestamp(row.sent_at ?? row.created_at),
    },
    {
      key: "error",
      label: "Error",
      render: (row) =>
        row.last_error ? (
          <span className="max-w-sm text-xs text-[var(--color-danger)]">
            {row.last_error}
          </span>
        ) : (
          "—"
        ),
    },
    {
      key: "action",
      label: "",
      render: (row) =>
        manageAllowed && row.status === "FAILED" ? (
          <button
            className="erp-button !h-7 !min-h-7 text-[11px]"
            disabled={retryMutation.isPending}
            onClick={() => retryMutation.mutate(row.id)}
            type="button"
          >
            Retry
          </button>
        ) : null,
    },
  ];

  const ruleColumns: Array<TableColumn<AlertRule>> = [
    {
      key: "rule",
      label: "Rule",
      render: (row) => (
        <div>
          <div className="font-semibold">{row.name}</div>
          <div className="mt-0.5 text-[11px] text-[var(--color-text-muted)]">
            {row.legal_entity_name ?? "Organization default"} · {row.signal.replaceAll("_", " ")}
          </div>
        </div>
      ),
    },
    {
      key: "enabled",
      label: "State",
      render: (row) => <StatusBadge value={row.enabled ? "ENABLED" : "DISABLED"} />,
    },
    {
      key: "schedule",
      label: "Schedule",
      render: (row) => (
        <div>
          <div>{row.frequency === "HOURLY" ? "Hourly" : `Daily · ${String(row.schedule_hour).padStart(2, "0")}:00`}</div>
          <div className="text-[11px] text-[var(--color-text-muted)]">
            {row.schedule_timezone}
          </div>
        </div>
      ),
    },
    {
      key: "channels",
      label: "Delivery",
      render: (row) => (
        <div className="text-[11px]">
          {row.respect_subscription_channels ? (
            <>
              <div className="font-semibold">Per-subscription channels</div>
              <div className="text-[var(--color-text-muted)]">
                Keeps each subscription’s In-App / Email / Hermes choices
              </div>
            </>
          ) : (
            <div>
              {[
                row.in_app_enabled ? "In-App" : null,
                row.email_enabled ? "Email" : null,
                row.hermes_enabled ? "Hermes" : null,
              ]
                .filter(Boolean)
                .join(" · ") || "No channels"}
            </div>
          )}
        </div>
      ),
    },
    {
      key: "last",
      label: "Last Evaluation",
      render: (row) => (
        <div>
          <div>{timestamp(row.last_evaluated_at)}</div>
          <div className="text-[11px] text-[var(--color-text-muted)]">
            {row.last_delivery_count} delivered · {row.last_failure_count} failed
          </div>
          {row.last_error ? (
            <div className="mt-1 text-[11px] text-[var(--color-danger)]">{row.last_error}</div>
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
              onClick={() => setRuleEditor({ rule: row, createOverride: false })}
              type="button"
            >
              Configure
            </button>
            {!row.legal_entity && entity && !(rules.data ?? []).some(
              (candidate) =>
                candidate.legal_entity === entity.id && candidate.signal === row.signal,
            ) ? (
              <button
                className="erp-button !h-7 !min-h-7 text-[11px]"
                onClick={() => setRuleEditor({ rule: row, createOverride: true })}
                type="button"
              >
                Entity Override
              </button>
            ) : null}
          </div>
        ) : null,
    },
  ];

  const deliveryRows = deliveries.data?.results ?? [];
  const failures = deliveryRows.filter((item) => item.status === "FAILED").length;
  const enabledRules = (rules.data ?? []).filter((item) => item.enabled).length;
  const mutationError =
    readMutation.error
    ?? dismissMutation.error
    ?? readAllMutation.error
    ?? retryMutation.error
    ?? updateRuleMutation.error
    ?? createRuleMutation.error
    ?? runNowMutation.error;

  function ruleBody(event: FormEvent<HTMLFormElement>, editor: NonNullable<typeof ruleEditor>) {
    const data = new FormData(event.currentTarget);
    const renewalDays = String(data.get("renewal_days") ?? "")
      .split(",")
      .map((item) => Number(item.trim()))
      .filter((item) => Number.isInteger(item) && item >= 0 && item <= 365);
    const emailRecipients = String(data.get("email_recipients") ?? "")
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
    const selectedUsers = data.getAll("recipient_user_ids").map(String);
    return {
      name: String(data.get("name") ?? editor.rule.name),
      signal: editor.rule.signal,
      legal_entity: editor.createOverride ? entity?.id ?? null : editor.rule.legal_entity,
      enabled: data.get("enabled") === "on",
      severity: String(data.get("severity") ?? "WARNING"),
      frequency: String(data.get("frequency") ?? "DAILY"),
      schedule_hour: Number(data.get("schedule_hour") ?? 0),
      schedule_timezone: String(data.get("schedule_timezone") ?? "UTC"),
      in_app_enabled: data.get("in_app_enabled") === "on",
      email_enabled: data.get("email_enabled") === "on",
      hermes_enabled: data.get("hermes_enabled") === "on",
      recipient_user_ids: selectedUsers,
      email_recipients: emailRecipients,
      hermes_target: String(data.get("hermes_target") ?? ""),
      email_template: String(data.get("email_template") ?? "") || null,
      renewal_days: renewalDays,
      grace_days: Number(data.get("grace_days") ?? 0),
      respect_subscription_channels:
        data.get("respect_subscription_channels") === "on",
    };
  }

  return (
    <>
      <PageHeader
        eyebrow="Alerts & Automation"
        title="Notification Center"
        description="One place for operational alerts, alert rules, schedules, delivery channels and retry history."
        actions={
          <div className="flex flex-wrap gap-2">
            <button
              className="erp-button"
              disabled={readAllMutation.isPending}
              onClick={() => readAllMutation.mutate()}
              type="button"
            >
              Mark All Read
            </button>
            {manageAllowed ? (
              <button
                className="erp-button erp-button-primary"
                disabled={runNowMutation.isPending}
                onClick={() => runNowMutation.mutate()}
                type="button"
              >
                {runNowMutation.isPending ? "Evaluating..." : "Run Rules Now"}
              </button>
            ) : null}
          </div>
        }
      />
      <MetricStrip
        metrics={[
          { label: "Unread", value: String(inbox.data?.unread_count ?? 0) },
          { label: "Active Alerts", value: String(inbox.data?.count ?? 0) },
          { label: "Enabled Rules", value: String(enabledRules) },
          {
            label: "Failed Deliveries",
            value: String(failures),
            tone: failures ? "bad" : "good",
          },
        ]}
      />

      <div className="space-y-4 p-4 lg:p-6">
        {runNowMutation.data ? (
          <div className="border border-[var(--color-success)] bg-[#f3fbf6] px-4 py-3 text-sm">
            Rule evaluation complete: <strong>{runNowMutation.data.active_events}</strong> active
            events · <strong>{runNowMutation.data.deliveries_sent}</strong> delivered ·{" "}
            <strong>{runNowMutation.data.deliveries_failed}</strong> failed.
          </div>
        ) : null}
        {mutationError ? <ErrorState message={errorMessage(mutationError)} /> : null}

        <div className="flex flex-wrap gap-1 border-b border-[var(--color-border)]">
          {[
            ["inbox", "Inbox"],
            ["rules", "Alert Rules"],
            ["deliveries", "Delivery History"],
          ].map(([value, label]) => (
            <button
              className={`px-4 py-2 text-sm font-semibold ${tab === value
                ? "border-b-2 border-[var(--color-primary)] text-[var(--color-primary)]"
                : "text-[var(--color-text-muted)]"}`}
              key={value}
              onClick={() => setTab(value as typeof tab)}
              type="button"
            >
              {label}
            </button>
          ))}
        </div>

        {tab === "inbox" ? (
          <section className="space-y-3">
            <div className="flex flex-wrap items-center gap-2 border border-[var(--color-border)] bg-white p-2.5">
              <select
                className="erp-field !h-8 !w-auto text-xs"
                onChange={(event) => setKindFilter(event.target.value)}
                value={kindFilter}
              >
                <option value="">All signals</option>
                {signalOptions.map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
              <select
                className="erp-field !h-8 !w-auto text-xs"
                onChange={(event) => setSeverityFilter(event.target.value)}
                value={severityFilter}
              >
                <option value="">All severities</option>
                <option value="INFO">Info</option>
                <option value="WARNING">Warning</option>
                <option value="CRITICAL">Critical</option>
              </select>
              <select
                className="erp-field !h-8 !w-auto text-xs"
                onChange={(event) => setStateFilter(event.target.value)}
                value={stateFilter}
              >
                <option value="">All states</option>
                <option value="UNREAD">Unread</option>
                <option value="READ">Read</option>
                <option value="RESOLVED">Resolved</option>
              </select>
              <label className="ml-auto flex items-center gap-2 text-xs">
                <input
                  checked={includeResolved}
                  onChange={(event) => setIncludeResolved(event.target.checked)}
                  type="checkbox"
                />
                Include resolved history
              </label>
            </div>
            <DataTable
              columns={notificationColumns}
              rows={inbox.data?.results ?? []}
              rowKey={(row) => row.id}
              emptyTitle="No matching alerts"
              emptyDescription="MateERP will surface renewal, budget, invoice and reconciliation conditions here."
            />
          </section>
        ) : null}

        {tab === "rules" ? (
          <section className="space-y-3">
            <div className="border border-[var(--color-border)] bg-white px-4 py-3 text-xs text-[var(--color-text-muted)]">
              Organization defaults apply to every legal entity. An entity override takes precedence
              for the same signal. Hourly rules are evaluated at most once per clock hour; daily
              rules run after their configured local hour.
            </div>
            <DataTable
              columns={ruleColumns}
              rows={rules.data ?? []}
              rowKey={(row) => row.id}
              emptyTitle="No alert rules"
              emptyDescription="Default operational rules are created automatically for this organization."
            />
          </section>
        ) : null}

        {tab === "deliveries" ? (
          <section className="space-y-3">
            <div className="flex flex-wrap items-center gap-2 border border-[var(--color-border)] bg-white p-2.5">
              <select
                className="erp-field !h-8 !w-auto text-xs"
                onChange={(event) => setDeliverySignal(event.target.value)}
                value={deliverySignal}
              >
                <option value="">All signals</option>
                {signalOptions.map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
              <select
                className="erp-field !h-8 !w-auto text-xs"
                onChange={(event) => setDeliveryChannel(event.target.value)}
                value={deliveryChannel}
              >
                <option value="">All channels</option>
                <option value="IN_APP">In-App</option>
                <option value="EMAIL">Email</option>
                <option value="HERMES">Hermes</option>
              </select>
              <select
                className="erp-field !h-8 !w-auto text-xs"
                onChange={(event) => setDeliveryStatus(event.target.value)}
                value={deliveryStatus}
              >
                <option value="">All statuses</option>
                <option value="SENT">Sent</option>
                <option value="FAILED">Failed</option>
                <option value="PENDING">Pending</option>
              </select>
            </div>
            <DataTable
              columns={deliveryColumns}
              rows={deliveryRows}
              rowKey={(row) => row.id}
              emptyTitle="No delivery history"
              emptyDescription="In-App, Email and Hermes attempts will be recorded with retry state."
            />
          </section>
        ) : null}
      </div>

      {ruleEditor ? (
        <div className="fixed inset-0 z-[90] flex items-start justify-center overflow-y-auto bg-black/55 px-3 py-[6vh]">
          <section className="w-full max-w-4xl border border-[var(--color-border-strong)] bg-white shadow-2xl">
            <header className="flex items-start justify-between gap-4 border-b border-[var(--color-border)] px-5 py-4">
              <div>
                <h2 className="text-lg font-semibold">
                  {ruleEditor.createOverride
                    ? `Create ${entity?.name ?? "Entity"} Override`
                    : `Configure · ${ruleEditor.rule.name}`}
                </h2>
                <p className="mt-1 text-xs text-[var(--color-text-muted)]">
                  {ruleEditor.rule.signal.replaceAll("_", " ")} ·{" "}
                  {ruleEditor.createOverride
                    ? "This legal entity will use the override instead of the organization default."
                    : ruleEditor.rule.legal_entity_name ?? "Organization default"}
                </p>
              </div>
              <button
                aria-label="Close rule editor"
                className="erp-button !h-8 !min-h-8 !w-8 !p-0"
                onClick={() => setRuleEditor(null)}
                type="button"
              >
                ×
              </button>
            </header>

            <form
              onSubmit={(event) => {
                event.preventDefault();
                const body = ruleBody(event, ruleEditor);
                if (ruleEditor.createOverride) {
                  createRuleMutation.mutate(body);
                } else {
                  updateRuleMutation.mutate({ id: ruleEditor.rule.id, body });
                }
              }}
            >
              <div className="grid gap-4 p-5 sm:grid-cols-2">
                <label className="block text-xs font-medium sm:col-span-2">
                  <span className="mb-1 block text-[var(--color-text-muted)]">Rule Name</span>
                  <input
                    className="erp-field"
                    defaultValue={
                      ruleEditor.createOverride
                        ? `${ruleEditor.rule.name} · ${entity?.name ?? "Entity"}`
                        : ruleEditor.rule.name
                    }
                    name="name"
                    required
                  />
                </label>

                <label className="flex items-center gap-2 border border-[var(--color-border)] p-3 text-sm sm:col-span-2">
                  <input
                    defaultChecked={ruleEditor.rule.enabled}
                    name="enabled"
                    type="checkbox"
                  />
                  Rule enabled
                </label>

                <label className="block text-xs font-medium">
                  <span className="mb-1 block text-[var(--color-text-muted)]">Severity</span>
                  <select
                    className="erp-field"
                    defaultValue={ruleEditor.rule.severity}
                    name="severity"
                  >
                    <option value="INFO">Info</option>
                    <option value="WARNING">Warning</option>
                    <option value="CRITICAL">Critical</option>
                  </select>
                </label>

                <label className="block text-xs font-medium">
                  <span className="mb-1 block text-[var(--color-text-muted)]">Frequency</span>
                  <select
                    className="erp-field"
                    defaultValue={ruleEditor.rule.frequency}
                    name="frequency"
                  >
                    <option value="HOURLY">Hourly</option>
                    <option value="DAILY">Daily</option>
                  </select>
                </label>

                <label className="block text-xs font-medium">
                  <span className="mb-1 block text-[var(--color-text-muted)]">Daily Schedule Hour</span>
                  <input
                    className="erp-field"
                    defaultValue={ruleEditor.rule.schedule_hour}
                    max={23}
                    min={0}
                    name="schedule_hour"
                    required
                    type="number"
                  />
                </label>

                <label className="block text-xs font-medium">
                  <span className="mb-1 block text-[var(--color-text-muted)]">Schedule Timezone</span>
                  <input
                    className="erp-field"
                    defaultValue={ruleEditor.rule.schedule_timezone}
                    name="schedule_timezone"
                    placeholder="Asia/Dhaka"
                    required
                  />
                </label>

                <div className="border border-[var(--color-border)] p-3 sm:col-span-2">
                  <div className="mb-2 text-xs font-semibold">Delivery Channels</div>
                  <div className="flex flex-wrap gap-5">
                    <label className="flex items-center gap-2 text-xs">
                      <input
                        defaultChecked={ruleEditor.rule.in_app_enabled}
                        name="in_app_enabled"
                        type="checkbox"
                      />
                      In-App
                    </label>
                    <label className="flex items-center gap-2 text-xs">
                      <input
                        defaultChecked={ruleEditor.rule.email_enabled}
                        name="email_enabled"
                        type="checkbox"
                      />
                      Email
                    </label>
                    <label className="flex items-center gap-2 text-xs">
                      <input
                        defaultChecked={ruleEditor.rule.hermes_enabled}
                        name="hermes_enabled"
                        type="checkbox"
                      />
                      Hermes
                    </label>
                  </div>
                </div>

                {ruleEditor.rule.signal === "RENEWAL_DUE" ? (
                  <>
                    <label className="flex items-center gap-2 border border-[var(--color-border)] p-3 text-xs sm:col-span-2">
                      <input
                        defaultChecked={ruleEditor.rule.respect_subscription_channels}
                        name="respect_subscription_channels"
                        type="checkbox"
                      />
                      Preserve each subscription’s own reminder channels and recipients
                    </label>
                    <label className="block text-xs font-medium">
                      <span className="mb-1 block text-[var(--color-text-muted)]">
                        Renewal Offsets (days)
                      </span>
                      <input
                        className="erp-field"
                        defaultValue={ruleEditor.rule.renewal_days.join(", ")}
                        name="renewal_days"
                      />
                    </label>
                  </>
                ) : (
                  <input
                    name="renewal_days"
                    type="hidden"
                    value={ruleEditor.rule.renewal_days.join(",")}
                  />
                )}

                {ruleEditor.rule.signal !== "RENEWAL_DUE" ? (
                  <label className="block text-xs font-medium">
                    <span className="mb-1 block text-[var(--color-text-muted)]">
                      Grace Days
                    </span>
                    <input
                      className="erp-field"
                      defaultValue={ruleEditor.rule.grace_days}
                      min={0}
                      name="grace_days"
                      type="number"
                    />
                  </label>
                ) : (
                  <input
                    name="grace_days"
                    type="hidden"
                    value={ruleEditor.rule.grace_days}
                  />
                )}

                <label className="block text-xs font-medium">
                  <span className="mb-1 block text-[var(--color-text-muted)]">
                    Email Recipients
                  </span>
                  <input
                    className="erp-field"
                    defaultValue={ruleEditor.rule.email_recipients.join(", ")}
                    name="email_recipients"
                    placeholder="finance@example.com, owner@example.com"
                  />
                  <span className="mt-1 block text-[10px] text-[var(--color-text-muted)]">
                    Blank uses selected in-app members’ email addresses.
                  </span>
                </label>

                <label className="block text-xs font-medium">
                  <span className="mb-1 block text-[var(--color-text-muted)]">
                    Hermes Target
                  </span>
                  <input
                    className="erp-field"
                    defaultValue={ruleEditor.rule.hermes_target}
                    name="hermes_target"
                    placeholder="Default integration target"
                  />
                </label>

                <label className="block text-xs font-medium sm:col-span-2">
                  <span className="mb-1 block text-[var(--color-text-muted)]">
                    Email Template
                  </span>
                  <select
                    className="erp-field"
                    defaultValue={ruleEditor.rule.email_template ?? ""}
                    name="email_template"
                  >
                    <option value="">System default for this signal</option>
                    {(emailTemplates.data ?? [])
                      .filter(
                        (template) =>
                          template.status === "ACTIVE"
                          && (template.signal === null || template.signal === ruleEditor.rule.signal)
                          && (
                            template.legal_entity === null
                            || template.legal_entity === ruleEditor.rule.legal_entity
                            || (ruleEditor.createOverride && template.legal_entity === entity?.id)
                          ),
                      )
                      .map((template) => (
                        <option key={template.id} value={template.id}>
                          {template.name} · v{template.current_version}
                        </option>
                      ))}
                  </select>
                  <span className="mt-1 block text-[10px] text-[var(--color-text-muted)]">
                    Email deliveries snapshot the rendered subject, text, HTML and template version.
                  </span>
                </label>

                <div className="border border-[var(--color-border)] p-3 sm:col-span-2">
                  <div className="mb-2 text-xs font-semibold">In-App Recipients</div>
                  <p className="mb-3 text-[11px] text-[var(--color-text-muted)]">
                    Leave everyone unchecked to notify every member who can view notifications in
                    the legal entity. Select members to narrow the audience.
                  </p>
                  {members.isLoading ? (
                    <div className="text-xs text-[var(--color-text-muted)]">Loading members...</div>
                  ) : (
                    <div className="grid gap-2 sm:grid-cols-2">
                      {(members.data ?? [])
                        .filter((item) => item.permissions.includes("VIEW_NOTIFICATIONS"))
                        .map((item) => (
                          <label
                            className="flex items-center gap-2 border border-[var(--color-border-soft)] p-2 text-xs"
                            key={item.user.id}
                          >
                            <input
                              defaultChecked={ruleEditor.rule.recipient_user_ids.includes(item.user.id)}
                              name="recipient_user_ids"
                              type="checkbox"
                              value={item.user.id}
                            />
                            <span>
                              <strong>{item.user.display_name || item.user.email}</strong>
                              <span className="ml-1 text-[var(--color-text-muted)]">
                                {item.user.email}
                              </span>
                            </span>
                          </label>
                        ))}
                    </div>
                  )}
                </div>
              </div>

              {(updateRuleMutation.error || createRuleMutation.error) ? (
                <div className="px-5 pb-3">
                  <ErrorState
                    message={errorMessage(updateRuleMutation.error ?? createRuleMutation.error)}
                  />
                </div>
              ) : null}

              <div className="flex justify-end gap-2 border-t border-[var(--color-border)] px-5 py-3">
                <button
                  className="erp-button"
                  onClick={() => setRuleEditor(null)}
                  type="button"
                >
                  Cancel
                </button>
                <button
                  className="erp-button erp-button-primary"
                  disabled={updateRuleMutation.isPending || createRuleMutation.isPending}
                  type="submit"
                >
                  {updateRuleMutation.isPending || createRuleMutation.isPending
                    ? "Saving..."
                    : ruleEditor.createOverride
                    ? "Create Override"
                    : "Save Rule"}
                </button>
              </div>
            </form>
          </section>
        </div>
      ) : null}
    </>
  );
}

export function DocumentIntegrityPage({ session }: { session: SessionPayload }) {
  const entity = activeEntity(session);
  const allowed = Boolean(entity) && can(session, "VIEW_FINANCE");
  const documents = useQuery({
    queryKey: ["document-integrity", entity?.id],
    queryFn: documentIntegrityApi.list,
    enabled: allowed,
  });

  if (!entity) return <PermissionNotice>Select a legal entity to view document integrity.</PermissionNotice>;
  if (!allowed) return <PermissionNotice>You do not have permission to view finance documents.</PermissionNotice>;
  if (documents.isLoading) return <LoadingState label="Loading document integrity metadata..." />;
  if (documents.error) return <ErrorState message={errorMessage(documents.error)} />;

  const columns: Array<TableColumn<FinanceDocumentIntegrity>> = [
    { key: "name", label: "Original File", render: (row) => row.original_name },
    { key: "type", label: "Document Type", render: (row) => row.document_type },
    { key: "mime", label: "MIME Type", render: (row) => row.mime_type ?? "Not backfilled" },
    { key: "size", label: "Bytes", numeric: true, render: (row) => row.size_bytes?.toLocaleString() ?? "—" },
    { key: "checksum", label: "SHA-256", render: (row) => row.checksum_sha256 ? <code className="text-[10px]">{row.checksum_sha256}</code> : "Not backfilled" },
    { key: "uploader", label: "Uploader", render: (row) => row.uploaded_by_email },
    { key: "created", label: "Uploaded", render: (row) => timestamp(row.created_at) },
  ];

  const verified = (documents.data ?? []).filter((item) => item.checksum_sha256).length;
  return (
    <>
      <PageHeader eyebrow="Phase 8 · Administration" title="Document Integrity" description="Stored finance-document provenance with original filename, MIME type, byte size, uploader, timestamp, and SHA-256 checksum." />
      <MetricStrip metrics={[{ label: "Documents", value: String(documents.data?.length ?? 0) }, { label: "Integrity Metadata", value: String(verified) }, { label: "Missing Metadata", value: String((documents.data?.length ?? 0) - verified), tone: verified === (documents.data?.length ?? 0) ? "good" : "bad" }, { label: "Max Upload", value: "25 MB" }]} />
      <div className="p-4 lg:p-6"><DataTable columns={columns} rows={documents.data ?? []} rowKey={(row) => row.id} /></div>
    </>
  );
}
