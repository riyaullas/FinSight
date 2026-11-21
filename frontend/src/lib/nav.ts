import {
  Bell,
  Bot,
  BookOpen,
  Briefcase,
  CreditCard,
  FileBarChart,
  LayoutDashboard,
  LineChart,
  Settings,
  ShieldAlert,
  Store,
  Target,
  Users,
  UserSquare,
  Wallet,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  /** Any one of these permissions makes the item visible. */
  permissions: string[];
  /** Development phase in which the module ships. Items without one are available now. */
  phase?: number;
  summary: string;
}

export const NAV: NavItem[] = [
  { href: "/overview", label: "Overview", icon: LayoutDashboard, permissions: ["dashboard:read"], summary: "Executive dashboard." },
  { href: "/finance", label: "Finance", icon: Wallet, permissions: ["finance:read"], phase: 2, summary: "Cash position, profitability, budgets and forecasts." },
  { href: "/payments", label: "Payments", icon: CreditCard, permissions: ["payments:read"], phase: 2, summary: "Payment ledger with Razorpay, Stripe, Cashfree, PayU and bank imports; refunds, chargebacks and reconciliation." },
  { href: "/accounting", label: "Accounting", icon: BookOpen, permissions: ["accounting:read"], phase: 2, summary: "General ledger, chart of accounts, journal entries, GST records and financial statements." },
  { href: "/risk", label: "Fraud & Risk", icon: ShieldAlert, permissions: ["risk:read"], phase: 4, summary: "Revenue-leakage and anomaly detection with risk scores and evidence for human review." },
  { href: "/crm", label: "CRM", icon: UserSquare, permissions: ["crm:read"], phase: 3, summary: "Leads, contacts, communication history, follow-ups and segmentation." },
  { href: "/sales", label: "Sales", icon: Target, permissions: ["sales:read"], phase: 3, summary: "Pipeline from lead to won, conversion rates, targets and stuck-deal detection." },
  { href: "/customers", label: "Customers", icon: Users, permissions: ["crm:read"], phase: 3, summary: "Customer profiles linked to invoices, payments, lifetime value and churn risk." },
  { href: "/employees", label: "Employees", icon: Briefcase, permissions: ["employees:read"], phase: 3, summary: "Departments, reimbursements, expense claims, approvals and budgets." },
  { href: "/vendors", label: "Vendors", icon: Store, permissions: ["vendors:read"], phase: 3, summary: "Vendor profiles, purchase orders, bills, payment schedules and performance." },
  { href: "/analytics", label: "Analytics", icon: LineChart, permissions: ["analytics:read"], phase: 4, summary: "Growth, retention, cohorts, CAC, LTV and forecasting." },
  { href: "/reports", label: "Reports", icon: FileBarChart, permissions: ["reports:read"], phase: 4, summary: "Daily, weekly, monthly and investor reports with PDF, Excel and CSV export." },
  { href: "/assistant", label: "AI Assistant", icon: Bot, permissions: ["ai:use"], phase: 5, summary: "Ask questions about your business, answered by a local model from verified figures." },
  { href: "/notifications", label: "Notifications", icon: Bell, permissions: ["notifications:read"], phase: 4, summary: "Proactive alerts: what happened, why it was flagged, impact and recommended action." },
  { href: "/settings", label: "Settings", icon: Settings, permissions: ["settings:manage", "users:manage", "audit:read"], summary: "Company, users, roles, security and audit log." },
];

export function visibleNav(can: (p: string) => boolean): NavItem[] {
  // Settings always shows so every user can reach their own security settings.
  return NAV.filter((n) => n.href === "/settings" || n.permissions.some(can));
}
