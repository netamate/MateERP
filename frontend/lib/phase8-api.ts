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
  legal_entity: string | null;
  severity: string;
  title: string;
  message: string;
  email_subject: string;
  email_text_body: string;
  email_html_body: string;
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
  subscription: string | null;
  subscription_name: string | null;
  alert_rule: string | null;
  alert_rule_name: string | null;
  email_template: string | null;
  email_template_name: string | null;
  email_template_version: number | null;
  signal: string;
  source_type: string;
  source_id: string;
  source_label: string;
  channel: "IN_APP" | "EMAIL" | "HERMES";
  destination: string;
  reminder_days_before: number | null;
  due_date: string | null;
  severity: string;
  title: string;
  message: string;
  link: string;
  status: "PENDING" | "SENT" | "FAILED";
  attempt_count: number;
  last_error: string;
  sent_at: string | null;
  created_at: string;
};

export type AlertRule = {
  id: string;
  legal_entity: string | null;
  legal_entity_name: string | null;
  name: string;
  signal:
    | "RENEWAL_DUE"
    | "BUDGET_THRESHOLD"
    | "MISSING_INVOICE"
    | "INVOICE_OVERDUE"
    | "RECONCILIATION_NEEDED";
  enabled: boolean;
  severity: "INFO" | "WARNING" | "CRITICAL";
  frequency: "HOURLY" | "DAILY";
  schedule_hour: number;
  schedule_timezone: string;
  in_app_enabled: boolean;
  email_enabled: boolean;
  hermes_enabled: boolean;
  recipient_user_ids: string[];
  recipient_users: Array<{
    id: string;
    email: string;
    display_name: string;
  }>;
  email_recipients: string[];
  hermes_target: string;
  email_template: string | null;
  email_template_name: string | null;
  renewal_days: number[];
  grace_days: number;
  respect_subscription_channels: boolean;
  last_evaluated_at: string | null;
  last_delivery_count: number;
  last_failure_count: number;
  last_error: string;
  created_at: string;
  updated_at: string;
};

export type AlertRunResult = {
  rules_evaluated: number;
  rules_skipped: number;
  active_events: number;
  deliveries_sent: number;
  deliveries_failed: number;
  results: Array<{
    rule_id: string;
    signal: string;
    active_events: number;
    sent: number;
    failed: number;
    error: string;
  }>;
};

export type DirectEmailNotification = {
  id: string;
  legal_entity: string | null;
  to_recipients: string[];
  cc_recipients: string[];
  bcc_recipients: string[];
  template: string | null;
  template_name: string | null;
  template_version: number | null;
  subject: string;
  body: string;
  html_body: string;
  scheduled_for: string | null;
  schedule_timezone: string;
  status: "DRAFT" | "SCHEDULED" | "SENDING" | "SENT" | "FAILED" | "CANCELLED";
  attempt_count: number;
  last_error: string;
  sent_at: string | null;
  created_by_email: string | null;
  created_at: string;
  updated_at: string;
};

export type EmailTemplate = {
  id: string;
  legal_entity: string | null;
  legal_entity_name: string | null;
  template_key: string;
  name: string;
  description: string;
  signal:
    | "RENEWAL_DUE"
    | "BUDGET_THRESHOLD"
    | "MISSING_INVOICE"
    | "INVOICE_OVERDUE"
    | "RECONCILIATION_NEEDED"
    | null;
  subject_template: string;
  html_body_template: string;
  text_body_template: string;
  status: "ACTIVE" | "ARCHIVED";
  current_version: number;
  is_system_default: boolean;
  created_by_email: string | null;
  updated_by_email: string | null;
  available_variables: Record<string, string>;
  version_count: number;
  created_at: string;
  updated_at: string;
};

export type EmailTemplateVersion = {
  id: string;
  version_number: number;
  name: string;
  description: string;
  signal: EmailTemplate["signal"];
  subject_template: string;
  html_body_template: string;
  text_body_template: string;
  created_at: string;
};

