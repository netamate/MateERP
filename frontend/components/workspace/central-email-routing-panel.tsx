"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  History,
  MailCheck,
  Pencil,
  Plus,
  RefreshCcw,
  Trash2,
  Users,
} from "lucide-react";
import Link from "next/link";
import { useState, type FormEvent } from "react";

import {
  DataTable,
  ErrorState,
  LoadingState,
  PermissionNotice,
  StatusBadge,
  type TableColumn,
} from "@/components/ui/erp";
import type { SessionPayload } from "@/lib/api";
import {
  notificationApi,
  type CentralEmailEvent,
  type CentralEmailRecipient,
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

function contextString(row: NotificationDelivery, key: string) {
  const value = row.context?.[key];
  return typeof value === "string" ? value : "";
}

function contextBoolean(row: NotificationDelivery, key: string) {
  return row.context?.[key] === true;
}

export function CentralEmailRoutingPanel({
  session,
  smtpReady,
}: {
  session: SessionPayload;
  smtpReady: boolean;
}) {
  const queryClient = useQueryClient();
  const allowed = can(session, "VIEW_NOTIFICATIONS");
  const manageAllowed = can(session, "MANAGE_NOTIFICATIONS");
  const [editorOpen, setEditorOpen] = useState(false);
  const [editing, setEditing] = useState<CentralEmailRecipient | null>(null);
  const [selectedEvents, setSelectedEvents] = useState<CentralEmailEvent[]>([]);
  const [deliveryStatus, setDeliveryStatus] = useState("");
  const [deliverySignal, setDeliverySignal] = useState("");
  const [message, setMessage] = useState("");

  const recipients = useQuery({
    queryKey: ["central-email-recipients", session.active_organization_id],
    queryFn: notificationApi.centralRecipients,
    enabled: allowed && Boolean(session.active_organization_id),
  });
  const events = useQuery({
    queryKey: ["central-email-events"],
    queryFn: notificationApi.centralRecipientEvents,
    enabled: allowed && Boolean(session.active_organization_id),
  });
  const deliveries = useQuery({
    queryKey: [
      "central-email-deliveries",
      session.active_organization_id,
      session.active_legal_entity_id,
      deliveryStatus,
      deliverySignal,
    ],
    queryFn: () =>
      notificationApi.deliveries({
        channel: "EMAIL",
        central_only: true,
        status: deliveryStatus || undefined,
        signal: deliverySignal || undefined,
      }),
    enabled: allowed && Boolean(session.active_organization_id),
  });

  const saveRecipient = useMutation({
    mutationFn: ({
      id,
      body,
    }: {
      id?: string;
      body: Record<string, unknown>;
    }) =>
      id
        ? notificationApi.updateCentralRecipient(id, body)
        : notificationApi.createCentralRecipient(body),
    onSuccess: async (recipient) => {
      setMessage(
        editing
          ? `${recipient.email} routing updated.`
          : `${recipient.email} added to central routing.`,
      );
      setEditorOpen(false);
      setEditing(null);
      setSelectedEvents([]);
      await queryClient.invalidateQueries({ queryKey: ["central-email-recipients"] });
    },
  });

  const toggleRecipient = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) =>
      notificationApi.updateCentralRecipient(id, { enabled }),
    onSuccess: async (recipient) => {
      setMessage(
        `${recipient.email} ${recipient.enabled ? "enabled" : "disabled"}.`,
      );
      await queryClient.invalidateQueries({ queryKey: ["central-email-recipients"] });
    },
  });

  const deleteRecipient = useMutation({
    mutationFn: notificationApi.deleteCentralRecipient,
    onSuccess: async () => {
      setMessage("Central recipient removed.");
      await queryClient.invalidateQueries({ queryKey: ["central-email-recipients"] });
    },
  });

  const retryDelivery = useMutation({
    mutationFn: notificationApi.retryDelivery,
    onSuccess: async (delivery) => {
      setMessage(
        delivery.status === "SENT"
          ? `Delivery to ${delivery.destination} succeeded.`
          : `Delivery to ${delivery.destination} is still ${delivery.status.toLowerCase()}.`,
      );
      await queryClient.invalidateQueries({ queryKey: ["central-email-deliveries"] });
    },
  });

  function openCreate() {
    setEditing(null);
    setSelectedEvents([]);
    setEditorOpen(true);
    setMessage("");
  }

  function openEdit(recipient: CentralEmailRecipient) {
    setEditing(recipient);
    setSelectedEvents(recipient.event_types);
    setEditorOpen(true);
    setMessage("");
  }

  function toggleEvent(value: CentralEmailEvent) {
    setSelectedEvents((current) =>
      current.includes(value)
        ? current.filter((item) => item !== value)
        : [...current, value],
    );
  }

  function submitRecipient(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    saveRecipient.mutate({
      id: editing?.id,
      body: {
        name: String(form.get("name") ?? "").trim(),
        email: String(form.get("email") ?? "").trim(),
        recipient_type: String(form.get("recipient_type") ?? "TO"),
        enabled: form.get("enabled") === "on",
        attach_documents: form.get("attach_documents") === "on",
        event_types: selectedEvents,
      },
    });
  }

  if (!allowed) return null;
  if (recipients.isLoading || events.isLoading || deliveries.isLoading) {
    return <LoadingState label="Loading central email routing..." />;
  }
  if (recipients.error || events.error || deliveries.error) {
    return (
      <ErrorState
        message={errorMessage(recipients.error ?? events.error ?? deliveries.error)}
      />
    );
  }

  const recipientRows = recipients.data ?? [];
  const eventRows = events.data ?? [];
  const deliveryRows = deliveries.data?.results ?? [];
  const activeRecipients = recipientRows.filter((row) => row.enabled).length;
  const routeCount = recipientRows.reduce(
    (total, row) => total + row.event_types.length,
    0,
  );
  const deliverySent = deliveryRows.filter((row) => row.status === "SENT").length;
  const deliveryFailed = deliveryRows.filter((row) => row.status === "FAILED").length;
  const eventLabels = new Map(eventRows.map((row) => [row.value, row.label]));

  const recipientColumns: Array<TableColumn<CentralEmailRecipient>> = [
    {
      key: "recipient",
      label: "Recipient",
      render: (row) => (
        <div>
          <strong>{row.name || row.email}</strong>
          {row.name ? (
            <div className="mt-0.5 text-xs text-[var(--color-text-muted)]">
              {row.email}
            </div>
          ) : null}
        </div>
      ),
    },
    {
      key: "role",
      label: "Role",
      render: (row) => <StatusBadge value={row.recipient_type} />,
    },
    {
      key: "events",
      label: "Notifications",
      render: (row) =>
        row.event_types.length ? (
          <div className="max-w-xl text-xs leading-5">
            {row.event_types
              .map((value) => eventLabels.get(value) ?? value)
              .join(" · ")}
          </div>
        ) : (
          <span className="text-xs text-[var(--color-text-muted)]">None selected</span>
        ),
    },
    {
      key: "attachment",
      label: "Documents",
      render: (row) => (row.attach_documents ? "Attach when available" : "Link only"),
    },
    {
      key: "status",
      label: "Status",
      render: (row) => <StatusBadge value={row.enabled ? "ACTIVE" : "DISABLED"} />,
    },
    {
      key: "actions",
      label: "Actions",
      render: (row) =>
        manageAllowed ? (
          <div className="flex flex-wrap gap-1">
            <button
              className="erp-button !h-7 !min-h-7 !px-2 text-[11px]"
              onClick={() => openEdit(row)}
              type="button"
            >
              <Pencil size={12} /> Edit
            </button>
            <button
              className="erp-button !h-7 !min-h-7 !px-2 text-[11px]"
              disabled={toggleRecipient.isPending}
              onClick={() =>
                toggleRecipient.mutate({ id: row.id, enabled: !row.enabled })
              }
              type="button"
            >
              {row.enabled ? "Disable" : "Enable"}
            </button>
            <button
              className="erp-button !h-7 !min-h-7 !px-2 text-[11px]"
              disabled={deleteRecipient.isPending}
              onClick={() => {
                if (
                  window.confirm(
                    `Remove ${row.email} from central email routing?`,
                  )
                ) {
                  deleteRecipient.mutate(row.id);
                }
              }}
              type="button"
            >
              <Trash2 size={12} /> Remove
            </button>
          </div>
        ) : (
          "—"
        ),
    },
  ];

  const deliveryColumns: Array<TableColumn<NotificationDelivery>> = [
    {
      key: "event",
      label: "Event",
      render: (row) => (
        <div>
          <strong>
            {eventLabels.get(row.signal as CentralEmailEvent) ?? row.signal}
          </strong>
          <div className="mt-0.5 text-xs text-[var(--color-text-muted)]">
            {row.source_label}
          </div>
        </div>
      ),
    },
    {
      key: "destination",
      label: "Recipient",
      render: (row) => (
        <div>
          <span>{row.destination}</span>
          {contextString(row, "recipient_type") ? (
            <div className="mt-0.5 text-[10px] text-[var(--color-text-muted)]">
              {contextString(row, "recipient_type")}
            </div>
          ) : null}
        </div>
      ),
    },
    {
      key: "attachment",
      label: "Document",
      render: (row) => {
        if (contextBoolean(row, "attach_document")) return "Attached";
        const skipped = contextString(row, "attachment_skipped_reason");
        if (skipped) {
          return <span className="text-xs text-[var(--color-warning)]">{skipped}</span>;
        }
        if (row.context?.attachment_requested === false) return "Link only";
        return "—";
      },
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
      key: "time",
      label: "Sent / Created",
      render: (row) => timestamp(row.sent_at ?? row.created_at),
    },
    {
      key: "result",
      label: "Result",
      render: (row) => (
        <div className="max-w-sm">
          {row.last_error ? (
            <div className="text-xs text-[var(--color-danger)]">{row.last_error}</div>
          ) : (
            <span className="text-xs text-[var(--color-text-muted)]">
              {row.status === "SENT" ? "Delivered successfully" : "Waiting for delivery"}
            </span>
          )}
          {manageAllowed && row.status === "FAILED" ? (
            <button
              className="erp-button mt-1 !h-7 !min-h-7 !px-2 text-[11px]"
              disabled={retryDelivery.isPending}
              onClick={() => retryDelivery.mutate(row.id)}
              type="button"
            >
              <RefreshCcw size={12} /> Retry
            </button>
          ) : null}
        </div>
      ),
    },
  ];

  const mutationError =
    saveRecipient.error ??
    toggleRecipient.error ??
    deleteRecipient.error ??
    retryDelivery.error;

  return (
    <div className="space-y-4">
      <section className="erp-panel">
        <div className="erp-panel-header">
          <div>
            <div className="flex items-center gap-2">
              <Users size={15} />
              <h2 className="text-sm font-semibold">Central Notification Recipients</h2>
            </div>
            <p className="mt-1 text-xs text-[var(--color-text-muted)]">
              Add each email once, then choose exactly which ERP events that address receives.
              Subscription records only decide whether their own email notifications are enabled.
            </p>
          </div>
          <div className="flex gap-2">
            <Link className="erp-button" href="/administration/email-templates">
              Email Templates
            </Link>
            {manageAllowed ? (
              <button
                className="erp-button erp-button-primary"
                onClick={openCreate}
                type="button"
              >
                <Plus size={13} /> Add Recipient
              </button>
            ) : null}
          </div>
        </div>

        <div className="grid border-b border-[var(--color-border)] sm:grid-cols-4">
          {[
            ["Active recipients", String(activeRecipients)],
            ["Configured routes", String(routeCount)],
            ["Recent sent", String(deliverySent)],
            ["Recent failed", String(deliveryFailed)],
          ].map(([label, value]) => (
            <div className="border-r border-[var(--color-border)] px-4 py-3 last:border-r-0" key={label}>
              <div className="text-[10px] uppercase tracking-wide text-[var(--color-text-muted)]">
                {label}
              </div>
              <div className="mt-1 text-lg font-semibold">{value}</div>
            </div>
          ))}
        </div>

        {!smtpReady ? (
          <div className="p-4">
            <PermissionNotice>
              Automatic email routing is configured here, but SMTP is currently disabled.
              Configure SMTP in{" "}
              <Link className="font-semibold underline" href="/administration/settings">
                Settings
              </Link>
              .
            </PermissionNotice>
          </div>
        ) : null}

        {editorOpen && manageAllowed ? (
          <form
            className="border-b border-[var(--color-border)] p-4"
            onSubmit={submitRecipient}
          >
            <div className="mb-4 flex items-start justify-between gap-3">
              <div>
                <h3 className="text-sm font-semibold">
                  {editing ? "Edit Central Recipient" : "Add Central Recipient"}
                </h3>
                <p className="mt-0.5 text-xs text-[var(--color-text-muted)]">
                  Event choices are organization-wide. Document attachments follow the
                  recipient preference below.
                </p>
              </div>
              <button
                className="erp-button"
                onClick={() => {
                  setEditorOpen(false);
                  setEditing(null);
                  setSelectedEvents([]);
                }}
                type="button"
              >
                Cancel
              </button>
            </div>

            <div className="grid gap-4 md:grid-cols-3">
              <label>
                <span className="erp-label">Name (optional)</span>
                <input
                  className="erp-field"
                  defaultValue={editing?.name ?? ""}
                  name="name"
                  placeholder="Finance"
                />
              </label>
              <label>
                <span className="erp-label">Email</span>
                <input
                  className="erp-field"
                  defaultValue={editing?.email ?? ""}
                  name="email"
                  placeholder="finance@example.com"
                  required
                  type="email"
                />
              </label>
              <label>
                <span className="erp-label">Recipient role</span>
                <select
                  className="erp-field"
                  defaultValue={editing?.recipient_type ?? "TO"}
                  name="recipient_type"
                >
                  <option value="TO">To</option>
                  <option value="CC">CC</option>
                  <option value="BCC">BCC</option>
                </select>
              </label>
            </div>

            <div className="mt-4">
              <span className="erp-label">Notification events</span>
              <div className="grid border border-[var(--color-border)] md:grid-cols-2 xl:grid-cols-3">
                {eventRows.map((option) => (
                  <label
                    className="flex items-center gap-2 border-b border-r border-[var(--color-border)] px-3 py-2 text-xs"
                    key={option.value}
                  >
                    <input
                      checked={selectedEvents.includes(option.value)}
                      onChange={() => toggleEvent(option.value)}
                      type="checkbox"
                    />
                    {option.label}
                  </label>
                ))}
              </div>
            </div>

            <div className="mt-4 flex flex-wrap items-center gap-5 border-t border-[var(--color-border)] pt-4">
              <label className="flex items-center gap-2 text-xs">
                <input
                  defaultChecked={editing?.enabled ?? true}
                  name="enabled"
                  type="checkbox"
                />
                Active recipient
              </label>
              <label className="flex items-center gap-2 text-xs">
                <input
                  defaultChecked={editing?.attach_documents ?? true}
                  name="attach_documents"
                  type="checkbox"
                />
                Attach documents when available
              </label>
              <button
                className="erp-button erp-button-primary ml-auto"
                disabled={saveRecipient.isPending}
                type="submit"
              >
                <MailCheck size={13} /> {editing ? "Save Changes" : "Add Recipient"}
              </button>
            </div>
          </form>
        ) : null}

        {!manageAllowed ? (
          <div className="p-4">
            <PermissionNotice>
              You can view central routing, but notification-management permission is
              required to change recipients.
            </PermissionNotice>
          </div>
        ) : null}

        <div className="p-4">
          <DataTable
            columns={recipientColumns}
            rows={recipientRows}
            rowKey={(row) => row.id}
            emptyTitle="No central recipients"
            emptyDescription="Add a recipient and choose which ERP events should be delivered to it."
          />
        </div>
      </section>

      <section className="erp-panel">
        <div className="erp-panel-header">
          <div>
            <div className="flex items-center gap-2">
              <History size={15} />
              <h2 className="text-sm font-semibold">Automatic Delivery History</h2>
            </div>
            <p className="mt-1 text-xs text-[var(--color-text-muted)]">
              Centralized event email attempts, attachment state, failures and retries.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <select
              className="erp-field !w-auto min-w-40"
              onChange={(event) => setDeliverySignal(event.target.value)}
              value={deliverySignal}
            >
              <option value="">All events</option>
              {eventRows.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            <select
              className="erp-field !w-auto min-w-36"
              onChange={(event) => setDeliveryStatus(event.target.value)}
              value={deliveryStatus}
            >
              <option value="">All statuses</option>
              <option value="SENT">Sent</option>
              <option value="FAILED">Failed</option>
              <option value="PENDING">Pending</option>
            </select>
          </div>
        </div>
        <div className="p-4">
          <DataTable
            columns={deliveryColumns}
            rows={deliveryRows}
            rowKey={(row) => row.id}
            emptyTitle="No automatic email deliveries"
            emptyDescription="Delivery records will appear after a configured ERP event triggers an email."
          />
        </div>
      </section>

      {mutationError ? <ErrorState message={errorMessage(mutationError)} /> : null}
      {message ? (
        <div className="border border-[var(--color-border)] bg-white px-4 py-3 text-sm">
          {message}
        </div>
      ) : null}
    </div>
  );
}
