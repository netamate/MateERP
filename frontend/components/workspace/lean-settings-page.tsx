"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Mail, MessageSquareText, ShieldCheck, Send, XCircle } from "lucide-react";
import { useRef, useState, type FormEvent, type ReactNode } from "react";

import {
  ErrorState,
  LoadingState,
  PageHeader,
  PermissionNotice,
  StatusBadge,
} from "@/components/ui/erp";
import type { SessionPayload } from "@/lib/api";
import {
  notificationApi,
  type NotificationIntegrationSettings,
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

type Feedback = { kind: "error" | "success" | "info"; text: string };

function InlineFeedback({ feedback }: { feedback: Feedback | null }) {
  if (!feedback) return null;
  const tone =
    feedback.kind === "error"
      ? "border-[#f0b8b8] bg-[#fff5f4] text-[#a61b1b]"
      : feedback.kind === "success"
        ? "border-[#a9d8c4] bg-[#f0faf5] text-[#126343]"
        : "border-[#c6d6ea] bg-[#f4f8fd] text-[#254b7a]";
  return (
    <div role={feedback.kind === "error" ? "alert" : "status"}
      className={"flex items-start gap-2 border px-3 py-2.5 text-xs leading-relaxed " + tone}>
      {feedback.kind === "error" ? <XCircle size={15} className="mt-0.5 shrink-0" /> : <CheckCircle2 size={15} className="mt-0.5 shrink-0" />}
      <span>{feedback.text}</span>
    </div>
  );
}

function IntegrationCard({
  title,
  icon,
  children,
  badge,
}: {
  title: string;
  icon: ReactNode;
  children: ReactNode;
  badge?: ReactNode;
}) {
  return (
    <section className="erp-panel">
      <div className="erp-panel-header flex-wrap gap-2">
        <div className="flex items-center gap-2">
          {icon}
          <h2 className="text-sm font-semibold">{title}</h2>
        </div>
        {badge}
      </div>
      {children}
    </section>
  );
}

type SmtpDraft = {
  smtp_enabled: boolean;
  smtp_host: string;
  smtp_port: number;
  smtp_username: string;
  smtp_password: string;
  smtp_use_tls: boolean;
  smtp_use_ssl: boolean;
  smtp_from_name: string;
  smtp_from_email: string;
};

function smtpDraftFrom(saved: NotificationIntegrationSettings): SmtpDraft {
  return {
    smtp_enabled: saved.smtp_enabled,
    smtp_host: saved.smtp_host,
    smtp_port: saved.smtp_port,
    smtp_username: saved.smtp_username,
    smtp_password: "",
    smtp_use_tls: saved.smtp_use_tls,
    smtp_use_ssl: saved.smtp_use_ssl,
    smtp_from_name: saved.smtp_from_name,
    smtp_from_email: saved.smtp_from_email,
  };
}

function smtpPayload(draft: SmtpDraft): Record<string, unknown> {
  const { smtp_password, ...fields } = draft;
  return smtp_password ? { ...fields, smtp_password } : fields;
}

function SmtpSection({
  saved,
  canManage,
  defaultRecipient,
  onSaved,
}: {
  saved: NotificationIntegrationSettings;
  canManage: boolean;
  defaultRecipient: string;
  onSaved: () => Promise<unknown>;
}) {
  const [draft, setDraft] = useState<SmtpDraft>(() => smtpDraftFrom(saved));
  const [recipient, setRecipient] = useState(defaultRecipient);
  const [savedPassword, setSavedPassword] = useState(saved.smtp_password_configured);
  const [verifiedFingerprint, setVerifiedFingerprint] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<Feedback | null>(null);

  const fingerprint = JSON.stringify({ recipient: recipient.trim(), settings: smtpPayload(draft) });
  const fingerprintRef = useRef(fingerprint);
  fingerprintRef.current = fingerprint;
  const verified = draft.smtp_enabled && verifiedFingerprint === fingerprint;

  const test = useMutation({
    mutationFn: (input: { recipient: string; settings: Record<string, unknown>; fingerprint: string }) =>
      notificationApi.testEmail({ recipient: input.recipient, settings: input.settings }),
    onSuccess: (result, input) => {
      if (fingerprintRef.current === input.fingerprint) {
        setVerifiedFingerprint(input.fingerprint);
        setFeedback({ kind: "success", text: result.detail });
      } else {
        setFeedback({ kind: "info", text: "The test succeeded for the previous values. Test again to verify the latest changes." });
      }
    },
    onError: (error) => {
      setVerifiedFingerprint(null);
      setFeedback({ kind: "error", text: errorMessage(error) });
    },
  });

  const save = useMutation({
    mutationFn: notificationApi.updateIntegrations,
    onSuccess: async (result) => {
      setSavedPassword(result.smtp_password_configured);
      setDraft((value) => ({ ...value, smtp_password: "" }));
      setVerifiedFingerprint(null);
      setFeedback({ kind: "success", text: "SMTP settings saved. Future email notifications will use this configuration." });
      await onSaved();
    },
    onError: (error) => setFeedback({ kind: "error", text: errorMessage(error) }),
  });

  function update<K extends keyof SmtpDraft>(field: K, value: SmtpDraft[K]) {
    setDraft((existing) => ({ ...existing, [field]: value }));
    setFeedback(null);
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (draft.smtp_enabled && !verified) return;
    save.mutate(smtpPayload(draft));
  }

  const busy = test.isPending || save.isPending;
  return (
    <form onSubmit={submit}>
      <IntegrationCard title="Direct Email / SMTP" icon={<Mail size={15} />}
        badge={<StatusBadge value={saved.smtp_source} />}>
        <div className="space-y-4 p-4">
          <div className="flex flex-wrap items-center justify-between gap-3 border border-[var(--color-border)] bg-[var(--color-surface-subtle)] p-3">
            <label className="flex items-center gap-2 text-sm font-medium">
              <input type="checkbox" checked={draft.smtp_enabled} disabled={!canManage || busy}
                onChange={(event) => update("smtp_enabled", event.target.checked)} />
              Enable direct email notifications
            </label>
            <span className="text-xs text-[var(--color-text-muted)]">
              {draft.smtp_password ? "New password entered · not saved" : savedPassword ? "Password safely stored" : "Password not saved"}
            </span>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <label><span className="erp-label">SMTP Host</span>
              <input name="smtp_host" className="erp-field" value={draft.smtp_host}
                onChange={(e) => update("smtp_host", e.target.value)} disabled={!canManage || busy}
                placeholder="mx.matemail.online" required />
            </label>
            <label><span className="erp-label">SMTP Port</span>
              <input name="smtp_port" className="erp-field" type="number" min="1" max="65535"
                value={draft.smtp_port} onChange={(e) => update("smtp_port", Number(e.target.value))}
                disabled={!canManage || busy} required />
            </label>
            <label><span className="erp-label">SMTP Username / Mailbox</span>
              <input name="smtp_username" className="erp-field" autoComplete="off" value={draft.smtp_username}
                onChange={(e) => update("smtp_username", e.target.value)}
                disabled={!canManage || busy} placeholder="erp@netamate.com" />
            </label>
            <label><span className="erp-label">SMTP Password</span>
              <input name="smtp_password" className="erp-field" autoComplete="new-password"
                type="password" value={draft.smtp_password}
                onChange={(e) => update("smtp_password", e.target.value)}
                disabled={!canManage || busy}
                placeholder={savedPassword ? "Saved securely · leave blank to reuse" : "Enter mailbox password"} />
            </label>
            <label><span className="erp-label">From Name</span>
              <input name="smtp_from_name" className="erp-field" value={draft.smtp_from_name}
                onChange={(e) => update("smtp_from_name", e.target.value)}
                disabled={!canManage || busy} placeholder="NetaMate ERP" />
            </label>
            <label><span className="erp-label">From Email</span>
              <input name="smtp_from_email" className="erp-field" type="email" value={draft.smtp_from_email}
                onChange={(e) => update("smtp_from_email", e.target.value)}
                disabled={!canManage || busy} placeholder="erp@netamate.com" required />
            </label>
            <fieldset className="flex flex-wrap items-center gap-4 sm:col-span-2">
              <legend className="erp-label mb-1">Encryption</legend>
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={draft.smtp_use_tls} disabled={!canManage || busy}
                  onChange={(e) => {
                    setDraft((value) => ({ ...value, smtp_use_tls: e.target.checked, smtp_use_ssl: e.target.checked ? false : value.smtp_use_ssl }));
                    setFeedback(null);
                  }} /> STARTTLS (587)
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={draft.smtp_use_ssl} disabled={!canManage || busy}
                  onChange={(e) => {
                    setDraft((value) => ({ ...value, smtp_use_ssl: e.target.checked, smtp_use_tls: e.target.checked ? false : value.smtp_use_tls }));
                    setFeedback(null);
                  }} /> SSL/TLS (465)
              </label>
            </fieldset>
          </div>

          {canManage ? (
            <div className="space-y-3 border-t border-[var(--color-border)] pt-4">
              <div className="flex flex-wrap items-end gap-3">
                <label className="min-w-64 flex-1">
                  <span className="erp-label">Test recipient</span>
                  <input type="email" className="erp-field" value={recipient} disabled={busy}
                    onChange={(e) => { setRecipient(e.target.value); setFeedback(null); }}
                    placeholder="you@example.com" />
                </label>
                <button className="erp-button !min-h-10" type="button"
                  disabled={!draft.smtp_enabled || !recipient.trim() || busy}
                  onClick={() => {
                    setFeedback(null);
                    test.mutate({ recipient: recipient.trim(), settings: smtpPayload(draft), fingerprint });
                  }}>
                  <Send size={14} /> {test.isPending ? "Testing SMTP..." : "Send Test Email"}
                </button>
              </div>
              <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[var(--color-border-soft)] pt-3">
                <div className="flex min-w-0 items-center gap-2 text-xs">
                  {verified ? (
                    <span className="flex items-center gap-1.5 font-semibold text-[#126343]">
                      <CheckCircle2 size={15} /> Verified draft — ready to save
                    </span>
                  ) : draft.smtp_enabled ? (
                    <span className="text-[var(--color-text-muted)]">1. Configure → 2. Send test → 3. Save after success</span>
                  ) : (
                    <span className="text-[var(--color-text-muted)]">SMTP is disabled. Enable it to test, or save the disabled state.</span>
                  )}
                </div>
                <button className="erp-button erp-button-primary !min-h-10"
                  type="submit" disabled={busy || (draft.smtp_enabled && !verified)}>
                  {save.isPending ? "Saving SMTP..." : "Save SMTP Settings"}
                </button>
              </div>
              <InlineFeedback feedback={feedback} />
              <p className="text-[11px] text-[var(--color-text-muted)]">
                Test sends an email using the values above without saving them. A successful result means the SMTP server accepted the message, not that it has reached the inbox. Editing verified details requires a new test.
              </p>
            </div>
          ) : null}
        </div>
      </IntegrationCard>
    </form>
  );
}

type HermesDraft = {
  hermes_enabled: boolean;
  hermes_webhook_url: string;
  hermes_token: string;
  hermes_default_target: string;
};

function HermesSection({
  saved,
  canManage,
  onSaved,
}: {
  saved: NotificationIntegrationSettings;
  canManage: boolean;
  onSaved: () => Promise<unknown>;
}) {
  const [draft, setDraft] = useState<HermesDraft>({
    hermes_enabled: saved.hermes_enabled,
    hermes_webhook_url: saved.hermes_webhook_url,
    hermes_token: "",
    hermes_default_target: saved.hermes_default_target,
  });
  const [target, setTarget] = useState("");
  const [tokenSaved, setTokenSaved] = useState(saved.hermes_token_configured);
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const save = useMutation({
    mutationFn: notificationApi.updateIntegrations,
    onSuccess: async (result) => {
      setTokenSaved(result.hermes_token_configured);
      setDraft((value) => ({ ...value, hermes_token: "" }));
      setFeedback({ kind: "success", text: "Hermes settings saved." });
      await onSaved();
    },
    onError: (error) => setFeedback({ kind: "error", text: errorMessage(error) }),
  });
  const test = useMutation({
    mutationFn: notificationApi.testHermes,
    onSuccess: (result) => setFeedback({ kind: "success", text: result.detail }),
    onError: (error) => setFeedback({ kind: "error", text: errorMessage(error) }),
  });
  const busy = save.isPending || test.isPending;
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const { hermes_token, ...fields } = draft;
    save.mutate(hermes_token ? { ...fields, hermes_token } : fields);
  }
  return (
    <form onSubmit={submit}>
      <IntegrationCard title="Hermes / WhatsApp" icon={<MessageSquareText size={15} />}
        badge={<StatusBadge value={saved.hermes_source} />}>
        <div className="space-y-4 p-4">
          <label className="flex items-center justify-between gap-3 border border-[var(--color-border)] p-3 text-sm">
            <span className="flex items-center gap-2">
              <input type="checkbox" checked={draft.hermes_enabled} disabled={!canManage || busy}
                onChange={(e) => setDraft({ ...draft, hermes_enabled: e.target.checked })} />
              Enable Hermes reminders
            </span>
            <span className="text-xs text-[var(--color-text-muted)]">{tokenSaved ? "Secret stored" : "No secret"}</span>
          </label>
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="sm:col-span-2"><span className="erp-label">Hermes Webhook URL</span>
              <input className="erp-field" type="url" value={draft.hermes_webhook_url}
                onChange={(e) => setDraft({ ...draft, hermes_webhook_url: e.target.value })}
                disabled={!canManage || busy} placeholder="https://..." />
            </label>
            <label><span className="erp-label">Webhook Secret</span>
              <input className="erp-field" type="password" autoComplete="new-password"
                value={draft.hermes_token}
                onChange={(e) => setDraft({ ...draft, hermes_token: e.target.value })}
                disabled={!canManage || busy} placeholder={tokenSaved ? "Leave blank to keep saved secret" : "Enter HMAC secret"} />
            </label>
            <label><span className="erp-label">Default Target / Group</span>
              <input className="erp-field" value={draft.hermes_default_target}
                onChange={(e) => setDraft({ ...draft, hermes_default_target: e.target.value })}
                disabled={!canManage || busy} placeholder="netamate-alerts" />
            </label>
          </div>
          {canManage ? (
            <div className="space-y-3 border-t border-[var(--color-border)] pt-4">
              <div className="flex flex-wrap items-end gap-2">
                <label className="min-w-64 flex-1">
                  <span className="erp-label">Test target (optional)</span>
                  <input className="erp-field" value={target} disabled={busy}
                    onChange={(e) => setTarget(e.target.value)} placeholder="Leave blank for saved default" />
                </label>
                <button className="erp-button !min-h-10" type="button" disabled={busy}
                  onClick={() => test.mutate(target)}>{test.isPending ? "Testing..." : "Test Saved Hermes"}</button>
                <button className="erp-button erp-button-primary !min-h-10" type="submit" disabled={busy}>
                  {save.isPending ? "Saving..." : "Save Hermes Settings"}
                </button>
              </div>
              <p className="text-[11px] text-[var(--color-text-muted)]">
                Hermes test currently uses the saved webhook configuration. Save changes here without affecting SMTP settings.
              </p>
              <InlineFeedback feedback={feedback} />
            </div>
          ) : null}
        </div>
      </IntegrationCard>
    </form>
  );
}

