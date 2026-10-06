import { request, type FinancialAccount } from "@/lib/api";

export type Paginated<T> = {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
};

export type ReportingEnvelope<T> = {
  base_currency: string;
  total?: string;
  unattributed?: string;
  rows: T[];
};

export type FinancialOverview = {
  base_currency: string;
  revenue: string;
  expenses: string;
  net_income: string;
  cash_inflow: string;
  cash_outflow: string;
  net_cash_change: string;
  operational_expense_total: string;
  operational_revenue_total: string;
};

export type ExpenseReportRow = {
  id: string;
  date: string;
  description: string;
  vendor_id: string | null;
  vendor_name: string | null;
  account_code: string;
  account_name: string;
  amount: string;
  currency: string;
  fx_rate: string;
  base_amount: string;
};

export type RevenueReportRow = {
  id: string;
  date: string;
  payer_name: string;
  description: string;
  account_code: string;
  account_name: string;
  amount: string;
  currency: string;
  fx_rate: string;
  base_amount: string;
};

export type SpendRow = {
  vendor_id?: string;
  vendor_name?: string;
  product_id?: string;
  product_name?: string;
  cost_center_id?: string;
  cost_center_name?: string;
  base_amount: string;
};

export type AccountBalanceRow = {
  account_id: string;
  account_code: string;
  account_name: string;
  account_type: string;
  debit: string;
  credit: string;
  natural_balance: string;
};

export type CurrencyExposureRow = {
  currency: string;
  transaction_net: string;
  base_net: string;
};

export type FounderCapitalRow = {
  founder_name: string;
  funding_type: string;
  base_amount: string;
};

export type ReconciliationSummary = {
  reconciliation_id: string;
  currency: string;
  previously_reconciled_balance: string;
  selected_movement: string;
  calculated_ending_balance: string;
  statement_ending_balance: string;
  difference: string;
  selected_count: number;
  candidate_count: number;
};

export type Reconciliation = {
  id: string;
  financial_account: string;
  financial_account_name: string;
  currency: string;
  start_date: string;
  end_date: string;
  statement_ending_balance: string;
  status: string;
  notes: string;
  completed_by: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
  summary: ReconciliationSummary;
};

export type ReconciliationCandidate = {
  id: string;
  journal_id: string;
  journal_number: string;
  date: string;
  source_type: string;
  source_id: string;
  description: string;
  debit: string;
  credit: string;
  currency: string;
  signed_amount: string;
  selected: boolean;
};

export type AuditEvent = {
  id: string;
  actor: string | null;
  actor_email: string | null;
  action: string;
  object_type: string;
  object_id: string;
  previous_state: Record<string, unknown>;
  new_state: Record<string, unknown>;
  ip_address: string | null;
  user_agent: string;
  request_id: string;
  legal_entity: string | null;
  legal_entity_name: string | null;
  created_at: string;
};

export type Notification = {
  id: string;
  kind: string;
  severity: string;
  title: string;
  message: string;
  link: string;
  due_date: string | null;
  read_at: string | null;
  resolved_at: string | null;
  created_at: string;
};

export type NotificationInbox = Paginated<Notification> & {
  unread_count: number;
};

export type NotificationDelivery = {
  id: string;
  subscription: string;
  subscription_name: string;
  channel: "IN_APP" | "EMAIL" | "HERMES";
  destination: string;
  reminder_days_before: number;
  due_date: string;
  title: string;
  message: string;
  status: "PENDING" | "SENT" | "FAILED";
  attempt_count: number;
  last_error: string;
  sent_at: string | null;
  created_at: string;
};

export type NotificationIntegrationSettings = {
  smtp_enabled: boolean;
  smtp_host: string;
  smtp_port: number;
  smtp_username: string;
  smtp_password_configured: boolean;
  smtp_use_tls: boolean;
  smtp_use_ssl: boolean;
  smtp_from_name: string;
  smtp_from_email: string;
  smtp_source: "ERP" | "ENV" | "NONE";
  hermes_enabled: boolean;
  hermes_webhook_url: string;
  hermes_token_configured: boolean;
  hermes_default_target: string;
  hermes_source: "ERP" | "ENV" | "NONE";
  updated_at: string | null;
};

export type FinanceDocumentIntegrity = {
  id: string;
  document_type: string;
  file: string;
  original_name: string;
  vendor: string | null;
  expense: string | null;
  income: string | null;
  reimbursement: string | null;
  transfer: string | null;
  founder_funding: string | null;
  uploaded_by_email: string;
  mime_type: string | null;
  size_bytes: number | null;
  checksum_sha256: string | null;
  created_at: string;
};

function rangeQuery(startDate?: string, endDate?: string) {
  const params = new URLSearchParams();
  if (startDate) params.set("start_date", startDate);
  if (endDate) params.set("end_date", endDate);
  const query = params.toString();
  return query ? `?${query}` : "";
}

function asOfQuery(asOf?: string) {
  return asOf ? `?as_of=${encodeURIComponent(asOf)}` : "";
}

