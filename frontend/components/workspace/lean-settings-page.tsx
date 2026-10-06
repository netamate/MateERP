"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Mail, MessageSquareText, ShieldCheck } from "lucide-react";
import { useState, type FormEvent, type ReactNode } from "react";

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

function serializeSettings(
  event: FormEvent<HTMLFormElement>,
  current: NotificationIntegrationSettings,
) {
  event.preventDefault();
  const data = new FormData(event.currentTarget);
  const payload: Record<string, unknown> = {
    smtp_enabled: data.get("smtp_enabled") === "on",
    smtp_host: String(data.get("smtp_host") ?? "").trim(),
    smtp_port: Number(data.get("smtp_port") || 587),
    smtp_username: String(data.get("smtp_username") ?? "").trim(),
    smtp_use_tls: data.get("smtp_use_tls") === "on",
    smtp_use_ssl: data.get("smtp_use_ssl") === "on",
    smtp_from_name: String(data.get("smtp_from_name") ?? "").trim(),
    smtp_from_email: String(data.get("smtp_from_email") ?? "").trim(),
    hermes_enabled: data.get("hermes_enabled") === "on",
    hermes_webhook_url: String(data.get("hermes_webhook_url") ?? "").trim(),
    hermes_default_target: String(data.get("hermes_default_target") ?? "").trim(),
  };

  const smtpPassword = String(data.get("smtp_password") ?? "");
  if (smtpPassword) payload.smtp_password = smtpPassword;

  const hermesToken = String(data.get("hermes_token") ?? "");
  if (hermesToken) payload.hermes_token = hermesToken;

  return payload;
}

