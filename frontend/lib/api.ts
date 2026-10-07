export type User = {
  id: string;
  email: string;
  display_name: string;
  timezone: string;
};

export type Membership = {
  id: string;
  organization_id: string;
  user: User;
  role: string;
  status: string;
  all_legal_entities: boolean;
  legal_entity_ids: string[];
  permissions: string[];
};

export type Organization = {
  id: string;
  name: string;
  slug: string;
  status: string;
  timezone: string;
};

export type LegalEntity = {
  id: string;
  organization_id: string;
  name: string;
  slug: string;
  status: string;
  base_currency: string;
  timezone: string;
  fiscal_year_start_month: number;
  fiscal_year_start_day: number;
};

export type SessionPayload = {
  user: User;
  memberships: Membership[];
  organizations: Organization[];
  active_organization_id: string | null;
  active_legal_entity_id: string | null;
  active_legal_entities: LegalEntity[];
};

export type Vendor = {
  id: string;
  code: string;
  name: string;
  contact_name: string;
  email: string;
  phone: string;
  payment_terms_days: number;
  status: string;
  default_expense_account: string | null;
  payable_account: string | null;
};

export type FinancialAccount = {
  id: string;
  name: string;
  account_type: string;
  currency: string;
  ledger_account: string;
  institution_name: string;
  last_four: string;
  is_active: boolean;
};

export type Expense = {
  id: string;
  vendor: string | null;
  expense_date: string;
  due_date: string | null;
  description: string;
  reference: string;
  amount: string;
  tax_amount: string;
  currency: string;
  fx_rate: string;
  expense_account: string;
  payable_account: string;
  tax_code: string | null;
  status: string;
  journal_entry: string | null;
  approved_at: string | null;
  rejection_reason: string;
  payments: ExpensePayment[];
};

export type ExpensePayment = {
  id: string;
  expense: string;
  financial_account: string;
  payment_date: string;
  amount: string;
  currency: string;
  fx_rate: string;
  base_amount: string;
  reference: string;
  journal_entry: string;
  created_at: string;
};

export type Income = {
  id: string;
  income_date: string;
  payer_name: string;
  description: string;
  reference: string;
  amount: string;
  currency: string;
  fx_rate: string;
  revenue_account: string;
  financial_account: string;
  status: string;
  journal_entry: string | null;
};

export type Transfer = {
  id: string;
  transfer_date: string;
  from_account: string;
  to_account: string;
  source_amount: string;
  destination_amount: string;
  source_fx_rate: string;
  destination_fx_rate: string;
  reference: string;
  memo: string;
  status: string;
  journal_entry: string | null;
};

export type Reimbursement = {
  id: string;
  claimant: string;
  expense_date: string;
  description: string;
  amount: string;
  currency: string;
  fx_rate: string;
  expense_account: string;
  payable_account: string;
  status: string;
  journal_entry: string | null;
  approved_at: string | null;
  rejection_reason: string;
  payments: ReimbursementPayment[];
};

export type ReimbursementPayment = {
  id: string;
  reimbursement: string;
  financial_account: string;
  payment_date: string;
  amount: string;
  currency: string;
  fx_rate: string;
  base_amount: string;
  reference: string;
  journal_entry: string;
  created_at: string;
};

export type LedgerAccount = {
  id: string;
  code: string;
  name: string;
  account_type: string;
  normal_balance: string;
  is_active: boolean;
  parent: string | null;
};

export type JournalEntry = {
  id: string;
  number: string;
  entry_date: string;
  memo: string;
  status: string;
  source_type: string;
  source_id: string;
  posted_at: string | null;
  lines: Array<{
    id: string;
    account: string;
    description: string;
    debit: string;
    credit: string;
    currency: string;
    fx_rate: string;
    base_debit: string;
    base_credit: string;
  }>;
};

export type ReportRow = {
  account_id?: string;
  account_code?: string;
  account_name?: string;
  debit?: string;
  credit?: string;
  balance?: string;
  amount?: string;
  label?: string;
  [key: string]: unknown;
};

export type CostCenter = {
  id: string;
  code: string;
  name: string;
  description: string;
  status: string;
  created_at: string;
  updated_at: string;
};

export type Product = CostCenter;

export type Project = {
  id: string;
  product: string | null;
  code: string;
  name: string;
  client_name: string;
  description: string;
  start_date: string | null;
  end_date: string | null;
  status: string;
  created_at: string;
  updated_at: string;
};

