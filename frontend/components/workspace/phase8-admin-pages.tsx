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
import type { SessionPayload } from "@/lib/api";
import {
  auditApi,
  documentIntegrityApi,
  notificationApi,
  type AuditEvent,
  type FinanceDocumentIntegrity,
  type Notification,
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
  const [includeResolved, setIncludeResolved] = useState(false);
  const inbox = useQuery({
    queryKey: ["notifications", session.active_organization_id, session.active_legal_entity_id, includeResolved],
    queryFn: () => notificationApi.inbox(includeResolved),
    enabled: allowed && Boolean(session.active_organization_id),
  });
  const readMutation = useMutation({
    mutationFn: notificationApi.markRead,
    onSuccess: async () => queryClient.invalidateQueries({ queryKey: ["notifications"] }),
  });
  const readAllMutation = useMutation({
    mutationFn: notificationApi.markAllRead,
    onSuccess: async () => queryClient.invalidateQueries({ queryKey: ["notifications"] }),
  });

  if (!allowed) return <PermissionNotice>You do not have permission to view notifications.</PermissionNotice>;
  if (inbox.isLoading) return <LoadingState label="Loading notifications..." />;
  if (inbox.error) return <ErrorState message={errorMessage(inbox.error)} />;

  const columns: Array<TableColumn<Notification>> = [
    { key: "severity", label: "Severity", render: (row) => <StatusBadge value={row.severity} /> },
    { key: "title", label: "Notification", render: (row) => <div><div className="font-semibold">{row.title}</div><div className="mt-0.5 max-w-xl text-xs text-[var(--color-text-muted)]">{row.message}</div></div> },
    { key: "due", label: "Due", render: (row) => row.due_date ?? "—" },
    { key: "state", label: "State", render: (row) => row.resolved_at ? <StatusBadge value="RESOLVED" /> : row.read_at ? <StatusBadge value="READ" /> : <StatusBadge value="UNREAD" /> },
    { key: "created", label: "Created", render: (row) => timestamp(row.created_at) },
    {
      key: "action",
      label: "",
      render: (row) => (
        <div className="flex gap-2">
          {row.link ? <Link className="erp-button !h-7 !min-h-7" href={row.link}>Open</Link> : null}
          {!row.read_at && !row.resolved_at ? <button className="erp-button !h-7 !min-h-7" disabled={readMutation.isPending} onClick={() => readMutation.mutate(row.id)} type="button">Mark Read</button> : null}
        </div>
      ),
    },
  ];

  return (
    <>
      <PageHeader
        eyebrow="Phase 8 · Administration"
        title="Notifications"
        description="Targeted renewal and approval alerts. Read state is independent from resolution so operational obligations remain visible until the underlying condition is cleared."
        actions={<button className="erp-button" disabled={readAllMutation.isPending} onClick={() => readAllMutation.mutate()} type="button">Mark All Read</button>}
      />
      <MetricStrip metrics={[{ label: "Unread", value: String(inbox.data?.unread_count ?? 0) }, { label: "Visible", value: String(inbox.data?.results.length ?? 0) }, { label: "Scope", value: activeEntity(session)?.name ?? "Organization" }, { label: "Refresh", value: "Idempotent" }]} />
      <div className="space-y-3 p-4 lg:p-6">
        <label className="flex items-center gap-2 text-xs"><input checked={includeResolved} onChange={(event) => setIncludeResolved(event.target.checked)} type="checkbox" /> Include resolved history</label>
        {readMutation.error || readAllMutation.error ? <ErrorState message={errorMessage(readMutation.error ?? readAllMutation.error)} /> : null}
        <DataTable columns={columns} rows={inbox.data?.results ?? []} rowKey={(row) => row.id} emptyTitle="No active notifications" emptyDescription="Renewal and approval alerts will appear here after the notification refresh job runs." />
      </div>
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