export const reportingApi = {
  overview: (startDate?: string, endDate?: string) =>
    request<FinancialOverview>(`/api/v1/reporting/overview/${rangeQuery(startDate, endDate)}`),
  expenses: (startDate?: string, endDate?: string) =>
    request<ReportingEnvelope<ExpenseReportRow>>(
      `/api/v1/reporting/expenses/${rangeQuery(startDate, endDate)}`,
    ),
  revenue: (startDate?: string, endDate?: string) =>
    request<ReportingEnvelope<RevenueReportRow>>(
      `/api/v1/reporting/revenue/${rangeQuery(startDate, endDate)}`,
    ),
  vendorSpend: (startDate?: string, endDate?: string) =>
    request<ReportingEnvelope<SpendRow>>(
      `/api/v1/reporting/vendor-spend/${rangeQuery(startDate, endDate)}`,
    ),
  productCost: (startDate?: string, endDate?: string) =>
    request<ReportingEnvelope<SpendRow>>(
      `/api/v1/reporting/product-cost/${rangeQuery(startDate, endDate)}`,
    ),
  costCenterSpend: (startDate?: string, endDate?: string) =>
    request<ReportingEnvelope<SpendRow>>(
      `/api/v1/reporting/cost-center-spend/${rangeQuery(startDate, endDate)}`,
    ),
  accountBalances: (asOf?: string) =>
    request<ReportingEnvelope<AccountBalanceRow>>(
      `/api/v1/reporting/account-balances/${asOfQuery(asOf)}`,
    ),
  currencyExposure: (asOf?: string) =>
    request<ReportingEnvelope<CurrencyExposureRow>>(
      `/api/v1/reporting/currency-exposure/${asOfQuery(asOf)}`,
    ),
  founderCapital: (startDate?: string, endDate?: string) =>
    request<ReportingEnvelope<FounderCapitalRow>>(
      `/api/v1/reporting/founder-capital/${rangeQuery(startDate, endDate)}`,
    ),
};

export const reconciliationApi = {
  list: () => request<Reconciliation[]>("/api/v1/finance/reconciliations/"),
  candidates: (id: string) =>
    request<ReconciliationCandidate[]>(`/api/v1/finance/reconciliations/${id}/candidates/`),
  create: (body: {
    financial_account: FinancialAccount["id"];
    start_date: string;
    end_date: string;
    statement_ending_balance: string;
    notes?: string;
  }) =>
    request<Reconciliation>(
      "/api/v1/finance/reconciliations/",
      { method: "POST", body: JSON.stringify(body) },
      true,
    ),
  replaceItems: (id: string, journalLineIds: string[]) =>
    request<Reconciliation>(
      `/api/v1/finance/reconciliations/${id}/items/`,
      { method: "PUT", body: JSON.stringify({ journal_line_ids: journalLineIds }) },
      true,
    ),
  complete: (id: string) =>
    request<Reconciliation>(
      `/api/v1/finance/reconciliations/${id}/complete/`,
      { method: "POST" },
      true,
    ),
};

export const auditApi = {
  events: (params?: Record<string, string>) => {
    const query = new URLSearchParams(params ?? {}).toString();
    return request<Paginated<AuditEvent>>(`/api/v1/audit/events/${query ? `?${query}` : ""}`);
  },
};

export const notificationApi = {
  inbox: (includeResolved = false) =>
    request<NotificationInbox>(
      `/api/v1/notifications/${includeResolved ? "?include_resolved=1" : ""}`,
    ),
  markRead: (id: string) =>
    request<Notification>(`/api/v1/notifications/${id}/read/`, { method: "POST" }, true),
  markAllRead: () =>
    request<{ marked_read: number }>("/api/v1/notifications/read-all/", { method: "POST" }, true),
  deliveries: () =>
    request<Paginated<NotificationDelivery>>("/api/v1/notifications/deliveries/"),
  integrations: () =>
    request<NotificationIntegrationSettings>("/api/v1/notifications/integrations/"),
  updateIntegrations: (body: Record<string, unknown>) =>
    request<NotificationIntegrationSettings>(
      "/api/v1/notifications/integrations/",
      { method: "PATCH", body: JSON.stringify(body) },
      true,
    ),
  testEmail: (recipient: string) =>
    request<{ detail: string }>(
      "/api/v1/notifications/integrations/test-email/",
      { method: "POST", body: JSON.stringify({ recipient }) },
      true,
    ),
  testHermes: (target: string) =>
    request<{ detail: string }>(
      "/api/v1/notifications/integrations/test-hermes/",
      { method: "POST", body: JSON.stringify({ target }) },
      true,
    ),
};

export const documentIntegrityApi = {
  list: () => request<FinanceDocumentIntegrity[]>("/api/v1/finance/documents/"),
  upload: (body: FormData) =>
    request<FinanceDocumentIntegrity>(
      "/api/v1/finance/documents/",
      { method: "POST", body },
      true,
    ),
};
