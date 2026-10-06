"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Archive, CheckCircle2, History, Pencil, Plus, X } from "lucide-react";
import { useState, type FormEvent, type ReactNode } from "react";

import {
  DataTable,
  ErrorState,
  LoadingState,
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
  type SubscriptionPayment,
  type Vendor,
} from "@/lib/api";

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

function shortDate(value: string | null | undefined) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("en-US", { dateStyle: "medium" }).format(
    new Date(`${value}T00:00:00`),
  );
}

function money(value: string, currency: string) {
  const amount = Number(value);
  if (!Number.isFinite(amount)) return `${value} ${currency}`;
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(amount);
}

function today() {
  return new Date().toISOString().slice(0, 10);
}

function parseCsv(value: FormDataEntryValue | null) {
  return String(value ?? "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function parseReminderDays(value: FormDataEntryValue | null) {
  return [...new Set(
    parseCsv(value)
      .map((item) => Number(item))
      .filter((item) => Number.isInteger(item) && item >= 0 && item <= 365),
  )].sort((a, b) => b - a);
}

function subscriptionPayload(data: FormData, existing?: Subscription) {
  const billingCycle = String(data.get("billing_cycle") ?? "MONTHLY");
  return {
    name: String(data.get("name") ?? ""),
    service_type: String(data.get("service_type") ?? "OTHER"),
    vendor: String(data.get("vendor") ?? "") || null,
    amount: String(data.get("amount") ?? "0"),
    currency: String(data.get("currency") ?? "USD"),
    billing_cycle: billingCycle,
    custom_cycle_days:
      billingCycle === "CUSTOM" ? Number(data.get("custom_cycle_days") || 0) : null,
    started_on: String(data.get("started_on") ?? "") || null,
    next_renewal_date: String(data.get("next_renewal_date") ?? "") || null,
    auto_renew: data.get("auto_renew") === "on",
    payment_method: String(data.get("payment_method") ?? ""),
    reference: String(data.get("reference") ?? ""),
    description: String(data.get("description") ?? ""),
    notes: String(data.get("notes") ?? ""),
    reminder_days: parseReminderDays(data.get("reminder_days")),
    reminder_in_app: data.get("reminder_in_app") === "on",
    reminder_email: data.get("reminder_email") === "on",
    reminder_hermes: data.get("reminder_hermes") === "on",
    reminder_email_recipients: parseCsv(data.get("reminder_email_recipients")),
    hermes_target: String(data.get("hermes_target") ?? ""),
    status: existing?.status ?? "ACTIVE",
  };
}

function Panel({
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
    <section className="mb-4 border border-[var(--color-border-strong)] bg-white">
      <header className="flex items-start justify-between border-b border-[var(--color-border)] px-4 py-3">
        <div>
          <h2 className="text-sm font-semibold">{title}</h2>
          <p className="mt-1 text-xs text-[var(--color-text-muted)]">{description}</p>
        </div>
        <button
          aria-label="Close panel"
          className="erp-button !h-7 !min-h-7 !w-7 !p-0"
          onClick={onClose}
          type="button"
        >
          <X size={14} />
        </button>
      </header>
      {children}
    </section>
  );
}

function Field({
  label,
  name,
  defaultValue,
  type = "text",
  required = false,
  step,
}: {
  label: string;
  name: string;
  defaultValue?: string | number | null;
  type?: string;
  required?: boolean;
  step?: string;
}) {
  return (
    <label className="block text-xs font-medium">
      <span className="mb-1 block text-[var(--color-text-muted)]">{label}</span>
      <input
        className="erp-field"
        defaultValue={defaultValue ?? ""}
        name={name}
        required={required}
        step={step}
        type={type}
      />
    </label>
  );
}

function SelectField({
  label,
  name,
  defaultValue,
  children,
}: {
  label: string;
  name: string;
  defaultValue?: string;
  children: ReactNode;
}) {
  return (
    <label className="block text-xs font-medium">
      <span className="mb-1 block text-[var(--color-text-muted)]">{label}</span>
      <select className="erp-field" defaultValue={defaultValue} name={name}>
        {children}
      </select>
    </label>
  );
}

function SubscriptionForm({
  subscription,
  vendors,
  defaultCurrency,
  pending,
  onSubmit,
}: {
  subscription?: Subscription;
  vendors: Vendor[];
  defaultCurrency: string;
  pending: boolean;
  onSubmit: (payload: Record<string, unknown>) => void;
}) {
  return (
    <form
      className="grid gap-4 p-4 sm:grid-cols-2"
      key={subscription?.id ?? "new"}
      onSubmit={(event: FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        onSubmit(subscriptionPayload(new FormData(event.currentTarget), subscription));
      }}
    >
      <Field defaultValue={subscription?.name} label="Name" name="name" required />
      <SelectField
        defaultValue={subscription?.service_type ?? "SAAS"}
        label="Type"
        name="service_type"
      >
        <option value="DOMAIN">Domain</option>
        <option value="VPS">VPS / Server</option>
        <option value="CLOUD">Cloud</option>
        <option value="HOSTING">Hosting</option>
        <option value="SAAS">SaaS / Software</option>
        <option value="API">API / Usage Service</option>
        <option value="STORAGE">Storage / Backup</option>
        <option value="EMAIL">Email Service</option>
        <option value="AI">AI Service</option>
        <option value="OTHER">Other</option>
      </SelectField>
      <SelectField
        defaultValue={subscription?.vendor ?? ""}
        label="Vendor"
        name="vendor"
      >
        <option value="">No vendor</option>
        {vendors
          .filter((vendor) => vendor.status === "ACTIVE")
          .map((vendor) => (
            <option key={vendor.id} value={vendor.id}>
              {vendor.name}
            </option>
          ))}
      </SelectField>
      <SelectField
        defaultValue={subscription?.billing_cycle ?? "MONTHLY"}
        label="Billing cycle"
        name="billing_cycle"
      >
        <option value="MONTHLY">Monthly</option>
        <option value="QUARTERLY">Quarterly</option>
        <option value="SEMIANNUAL">Semiannual</option>
        <option value="ANNUAL">Annual</option>
        <option value="CUSTOM">Custom days</option>
      </SelectField>
      <Field
        defaultValue={subscription?.custom_cycle_days}
        label="Custom cycle days"
        name="custom_cycle_days"
        type="number"
      />
      <Field
        defaultValue={subscription?.amount}
        label="Amount"
        name="amount"
        required
        step="0.01"
        type="number"
      />
      <Field
        defaultValue={subscription?.currency ?? defaultCurrency}
        label="Currency"
        name="currency"
        required
      />
      <Field
        defaultValue={subscription?.started_on}
        label="Started on"
        name="started_on"
        type="date"
      />
      <Field
        defaultValue={subscription?.next_renewal_date}
        label="Next payment / renewal"
        name="next_renewal_date"
        type="date"
      />
      <Field
        defaultValue={subscription?.payment_method}
        label="Payment method"
        name="payment_method"
      />
      <Field
        defaultValue={subscription?.reference}
        label="Reference / Account ID"
        name="reference"
      />
      <Field
        defaultValue={(subscription?.reminder_days ?? [30, 15, 7, 3, 1, 0]).join(", ")}
        label="Reminder days before due"
        name="reminder_days"
      />
      <Field
        defaultValue={subscription?.reminder_email_recipients.join(", ")}
        label="Email recipients (comma separated)"
        name="reminder_email_recipients"
      />
      <Field
        defaultValue={subscription?.hermes_target}
        label="Hermes target"
        name="hermes_target"
      />
      <label className="flex items-center gap-2 pt-6 text-sm">
        <input defaultChecked={subscription?.auto_renew ?? true} name="auto_renew" type="checkbox" />
        Auto renew
      </label>
      <div className="flex flex-wrap items-center gap-4 border border-[var(--color-border)] p-3 sm:col-span-2">
        <span className="text-xs font-semibold">Reminder channels</span>
        <label className="flex items-center gap-2 text-xs">
          <input
            defaultChecked={subscription?.reminder_in_app ?? true}
            name="reminder_in_app"
            type="checkbox"
          />
          In-app
        </label>
        <label className="flex items-center gap-2 text-xs">
          <input
            defaultChecked={subscription?.reminder_email ?? false}
            name="reminder_email"
            type="checkbox"
          />
          Email
        </label>
        <label className="flex items-center gap-2 text-xs">
          <input
            defaultChecked={subscription?.reminder_hermes ?? false}
            name="reminder_hermes"
            type="checkbox"
          />
          Hermes
        </label>
      </div>
      <Field
        defaultValue={subscription?.description}
        label="Description"
        name="description"
      />
      <Field defaultValue={subscription?.notes} label="Notes" name="notes" />
      <div className="flex justify-end border-t border-[var(--color-border)] pt-3 sm:col-span-2">
        <button className="erp-button erp-button-primary" disabled={pending} type="submit">
          {pending ? "Saving..." : subscription ? "Save Changes" : "Add Subscription"}
        </button>
      </div>
    </form>
  );
}

export function LeanSubscriptionsPage({ session }: { session: SessionPayload }) {
  const queryClient = useQueryClient();
  const entity = activeEntity(session);
  const viewAllowed = can(session, "VIEW_OPERATIONS");
  const manageAllowed = can(session, "MANAGE_OPERATIONS");
  const [mode, setMode] = useState<"create" | "edit" | "paid" | "history" | null>(null);
  const [selected, setSelected] = useState<Subscription | null>(null);

  const subscriptions = useQuery({
    queryKey: ["subscriptions", entity?.id],
    queryFn: operationsApi.subscriptions,
    enabled: Boolean(entity && viewAllowed),
  });
  const vendors = useQuery({
    queryKey: ["vendors", entity?.id],
    queryFn: financeApi.vendors,
    enabled: Boolean(entity && viewAllowed),
  });

  const refresh = async () => {
    await queryClient.invalidateQueries({ queryKey: ["subscriptions", entity?.id] });
    await queryClient.invalidateQueries({ queryKey: ["renewals", entity?.id] });
    await queryClient.invalidateQueries({ queryKey: ["notifications"] });
  };

  const create = useMutation({
    mutationFn: operationsApi.createSubscription,
    onSuccess: async () => {
      setMode(null);
      await refresh();
    },
  });
  const update = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Record<string, unknown> }) =>
      operationsApi.updateSubscription(id, body),
    onSuccess: async () => {
      setMode(null);
      setSelected(null);
      await refresh();
    },
  });
  const markPaid = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Record<string, unknown> }) =>
      operationsApi.markSubscriptionPaid(id, body),
    onSuccess: async () => {
      setMode(null);
      setSelected(null);
      await refresh();
    },
  });

  if (!entity) return <PermissionNotice>Select a legal entity to manage subscriptions.</PermissionNotice>;
  if (!viewAllowed) return <PermissionNotice>You do not have permission to view subscriptions.</PermissionNotice>;

  const open = (nextMode: "edit" | "paid" | "history", row: Subscription) => {
    setSelected(row);
    setMode(nextMode);
  };

  const rows = subscriptions.data ?? [];
  const columns: Array<TableColumn<Subscription>> = [
    {
      key: "name",
      label: "Subscription",
      render: (row) => (
        <div>
          <div className="font-semibold">{row.name}</div>
          <div className="mt-0.5 text-[11px] text-[var(--color-text-muted)]">
            {row.vendor_name || "No vendor"} · {row.service_type.replaceAll("_", " ")}
          </div>
        </div>
      ),
    },
    {
      key: "billing",
      label: "Billing",
      render: (row) =>
        row.billing_cycle === "CUSTOM"
          ? `Every ${row.custom_cycle_days ?? "?"} days`
          : row.billing_cycle.replaceAll("_", " "),
    },
    { key: "due", label: "Next Payment", render: (row) => shortDate(row.next_renewal_date) },
    {
      key: "amount",
      label: "Amount",
      numeric: true,
      render: (row) => money(row.amount, row.currency),
    },
    {
      key: "alerts",
      label: "Alerts",
      render: (row) => (
        <div className="text-[11px]">
          <div>{row.reminder_days.join(", ") || "None"} days</div>
          <div className="text-[var(--color-text-muted)]">
            {[
              row.reminder_in_app ? "In-app" : null,
              row.reminder_email ? "Email" : null,
              row.reminder_hermes ? "Hermes" : null,
            ]
              .filter(Boolean)
              .join(" · ") || "Disabled"}
          </div>
        </div>
      ),
    },
    { key: "history", label: "Payments", render: (row) => String(row.payment_count) },
    { key: "status", label: "Status", render: (row) => <StatusBadge value={row.status} /> },
    {
      key: "actions",
      label: "Actions",
      render: (row) => (
        <div className="flex flex-wrap gap-1">
          {manageAllowed && row.status === "ACTIVE" ? (
            <>
              <button className="erp-button !h-7 !min-h-7 text-[11px]" onClick={() => open("edit", row)} type="button">
                <Pencil size={12} /> Edit
              </button>
              <button className="erp-button !h-7 !min-h-7 text-[11px]" onClick={() => open("paid", row)} type="button">
                <CheckCircle2 size={12} /> Mark Paid
              </button>
            </>
          ) : null}
          <button className="erp-button !h-7 !min-h-7 text-[11px]" onClick={() => open("history", row)} type="button">
            <History size={12} /> History
          </button>
          {manageAllowed && row.status === "ACTIVE" ? (
            <button
              className="erp-button !h-7 !min-h-7 text-[11px]"
              disabled={update.isPending}
              onClick={() => update.mutate({ id: row.id, body: { status: "ARCHIVED" } })}
              type="button"
            >
              <Archive size={12} /> Archive
            </button>
          ) : null}
        </div>
      ),
    },
  ];

  const mutationError = create.error ?? update.error ?? markPaid.error;

  return (
    <>
      <PageHeader
        actions={
          manageAllowed ? (
            <button
              className="erp-button erp-button-primary"
              onClick={() => {
                setSelected(null);
                setMode("create");
              }}
              type="button"
            >
              <Plus size={13} /> Add Subscription
            </button>
          ) : undefined
        }
        description="Manage recurring business costs, payment dates, payment history, and reminder delivery from one place."
        eyebrow="Management"
        title="Subscriptions"
      />
      <div className="p-4 lg:p-6">
        {mode === "create" ? (
          <Panel
            description="Create one recurring obligation and define when and where its reminders should be delivered."
            onClose={() => setMode(null)}
            title="Add Subscription"
          >
            <SubscriptionForm
              defaultCurrency={entity.base_currency}
              onSubmit={(body) => create.mutate(body)}
              pending={create.isPending}
              vendors={vendors.data ?? []}
            />
          </Panel>
        ) : null}

        {mode === "edit" && selected ? (
          <Panel
            description="Update billing, next payment, payment method, or reminder delivery without recreating the record."
            onClose={() => setMode(null)}
            title={`Edit · ${selected.name}`}
          >
            <SubscriptionForm
              defaultCurrency={entity.base_currency}
              onSubmit={(body) => update.mutate({ id: selected.id, body })}
              pending={update.isPending}
              subscription={selected}
              vendors={vendors.data ?? []}
            />
          </Panel>
        ) : null}

        {mode === "paid" && selected ? (
          <Panel
            description="Record the payment. MateERP will advance the next due date from the configured billing cycle."
            onClose={() => setMode(null)}
            title={`Mark Paid · ${selected.name}`}
          >
            <form
              className="grid gap-4 p-4 sm:grid-cols-2"
              onSubmit={(event) => {
                event.preventDefault();
                const data = new FormData(event.currentTarget);
                markPaid.mutate({
                  id: selected.id,
                  body: {
                    paid_on: String(data.get("paid_on")),
                    amount: String(data.get("amount")),
                    currency: String(data.get("currency")),
                    reference: String(data.get("reference") ?? ""),
                    notes: String(data.get("notes") ?? ""),
                  },
                });
              }}
            >
              <Field defaultValue={today()} label="Paid on" name="paid_on" required type="date" />
              <Field defaultValue={selected.amount} label="Amount" name="amount" required step="0.01" type="number" />
              <Field defaultValue={selected.currency} label="Currency" name="currency" required />
              <Field label="Reference" name="reference" />
              <Field label="Notes" name="notes" />
              <div className="flex items-end justify-end">
                <button className="erp-button erp-button-primary" disabled={markPaid.isPending} type="submit">
                  {markPaid.isPending ? "Recording..." : "Record Payment"}
                </button>
              </div>
            </form>
          </Panel>
        ) : null}

        {mode === "history" && selected ? (
          <Panel
            description="Immutable payment and renewal history for this subscription."
            onClose={() => setMode(null)}
            title={`History · ${selected.name}`}
          >
            <div className="p-4">
              <DataTable<SubscriptionPayment>
                columns={[
                  { key: "paid", label: "Paid On", render: (row) => shortDate(row.paid_on) },
                  { key: "previous", label: "Previous Due", render: (row) => shortDate(row.previous_due_date) },
                  { key: "next", label: "Next Due", render: (row) => shortDate(row.next_due_date) },
                  { key: "amount", label: "Amount", numeric: true, render: (row) => money(row.amount, row.currency) },
                  { key: "reference", label: "Reference", render: (row) => row.reference || "—" },
                ]}
                emptyDescription="Mark this subscription paid to create its first payment history record."
                emptyTitle="No payment history"
                rowKey={(row) => row.id}
                rows={selected.payments}
              />
            </div>
          </Panel>
        ) : null}

        {mutationError ? <ErrorState message={errorMessage(mutationError)} /> : null}
        {subscriptions.isLoading || vendors.isLoading ? (
          <LoadingState label="Loading subscriptions..." />
        ) : subscriptions.error || vendors.error ? (
          <ErrorState message={errorMessage(subscriptions.error ?? vendors.error)} />
        ) : (
          <DataTable
            columns={columns}
            emptyDescription="Add the first recurring business cost to start tracking payment dates and reminders."
            emptyTitle="No subscriptions yet"
            rowKey={(row) => row.id}
            rows={rows}
          />
        )}
      </div>
    </>
  );
}
