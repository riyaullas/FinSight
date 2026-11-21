"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AuthShell } from "@/components/auth-shell";
import { Alert, Button, Field, Input } from "@/components/ui/primitives";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { LoginResponse, Me } from "@/lib/types";

export default function LoginPage() {
  const router = useRouter();
  const { user, setUser } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mfaToken, setMfaToken] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (user) router.replace("/");
  }, [user, router]);

  function done(me: Me) {
    setUser(me);
    router.replace(me.company.onboarding_completed ? "/overview" : "/onboarding");
  }

  async function submitPassword(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const r = await api<LoginResponse>("/api/auth/login", { method: "POST", json: { email, password } });
      if (r.mfa_required && r.mfa_token) {
        setMfaToken(r.mfa_token);
        setPassword("");
      } else if (r.user) done(r.user);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Unable to reach the server");
    } finally {
      setBusy(false);
    }
  }

  async function submitCode(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const r = await api<LoginResponse>("/api/auth/mfa/verify", { method: "POST", json: { mfa_token: mfaToken, code } });
      if (r.user) done(r.user);
    } catch (err) {
      if (err instanceof ApiError && err.detail.includes("expired")) setMfaToken(null);
      setError(err instanceof ApiError ? err.detail : "Unable to reach the server");
    } finally {
      setBusy(false);
    }
  }

  if (mfaToken) {
    return (
      <AuthShell title="Two-factor verification" subtitle="Enter the 6-digit code from your authenticator app, or a recovery code.">
        <form onSubmit={submitCode} className="space-y-4">
          {error ? <Alert tone="critical">{error}</Alert> : null}
          <Field label="Verification code" htmlFor="code">
            <Input
              id="code"
              inputMode="text"
              autoComplete="one-time-code"
              autoFocus
              required
              value={code}
              onChange={(e) => setCode(e.target.value)}
              className="tabular tracking-widest"
              maxLength={20}
            />
          </Field>
          <Button type="submit" className="w-full" loading={busy}>
            Verify
          </Button>
          <Button type="button" variant="ghost" className="w-full" onClick={() => setMfaToken(null)}>
            Back to sign in
          </Button>
        </form>
      </AuthShell>
    );
  }

  return (
    <AuthShell title="Sign in" subtitle="Use the account your administrator created for you.">
      <form onSubmit={submitPassword} className="space-y-4">
        {error ? <Alert tone="critical">{error}</Alert> : null}
        <Field label="Work email" htmlFor="email">
          <Input id="email" type="email" autoComplete="username" required autoFocus value={email} onChange={(e) => setEmail(e.target.value)} />
        </Field>
        <Field label="Password" htmlFor="password">
          <Input
            id="password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </Field>
        <Button type="submit" className="w-full" loading={busy}>
          Sign in
        </Button>
        <p className="text-center text-xs text-muted-foreground">
          Forgotten your password? Ask a company administrator to reset it.
        </p>
      </form>
    </AuthShell>
  );
}