export type ExpenseAllocation = {
  id: string;
  expense: string;
  cost_center: string | null;
  product: string | null;
  project: string | null;
  amount: string;
  base_amount: string;
  note: string;
  created_at: string;
};

export type Budget = {
  id: string;
  name: string;
  start_date: string;
  end_date: string;
  status: string;
  notes: string;
  line_count: number;
  created_at: string;
  updated_at: string;
};

export type BudgetLine = {
  id: string;
  expense_account: string | null;
  expense_account_name: string | null;
  cost_center: string | null;
  cost_center_name: string | null;
  product: string | null;
  product_name: string | null;
  project: string | null;
  project_name: string | null;
  amount: string;
  notes: string;
  created_at: string;
  updated_at: string;
};

export type BudgetActualLine = {
  id: string;
  expense_account_id: string | null;
  expense_account_name: string | null;
  cost_center_id: string | null;
  cost_center_name: string | null;
  product_id: string | null;
  product_name: string | null;
  project_id: string | null;
  project_name: string | null;
  budget_amount: string;
  actual_amount: string;
  variance: string;
  utilization_percent: string;
  notes: string;
};

export type BudgetActuals = {
  budget_id: string;
  name: string;
  base_currency: string;
  start_date: string;
  end_date: string;
  status: string;
  total_budget: string;
  total_actual: string;
  total_variance: string;
  lines: BudgetActualLine[];
};

export type SubscriptionPayment = {
  id: string;
  subscription: string;
  paid_on: string;
  previous_due_date: string | null;
  next_due_date: string | null;
  amount: string;
  currency: string;
  reference: string;
  notes: string;
  created_by_email: string | null;
  created_at: string;
};

export type VendorService = {
  id: string;
  vendor: string;
  vendor_name: string;
  code: string;
  name: string;
  service_type: Subscription["service_type"];
  description: string;
  status: "ACTIVE" | "ARCHIVED";
  account_count: number;
  created_at: string;
  updated_at: string;
};

export type ServiceAccount = {
  id: string;
  service: string;
  service_name: string;
  vendor_id: string;
  vendor_name: string;
  code: string;
  alias: string;
  reference: string;
  status: "ACTIVE" | "ARCHIVED";
  notes: string;
  subscription_count: number;
  created_at: string;
  updated_at: string;
};

export type Subscription = {
  id: string;
  subscription_code: string;
  vendor: string | null;
  vendor_name: string | null;
  service: string | null;
  vendor_service_name: string | null;
  service_account: string | null;
  account_alias: string | null;
  account_code: string | null;
  name: string;
  service_type: "DOMAIN" | "VPS" | "CLOUD" | "HOSTING" | "SAAS" | "API" | "STORAGE" | "EMAIL" | "AI" | "OTHER";
  description: string;
  reference: string;
  payment_method: string;
  amount: string;
  currency: string;
  billing_mode: "FIXED" | "PAYG";
  estimated_cost: string;
  monthly_budget: string | null;
  budget_alert_thresholds: number[];
  usage_unit: string;
  billing_cycle: string;
  custom_cycle_days: number | null;
  started_on: string | null;
  next_renewal_date: string | null;
  auto_renew: boolean;
  reminder_days: number[];
  reminder_in_app: boolean;
  reminder_email: boolean;
  reminder_hermes: boolean;
  reminder_email_recipients: string[];
  hermes_target: string;
  status: string;
  notes: string;
  payments: SubscriptionPayment[];
  payment_count: number;
};

export type BillingPeriod = {
  id: string;
  subscription: string;
  subscription_name: string;
  subscription_code: string;
  vendor_name: string | null;
  service_name: string | null;
  account_alias: string | null;
  billing_mode: "FIXED" | "PAYG";
  currency: string;
  period_start: string;
  period_end: string;
  estimated_cost: string;
  current_usage_amount: string;
  usage_quantity: string | null;
  usage_unit: string;
  current_usage_updated_at: string | null;
  is_closed: boolean;
  notes: string;
  status: "OPEN" | "AWAITING_INVOICE" | "INVOICED" | "PARTIALLY_PAID" | "PAID" | "CLOSED";
  actual_billed_amount: string;
  paid_amount: string;
  outstanding_amount: string;
  variance_from_estimate: string;
  monthly_budget: string | null;
  budget_percent: string | null;
  budget_thresholds_reached: number[];
  over_budget: boolean;
  missing_invoice: boolean;
  invoice_count: number;
  created_at: string;
  updated_at: string;
};

