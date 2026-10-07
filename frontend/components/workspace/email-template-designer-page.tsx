"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Archive, MailCheck, Pencil, Plus, Save, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

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
import type { SessionPayload } from "@/lib/api";
import {
  notificationApi,
  type EmailTemplate,
  type EmailTemplatePreview,
} from "@/lib/phase8-api";

const signalOptions: Array<[string, string]> = [
  ["", "General / Direct Email"],
  ["RENEWAL_DUE", "Renewal Due"],
  ["BUDGET_THRESHOLD", "Budget Threshold"],
  ["MISSING_INVOICE", "Missing Invoice"],
  ["INVOICE_OVERDUE", "Invoice Overdue"],
  ["RECONCILIATION_NEEDED", "Reconciliation Needed"],
];

type Draft = {
  id?: string;
  template_key: string;
  name: string;
  description: string;
  signal: EmailTemplate["signal"];
  subject_template: string;
  html_body_template: string;
  text_body_template: string;
  status: "ACTIVE" | "ARCHIVED";
};

function member(session: SessionPayload) {
  return session.memberships.find(
    (item) => item.organization_id === session.active_organization_id,
  );
}

function can(session: SessionPayload, permission: string) {
  return member(session)?.permissions.includes(permission) ?? false;
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

function blankDraft(): Draft {
  return {
    template_key: "",
    name: "",
    description: "",
    signal: null,
    subject_template: "Update from {{organization_name}}",
    text_body_template: "{{alert_message}}\n\n{{organization_name}}",
    html_body_template:
      '<div style="font-family:Arial,sans-serif;padding:24px"><h2>{{alert_title}}</h2><p>{{alert_message}}</p></div>',
    status: "ACTIVE",
  };
}

function asDraft(template: EmailTemplate): Draft {
  return {
    id: template.id,
    template_key: template.template_key,
    name: template.name,
    description: template.description,
    signal: template.signal,
    subject_template: template.subject_template,
    html_body_template: template.html_body_template,
    text_body_template: template.text_body_template,
    status: template.status,
  };
}

export function EmailTemplateDesignerPage({ session }: { session: SessionPayload }) {
  const queryClient = useQueryClient();
  const allowed = can(session, "VIEW_NOTIFICATIONS");
  const manageAllowed = can(session, "MANAGE_NOTIFICATIONS");
  const [includeArchived, setIncludeArchived] = useState(false);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [preview, setPreview] = useState<EmailTemplatePreview | null>(null);
  const [previewError, setPreviewError] = useState("");
  const [testRecipient, setTestRecipient] = useState("");
  const [message, setMessage] = useState("");

  const templates = useQuery({
    queryKey: ["email-templates", session.active_organization_id, session.active_legal_entity_id, includeArchived],
    queryFn: () => notificationApi.emailTemplates(includeArchived),
    enabled: allowed && Boolean(session.active_organization_id),
  });
  const versions = useQuery({
    queryKey: ["email-template-versions", draft?.id],
    queryFn: () => notificationApi.emailTemplateVersions(draft!.id!),
    enabled: Boolean(draft?.id),
  });

  const refresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["email-templates"] }),
      queryClient.invalidateQueries({ queryKey: ["email-template-versions"] }),
      queryClient.invalidateQueries({ queryKey: ["notification-rules"] }),
    ]);
  };

  const create = useMutation({
    mutationFn: notificationApi.createEmailTemplate,
    onSuccess: async (result) => {
      setMessage("Template saved as v" + result.current_version + ".");
      setDraft(asDraft(result));
      await refresh();
    },
  });
  const update = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Record<string, unknown> }) =>
      notificationApi.updateEmailTemplate(id, body),
    onSuccess: async (result) => {
      setMessage("Template saved as v" + result.current_version + ".");
      setDraft(asDraft(result));
      await refresh();
    },
  });
  const archive = useMutation({
    mutationFn: notificationApi.archiveEmailTemplate,
    onSuccess: async (result) => {
      setMessage("Template archived.");
      setDraft(asDraft(result));
      await refresh();
    },
  });
  const testSend = useMutation({
    mutationFn: notificationApi.testEmailTemplate,
    onSuccess: (result) => setMessage(result.detail),
  });

  useEffect(() => {
    if (!draft) return;
    const timer = window.setTimeout(() => {
      notificationApi
        .previewEmailTemplate({
          signal: draft.signal,
          subject_template: draft.subject_template,
          text_body_template: draft.text_body_template,
          html_body_template: draft.html_body_template,
        })
        .then((result) => {
          setPreview(result);
          setPreviewError("");
        })
        .catch((error: unknown) => {
          setPreview(null);
          setPreviewError(errorMessage(error));
        });
    }, 350);
    return () => window.clearTimeout(timer);
  }, [draft]);

  const selected = useMemo(
    () => (templates.data ?? []).find((item) => item.id === draft?.id),
    [templates.data, draft?.id],
  );
  const variables = selected?.available_variables ?? preview?.context ?? {};

  if (!allowed) {
    return <PermissionNotice>You do not have permission to view email templates.</PermissionNotice>;
  }
  if (templates.isLoading) return <LoadingState label="Loading email templates..." />;
  if (templates.error) return <ErrorState message={errorMessage(templates.error)} />;

  const rows = templates.data ?? [];
  const columns: Array<TableColumn<EmailTemplate>> = [
    {
      key: "name",
      label: "Template",
      render: (row) => (
        <div>
          <div className="font-semibold">{row.name}</div>
          <div className="mt-0.5 font-mono text-[10px] text-[var(--color-text-muted)]">
            {row.template_key}
          </div>
        </div>
      ),
    },
    { key: "purpose", label: "Purpose", render: (row) => <StatusBadge value={row.signal ?? "GENERAL"} /> },
    { key: "version", label: "Version", render: (row) => "v" + row.current_version },
    { key: "scope", label: "Scope", render: (row) => row.legal_entity_name ?? "Organization" },
    { key: "status", label: "Status", render: (row) => <StatusBadge value={row.status} /> },
    { key: "updated", label: "Updated", render: (row) => timestamp(row.updated_at) },
    {
      key: "actions",
      label: "",
      render: (row) => (
        <button className="erp-button !h-7 !min-h-7 text-[11px]" onClick={() => setDraft(asDraft(row))} type="button">
          <Pencil size={12} /> Edit
        </button>
      ),
    },
  ];

  function saveDraft() {
    if (!draft) return;
    const body = {
      template_key: draft.template_key,
      name: draft.name,
      description: draft.description,
      signal: draft.signal,
      subject_template: draft.subject_template,
      html_body_template: draft.html_body_template,
      text_body_template: draft.text_body_template,
      status: draft.status,
    };
    if (draft.id) update.mutate({ id: draft.id, body });
    else create.mutate(body);
  }

  function testDraft() {
    if (!draft || !testRecipient.trim()) return;
    testSend.mutate({
      recipient: testRecipient.trim(),
      signal: draft.signal,
      subject_template: draft.subject_template,
      text_body_template: draft.text_body_template,
      html_body_template: draft.html_body_template,
    });
  }

  return (
    <>
      <PageHeader
        eyebrow="Alerts & Delivery"
        title="Email Template Designer"
        description="Design reusable HTML email, preview it live, preserve every version and use templates from alert rules."
        actions={manageAllowed ? (
          <button className="erp-button erp-button-primary" onClick={() => setDraft(blankDraft())} type="button">
            <Plus size={14} /> New Template
          </button>
        ) : undefined}
      />
      <MetricStrip metrics={[
        { label: "Templates", value: String(rows.length) },
        { label: "Active", value: String(rows.filter((item) => item.status === "ACTIVE").length) },
        { label: "System Defaults", value: String(rows.filter((item) => item.is_system_default).length) },
        { label: "Designer", value: "Versioned", note: "HTML + text fallback" },
      ]} />

      <div className="space-y-4 p-4 lg:p-6">
        <div className="flex justify-end">
          <label className="flex items-center gap-2 text-xs">
            <input checked={includeArchived} onChange={(event) => setIncludeArchived(event.target.checked)} type="checkbox" />
            Include archived
          </label>
        </div>
        {create.error || update.error || archive.error || testSend.error ? (
          <ErrorState message={errorMessage(create.error ?? update.error ?? archive.error ?? testSend.error)} />
        ) : null}
        {message ? <div className="border border-[var(--color-border)] bg-white px-4 py-3 text-sm">{message}</div> : null}
        <DataTable columns={columns} rows={rows} rowKey={(row) => row.id} emptyTitle="No email templates" emptyDescription="Create a reusable alert or direct-email template." />
      </div>

      {draft ? (
        <div className="fixed inset-0 z-[90] overflow-y-auto bg-black/55 p-3 lg:p-6">
          <section className="mx-auto max-w-[1500px] border border-[var(--color-border-strong)] bg-white shadow-2xl">
            <header className="flex items-start justify-between gap-4 border-b border-[var(--color-border)] px-5 py-4">
              <div>
                <h2 className="text-lg font-semibold">{draft.id ? "Edit · " + draft.name : "New Email Template"}</h2>
                <p className="mt-1 text-xs text-[var(--color-text-muted)]">Content changes create a new immutable version.</p>
              </div>
              <button aria-label="Close designer" className="erp-button !h-8 !min-h-8 !w-8 !p-0" onClick={() => setDraft(null)} type="button">
                <X size={14} />
              </button>
            </header>

            <div className="grid xl:grid-cols-[minmax(0,1fr)_minmax(420px,0.9fr)]">
              <div className="space-y-4 border-r border-[var(--color-border)] p-5">
                <div className="grid gap-4 sm:grid-cols-2">
                  <label><span className="erp-label">Name</span><input className="erp-field" value={draft.name} onChange={(event) => setDraft({ ...draft, name: event.target.value })} /></label>
                  <label><span className="erp-label">Template Key</span><input className="erp-field font-mono" disabled={Boolean(draft.id)} value={draft.template_key} onChange={(event) => setDraft({ ...draft, template_key: event.target.value.toLowerCase().replace(/[^a-z0-9-]/g, "-") })} /></label>
                  <label>
                    <span className="erp-label">Purpose</span>
                    <select className="erp-field" value={draft.signal ?? ""} onChange={(event) => setDraft({ ...draft, signal: (event.target.value || null) as Draft["signal"] })}>
                      {signalOptions.map(([value, label]) => <option key={value || "general"} value={value}>{label}</option>)}
                    </select>
                  </label>
                  <label>
                    <span className="erp-label">Status</span>
                    <select className="erp-field" value={draft.status} onChange={(event) => setDraft({ ...draft, status: event.target.value as Draft["status"] })}>
                      <option value="ACTIVE">Active</option><option value="ARCHIVED">Archived</option>
                    </select>
                  </label>
                  <label className="sm:col-span-2"><span className="erp-label">Description</span><input className="erp-field" value={draft.description} onChange={(event) => setDraft({ ...draft, description: event.target.value })} /></label>
                </div>

                <div className="border border-[var(--color-border)] bg-[var(--color-surface-subtle)] p-3">
                  <div className="mb-2 text-xs font-semibold">Available Variables</div>
                  <div className="flex flex-wrap gap-1.5">
                    {Object.keys(variables).map((key) => (
                      <span className="border border-[var(--color-border)] bg-white px-2 py-1 font-mono text-[10px]" key={key}>
                        {"{{" + key + "}}"}
                      </span>
                    ))}
                  </div>
                </div>

                <label><span className="erp-label">Subject</span><input className="erp-field font-mono text-xs" value={draft.subject_template} onChange={(event) => setDraft({ ...draft, subject_template: event.target.value })} /></label>
                <label><span className="erp-label">Plain-Text Fallback</span><textarea className="erp-field min-h-36 font-mono text-xs" value={draft.text_body_template} onChange={(event) => setDraft({ ...draft, text_body_template: event.target.value })} /></label>
                <label>
                  <span className="erp-label">HTML Template</span>
                  <textarea className="erp-field min-h-[360px] font-mono text-xs" spellCheck={false} value={draft.html_body_template} onChange={(event) => setDraft({ ...draft, html_body_template: event.target.value })} />
                  <span className="mt-1 block text-[10px] text-[var(--color-text-muted)]">Scripts, iframes, unsafe URLs and unsafe CSS are stripped server-side.</span>
                </label>

                <div className="flex flex-wrap items-end gap-2 border-t border-[var(--color-border)] pt-4">
                  <label className="min-w-64 flex-1"><span className="erp-label">Send Preview To</span><input className="erp-field" type="email" value={testRecipient} onChange={(event) => setTestRecipient(event.target.value)} /></label>
                  <button className="erp-button" disabled={testSend.isPending || !testRecipient.trim()} onClick={testDraft} type="button"><MailCheck size={13} /> Send Test</button>
                  <button className="erp-button erp-button-primary" disabled={!manageAllowed || create.isPending || update.isPending} onClick={saveDraft} type="button"><Save size={13} /> Save</button>
                  {draft.id && draft.status === "ACTIVE" && manageAllowed ? (
                    <button className="erp-button" disabled={archive.isPending} onClick={() => archive.mutate(draft.id!)} type="button"><Archive size={13} /> Archive</button>
                  ) : null}
                </div>
              </div>

              <aside className="space-y-4 bg-[var(--color-surface-subtle)] p-5">
                {previewError ? <ErrorState message={previewError} /> : (
                  <>
                    <div className="border border-[var(--color-border)] bg-white p-3">
                      <div className="erp-label">Live Subject Preview</div>
                      <div className="mt-1 text-sm font-semibold">{preview?.subject ?? "Rendering..."}</div>
                    </div>
                    <iframe className="h-[600px] w-full border border-[var(--color-border)] bg-white" sandbox="" srcDoc={preview?.html_body ?? "<p>Rendering...</p>"} title="Email template live preview" />
                    <div className="border border-[var(--color-border)] bg-white p-3">
                      <div className="erp-label">Plain Text Preview</div>
                      <pre className="mt-2 whitespace-pre-wrap text-xs">{preview?.text_body ?? "Rendering..."}</pre>
                    </div>
                  </>
                )}

                {draft.id ? (
                  <div className="border border-[var(--color-border)] bg-white">
                    <div className="border-b border-[var(--color-border)] px-3 py-2 text-xs font-semibold">Version History</div>
                    {versions.isLoading ? <div className="p-3 text-xs">Loading...</div> : versions.error ? (
                      <div className="p-3 text-xs text-[var(--color-danger)]">{errorMessage(versions.error)}</div>
                    ) : (
                      <div className="max-h-72 overflow-y-auto">
                        {(versions.data ?? []).map((version) => (
                          <div className="border-b border-[var(--color-border-soft)] px-3 py-2 last:border-b-0" key={version.id}>
                            <div className="flex justify-between gap-2 text-xs"><strong>{"v" + version.version_number}</strong><span className="text-[var(--color-text-muted)]">{timestamp(version.created_at)}</span></div>
                            <div className="mt-1 truncate text-[11px] text-[var(--color-text-muted)]">{version.subject_template}</div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ) : null}
              </aside>
            </div>
          </section>
        </div>
      ) : null}
    </>
  );
}
