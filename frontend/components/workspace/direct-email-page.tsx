"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { MailPlus, Send, XCircle } from "lucide-react";
import Link from "next/link";
import { useRef, useState } from "react";

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
  type DirectEmailNotification,
} from "@/lib/phase8-api";

function membership(session: SessionPayload) {
  return session.memberships.find(
    (item) => item.organization_id === session.active_organization_id,
  );
}

function can(session: SessionPayload, permission: string) {
  return membership(session)?.permissions.includes(permission) ?? false;
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

function emails(value: FormDataEntryValue | null) {
  return String(value ?? "")
    .split(/[\n,;]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

export function DirectEmailPage({ session }: { session: SessionPayload }) {
  const queryClient = useQueryClient();
  const formRef = useRef<HTMLFormElement>(null);
  const [composing, setComposing] = useState(false);
  const [message, setMessage] = useState("");
  const allowed = can(session, "VIEW_NOTIFICATIONS");
  const manageAllowed = can(session, "MANAGE_ORGANIZATION");

  const rows = useQuery({
    queryKey: [
      "direct-email-notifications",
      session.active_organization_id,
      session.active_legal_entity_id,
    ],
    queryFn: notificationApi.directEmails,
    enabled: allowed && Boolean(session.active_organization_id),
  });
  const integrations = useQuery({
    queryKey: ["notification-integrations", session.active_organization_id],
    queryFn: notificationApi.integrations,
    enabled: allowed && Boolean(session.active_organization_id),
  });

  const create = useMutation({
    mutationFn: notificationApi.createDirectEmail,
    onSuccess: async (result) => {
      setMessage(
        result.status === "SENT"
          ? "Email sent."
          : result.status === "SCHEDULED"
            ? "Email scheduled."
            : "Draft saved.",
      );
      setComposing(false);
      formRef.current?.reset();
      await queryClient.invalidateQueries({
        queryKey: ["direct-email-notifications"],
      });
    },
  });
  const send = useMutation({
    mutationFn: notificationApi.sendDirectEmail,
    onSuccess: async (result) => {
      setMessage(result.status === "SENT" ? "Email sent." : "Email send failed.");
      await queryClient.invalidateQueries({
        queryKey: ["direct-email-notifications"],
      });
    },
  });
  const cancel = useMutation({
    mutationFn: notificationApi.cancelDirectEmail,
    onSuccess: async () => {
      setMessage("Scheduled email cancelled.");
      await queryClient.invalidateQueries({
        queryKey: ["direct-email-notifications"],
      });
    },
  });

  function submit(action: "DRAFT" | "SCHEDULE" | "SEND_NOW") {
    if (!formRef.current) return;
    const form = new FormData(formRef.current);
    const scheduledLocal = String(form.get("scheduled_for") ?? "").trim();
    create.mutate({
      action,
      to_recipients: emails(form.get("to_recipients")),
      cc_recipients: emails(form.get("cc_recipients")),
      bcc_recipients: emails(form.get("bcc_recipients")),
      subject: String(form.get("subject") ?? "").trim(),
      body: String(form.get("body") ?? ""),
      schedule_timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
      scheduled_for: scheduledLocal ? new Date(scheduledLocal).toISOString() : null,
    });
  }

  if (!allowed) {
    return (
      <PermissionNotice>
        You do not have permission to view email notifications.
      </PermissionNotice>
    );
  }
  if (rows.isLoading || integrations.isLoading) {
    return <LoadingState label="Loading email notifications..." />;
  }
  if (rows.error || integrations.error) {
    return <ErrorState message={errorMessage(rows.error ?? integrations.error)} />;
  }

  const data = rows.data?.results ?? [];
  const scheduled = data.filter((item) => item.status === "SCHEDULED").length;
  const failed = data.filter((item) => item.status === "FAILED").length;
  const sentCount = data.filter((item) => item.status === "SENT").length;
  const smtpReady = Boolean(integrations.data?.smtp_enabled);

  const columns: Array<TableColumn<DirectEmailNotification>> = [
    {
      key: "subject",
      label: "Email",
      render: (row) => (
        <div>
          <strong>{row.subject}</strong>
          <div className="mt-0.5 max-w-lg truncate text-xs text-[var(--color-text-muted)]">
            To: {row.to_recipients.join(", ")}
          </div>
        </div>
      ),
    },
    {
      key: "status",
      label: "Status",
      render: (row) => <StatusBadge value={row.status} />,
    },
    {
      key: "scheduled",
      label: "Scheduled",
      render: (row) => timestamp(row.scheduled_for),
    },
    { key: "sent", label: "Sent", render: (row) => timestamp(row.sent_at) },
    {
      key: "attempts",
      label: "Attempts",
      numeric: true,
      render: (row) => String(row.attempt_count),
    },
    {
      key: "error",
      label: "Error",
      render: (row) =>
        row.last_error ? (
          <span className="text-xs text-[var(--color-danger)]">{row.last_error}</span>
        ) : (
          "—"
        ),
    },
    {
      key: "actions",
      label: "Actions",
      render: (row) => (
        <div className="flex gap-1">
          {manageAllowed && ["DRAFT", "FAILED", "SCHEDULED"].includes(row.status) ? (
            <button
              className="erp-button !h-7 !min-h-7 !px-2 text-[11px]"
              disabled={send.isPending}
              onClick={() => send.mutate(row.id)}
              type="button"
            >
              <Send size={12} /> Send Now
            </button>
          ) : null}
          {manageAllowed && ["DRAFT", "FAILED", "SCHEDULED"].includes(row.status) ? (
            <button
              className="erp-button !h-7 !min-h-7 !px-2 text-[11px]"
              disabled={cancel.isPending}
              onClick={() => cancel.mutate(row.id)}
              type="button"
            >
              <XCircle size={12} /> Cancel
            </button>
          ) : null}
        </div>
      ),
    },
  ];

  return (
    <>
      <PageHeader
        eyebrow="Alerts & Delivery"
        title="Email Notifications"
        description="Send or schedule direct SMTP email from MateERP without depending on Hermes."
        actions={
          manageAllowed ? (
            <button
              className="erp-button erp-button-primary"
              onClick={() => setComposing((value) => !value)}
              type="button"
            >
              <MailPlus size={14} /> New Email
            </button>
          ) : undefined
        }
      />
      <MetricStrip
        metrics={[
          { label: "Sent", value: String(sentCount) },
          { label: "Scheduled", value: String(scheduled) },
          {
            label: "Failed",
            value: String(failed),
            tone: failed ? "bad" : "good",
          },
          {
            label: "SMTP",
            value: smtpReady ? "Ready" : "Not configured",
            tone: smtpReady ? "good" : "bad",
          },
        ]}
      />
      <div className="space-y-4 p-4 lg:p-6">
        {!smtpReady ? (
          <PermissionNotice>
            Direct Email SMTP is not enabled. Configure the mailbox in{" "}
            <Link className="font-semibold underline" href="/administration/settings">
              Settings
            </Link>
            .
          </PermissionNotice>
        ) : null}

        {composing && manageAllowed ? (
          <section className="erp-panel">
            <div className="erp-panel-header">
              <div>
                <h2 className="text-sm font-semibold">Compose Email Notification</h2>
                <p className="mt-0.5 text-xs text-[var(--color-text-muted)]">
                  Use commas or new lines for multiple recipients.
                </p>
              </div>
            </div>
            <form className="grid gap-4 p-4 sm:grid-cols-2" ref={formRef}>
              <label className="sm:col-span-2">
                <span className="erp-label">To</span>
                <textarea
                  className="erp-field min-h-20"
                  name="to_recipients"
                  placeholder="rizwan@netamate.com, shahbaj@netamate.com"
                  required
                />
              </label>
              <label>
                <span className="erp-label">CC</span>
                <input className="erp-field" name="cc_recipients" />
              </label>
              <label>
                <span className="erp-label">BCC</span>
                <input className="erp-field" name="bcc_recipients" />
              </label>
              <label className="sm:col-span-2">
                <span className="erp-label">Subject</span>
                <input className="erp-field" name="subject" required />
              </label>
              <label className="sm:col-span-2">
                <span className="erp-label">Body</span>
                <textarea className="erp-field min-h-40" name="body" required />
              </label>
              <label>
                <span className="erp-label">Schedule date & time</span>
                <input className="erp-field" name="scheduled_for" type="datetime-local" />
              </label>
              <div className="flex items-end text-xs text-[var(--color-text-muted)]">
                Time is interpreted in your browser timezone and stored safely in UTC.
              </div>
              <div className="flex flex-wrap justify-end gap-2 border-t border-[var(--color-border)] pt-4 sm:col-span-2">
                <button
                  className="erp-button"
                  disabled={create.isPending}
                  onClick={() => submit("DRAFT")}
                  type="button"
                >
                  Save Draft
                </button>
                <button
                  className="erp-button"
                  disabled={create.isPending}
                  onClick={() => submit("SCHEDULE")}
                  type="button"
                >
                  Schedule
                </button>
                <button
                  className="erp-button erp-button-primary"
                  disabled={create.isPending || !smtpReady}
                  onClick={() => submit("SEND_NOW")}
                  type="button"
                >
                  <Send size={13} /> Send Now
                </button>
              </div>
            </form>
          </section>
        ) : null}

        {create.error || send.error || cancel.error ? (
          <ErrorState message={errorMessage(create.error ?? send.error ?? cancel.error)} />
        ) : null}
        {message ? (
          <div className="border border-[var(--color-border)] bg-white px-4 py-3 text-sm">
            {message}
          </div>
        ) : null}

        <DataTable
          columns={columns}
          rows={data}
          rowKey={(row) => row.id}
          emptyTitle="No email notifications"
          emptyDescription="Create a direct email notification to send now or schedule for later."
        />
      </div>
    </>
  );
}
