"use client";

import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { formatDate, formatMoney, monthLabel } from "@/lib/format";
import type { DashboardData } from "@/lib/types";

const AXIS = { stroke: "var(--axis)", tick: { fill: "var(--subtle)", fontSize: 11 }, tickLine: false } as const;
const GRID = <CartesianGrid stroke="var(--grid)" strokeDasharray="0" vertical={false} />;

interface SeriesDef {
  key: string;
  label: string;
  color: string;
}

function ChartTooltip({
  active,
  payload,
  label,
  currency,
  labelFormat,
  money = true,
}: {
  active?: boolean;
  payload?: ReadonlyArray<{ dataKey?: unknown; name?: unknown; value?: unknown; color?: string }>;
  label?: unknown;
  currency: string;
  labelFormat: (l: string) => string;
  money?: boolean;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-md border border-border bg-card px-3 py-2 text-xs shadow-sm">
      <p className="mb-1 font-medium text-foreground">{labelFormat(String(label))}</p>
      {payload.map((p) => (
        <p key={String(p.dataKey)} className="flex items-center gap-2 text-muted-foreground">
          <span className="size-2 rounded-full" style={{ background: p.color }} aria-hidden />
          <span className="flex-1">{String(p.name)}</span>
          <span className="tabular font-medium text-foreground">{money ? formatMoney(Number(p.value), currency) : String(p.value)}</span>
        </p>
      ))}
    </div>
  );
}

export function Legend({ series }: { series: SeriesDef[] }) {
  if (series.length < 2) return null;
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
      {series.map((s) => (
        <li key={s.key} className="flex items-center gap-1.5">
          <span className="h-2 w-2.5 rounded-sm" style={{ background: s.color }} aria-hidden />
          {s.label}
        </li>
      ))}
    </ul>
  );
}

function toNumbers<T extends object>(rows: T[], keys: string[]): Record<string, number | string>[] {
  return rows.map((r) => {
    const out: Record<string, number | string> = { ...(r as Record<string, number | string>) };
    for (const k of keys) out[k] = Number(out[k]);
    return out;
  });
}

const compact = (currency: string) => (v: number) => formatMoney(v, currency, { compact: true });

export const REV_EXP: SeriesDef[] = [
  { key: "revenue", label: "Revenue", color: "var(--series-1)" },
  { key: "expenses", label: "Expenses", color: "var(--series-2)" },
];