export type EmailTemplatePreview = {
  subject: string;
  text_body: string;
  html_body: string;
  used_variables: string[];
  context: Record<string, unknown>;
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
  document_date: string;
  reference: string;
  original_name: string;
  standardized_name: string;
  vendor: string | null;
  vendor_name: string | null;
  service: string | null;
  service_name: string | null;
  service_account: string | null;
  account_alias: string | null;
  account_code: string | null;
  subscription: string | null;
  subscription_name: string | null;
  subscription_code: string | null;
  expense: string | null;
  income: string | null;
  reimbursement: string | null;
  transfer: string | null;
  founder_funding: string | null;
  uploaded_by_email: string;
  mime_type: string | null;
  size_bytes: number | null;
  checksum_sha256: string | null;
  folder_year: number;
  folder_month: number;
  content_url: string;
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
  emailTemplates: (includeArchived = false) =>
    request<EmailTemplate[]>(
      `/api/v1/notifications/email-templates/${includeArchived ? "?include_archived=1" : ""}`,
    ),
  createEmailTemplate: (body: Record<string, unknown>) =>
    request<EmailTemplate>(
      "/api/v1/notifications/email-templates/",
      { method: "POST", body: JSON.stringify(body) },
      true,
    ),
  updateEmailTemplate: (id: string, body: Record<string, unknown>) =>
    request<EmailTemplate>(
      `/api/v1/notifications/email-templates/${id}/`,
      { method: "PATCH", body: JSON.stringify(body) },
      true,
    ),
  archiveEmailTemplate: (id: string) =>
    request<EmailTemplate>(
      `/api/v1/notifications/email-templates/${id}/archive/`,
      { method: "POST" },
      true,
    ),
  emailTemplateVersions: (id: string) =>
    request<EmailTemplateVersion[]>(
      `/api/v1/notifications/email-templates/${id}/versions/`,
    ),
  previewEmailTemplate: (body: Record<string, unknown>) =>
    request<EmailTemplatePreview>(
      "/api/v1/notifications/email-templates/preview/",
      { method: "POST", body: JSON.stringify(body) },
      true,
    ),
  testEmailTemplate: (body: Record<string, unknown>) =>
    request<{ detail: string; subject: string }>(
      "/api/v1/notifications/email-templates/test/",
      { method: "POST", body: JSON.stringify(body) },
      true,
    ),

  inbox: (
    includeResolved = false,
    filters?: { kind?: string; severity?: string; state?: string },
  ) => {
    const params = new URLSearchParams();
    if (includeResolved) params.set("include_resolved", "1");
    if (filters?.kind) params.set("kind", filters.kind);
    if (filters?.severity) params.set("severity", filters.severity);
    if (filters?.state) params.set("state", filters.state);
    const query = params.toString();
    return request<NotificationInbox>(`/api/v1/notifications/${query ? `?${query}` : ""}`);
  },
  markRead: (id: string) =>
    request<Notification>(`/api/v1/notifications/${id}/read/`, { method: "POST" }, true),
  dismiss: (id: string) =>
    request<Notification>(`/api/v1/notifications/${id}/dismiss/`, { method: "POST" }, true),
  markAllRead: () =>
    request<{ marked_read: number }>("/api/v1/notifications/read-all/", { method: "POST" }, true),
  deliveries: (filters?: { signal?: string; channel?: string; status?: string; alert_rule?: string }) => {
    const params = new URLSearchParams();
    if (filters?.signal) params.set("signal", filters.signal);
    if (filters?.channel) params.set("channel", filters.channel);
    if (filters?.status) params.set("status", filters.status);
    if (filters?.alert_rule) params.set("alert_rule", filters.alert_rule);
    const query = params.toString();
    return request<Paginated<NotificationDelivery>>(
      `/api/v1/notifications/deliveries/${query ? `?${query}` : ""}`,
    );
  },
  retryDelivery: (id: string) =>
    request<NotificationDelivery>(
      `/api/v1/notifications/deliveries/${id}/retry/`,
      { method: "POST" },
      true,
    ),
  rules: () => request<AlertRule[]>("/api/v1/notifications/rules/"),
  createRule: (body: Record<string, unknown>) =>
    request<AlertRule>(
      "/api/v1/notifications/rules/",
      { method: "POST", body: JSON.stringify(body) },
      true,
    ),
  updateRule: (id: string, body: Record<string, unknown>) =>
    request<AlertRule>(
      `/api/v1/notifications/rules/${id}/`,
      { method: "PATCH", body: JSON.stringify(body) },
      true,
    ),
  runRulesNow: () =>
    request<AlertRunResult>(
      "/api/v1/notifications/rules/run-now/",
      { method: "POST" },
      true,
    ),
  integrations: () =>
    request<NotificationIntegrationSettings>("/api/v1/notifications/integrations/"),
  updateIntegrations: (body: Record<string, unknown>) =>
    request<NotificationIntegrationSettings>(
      "/api/v1/notifications/integrations/",
      { method: "PATCH", body: JSON.stringify(body) },
      true,
    ),
  testEmail: (payload: { recipient: string; settings: Record<string, unknown> }) =>
    request<{ detail: string }>(
      "/api/v1/notifications/integrations/test-email/",
      { method: "POST", body: JSON.stringify({ ...payload.settings, recipient: payload.recipient }) },
      true,
    ),
  testHermes: (target: string) =>
    request<{ detail: string }>(
      "/api/v1/notifications/integrations/test-hermes/",
      { method: "POST", body: JSON.stringify({ target }) },
      true,
    ),
  directEmails: () =>
    request<Paginated<DirectEmailNotification>>("/api/v1/notifications/email/"),
  createDirectEmail: (body: Record<string, unknown>) =>
    request<DirectEmailNotification>(
      "/api/v1/notifications/email/",
      { method: "POST", body: JSON.stringify(body) },
      true,
    ),
  sendDirectEmail: (id: string) =>
    request<DirectEmailNotification>(
      `/api/v1/notifications/email/${id}/send/`,
      { method: "POST" },
      true,
    ),
  cancelDirectEmail: (id: string) =>
    request<DirectEmailNotification>(
      `/api/v1/notifications/email/${id}/cancel/`,
      { method: "POST" },
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