export type SubscriptionInvoice = {
  id: string;
  billing_period: string;
  subscription: string;
  subscription_name: string;
  subscription_code: string;
  vendor: string;
  vendor_name: string;
  invoice_number: string;
  invoice_date: string;
  due_date: string | null;
  period_start: string;
  period_end: string;
  currency: string;
  subtotal: string;
  tax_amount: string;
  total_amount: string;
  document: string | null;
  document_name: string | null;
  expense: string | null;
  expense_description: string | null;
  status: "OPEN" | "PARTIALLY_PAID" | "PAID" | "VOID";
  paid_amount: string;
  outstanding_amount: string;
  expense_reconciliation_status: "UNMATCHED" | "MISMATCH" | "MATCHED";
  expense_difference: string | null;
  notes: string;
  created_at: string;
  updated_at: string;
};

export type BillingPaymentAllocation = {
  id: string;
  invoice: string;
  invoice_number: string;
  amount: string;
  created_at: string;
};

export type BillingPayment = {
  id: string;
  subscription: string;
  subscription_name: string;
  subscription_code: string;
  payment_code: string;
  paid_on: string;
  amount: string;
  currency: string;
  reference: string;
  financial_account: string | null;
  financial_account_name: string | null;
  expense_payment: string | null;
  expense_payment_reference: string | null;
  notes: string;
  allocations: BillingPaymentAllocation[];
  allocated_amount: string;
  unallocated_amount: string;
  reconciliation_status: "UNMATCHED" | "ACCOUNT_IDENTIFIED" | "MATCHED";
  created_at: string;
};

export type BillingDashboard = {
  totals_by_currency: Array<{
    currency: string;
    estimated_cost: string;
    current_usage_amount: string;
    actual_billed_amount: string;
    paid_amount: string;
    outstanding_amount: string;
  }>;
  missing_invoice_count: number;
  over_budget_period_count: number;
  unpaid_invoice_count: number;
  unreconciled_invoice_count: number;
  unallocated_payment_by_currency: Array<{
    currency: string;
    amount: string;
  }>;
  trend: Array<{
    period: string;
    currency: string;
    estimated_cost: string;
    current_usage_amount: string;
    actual_billed_amount: string;
    paid_amount: string;
    budget: string;
  }>;
};

export type DomainRecord = {
  id: string;
  product: string | null;
  product_name: string | null;
  payment_account: string | null;
  expense_account: string | null;
  payable_account: string | null;
  domain_name: string;
  registrar: string;
  dns_provider: string;
  purpose: string;
  purchase_date: string | null;
  expiry_date: string;
  renewal_amount: string;
  currency: string;
  auto_renew: boolean;
  status: string;
  notes: string;
  renewal_count: number;
};

export type DomainRenewal = {
  id: string;
  domain: string;
  expense: string | null;
  renewed_on: string;
  previous_expiry_date: string;
  new_expiry_date: string;
  amount: string;
  currency: string;
  fx_rate: string;
  notes: string;
  created_at: string;
};

export type InfrastructureAsset = {
  id: string;
  vendor: string | null;
  vendor_name: string | null;
  product: string | null;
  product_name: string | null;
  cost_center: string | null;
  cost_center_name: string | null;
  payment_account: string | null;
  expense_account: string | null;
  payable_account: string | null;
  name: string;
  asset_type: string;
  provider_reference: string;
  purpose: string;
  started_on: string | null;
  next_renewal_date: string | null;
  renewal_amount: string;
  currency: string;
  billing_cycle: string;
  auto_renew: boolean;
  status: string;
  notes: string;
};

export type RenewalItem = {
  source_type: "SUBSCRIPTION";
  source_id: string;
  service_type: Subscription["service_type"];
  name: string;
  renewal_date: string;
  amount: string;
  currency: string;
  auto_renew: boolean;
  vendor_name: string | null;
  reference: string;
  payment_method: string;
};

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
  }
}

async function ensureCsrfToken(): Promise<string> {
  const response = await fetch("/api/v1/auth/csrf/", {
    credentials: "include",
    cache: "no-store",
  });
  if (!response.ok) throw new ApiError("Unable to initialize secure request token.", response.status);
  const data = (await response.json()) as { csrf_token: string };
  return data.csrf_token;
}

