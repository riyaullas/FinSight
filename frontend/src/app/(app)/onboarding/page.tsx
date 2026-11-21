"use client";

import { Check } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { MfaSetup } from "@/components/security-forms";
import { CompanyForm } from "@/components/settings/company-form";
import { UsersPanel } from "@/components/settings/users-panel";
import { Alert, Button, Card, CardContent } from "@/components/ui/primitives";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

const STEPS = ["Company details", "Secure your account", "Invite your team"];

export default function OnboardingPage() {
  const { user, refresh, can } = useAuth();
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (!user) return null;
  if (!can("settings:manage")) {
    router.replace("/overview");
    return null;
  }

  async function finish() {
    setBusy(true);
    setError(null);
    try {
      await api("/api/company", { method: "PATCH", json: { onboarding_completed: true } });
      await refresh();
      router.replace("/overview");
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Unable to finish onboarding");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Welcome, {user.full_name.split(" ")[0]}</h1>
        <p className="mt-0.5 text-sm text-muted-foreground">Three short steps to get {user.company.name} ready. You can change everything later in Settings.</p>
      </div>
      <ol className="flex flex-col gap-2 sm:flex-row sm:gap-6">
        {STEPS.map((s, i) => (
          <li key={s} className="flex items-center gap-2 text-sm">
            <span
              className={cn(
                "flex size-6 items-center justify-center rounded-full border text-xs font-medium",
                i < step && "border-primary bg-primary text-primary-foreground",
                i === step && "border-primary text-primary",
                i > step && "border-border text-muted-foreground",
              )}
            >
              {i < step ? <Check className="size-3.5" /> : i + 1}
            </span>
            <span className={i === step ? "font-medium" : "text-muted-foreground"}>{s}</span>
          </li>
        ))}
      </ol>
      {error ? <Alert tone="critical">{error}</Alert> : null}

      {step === 0 ? (
        <Card>
          <CardContent className="pt-5">
            <CompanyForm includeOpeningBalance submitLabel="Save and continue" onSaved={() => setStep(1)} />
          </CardContent>
        </Card>
      ) : null}

      {step === 1 ? (
        <Card>
          <CardContent className="space-y-4 pt-5">
            {user.mfa_enabled ? <Alert tone="good">Two-factor authentication is enabled on your account.</Alert> : <MfaSetup />}
            <div className="flex gap-2 border-t border-border pt-4">
              <Button onClick={() => setStep(2)}>{user.mfa_enabled ? "Continue" : "Skip for now"}</Button>
            </div>
            {!user.mfa_enabled ? (
              <p className="text-xs text-muted-foreground">
                Strongly recommended: owner accounts control all financial data. You can enable it later under Settings → Security.
              </p>
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      {step === 2 ? (
        <div className="space-y-4">
          <UsersPanel />
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => setStep(1)}>
              Back
            </Button>
            <Button onClick={finish} loading={busy}>
              Finish and open dashboard
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
