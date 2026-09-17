"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ShieldCheck, X } from "lucide-react";
import { useMemo, useState } from "react";

import {
  DataTable,
  EmptyState,
  ErrorState,
  LoadingState,
  PageHeader,
  PermissionNotice,
  StatusBadge,
  type TableColumn,
} from "@/components/ui/erp";
import {
  adminApi,
  request,
  type LegalEntity,
  type Membership,
  type SessionPayload,
} from "@/lib/api";

const roles = [
  "OWNER",
  "ADMINISTRATOR",
  "FINANCE_MANAGER",
  "APPROVER",
  "MEMBER",
  "VIEWER",
] as const;

function activeMembership(session: SessionPayload) {
  return session.memberships.find(
    (membership) => membership.organization_id === session.active_organization_id,
  );
}

function canManage(session: SessionPayload) {
  return activeMembership(session)?.permissions.includes("MANAGE_MEMBERS") ?? false;
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "The request could not be completed.";
}

function AccessModal({
  member,
  entities,
  onClose,
  onSaved,
}: {
  member: Membership;
  entities: LegalEntity[];
  onClose: () => void;
  onSaved: () => Promise<void>;
}) {
  const [role, setRole] = useState(member.role);
  const [allEntities, setAllEntities] = useState(member.all_legal_entities);
  const [entityIds, setEntityIds] = useState<string[]>(
    member.all_legal_entities ? entities.map((entity) => entity.id) : member.legal_entity_ids,
  );
  const updateRole = useMutation({
    mutationFn: () =>
      request<Membership>(
        `/api/v1/memberships/${member.id}/role/`,
        { method: "POST", body: JSON.stringify({ role }) },
        true,
      ),
  });
  const updateScope = useMutation({
    mutationFn: () =>
      request<Membership>(
        `/api/v1/memberships/${member.id}/scope/`,
        {
          method: "POST",
          body: JSON.stringify({
            all_legal_entities: allEntities,
            legal_entity_ids: allEntities ? [] : entityIds,
          }),
        },
        true,
      ),
  });
  const error = updateRole.error ?? updateScope.error;
  const pending = updateRole.isPending || updateScope.isPending;

  async function save() {
    try {
      if (role !== member.role) {
        await updateRole.mutateAsync();
      }
      const normalizedCurrent = [...member.legal_entity_ids].sort().join(",");
      const normalizedNext = [...entityIds].sort().join(",");
      if (
        allEntities !== member.all_legal_entities ||
        (!allEntities && normalizedCurrent !== normalizedNext)
      ) {
        await updateScope.mutateAsync();
      }
      await onSaved();
      onClose();
    } catch {
      // Mutation state renders the backend error in this modal.
    }
  }

  function toggleEntity(id: string) {
    setEntityIds((current) =>
      current.includes(id) ? current.filter((item) => item !== id) : [...current, id],
    );
  }

  return (
    <div className="fixed inset-0 z-[80] flex items-start justify-center overflow-y-auto bg-black/50 px-4 py-[8vh]">
      <div className="w-full max-w-2xl border border-[var(--color-border-strong)] bg-white shadow-2xl">
        <div className="flex items-start justify-between border-b border-[var(--color-border)] px-5 py-4">
          <div>
            <h2 className="text-lg font-semibold">Edit Member Access</h2>
            <p className="mt-1 text-xs text-[var(--color-text-muted)]">
              {member.user.display_name || member.user.email} · {member.user.email}
            </p>
          </div>
          <button aria-label="Close" className="erp-button !h-8 !min-h-8 !w-8 !p-0" onClick={onClose} type="button"><X size={14} /></button>
        </div>
        <div className="space-y-5 p-5">
          <label>
            <span className="erp-label">Role</span>
            <select className="erp-field" onChange={(event) => setRole(event.target.value)} value={role}>
              {roles.map((item) => <option key={item} value={item}>{item.replaceAll("_", " ")}</option>)}
            </select>
          </label>
          <div>
            <div className="erp-label">Legal entity scope</div>
            <label className="mb-3 flex items-center gap-2 border border-[var(--color-border)] bg-[var(--color-surface-subtle)] px-3 py-2.5">
              <input checked={allEntities} onChange={(event) => setAllEntities(event.target.checked)} type="checkbox" />
              <span className="text-sm font-medium">All legal entities in this organization</span>
            </label>
            {!allEntities ? (
              <div className="grid border border-[var(--color-border)] sm:grid-cols-2">
                {entities.map((entity) => (
                  <label className="flex items-center gap-2 border-b border-r border-[var(--color-border-soft)] px-3 py-2.5" key={entity.id}>
                    <input checked={entityIds.includes(entity.id)} onChange={() => toggleEntity(entity.id)} type="checkbox" />
                    <span className="text-sm">{entity.name}</span>
                  </label>
                ))}
              </div>
            ) : null}
          </div>
          <div className="border border-[var(--color-border)] bg-[var(--color-surface-subtle)] px-3 py-2.5 text-xs text-[var(--color-text-muted)]">
            Backend policy checks remain authoritative. Invalid owner/administrator changes or empty scoped access are rejected server-side.
          </div>
          {error ? <ErrorState message={errorMessage(error)} /> : null}
        </div>
        <div className="flex justify-end gap-2 border-t border-[var(--color-border)] bg-[var(--color-surface-subtle)] px-5 py-3">
          <button className="erp-button" onClick={onClose} type="button">Cancel</button>
          <button className="erp-button erp-button-primary" disabled={pending || (!allEntities && entityIds.length === 0)} onClick={() => void save()} type="button">{pending ? "Saving..." : "Save Access"}</button>
        </div>
      </div>
    </div>
  );
}