function IntegrationCard({
  title,
  icon,
  children,
}: {
  title: string;
  icon: React.ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="erp-panel">
      <div className="erp-panel-header">
        <div className="flex items-center gap-2">
          {icon}
          <h2 className="text-sm font-semibold">{title}</h2>
        </div>
      </div>
      {children}
    </section>
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
  const [testEmail, setTestEmail] = useState(session.user.email);
  const [testHermesTarget, setTestHermesTarget] = useState("");
  const [message, setMessage] = useState("");

  const integrations = useQuery({
    queryKey: ["notification-integrations", session.active_organization_id],
    queryFn: notificationApi.integrations,
    enabled: Boolean(session.active_organization_id),
  });

  const save = useMutation({
    mutationFn: notificationApi.updateIntegrations,
    onSuccess: async () => {
      setMessage("Integration settings saved.");
      await queryClient.invalidateQueries({ queryKey: ["notification-integrations"] });
    },
  });

  const smtpTest = useMutation({
    mutationFn: notificationApi.testEmail,
    onSuccess: (result) => setMessage(result.detail),
  });

  const hermesTest = useMutation({
    mutationFn: notificationApi.testHermes,
    onSuccess: (result) => setMessage(result.detail),
  });

  if (!organization) {
    return <PermissionNotice>Select an organization to manage settings.</PermissionNotice>;
  }
  if (integrations.isLoading) {
    return <LoadingState label="Loading settings..." />;
  }
  if (integrations.error || !integrations.data) {
    return <ErrorState message={errorMessage(integrations.error)} />;
  }

  const current = integrations.data;
  const mutationError = save.error ?? smtpTest.error ?? hermesTest.error;

  return (
    <>
      <PageHeader
        eyebrow="Administration"
        title="Settings"
        description="Organization context and notification integrations for MateERP."
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
              <div
                className="border-b border-r border-[var(--color-border-soft)] p-4"
                key={label}
              >
                <div className="text-[10px] font-bold uppercase tracking-[0.08em] text-[var(--color-text-muted)]">
                  {label}
                </div>
                <div className="mt-1 text-sm font-semibold">{value}</div>
              </div>
            ))}
          </div>
        </section>

        {!canManage ? (
          <PermissionNotice>
            Your role can view integration status, but only an Owner or Administrator can
            change credentials or run connection tests.
          </PermissionNotice>
        ) : null}

        <form
          className="space-y-5"
          onSubmit={(event) => save.mutate(serializeSettings(event, current))}
        >
          <IntegrationCard title="Email / SMTP" icon={<Mail size={15} />}>
            <div className="grid gap-4 p-4 sm:grid-cols-2">
              <div className="sm:col-span-2 flex items-center justify-between border border-[var(--color-border)] p-3">
                <label className="flex items-center gap-2 text-sm">
                  <input
                    defaultChecked={current.smtp_enabled}
                    disabled={!canManage}
                    name="smtp_enabled"
                    type="checkbox"
                  />
                  Enable email reminders
                </label>
                <div className="flex items-center gap-2">
                  <StatusBadge value={current.smtp_source} />
                  <span className="text-xs text-[var(--color-text-muted)]">
                    {current.smtp_password_configured ? "Password configured" : "No password"}
                  </span>
                </div>
              </div>

              <label>
                <span className="erp-label">SMTP Host</span>
                <input
                  className="erp-field"
                  defaultValue={current.smtp_host}
                  disabled={!canManage}
                  name="smtp_host"
                  placeholder="smtp.example.com"
                />
              </label>
              <label>
                <span className="erp-label">SMTP Port</span>
                <input
                  className="erp-field"
                  defaultValue={current.smtp_port}
                  disabled={!canManage}
                  min="1"
                  max="65535"
                  name="smtp_port"
                  type="number"
                />
              </label>
              <label>
                <span className="erp-label">SMTP Username / Mailbox</span>
                <input
                  className="erp-field"
                  defaultValue={current.smtp_username}
                  disabled={!canManage}
                  name="smtp_username"
                  placeholder="alerts@netamate.com"
                />
              </label>
              <label>
                <span className="erp-label">
                  SMTP Password {current.smtp_password_configured ? "· configured" : ""}
                </span>
                <input
                  autoComplete="new-password"
                  className="erp-field"
                  disabled={!canManage}
                  name="smtp_password"
                  placeholder={
                    current.smtp_password_configured
                      ? "••••••••  Leave blank to keep current password"
                      : "Enter SMTP password"
                  }
                  type="password"
                />
              </label>
              <label>
                <span className="erp-label">From Name</span>
                <input
                  className="erp-field"
                  defaultValue={current.smtp_from_name}
                  disabled={!canManage}
                  name="smtp_from_name"
                  placeholder="MateERP"
                />
              </label>
              <label>
                <span className="erp-label">From Email</span>
                <input
                  className="erp-field"
                  defaultValue={current.smtp_from_email}
                  disabled={!canManage}
                  name="smtp_from_email"
                  placeholder="alerts@netamate.com"
                  type="email"
                />
              </label>
              <div className="flex flex-wrap gap-4 sm:col-span-2">
                <label className="flex items-center gap-2 text-sm">
                  <input
                    defaultChecked={current.smtp_use_tls}
                    disabled={!canManage}
                    name="smtp_use_tls"
                    type="checkbox"
                  />
                  TLS
                </label>
                <label className="flex items-center gap-2 text-sm">
                  <input
                    defaultChecked={current.smtp_use_ssl}
                    disabled={!canManage}
                    name="smtp_use_ssl"
                    type="checkbox"
                  />
                  SSL
                </label>
              </div>

              {canManage ? (
                <div className="flex flex-wrap items-end gap-2 border-t border-[var(--color-border)] pt-4 sm:col-span-2">
                  <label className="min-w-72 flex-1">
                    <span className="erp-label">Send test email to</span>
                    <input
                      className="erp-field"
                      onChange={(event) => setTestEmail(event.target.value)}
                      type="email"
                      value={testEmail}
                    />
                  </label>
                  <button
                    className="erp-button"
                    disabled={smtpTest.isPending || !testEmail}
                    onClick={() => smtpTest.mutate(testEmail)}
                    type="button"
                  >
                    {smtpTest.isPending ? "Testing..." : "Send Test Email"}
                  </button>
                </div>
              ) : null}
            </div>
          </IntegrationCard>

          <IntegrationCard
            title="Hermes"
            icon={<MessageSquareText size={15} />}
          >
            <div className="grid gap-4 p-4 sm:grid-cols-2">
              <div className="sm:col-span-2 flex items-center justify-between border border-[var(--color-border)] p-3">
                <label className="flex items-center gap-2 text-sm">
                  <input
                    defaultChecked={current.hermes_enabled}
                    disabled={!canManage}
                    name="hermes_enabled"
                    type="checkbox"
                  />
                  Enable Hermes reminders
                </label>
                <div className="flex items-center gap-2">
                  <StatusBadge value={current.hermes_source} />
                  <span className="text-xs text-[var(--color-text-muted)]">
                    {current.hermes_token_configured ? "Token configured" : "No token"}
                  </span>
                </div>
              </div>
              <label className="sm:col-span-2">
                <span className="erp-label">Hermes Webhook URL</span>
                <input
                  className="erp-field"
                  defaultValue={current.hermes_webhook_url}
                  disabled={!canManage}
                  name="hermes_webhook_url"
                  placeholder="https://..."
                  type="url"
                />
              </label>
              <label>
                <span className="erp-label">
                  Hermes Token {current.hermes_token_configured ? "· configured" : ""}
                </span>
                <input
                  autoComplete="new-password"
                  className="erp-field"
                  disabled={!canManage}
                  name="hermes_token"
                  placeholder={
                    current.hermes_token_configured
                      ? "••••••••  Leave blank to keep current token"
                      : "Enter token"
                  }
                  type="password"
                />
              </label>
              <label>
                <span className="erp-label">Default Target / Group</span>
                <input
                  className="erp-field"
                  defaultValue={current.hermes_default_target}
                  disabled={!canManage}
                  name="hermes_default_target"
                  placeholder="netamate-alerts"
                />
              </label>
              {canManage ? (
                <div className="flex flex-wrap items-end gap-2 border-t border-[var(--color-border)] pt-4 sm:col-span-2">
                  <label className="min-w-72 flex-1">
                    <span className="erp-label">Test target (optional)</span>
                    <input
                      className="erp-field"
                      onChange={(event) => setTestHermesTarget(event.target.value)}
                      placeholder="Leave blank for default target"
                      value={testHermesTarget}
                    />
                  </label>
                  <button
                    className="erp-button"
                    disabled={hermesTest.isPending}
                    onClick={() => hermesTest.mutate(testHermesTarget)}
                    type="button"
                  >
                    {hermesTest.isPending ? "Testing..." : "Send Test Hermes"}
                  </button>
                </div>
              ) : null}
            </div>
          </IntegrationCard>

          <section className="erp-panel">
            <div className="flex items-start gap-3 p-4 text-xs text-[var(--color-text-muted)]">
              <ShieldCheck size={16} className="mt-0.5 shrink-0" />
              <div>
                SMTP passwords and Hermes tokens are encrypted before database storage.
                Secret values are never returned by the API or written into audit-log state.
                Environment variables remain available only as a fallback until ERP settings
                are saved.
              </div>
            </div>
          </section>

          {mutationError ? <ErrorState message={errorMessage(mutationError)} /> : null}
          {message ? (
            <div className="border border-[var(--color-border)] bg-white px-4 py-3 text-sm">
              {message}
            </div>
          ) : null}

          {canManage ? (
            <div className="flex justify-end">
              <button
                className="erp-button erp-button-primary"
                disabled={save.isPending}
                type="submit"
              >
                {save.isPending ? "Saving..." : "Save Integration Settings"}
              </button>
            </div>
          ) : null}
        </form>
      </div>
    </>
  );
}
