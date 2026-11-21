import { PRODUCT_NAME } from "@/lib/brand";

export function Logo({ compact = false }: { compact?: boolean }) {
  return (
    <span className="flex items-center gap-2">
      <svg viewBox="0 0 24 24" className="size-6 shrink-0" aria-hidden>
        <rect width="24" height="24" rx="6" className="fill-primary" />
        <path d="M7 16.5V12M12 16.5V8M17 16.5v-6" stroke="white" strokeWidth="2.2" strokeLinecap="round" />
      </svg>
      {compact ? null : <span className="text-[15px] font-semibold tracking-tight text-foreground">{PRODUCT_NAME}</span>}
    </span>
  );
}