export function MembersProductionPage({ session }: { session: SessionPayload }) {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<Membership | null>(null);
  const members = useQuery({
    queryKey: ["members", session.active_organization_id],
    queryFn: () => request<Membership[]>("/api/v1/memberships/"),
    enabled: Boolean(session.active_organization_id),
  });
  const entities = useQuery({
    queryKey: ["legal-entities", session.active_organization_id],
    queryFn: adminApi.legalEntities,
    enabled: Boolean(session.active_organization_id),
  });
  const entityMap = useMemo(
    () => new Map((entities.data ?? []).map((entity) => [entity.id, entity.name])),
    [entities.data],
  );
  const manageable = canManage(session);

  const columns: Array<TableColumn<Membership>> = [
    {
      key: "user",
      label: "Member",
      render: (row) => (
        <div>
          <div className="font-semibold">{row.user.display_name || row.user.email}</div>
          <div className="text-[11px] text-[var(--color-text-muted)]">{row.user.email}</div>
        </div>
      ),
    },
    { key: "role", label: "Role", render: (row) => row.role.replaceAll("_", " ") },
    {
      key: "scope",
      label: "Legal Entity Scope",
      render: (row) => row.all_legal_entities
        ? "All legal entities"
        : row.legal_entity_ids.map((id) => entityMap.get(id) ?? id).join(", "),
    },
    { key: "status", label: "Status", render: (row) => <StatusBadge value={row.status} /> },
    {
      key: "action",
      label: "Action",
      render: (row) => manageable ? <button className="erp-button !h-7 !min-h-7 !px-2" onClick={() => setEditing(row)} type="button"><ShieldCheck size={11} /> Edit Access</button> : "—",
    },
  ];

  return (
    <>
      <PageHeader description="Manage organization membership roles and legal-entity scope using the Phase 3 RBAC policy layer." eyebrow="Administration" title="Members & Access" />
      <div className="p-4 lg:p-6">
        {!manageable ? <div className="mb-3"><PermissionNotice>You can view membership data, but your role cannot change member access.</PermissionNotice></div> : null}
        {members.isLoading || entities.isLoading ? <LoadingState /> : members.error || entities.error ? <ErrorState message={errorMessage(members.error ?? entities.error)} /> : (members.data ?? []).length ? <DataTable columns={columns} rowKey={(row) => row.id} rows={members.data ?? []} /> : <EmptyState description="Memberships will appear after users are added to the organization." title="No members" />}
      </div>
      {editing ? <AccessModal entities={entities.data ?? []} member={editing} onClose={() => setEditing(null)} onSaved={async () => { await queryClient.invalidateQueries({ queryKey: ["members", session.active_organization_id] }); }} /> : null}
    </>
  );
}
