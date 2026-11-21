"use client";

import { AlertTriangle, BarChart3, Info, Receipt, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  CashFlowChart,
  CustomerAcquisitionChart,
  DailyRevenueChart,
  ExpenseBreakdown,
  Legend,
  ProfitTrendChart,
  REV_EXP,
  RevenueExpenseChart,
} from "@/components/dashboard/charts";
import { KpiTile } from "@/components/dashboard/kpi";
import { Alert, Badge, Button, Card, CardContent, CardDescription, CardHeader, CardTitle, EmptyState, Skeleton } from "@/components/ui/primitives";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatDate, formatMoney } from "@/lib/format";
import type { DashboardData } from "@/lib/types";
import { cn } from "@/lib/utils";

type PeriodKey = "mtd" | "last_month" | "90d" | "fytd";

function iso(d: Date) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function periodRange(key: PeriodKey): { start: string; end: string } | null {
  const now = new Date();
  if (key === "mtd") return null;
  if (key === "last_month") {
    const start = new Date(now.getFullYear(), now.getMonth() - 1, 1);
    const end = new Date(now.getFullYear(), now.getMonth(), 0);
    return { start: iso(start), end: iso(end) };
  }
  if (key === "90d") {
    const start = new Date(now);
    start.setDate(start.getDate() - 89);
    return { start: iso(start), end: iso(now) };
  }
  // Indian financial year: April to March
  const fyStartYear = now.getMonth() >= 3 ? now.getFullYear() : now.getFullYear() - 1;
  return { start: iso(new Date(fyStartYear, 3, 1)), end: iso(now) };
}

const PERIODS: { key: PeriodKey; label: string }[] = [
  { key: "mtd", label: "This month" },
  { key: "last_month", label: "Last month" },
  { key: "90d", label: "Last 90 days" },
  { key: "fytd", label: "Financial year" },
];

const STATUS_TONE: Record<string, "good" | "critical" | "warning" | "neutral"> = {
  succeeded: "good",
  failed: "critical",
  pending: "warning",
  refunded: "neutral",
  partially_refunded: "neutral",
  disputed: "critical",
};