export function RevenueExpenseChart({ data, currency }: { data: DashboardData["charts"]["monthly"]; currency: string }) {
  const rows = toNumbers(data, ["revenue", "expenses"]);
  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart data={rows} barGap={2} barCategoryGap="28%" margin={{ top: 8, right: 4, left: 4, bottom: 0 }}>
        {GRID}
        <XAxis dataKey="month" tickFormatter={monthLabel} {...AXIS} />
        <YAxis tickFormatter={compact(currency)} {...AXIS} axisLine={false} width={64} />
        <Tooltip cursor={{ fill: "var(--muted)", opacity: 0.6 }} content={(p) => <ChartTooltip {...p} currency={currency} labelFormat={monthLabel} />} />
        {REV_EXP.map((s) => (
          <Bar key={s.key} dataKey={s.key} name={s.label} fill={s.color} radius={[4, 4, 0, 0]} maxBarSize={18} />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}

export function ProfitTrendChart({ data, currency }: { data: DashboardData["charts"]["monthly"]; currency: string }) {
  const rows = toNumbers(data, ["profit"]);
  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart data={rows} margin={{ top: 8, right: 8, left: 4, bottom: 0 }}>
        {GRID}
        <XAxis dataKey="month" tickFormatter={monthLabel} {...AXIS} />
        <YAxis tickFormatter={compact(currency)} {...AXIS} axisLine={false} width={64} />
        <ReferenceLine y={0} stroke="var(--axis)" />
        <Tooltip cursor={{ stroke: "var(--axis)" }} content={(p) => <ChartTooltip {...p} currency={currency} labelFormat={monthLabel} />} />
        <Line
          dataKey="profit"
          name="Net profit"
          stroke="var(--series-1)"
          strokeWidth={2}
          dot={{ r: 3, fill: "var(--series-1)", stroke: "var(--card)", strokeWidth: 2 }}
          activeDot={{ r: 5, stroke: "var(--card)", strokeWidth: 2 }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

export function CashFlowChart({ data, currency }: { data: DashboardData["charts"]["monthly"]; currency: string }) {
  const rows = toNumbers(data, ["net_cash", "cash_in", "cash_out"]);
  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={rows} margin={{ top: 8, right: 4, left: 4, bottom: 0 }}>
        {GRID}
        <XAxis dataKey="month" tickFormatter={monthLabel} {...AXIS} />
        <YAxis tickFormatter={compact(currency)} {...AXIS} axisLine={false} width={64} />
        <ReferenceLine y={0} stroke="var(--axis)" />
        <Tooltip cursor={{ fill: "var(--muted)", opacity: 0.6 }} content={(p) => <ChartTooltip {...p} currency={currency} labelFormat={monthLabel} />} />
        <Bar dataKey="net_cash" name="Net cash flow" radius={[4, 4, 4, 4]} maxBarSize={22}>
          {rows.map((r) => (
            <Cell key={String(r.month)} fill={Number(r.net_cash) >= 0 ? "var(--series-3)" : "var(--series-2)"} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

export function DailyRevenueChart({ data, currency }: { data: DashboardData["charts"]["daily_revenue"]; currency: string }) {
  const rows = toNumbers(data, ["revenue"]);
  const day = (d: string) => formatDate(d).replace(/ \d{4}$/, "");
  return (
    <ResponsiveContainer width="100%" height={220}>
      <AreaChart data={rows} margin={{ top: 8, right: 8, left: 4, bottom: 0 }}>
        <defs>
          <linearGradient id="rev-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--series-1)" stopOpacity={0.22} />
            <stop offset="100%" stopColor="var(--series-1)" stopOpacity={0} />
          </linearGradient>
        </defs>
        {GRID}
        <XAxis dataKey="date" tickFormatter={day} {...AXIS} minTickGap={24} />
        <YAxis tickFormatter={compact(currency)} {...AXIS} axisLine={false} width={64} />
        <Tooltip cursor={{ stroke: "var(--axis)" }} content={(p) => <ChartTooltip {...p} currency={currency} labelFormat={(l) => formatDate(l)} />} />
        <Area dataKey="revenue" name="Revenue" stroke="var(--series-1)" strokeWidth={2} fill="url(#rev-fill)" />
      </AreaChart>
    </ResponsiveContainer>
  );
}

export function CustomerAcquisitionChart({ data }: { data: DashboardData["charts"]["monthly"] }) {
  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={data} margin={{ top: 8, right: 4, left: 4, bottom: 0 }}>
        {GRID}
        <XAxis dataKey="month" tickFormatter={monthLabel} {...AXIS} />
        <YAxis allowDecimals={false} {...AXIS} axisLine={false} width={32} />
        <Tooltip
          cursor={{ fill: "var(--muted)", opacity: 0.6 }}
          content={(p) => <ChartTooltip {...p} currency="" money={false} labelFormat={monthLabel} />}
        />
        <Bar dataKey="new_customers" name="New customers" fill="var(--series-1)" radius={[4, 4, 0, 0]} maxBarSize={22} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export function ExpenseBreakdown({ data, currency }: { data: DashboardData["charts"]["expense_breakdown"]; currency: string }) {
  const total = data.reduce((s, d) => s + Number(d.amount), 0);
  const max = Math.max(...data.map((d) => Number(d.amount)), 1);
  return (
    <ul className="space-y-3">
      {data.slice(0, 8).map((d) => {
        const v = Number(d.amount);
        return (
          <li key={d.category}>
            <div className="mb-1 flex items-baseline justify-between gap-3 text-xs">
              <span className="truncate text-foreground">{d.category}</span>
              <span className="tabular shrink-0 text-muted-foreground">
                {formatMoney(v, currency, { compact: true })} · {total ? ((v / total) * 100).toFixed(0) : 0}%
              </span>
            </div>
            <div className="h-1.5 rounded-full bg-muted">
              <div className="h-1.5 rounded-full" style={{ width: `${(v / max) * 100}%`, background: "var(--series-1)" }} />
            </div>
          </li>
        );
      })}
    </ul>
  );
}