export function LeanSettingsPage({ session }: { session: SessionPayload }) {
  const queryClient = useQueryClient();
  const organization = session.organizations.find(
    (item) => item.id === session.active_organization_id,
  );
  const entity = activeEntity(session);
  const currentMembership = membership(session);
  const canManage = can(session, "MANAGE_ORGANIZATION");

  const integrations = useQuery({
    queryKey: ["notification-integrations", session.active_organization_id],
    queryFn: notificationApi.integrations,
    enabled: Boolean(session.active_organization_id),
  });

  if (!organization) {
    return <PermissionNotice>No active organization is available for settings.</PermissionNotice>;
  }
  if (integrations.isLoading) {
    return <LoadingState label="Loading settings..." />;
  }
  if (integrations.error || !integrations.data) {
    return <ErrorState message={errorMessage(integrations.error)} />;
  }

  const current = integrations.data;
  const refresh = () =>
    queryClient.invalidateQueries({
      queryKey: ["notification-integrations", session.active_organization_id],
    });

  return (
    <>
      <PageHeader
        eyebrow="Administration"
        title="Settings"
        description="Manage organization settings and verify integrations before saving."
      />
      <div className="space-y-5 p-4 lg:p-6">
        <section className="erp-panel">
          <div className="erp-panel-header">
            <h2 className="text-sm font-semibold">Organization Context</h2>
          </div>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3">
            {[
              ["Organization", organization.name],
              ["Organization timezone", organization.timezone],
              ["Legal entity", entity?.name ?? "Organization scope"],
              ["Base currency", entity?.base_currency ?? "—"],
              ["Signed in as", session.user.display_name || session.user.email],
              ["Role", currentMembership?.role ?? "—"],
            ].map(([label, value]) => (
              <div className="border-b border-r border-[var(--color-border-soft)] p-4" key={label}>
                <div className="text-[10px] font-bold uppercase tracking-[0.08em] text-[var(--color-text-muted)]">{label}</div>
                <div className="mt-1 text-sm font-semibold">{value}</div>
              </div>
            ))}
          </div>
        </section>

        {!canManage ? (
          <PermissionNotice>
            Your role can view integration status, but only an Owner or Administrator can change credentials or run connection tests.
          </PermissionNotice>
        ) : null}

        <SmtpSection key={"smtp-" + organization.id} saved={current}
          canManage={canManage} defaultRecipient={session.user.email} onSaved={refresh} />
        <HermesSection key={"hermes-" + organization.id} saved={current}
          canManage={canManage} onSaved={refresh} />

        <section className="erp-panel">
          <div className="erp-panel-header"><h2 className="text-sm font-semibold">Hermes WhatsApp Setup</h2></div>
          <div className="space-y-2 p-4 text-xs text-[var(--color-text-muted)]">
            <p><strong>1.</strong> In Hermes, enable the generic webhook platform and create a route named <code>mateerp-alerts</code>.</p>
            <p><strong>2.</strong> Use the same Webhook Secret as above, set <code>deliver_only: true</code>, <code>deliver: whatsapp</code>, and use the message field as the prompt template.</p>
            <p><strong>3.</strong> Put that route URL here, ending in <code>/webhooks/mateerp-alerts</code>, then use <strong>Test Saved Hermes</strong>.</p>
            <p><strong>4.</strong> MateERP owns the reminder schedule. Hermes Cron is not needed for MateERP reminders; Hermes only verifies the HMAC request and delivers it to WhatsApp.</p>
            <pre className="overflow-x-auto border border-[var(--color-border)] bg-[var(--color-surface-subtle)] p-3 text-[11px]">{`platforms:
  webhook:
    enabled: true
    extra:
      routes:
        mateerp-alerts:
          secret: <same secret as MateERP>
          deliver_only: true
          deliver: whatsapp
          prompt: "{message}"`}</pre>
          </div>
        </section>

        <section className="erp-panel">
          <div className="flex items-start gap-3 p-4 text-xs text-[var(--color-text-muted)]">
            <ShieldCheck size={16} className="mt-0.5 shrink-0" />
            <div>
              SMTP passwords and Hermes webhook secrets are encrypted before database storage.
              Secret values are never returned by the API or written into audit-log state.
              SMTP test credentials are temporary and are not stored until you choose Save SMTP Settings.
            </div>
          </div>
        </section>
      </div>
    </>
  );
}