function ChartCard({ title, description, legend, children, className }: { title: string; description?: string; legend?: React.ReactNode; children: React.ReactNode; className?: string }) {
  return (
    <Card className={className}>
      <CardHeader>
        <div>
          <CardTitle>{title}</CardTitle>
          {description ? <CardDescription className="mt-0.5">{description}</CardDescription> : null}
        </div>
        {legend}
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

export default function OverviewPage() {
  const { user, can } = useAuth();
  const [period, setPeriod] = useState<PeriodKey>("mtd");
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchSummary = useCallback((key: PeriodKey) => {
    const range = periodRange(key);
    const qs = range ? `?start=${range.start}&end=${range.end}` : "";
    return api<DashboardData>(`/api/dashboard/summary${qs}`);
  }, []);

  useEffect(() => {
    let cancelled = false;
    fetchSummary(period)
      .then((d) => {
        if (cancelled) return;
        setData(d);
        setError(null);
      })
      .catch((err) => !cancelled && setError(err instanceof ApiError ? err.detail : "Unable to load the dashboard"))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [period, fetchSummary]);

  function selectPeriod(key: PeriodKey) {
    setLoading(true);
    setPeriod(key);
  }

  function load(key: PeriodKey) {
    setLoading(true);
    setError(null);
    fetchSummary(key)
      .then(setData)
      .catch((err) => setError(err instanceof ApiError ? err.detail : "Unable to load the dashboard"))
      .finally(() => setLoading(false));
  }

  const currency = data?.currency ?? user?.company.currency ?? "INR";
  const money = useMemo(() => (v: string | null | undefined) => formatMoney(v, currency), [currency]);

  if (!can("dashboard:read")) {
    return (
      <Card>
        <EmptyState icon={<ShieldCheck className="size-5" />} title="No dashboard access" description="Your role does not include the executive dashboard. Ask an administrator if you need it." />
      </Card>
    );
  }

  const k = data?.kpis;

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Overview</h1>
          <p className="mt-0.5 text-sm text-muted-foreground">
            {data
              ? `${formatDate(data.period.start)} – ${formatDate(data.period.end)} · compared with ${formatDate(data.previous_period.start)} – ${formatDate(data.previous_period.end)}`
              : "Loading period…"}
          </p>
        </div>
        <div role="radiogroup" aria-label="Reporting period" className="inline-flex rounded-md border border-border bg-card p-0.5">
          {PERIODS.map((p) => (
            <button
              key={p.key}
              role="radio"
              aria-checked={period === p.key}
              onClick={() => selectPeriod(p.key)}
              className={cn(
                "rounded px-2.5 py-1 text-xs font-medium transition-colors",
                period === p.key ? "bg-muted text-foreground" : "text-muted-foreground hover:text-foreground",
              )}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {error ? (
        <Alert tone="critical">
          {error}{" "}
          <Button variant="link" size="sm" onClick={() => load(period)}>
            Retry
          </Button>
        </Alert>
      ) : null}

      {loading && !data ? (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-6">
          {Array.from({ length: 12 }).map((_, i) => (
            <Skeleton key={i} className="h-[92px]" />
          ))}
        </div>
      ) : null}

      {data && !data.has_data ? (
        <Card>
          <EmptyState
            icon={<BarChart3 className="size-5" />}
            title="No financial activity yet"
            description="The dashboard fills in automatically once payments, invoices and expenses are recorded. Payment-gateway connections and bank imports arrive with the Payments module."
            action={
              can("settings:manage") ? (
                <Button variant="secondary" asChild>
                  <Link href="/settings">Review company settings</Link>
                </Button>
              ) : undefined
            }
          />
        </Card>
      ) : null}

      {data && k && data.has_data ? (
        <div className={cn("space-y-6 transition-opacity", loading && "opacity-60")}>
          <section aria-label="Key metrics" className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-6">
            <KpiTile label="Revenue" value={money(k.revenue.value)} change={k.revenue.change_pct} />
            <KpiTile label="Expenses" value={money(k.expenses.value)} change={k.expenses.change_pct} higherIsBetter={false} />
            <KpiTile label="Net profit" value={money(k.net_profit.value)} change={k.net_profit.change_pct} />
            <KpiTile label="Gross profit" value={money(k.gross_profit.value)} change={k.gross_profit.change_pct} />
            <KpiTile label="Cash balance" value={money(k.cash_balance.value)} hint={`as of ${formatDate(data.as_of)}`} />
            <KpiTile
              label="Cash runway"
              value={k.runway_months.value ? `${k.runway_months.value} months` : "No net burn"}
              hint={Number(k.net_burn.value) > 0 ? `net burn ${formatMoney(k.net_burn.value, currency, { compact: true })}/mo` : undefined}
            />
            <KpiTile label="MRR" value={money(k.mrr.value)} hint={`ARR ${formatMoney(k.arr.value, currency, { compact: true })}`} />
            <KpiTile label="Accounts receivable" value={money(k.accounts_receivable.value)} hint={`${k.pending_invoices.count} open invoices`} />
            <KpiTile label="Accounts payable" value={money(k.accounts_payable.value)} />
            <KpiTile label="Active customers" value={String(k.active_customers.value)} hint={`${k.new_customers.value} new this period`} />
            <KpiTile
              label="Sales"
              value={String(k.sales.count)}
              hint={k.sales.count ? `avg ${formatMoney(k.sales.average_value, currency, { compact: true })}` : undefined}
            />
            <KpiTile label="Overdue invoices" value={money(k.overdue_invoices.amount)} hint={`${k.overdue_invoices.count} invoices`} />
          </section>

          {data.summary.length ? (
            <Card>
              <CardHeader>
                <div>
                  <CardTitle>Business summary</CardTitle>
                  <CardDescription className="mt-0.5">Generated from the figures above by fixed rules. The local AI assistant arrives in a later release.</CardDescription>
                </div>
                <Info className="size-4 text-subtle" aria-hidden />
              </CardHeader>
              <CardContent>
                <ul className="space-y-1.5 text-sm text-foreground">
                  {data.summary.map((s) => (
                    <li key={s} className="flex gap-2">
                      <span className="mt-2 size-1 shrink-0 rounded-full bg-subtle" aria-hidden />
                      {s}
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          ) : null}

          <div className="grid gap-4 xl:grid-cols-3">
            <ChartCard title="Revenue and expenses" description="Last 12 months" legend={<Legend series={REV_EXP} />} className="xl:col-span-2">
              <RevenueExpenseChart data={data.charts.monthly} currency={currency} />
            </ChartCard>
            <ChartCard title="Expense breakdown" description="Selected period, including gateway fees">
              {data.charts.expense_breakdown.length ? (
                <ExpenseBreakdown data={data.charts.expense_breakdown} currency={currency} />
              ) : (
                <EmptyState title="No expenses in this period" description="Expenses recorded for these dates will appear here." />
              )}
            </ChartCard>
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <ChartCard title="Daily revenue" description="Last 30 days">
              <DailyRevenueChart data={data.charts.daily_revenue} currency={currency} />
            </ChartCard>
            <ChartCard title="Net profit trend" description="Last 12 months">
              <ProfitTrendChart data={data.charts.monthly} currency={currency} />
            </ChartCard>
            <ChartCard title="Net cash flow" description="Cash received minus cash paid, by month">
              <CashFlowChart data={data.charts.monthly} currency={currency} />
            </ChartCard>
            <ChartCard title="Customer acquisition" description="New customers per month">
              <CustomerAcquisitionChart data={data.charts.monthly} />
            </ChartCard>
          </div>

          <div className="grid gap-4 xl:grid-cols-3">
            <Card className="xl:col-span-2">
              <CardHeader>
                <div>
                  <CardTitle>Recent transactions</CardTitle>
                  <CardDescription className="mt-0.5">Latest payments across all gateways</CardDescription>
                </div>
              </CardHeader>
              <CardContent className="overflow-x-auto px-0 pb-2">
                {data.recent_transactions.length ? (
                  <table className="w-full min-w-[560px] text-sm">
                    <thead>
                      <tr className="border-b border-border text-left text-xs text-muted-foreground">
                        <th className="px-5 py-2 font-medium">Date</th>
                        <th className="px-2 py-2 font-medium">Customer</th>
                        <th className="px-2 py-2 font-medium">Reference</th>
                        <th className="px-2 py-2 font-medium">Status</th>
                        <th className="px-5 py-2 text-right font-medium">Amount</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.recent_transactions.map((t) => (
                        <tr key={t.id} className="border-b border-border last:border-0">
                          <td className="whitespace-nowrap px-5 py-2.5 text-muted-foreground">{formatDate(t.occurred_at, true)}</td>
                          <td className="max-w-[200px] truncate px-2 py-2.5">{t.customer ?? "—"}</td>
                          <td className="px-2 py-2.5 font-mono text-xs text-muted-foreground">{t.reference ?? "—"}</td>
                          <td className="px-2 py-2.5">
                            <Badge tone={STATUS_TONE[t.status] ?? "neutral"}>{t.status.replace("_", " ")}</Badge>
                          </td>
                          <td className="tabular whitespace-nowrap px-5 py-2.5 text-right font-medium">{money(t.amount)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <EmptyState icon={<Receipt className="size-5" />} title="No transactions yet" description="Payments appear here as they are recorded." />
                )}
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <div>
                  <CardTitle>Recent alerts</CardTitle>
                  <CardDescription className="mt-0.5">Open items needing attention</CardDescription>
                </div>
              </CardHeader>
              <CardContent>
                {data.recent_alerts.length ? (
                  <ul className="space-y-3">
                    {data.recent_alerts.map((a) => (
                      <li key={a.id} className="flex gap-2.5">
                        <AlertTriangle className={cn("mt-0.5 size-4 shrink-0", a.severity === "critical" || a.severity === "high" ? "text-critical" : "text-serious")} aria-hidden />
                        <div className="min-w-0">
                          <p className="text-sm font-medium">{a.title}</p>
                          <p className="text-xs text-muted-foreground">
                            <span className="capitalize">{a.severity}</span> · {formatDate(a.detected_at)}
                            {a.estimated_impact ? ` · impact ${money(a.estimated_impact)}` : ""}
                          </p>
                        </div>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <EmptyState
                    icon={<ShieldCheck className="size-5" />}
                    title="No open alerts"
                    description="Automated fraud, leakage and anomaly detection is part of the Risk module (coming soon)."
                  />
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      ) : null}
    </div>
  );
}
