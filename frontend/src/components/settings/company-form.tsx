"use client";

import { useEffect, useState } from "react";
import { Alert, Button, Field, Input, Select } from "@/components/ui/primitives";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

interface CompanyOut {
  name: string;
  legal_name: string | null;
  industry: string | null;
  gstin: string | null;
  fiscal_year_start_month: number;
  timezone: string;
  country: string;
  currency: string;
  require_mfa: boolean;
}

const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

export function CompanyForm({ onSaved, includeOpeningBalance = false, submitLabel = "Save changes" }: { onSaved?: () => void; includeOpeningBalance?: boolean; submitLabel?: string }) {
  const { refresh, can } = useAuth();
  const [c, setC] = useState<CompanyOut | null>(null);
  const [opening, setOpening] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);
  const editable = can("settings:manage");

  useEffect(() => {
    api<CompanyOut>("/api/company").then(setC).catch((e) => setError(e instanceof ApiError ? e.detail : "Unable to load company"));
  }, []);

  if (!c) return error ? <Alert tone="critical">{error}</Alert> : <p className="text-sm text-muted-foreground">Loading…</p>;

  const set = (k: keyof CompanyOut) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setC({ ...c, [k]: k === "fiscal_year_start_month" ? Number(e.target.value) : e.target.value });

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!c) return;
    setBusy(true);
    setError(null);
    setSaved(false);
    try {
      await api("/api/company", {
        method: "PATCH",
        json: {
          name: c.name,
          legal_name: c.legal_name || null,
          industry: c.industry || null,
          gstin: c.gstin || null,
          fiscal_year_start_month: c.fiscal_year_start_month,
          timezone: c.timezone,
          ...(includeOpeningBalance && opening !== "" ? { opening_cash_balance: opening } : {}),
        },
      });
      await refresh();
      setSaved(true);
      onSaved?.();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Unable to save");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      {error ? <Alert tone="critical">{error}</Alert> : null}
      {saved && !onSaved ? <Alert tone="good">Saved.</Alert> : null}
      <fieldset disabled={!editable} className="grid gap-4 sm:grid-cols-2">
        <Field label="Display name" htmlFor="c-name">
          <Input id="c-name" required minLength={2} value={c.name} onChange={set("name")} />
        </Field>
        <Field label="Registered legal name" htmlFor="c-legal">
          <Input id="c-legal" value={c.legal_name ?? ""} onChange={set("legal_name")} />
        </Field>
        <Field label="Industry" htmlFor="c-industry">
          <Input id="c-industry" value={c.industry ?? ""} onChange={set("industry")} placeholder="e.g. SaaS, Retail, Manufacturing" />
        </Field>
        <Field label="GSTIN" htmlFor="c-gstin" hint={c.country === "IN" ? "15-character GST identification number (optional)." : "Applies to Indian entities."}>
          <Input id="c-gstin" value={c.gstin ?? ""} onChange={set("gstin")} maxLength={15} className="font-mono uppercase" />
        </Field>
        <Field label="Financial year starts in" htmlFor="c-fy">
          <Select id="c-fy" value={c.fiscal_year_start_month} onChange={set("fiscal_year_start_month")}>
            {MONTHS.map((m, i) => (
              <option key={m} value={i + 1}>
                {m}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Base currency" htmlFor="c-cur" hint="Set at company creation.">
          <Input id="c-cur" value={c.currency} disabled />
        </Field>
        {includeOpeningBalance ? (
          <Field label="Opening bank balance" htmlFor="c-open" hint="Today's balance across your business bank accounts. Used to compute cash position and runway.">
            <Input id="c-open" inputMode="decimal" pattern="-?[0-9]+(\.[0-9]{1,2})?" value={opening} onChange={(e) => setOpening(e.target.value)} placeholder="0.00" className="tabular" />
          </Field>
        ) : null}
      </fieldset>
      {editable ? (
        <Button type="submit" loading={busy}>
          {submitLabel}
        </Button>
      ) : (
        <p className="text-xs text-muted-foreground">You have read-only access to company settings.</p>
      )}
    </form>
  );
}
