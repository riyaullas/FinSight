/** Display formatting. Values arrive from the API as decimal strings; they are only parsed for display. */

const LOCALE_BY_CURRENCY: Record<string, string> = { INR: "en-IN", USD: "en-US", EUR: "en-IE", GBP: "en-GB" };

export function localeFor(currency: string): string {
  return LOCALE_BY_CURRENCY[currency] ?? "en-US";
}

export function formatMoney(value: string | number | null | undefined, currency: string, opts: { compact?: boolean } = {}): string {
  if (value === null || value === undefined || value === "") return "—";
  const n = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(n)) return "—";
  if (opts.compact && Math.abs(n) >= 100000) {
    if (currency === "INR") {
      // Indian numbering: lakh (1,00,000) and crore (1,00,00,000)
      const abs = Math.abs(n);
      const sign = n < 0 ? "-" : "";
      if (abs >= 1e7) return `${sign}₹${trim(abs / 1e7)} Cr`;
      return `${sign}₹${trim(abs / 1e5)} L`;
    }
    return new Intl.NumberFormat(localeFor(currency), {
      style: "currency",
      currency,
      notation: "compact",
      maximumFractionDigits: 1,
    }).format(n);
  }
  return new Intl.NumberFormat(localeFor(currency), {
    style: "currency",
    currency,
    minimumFractionDigits: opts.compact ? 0 : 2,
    maximumFractionDigits: opts.compact ? 0 : 2,
  }).format(n);
}

function trim(n: number): string {
  return n.toFixed(2).replace(/\.?0+$/, "");
}

export function formatPct(value: string | null | undefined): string {
  if (value === null || value === undefined) return "—";
  const n = Number(value);
  return `${n > 0 ? "+" : ""}${n.toFixed(1)}%`;
}

export function formatDate(iso: string, withTime = false): string {
  const d = new Date(iso);
  return new Intl.DateTimeFormat("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
    ...(withTime ? { hour: "2-digit", minute: "2-digit" } : {}),
  }).format(d);
}

export function monthLabel(yyyyMm: string): string {
  const [y, m] = yyyyMm.split("-").map(Number);
  return new Intl.DateTimeFormat("en-IN", { month: "short", year: "2-digit" }).format(new Date(y, m - 1, 1));
}

/** Whether a change is favourable. For costs, a decrease is good. */
export function trendTone(changePct: string | null | undefined, higherIsBetter = true): "good" | "bad" | "neutral" {
  if (changePct === null || changePct === undefined) return "neutral";
  const n = Number(changePct);
  if (n === 0) return "neutral";
  return n > 0 === higherIsBetter ? "good" : "bad";
}
