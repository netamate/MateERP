"use client";

import { AlertTriangle, LoaderCircle, SearchX } from "lucide-react";
import type { ReactNode } from "react";

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow: string;
  title: string;
  description: string;
  actions?: ReactNode;
}) {
  return (
    <section className="flex flex-col gap-4 border-b border-[var(--color-border)] bg-white px-5 py-5 md:flex-row md:items-end md:justify-between lg:px-6">
      <div>
        <div className="mb-1 text-[10px] font-bold uppercase tracking-[0.12em] text-[var(--color-text-muted)]">
          {eyebrow}
        </div>
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        <p className="mt-1 max-w-3xl text-sm text-[var(--color-text-muted)]">{description}</p>
      </div>
      {actions ? <div className="flex flex-wrap gap-2">{actions}</div> : null}
    </section>
  );
}

export function MetricStrip({
  metrics,
}: {
  metrics: Array<{ label: string; value: string; note?: string; tone?: "default" | "good" | "bad" }>;
}) {
  return (
    <section className="grid border-b border-[var(--color-border)] bg-white sm:grid-cols-2 xl:grid-cols-4">
      {metrics.map((metric) => (
        <div className="border-b border-r border-[var(--color-border)] px-5 py-4 sm:last:border-r-0 xl:border-b-0" key={metric.label}>
          <div className="text-[10px] font-bold uppercase tracking-[0.1em] text-[var(--color-text-muted)]">
            {metric.label}
          </div>
          <div className="mt-1 text-xl font-bold tabular-nums">{metric.value}</div>
          {metric.note ? (
            <div
              className={`mt-1 text-[11px] ${
                metric.tone === "good"
                  ? "text-[var(--color-success)]"
                  : metric.tone === "bad"
                    ? "text-[var(--color-danger)]"
                    : "text-[var(--color-text-muted)]"
              }`}
            >
              {metric.note}
            </div>
          ) : null}
        </div>
      ))}
    </section>
  );
}

export function StatusBadge({ value }: { value: string }) {
  const normalized = value.toUpperCase();
  const className = ["PAID", "POSTED", "APPROVED", "ACTIVE", "OPEN", "SENT"].includes(normalized)
    ? "erp-status-success"
    : ["SUBMITTED", "PARTIALLY_PAID", "PENDING", "DUE"].includes(normalized)
      ? "erp-status-warning"
      : ["REJECTED", "VOID", "CLOSED", "OVERDUE", "REVERSED", "FAILED"].includes(normalized)
        ? "erp-status-danger"
        : "erp-status-muted";
  return <span className={`erp-status ${className}`}>{value.replaceAll("_", " ")}</span>;
}

export function LoadingState({ label = "Loading data..." }: { label?: string }) {
  return (
    <div className="grid min-h-56 place-items-center border border-[var(--color-border)] bg-white text-sm text-[var(--color-text-muted)]">
      <div className="flex items-center gap-2">
        <LoaderCircle className="animate-spin" size={16} /> {label}
      </div>
    </div>
  );
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div className="flex min-h-40 items-center gap-3 border border-[#e0a8a8] bg-[#fff6f6] px-5 py-4 text-sm text-[var(--color-danger)]">
      <AlertTriangle size={18} />
      <span>{message}</span>
    </div>
  );
}

export function EmptyState({ title, description }: { title: string; description: string }) {
  return (
    <div className="grid min-h-48 place-items-center border border-[var(--color-border)] bg-white px-6 text-center">
      <div>
        <SearchX className="mx-auto mb-3 text-[var(--color-text-muted)]" size={22} />
        <div className="font-semibold">{title}</div>
        <div className="mt-1 max-w-md text-sm text-[var(--color-text-muted)]">{description}</div>
      </div>
    </div>
  );
}

export type TableColumn<T> = {
  key: string;
  label: string;
  numeric?: boolean;
  render: (row: T) => ReactNode;
};

export function DataTable<T>({
  rows,
  columns,
  rowKey,
  emptyTitle = "No records yet",
  emptyDescription = "Create the first record to start building this workspace.",
}: {
  rows: T[];
  columns: Array<TableColumn<T>>;
  rowKey: (row: T) => string;
  emptyTitle?: string;
  emptyDescription?: string;
}) {
  if (!rows.length) {
    return <EmptyState description={emptyDescription} title={emptyTitle} />;
  }
  return (
    <div className="erp-table-wrap">
      <table className="erp-table">
        <thead>
          <tr>
            {columns.map((column) => (
              <th className={column.numeric ? "erp-num" : undefined} key={column.key}>
                {column.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={rowKey(row)}>
              {columns.map((column) => (
                <td className={column.numeric ? "erp-num" : undefined} key={column.key}>
                  {column.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function PermissionNotice({ children }: { children: ReactNode }) {
  return (
    <div className="border border-[var(--color-border)] bg-[var(--color-surface-subtle)] px-4 py-3 text-xs text-[var(--color-text-muted)]">
      {children}
    </div>
  );
}
