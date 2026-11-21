"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AuthShell } from "@/components/auth-shell";
import { Alert, Button, Field, Input, Select } from "@/components/ui/primitives";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { passwordIssues } from "@/lib/password";
import type { LoginResponse, SetupStatus } from "@/lib/types";

const CURRENCIES = [
  ["INR", "Indian Rupee (₹)"],
  ["USD", "US Dollar ($)"],
  ["EUR", "Euro (€)"],
  ["GBP", "Pound Sterling (£)"],
];
const TIMEZONES = ["Asia/Kolkata", "Asia/Dubai", "Asia/Singapore", "Europe/London", "America/New_York", "UTC"];

export default function SetupPage() {
  const router = useRouter();
  const { setUser } = useAuth();
  const [status, setStatus] = useState<SetupStatus | null>(null);
  const [step, setStep] = useState<1 | 2>(1);
  const [form, setForm] = useState({
    company_name: "",
    country: "IN",
    currency: "INR",
    timezone: "Asia/Kolkata",
    owner_full_name: "",
    owner_email: "",
    owner_password: "",
    confirm: "",
  });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api<SetupStatus>("/api/setup/status").then(setStatus).catch(() => setError("Unable to reach the server"));
  }, []);

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  const issues = passwordIssues(form.owner_password);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (step === 1) {
      setStep(2);
      return;
    }
    if (issues.length || form.owner_password !== form.confirm) return;
    setBusy(true);
    setError(null);
    try {
      const payload = { ...form, confirm: undefined };
      const r = await api<LoginResponse>("/api/setup/company", { method: "POST", json: payload });
      if (r.user) {
        setUser(r.user);
        router.replace("/onboarding");
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Unable to reach the server");
    } finally {
      setBusy(false);
    }
  }

  if (status && !status.registration_open) {
    return (
      <AuthShell title="Already set up" subtitle="This installation already has a company.">
        <Button className="w-full" onClick={() => router.replace("/login")}>
          Go to sign in
        </Button>
      </AuthShell>
    );
  }

  return (
    <AuthShell
      title={step === 1 ? "Set up your company" : "Create the owner account"}
      subtitle={step === 1 ? "Step 1 of 2 — basic details. You can change these later." : "Step 2 of 2 — this account has full administrative access."}
    >
      <form onSubmit={submit} className="space-y-4">
        {error ? <Alert tone="critical">{error}</Alert> : null}
        {step === 1 ? (
          <>
            <Field label="Company name" htmlFor="company_name">
              <Input id="company_name" required minLength={2} maxLength={200} autoFocus value={form.company_name} onChange={set("company_name")} />
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Country" htmlFor="country">
                <Select id="country" value={form.country} onChange={set("country")}>
                  <option value="IN">India</option>
                  <option value="AE">UAE</option>
                  <option value="SG">Singapore</option>
                  <option value="GB">United Kingdom</option>
                  <option value="US">United States</option>
                </Select>
              </Field>
              <Field label="Currency" htmlFor="currency">
                <Select id="currency" value={form.currency} onChange={set("currency")}>
                  {CURRENCIES.map(([v, l]) => (
                    <option key={v} value={v}>
                      {l}
                    </option>
                  ))}
                </Select>
              </Field>
            </div>
            <Field label="Time zone" htmlFor="timezone" hint="Used to group transactions into days and months.">
              <Select id="timezone" value={form.timezone} onChange={set("timezone")}>
                {TIMEZONES.map((t) => (
                  <option key={t}>{t}</option>
                ))}
              </Select>
            </Field>
            <Button type="submit" className="w-full">
              Continue
            </Button>
          </>
        ) : (
          <>
            <Field label="Full name" htmlFor="owner_full_name">
              <Input id="owner_full_name" required minLength={2} autoFocus value={form.owner_full_name} onChange={set("owner_full_name")} />
            </Field>
            <Field label="Work email" htmlFor="owner_email">
              <Input id="owner_email" type="email" autoComplete="username" required value={form.owner_email} onChange={set("owner_email")} />
            </Field>
            <Field
              label="Password"
              htmlFor="owner_password"
              hint={form.owner_password && issues.length ? `Needs ${issues.join(" and ")}.` : "12+ characters, mixing letters, digits and symbols."}
            >
              <Input
                id="owner_password"
                type="password"
                autoComplete="new-password"
                required
                value={form.owner_password}
                onChange={set("owner_password")}
                aria-invalid={!!form.owner_password && issues.length > 0}
              />
            </Field>
            <Field label="Confirm password" htmlFor="confirm" hint={form.confirm && form.confirm !== form.owner_password ? "Passwords do not match." : undefined}>
              <Input
                id="confirm"
                type="password"
                autoComplete="new-password"
                required
                value={form.confirm}
                onChange={set("confirm")}
                aria-invalid={!!form.confirm && form.confirm !== form.owner_password}
              />
            </Field>
            <div className="flex gap-2">
              <Button type="button" variant="secondary" onClick={() => setStep(1)}>
                Back
              </Button>
              <Button type="submit" className="flex-1" loading={busy} disabled={issues.length > 0 || form.owner_password !== form.confirm}>
                Create company
              </Button>
            </div>
          </>
        )}
      </form>
    </AuthShell>
  );
}
