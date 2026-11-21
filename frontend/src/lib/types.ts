export interface Company {
  id: string;
  name: string;
  currency: string;
  country: string;
  timezone: string;
  is_demo: boolean;
  require_mfa: boolean;
  onboarding_completed: boolean;
}

export interface Me {
  id: string;
  email: string;
  full_name: string;
  role: string;
  role_name: string;
  permissions: string[];
  mfa_enabled: boolean;
  must_change_password: boolean;
  company: Company;
}

export interface LoginResponse {
  mfa_required: boolean;
  mfa_token: string | null;
  user: Me | null;
}

export interface SetupStatus {
  initialised: boolean;
  registration_open: boolean;
  product_name: string;
}

interface Kpi {
  value: string;
  previous: string;
  change_pct: string | null;
}

export interface DashboardData {
  currency: string;
  is_demo: boolean;
  has_data: boolean;
  period: { start: string; end: string };
  previous_period: { start: string; end: string };
  as_of: string;
  kpis: {
    revenue: Kpi;
    expenses: Kpi;
    net_profit: Kpi;
    gross_profit: Kpi;
    transaction_fees: Kpi;
    cash_balance: { value: string | null };
    accounts_receivable: { value: string };
    accounts_payable: { value: string };
    mrr: { value: string };
    arr: { value: string };
    net_burn: { value: string };
    gross_burn: { value: string };
    runway_months: { value: string | null };
    active_customers: { value: number };
    new_customers: { value: number; previous: number; change_pct: string | null };
    pending_invoices: { count: number; amount: string };
    overdue_invoices: { count: number; amount: string };
    failed_payments: { count: number; amount: string };
    sales: { count: number; average_value: string };
  };
  charts: {
    daily_revenue: { date: string; revenue: string }[];
    monthly: {
      month: string;
      revenue: string;
      expenses: string;
      profit: string;
      cash_in: string;
      cash_out: string;
      net_cash: string;
      new_customers: number;
    }[];
    expense_breakdown: { category: string; amount: string }[];
  };
  recent_transactions: {
    id: string;
    occurred_at: string;
    customer: string | null;
    gateway: string;
    method: string | null;
    amount: string;
    status: string;
    reference: string | null;
  }[];
  recent_alerts: {
    id: string;
    severity: string;
    title: string;
    description: string;
    estimated_impact: string | null;
    detected_at: string;
  }[];
  summary: string[];
}
