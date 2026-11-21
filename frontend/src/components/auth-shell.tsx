import { Lock } from "lucide-react";
import { Logo } from "./logo";

/** Two-column layout for login and first-run setup screens. */
export function AuthShell({ title, subtitle, children }: { title: string; subtitle: string; children: React.ReactNode }) {
  return (
    <main className="grid min-h-screen lg:grid-cols-[1fr_minmax(0,560px)]">
      <section className="relative hidden overflow-hidden border-r border-border bg-card lg:flex lg:flex-col lg:justify-between lg:p-12">
        <Logo />
        <div className="max-w-md">
          <p className="text-2xl font-semibold leading-snug tracking-tight text-foreground">
            One company. One system. Complete business visibility.
          </p>
          <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
            Finance, payments, accounting, CRM, risk and analytics in a single platform — running on your own
            infrastructure, with your data under your control.
          </p>
          <ul className="mt-8 space-y-3 text-sm text-muted-foreground">
            {[
              "Runs on your server — financial data never leaves your network",
              "Local AI assistant; no third-party AI services",
              "Role-based access, MFA and a tamper-evident audit trail",
            ].map((t) => (
              <li key={t} className="flex items-start gap-2.5">
                <Lock className="mt-0.5 size-3.5 shrink-0 text-primary" aria-hidden />
                {t}
              </li>
            ))}
          </ul>
        </div>
        <p className="text-xs text-subtle">Self-hosted edition</p>
      </section>
      <section className="flex items-center justify-center px-5 py-10 sm:px-10">
        <div className="w-full max-w-sm">
          <div className="mb-8 lg:hidden">
            <Logo />
          </div>
          <h1 className="text-xl font-semibold tracking-tight text-foreground">{title}</h1>
          <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p>
          <div className="mt-6">{children}</div>
        </div>
      </section>
    </main>
  );
}
