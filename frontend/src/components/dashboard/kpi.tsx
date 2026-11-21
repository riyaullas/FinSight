import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";
import { Card } from "@/components/ui/primitives";
import { formatPct, trendTone } from "@/lib/format";
import { cn } from "@/lib/utils";

export function KpiTile({
  label,
  value,
  change,
  higherIsBetter = true,
  hint,
}: {
  label: string;
  value: string;
  change?: string | null;
  higherIsBetter?: boolean;
  hint?: string;
}) {
  const tone = trendTone(change, higherIsBetter);
  const Icon = change == null || Number(change) === 0 ? Minus : Number(change) > 0 ? ArrowUpRight : ArrowDownRight;
  return (
    <Card className="px-4 py-3.5">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="tabular mt-1.5 truncate text-xl font-semibold tracking-tight text-foreground" title={value}>
        {value}
      </p>
      <div className="mt-1 flex min-h-4 items-center gap-1 text-[11px]">
        {change !== undefined ? (
          <span
            className={cn(
              "tabular inline-flex items-center gap-0.5 font-medium",
              tone === "good" && "text-good-ink",
              tone === "bad" && "text-critical",
              tone === "neutral" && "text-muted-foreground",
            )}
          >
            <Icon className="size-3" aria-hidden />
            {change == null ? "No prior data" : formatPct(change)}
            <span className="sr-only">{tone === "good" ? "(favourable)" : tone === "bad" ? "(unfavourable)" : ""}</span>
          </span>
        ) : null}
        {hint ? <span className="truncate text-subtle">{hint}</span> : null}
      </div>
    </Card>
  );
}