function extractErrorMessage(body: unknown): string | null {
  if (!body || typeof body !== "object") return null;
  const data = body as Record<string, unknown>;
  if (typeof data.detail === "string") return data.detail;
  if (Array.isArray(data.non_field_errors) && typeof data.non_field_errors[0] === "string") {
    return data.non_field_errors[0];
  }
  for (const [field, value] of Object.entries(data)) {
    if (Array.isArray(value) && typeof value[0] === "string") {
      return `${field.replaceAll("_", " ")}: ${value[0]}`;
    }
    if (typeof value === "string") return `${field.replaceAll("_", " ")}: ${value}`;
  }
  return null;
}

export async function request<T>(
  url: string,
  init: RequestInit = {},
  csrfProtected = false,
): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  if (csrfProtected) headers.set("X-CSRFToken", await ensureCsrfToken());

  const response = await fetch(url, { ...init, headers, credentials: "include", cache: "no-store" });
  if (!response.ok) {
    let message = "Request failed.";
    try {
      message = extractErrorMessage(await response.json()) ?? message;
    } catch {
      // Keep the safe generic message for non-JSON responses.
    }
    throw new ApiError(message, response.status);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export function getSession(): Promise<SessionPayload> {
  return request<SessionPayload>("/api/v1/session/");
}

export function login(email: string, password: string): Promise<SessionPayload> {
  return request<SessionPayload>(
    "/api/v1/auth/login/",
    { method: "POST", body: JSON.stringify({ email, password }) },
    true,
  );
}

export function logout(): Promise<void> {
  return request<void>("/api/v1/auth/logout/", { method: "POST" }, true);
}

export function setContext(
  organizationId: string,
  legalEntityId: string | null,
): Promise<SessionPayload> {
  return request<SessionPayload>(
    "/api/v1/session/context/",
    { method: "POST", body: JSON.stringify({ organization_id: organizationId, legal_entity_id: legalEntityId }) },
    true,
  );
}

export const financeApi = {
  vendors: () => request<Vendor[]>("/api/v1/finance/vendors/"),
  accounts: () => request<FinancialAccount[]>("/api/v1/finance/accounts/"),
  expenses: () => request<Expense[]>("/api/v1/finance/expenses/"),
  income: () => request<Income[]>("/api/v1/finance/income/"),
  transfers: () => request<Transfer[]>("/api/v1/finance/transfers/"),
  reimbursements: () => request<Reimbursement[]>("/api/v1/finance/reimbursements/"),
  createVendor: (body: Record<string, unknown>) => request<Vendor>("/api/v1/finance/vendors/", { method: "POST", body: JSON.stringify(body) }, true),
  createExpense: (body: Record<string, unknown>) => request<Expense>("/api/v1/finance/expenses/", { method: "POST", body: JSON.stringify(body) }, true),
  expenseWorkflow: (id: string, action: "submit" | "approve" | "reject", comment = "") => request<Expense>(`/api/v1/finance/expenses/${id}/workflow/`, { method: "POST", body: JSON.stringify({ action, comment }) }, true),
  payExpense: (id: string, body: Record<string, unknown>) => request<ExpensePayment>(`/api/v1/finance/expenses/${id}/payments/`, { method: "POST", body: JSON.stringify(body) }, true),
  createIncome: (body: Record<string, unknown>) => request<Income>("/api/v1/finance/income/", { method: "POST", body: JSON.stringify(body) }, true),
  createTransfer: (body: Record<string, unknown>) => request<Transfer>("/api/v1/finance/transfers/", { method: "POST", body: JSON.stringify(body) }, true),
  createReimbursement: (body: Record<string, unknown>) => request<Reimbursement>("/api/v1/finance/reimbursements/", { method: "POST", body: JSON.stringify(body) }, true),
  reimbursementWorkflow: (id: string, action: "submit" | "approve" | "reject", comment = "") => request<Reimbursement>(`/api/v1/finance/reimbursements/${id}/workflow/`, { method: "POST", body: JSON.stringify({ action, comment }) }, true),
};

export const accountingApi = {
  accounts: () => request<LedgerAccount[]>("/api/v1/accounting/accounts/"),
  journals: () => request<JournalEntry[]>("/api/v1/accounting/journals/"),
  periods: () => request<Array<Record<string, unknown>>>("/api/v1/accounting/periods/"),
  trialBalance: () => request<ReportRow[] | Record<string, unknown>>("/api/v1/accounting/reports/trial-balance/"),
  profitLoss: () => request<ReportRow[] | Record<string, unknown>>("/api/v1/accounting/reports/profit-loss/"),
  balanceSheet: () => request<ReportRow[] | Record<string, unknown>>("/api/v1/accounting/reports/balance-sheet/"),
  cashFlow: () => request<ReportRow[] | Record<string, unknown>>("/api/v1/accounting/reports/cash-flow/"),
};

export const planningApi = {
  costCenters: () => request<CostCenter[]>("/api/v1/planning/cost-centers/"),
  products: () => request<Product[]>("/api/v1/planning/products/"),
  projects: () => request<Project[]>("/api/v1/planning/projects/"),
  budgets: () => request<Budget[]>("/api/v1/planning/budgets/"),
  budget: (id: string) => request<Budget & { lines: BudgetLine[] }>(`/api/v1/planning/budgets/${id}/`),
  budgetActuals: (id: string) => request<BudgetActuals>(`/api/v1/planning/budgets/${id}/actuals/`),
  createCostCenter: (body: Record<string, unknown>) => request<CostCenter>("/api/v1/planning/cost-centers/", { method: "POST", body: JSON.stringify(body) }, true),
  updateCostCenter: (id: string, body: Record<string, unknown>) => request<CostCenter>(`/api/v1/planning/cost-centers/${id}/`, { method: "PATCH", body: JSON.stringify(body) }, true),
  createProduct: (body: Record<string, unknown>) => request<Product>("/api/v1/planning/products/", { method: "POST", body: JSON.stringify(body) }, true),
  updateProduct: (id: string, body: Record<string, unknown>) => request<Product>(`/api/v1/planning/products/${id}/`, { method: "PATCH", body: JSON.stringify(body) }, true),
  createProject: (body: Record<string, unknown>) => request<Project>("/api/v1/planning/projects/", { method: "POST", body: JSON.stringify(body) }, true),
  updateProject: (id: string, body: Record<string, unknown>) => request<Project>(`/api/v1/planning/projects/${id}/`, { method: "PATCH", body: JSON.stringify(body) }, true),
  createBudget: (body: Record<string, unknown>) => request<Budget>("/api/v1/planning/budgets/", { method: "POST", body: JSON.stringify(body) }, true),
  updateBudget: (id: string, body: Record<string, unknown>) => request<Budget>(`/api/v1/planning/budgets/${id}/`, { method: "PATCH", body: JSON.stringify(body) }, true),
  createBudgetLine: (budgetId: string, body: Record<string, unknown>) => request<BudgetLine>(`/api/v1/planning/budgets/${budgetId}/lines/`, { method: "POST", body: JSON.stringify(body) }, true),
  expenseAllocations: (expenseId: string) => request<ExpenseAllocation[]>(`/api/v1/planning/expenses/${expenseId}/allocations/`),
  replaceExpenseAllocations: (expenseId: string, allocations: Array<Record<string, unknown>>) => request<ExpenseAllocation[]>(`/api/v1/planning/expenses/${expenseId}/allocations/`, { method: "PUT", body: JSON.stringify({ allocations }) }, true),
};

export const operationsApi = {
  billingSummary: () => request<BillingDashboard>("/api/v1/operations/billing/summary/"),
  billingPeriods: () => request<BillingPeriod[]>("/api/v1/operations/billing/periods/"),
  createBillingPeriod: (body: Record<string, unknown>) => request<BillingPeriod>(
    "/api/v1/operations/billing/periods/",
    { method: "POST", body: JSON.stringify(body) }, true,
  ),
  updateBillingPeriod: (id: string, body: Record<string, unknown>) => request<BillingPeriod>(
    `/api/v1/operations/billing/periods/${id}/`,
    { method: "PATCH", body: JSON.stringify(body) }, true,
  ),
  billingInvoices: () => request<SubscriptionInvoice[]>("/api/v1/operations/billing/invoices/"),
  createBillingInvoice: (body: Record<string, unknown>) => request<SubscriptionInvoice>(
    "/api/v1/operations/billing/invoices/",
    { method: "POST", body: JSON.stringify(body) }, true,
  ),
  updateBillingInvoice: (id: string, body: Record<string, unknown>) => request<SubscriptionInvoice>(
    `/api/v1/operations/billing/invoices/${id}/`,
    { method: "PATCH", body: JSON.stringify(body) }, true,
  ),
  voidBillingInvoice: (id: string) => request<SubscriptionInvoice>(
    `/api/v1/operations/billing/invoices/${id}/void/`,
    { method: "POST" }, true,
  ),
  billingPayments: () => request<BillingPayment[]>("/api/v1/operations/billing/payments/"),
  createBillingPayment: (body: Record<string, unknown>) => request<BillingPayment>(
    "/api/v1/operations/billing/payments/",
    { method: "POST", body: JSON.stringify(body) }, true,
  ),
  replaceBillingAllocations: (id: string, allocations: Array<{ invoice: string; amount: string }>) =>
    request<BillingPayment>(
      `/api/v1/operations/billing/payments/${id}/allocations/`,
      { method: "PUT", body: JSON.stringify({ allocations }) }, true,
    ),
  vendorServices: () => request<VendorService[]>("/api/v1/operations/vendor-services/"),
  createVendorService: (body: Record<string, unknown>) => request<VendorService>(
    "/api/v1/operations/vendor-services/",
    { method: "POST", body: JSON.stringify(body) }, true,
  ),
  updateVendorService: (id: string, body: Record<string, unknown>) => request<VendorService>(
    `/api/v1/operations/vendor-services/${id}/`,
    { method: "PATCH", body: JSON.stringify(body) }, true,
  ),
  serviceAccounts: () => request<ServiceAccount[]>("/api/v1/operations/service-accounts/"),
  createServiceAccount: (body: Record<string, unknown>) => request<ServiceAccount>(
    "/api/v1/operations/service-accounts/",
    { method: "POST", body: JSON.stringify(body) }, true,
  ),
  updateServiceAccount: (id: string, body: Record<string, unknown>) => request<ServiceAccount>(
    `/api/v1/operations/service-accounts/${id}/`,
    { method: "PATCH", body: JSON.stringify(body) }, true,
  ),
  subscriptions: () => request<Subscription[]>("/api/v1/operations/subscriptions/"),
  domains: () => request<DomainRecord[]>("/api/v1/operations/domains/"),
  infrastructure: () => request<InfrastructureAsset[]>("/api/v1/operations/infrastructure/"),
  renewals: (startDate?: string, endDate?: string) => {
    const params = new URLSearchParams();
    if (startDate) params.set("start_date", startDate);
    if (endDate) params.set("end_date", endDate);
    const suffix = params.toString() ? `?${params.toString()}` : "";
    return request<RenewalItem[]>(`/api/v1/operations/renewals/${suffix}`);
  },
  domainRenewals: (domainId: string) => request<DomainRenewal[]>(`/api/v1/operations/domains/${domainId}/renewals/`),
  createSubscription: (body: Record<string, unknown>) => request<Subscription>("/api/v1/operations/subscriptions/", { method: "POST", body: JSON.stringify(body) }, true),
  updateSubscription: (id: string, body: Record<string, unknown>) => request<Subscription>(`/api/v1/operations/subscriptions/${id}/`, { method: "PATCH", body: JSON.stringify(body) }, true),
  subscriptionPayments: (id: string) => request<SubscriptionPayment[]>(`/api/v1/operations/subscriptions/${id}/payments/`),
  markSubscriptionPaid: (id: string, body: Record<string, unknown>) => request<SubscriptionPayment>(`/api/v1/operations/subscriptions/${id}/mark-paid/`, { method: "POST", body: JSON.stringify(body) }, true),
  createDomain: (body: Record<string, unknown>) => request<DomainRecord>("/api/v1/operations/domains/", { method: "POST", body: JSON.stringify(body) }, true),
  updateDomain: (id: string, body: Record<string, unknown>) => request<DomainRecord>(`/api/v1/operations/domains/${id}/`, { method: "PATCH", body: JSON.stringify(body) }, true),
  createInfrastructure: (body: Record<string, unknown>) => request<InfrastructureAsset>("/api/v1/operations/infrastructure/", { method: "POST", body: JSON.stringify(body) }, true),
  updateInfrastructure: (id: string, body: Record<string, unknown>) => request<InfrastructureAsset>(`/api/v1/operations/infrastructure/${id}/`, { method: "PATCH", body: JSON.stringify(body) }, true),
  renewDomain: (domainId: string, body: Record<string, unknown>) => request<DomainRenewal>(`/api/v1/operations/domains/${domainId}/renew/`, { method: "POST", body: JSON.stringify(body) }, true),
};

export const adminApi = {
  members: () => request<Membership[]>("/api/v1/memberships/"),
  legalEntities: () => request<LegalEntity[]>("/api/v1/legal-entities/"),
};
