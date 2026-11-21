"use client";

import QRCode from "qrcode";
import { useState } from "react";
import { Alert, Button, Field, Input } from "@/components/ui/primitives";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { passwordIssues } from "@/lib/password";
import type { Me } from "@/lib/types";

/** TOTP enrolment. The QR code is rendered locally; the secret never leaves this installation. */
export function MfaSetup({ onDone }: { onDone?: () => void }) {
  const { refresh } = useAuth();
  const [secret, setSecret] = useState<string | null>(null);
  const [qr, setQr] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [recovery, setRecovery] = useState<string[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function start() {
    setBusy(true);
    setError(null);
    try {
      const r = await api<{ secret: string; otpauth_uri: string }>("/api/auth/mfa/setup", { method: "POST" });
      setSecret(r.secret);
      setQr(await QRCode.toDataURL(r.otpauth_uri, { margin: 1, width: 180 }));
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Unable to start setup");
    } finally {
      setBusy(false);
    }
  }

  async function enable(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const r = await api<{ recovery_codes: string[] }>("/api/auth/mfa/enable", { method: "POST", json: { code } });
      setRecovery(r.recovery_codes);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Unable to enable MFA");
    } finally {
      setBusy(false);
    }
  }

  if (recovery) {
    return (
      <div className="space-y-4">
        <Alert tone="good">Two-factor authentication is now enabled.</Alert>
        <div>
          <p className="text-sm font-medium">Recovery codes</p>
          <p className="mt-1 text-xs text-muted-foreground">
            Store these somewhere safe. Each code can be used once if you lose access to your authenticator. They will not be shown again.
          </p>
          <ul className="tabular mt-3 grid grid-cols-2 gap-2 rounded-md border border-border bg-muted p-3 font-mono text-sm">
            {recovery.map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
        </div>
        <Button
          onClick={async () => {
            await refresh();
            onDone?.();
          }}
        >
          I have saved my recovery codes
        </Button>
      </div>
    );
  }

  if (!secret) {
    return (
      <div className="space-y-3">
        {error ? <Alert tone="critical">{error}</Alert> : null}
        <p className="text-sm text-muted-foreground">
          Use an authenticator app (such as Google Authenticator, Microsoft Authenticator or 1Password) to generate sign-in codes.
        </p>
        <Button onClick={start} loading={busy}>
          Set up two-factor authentication
        </Button>
      </div>
    );
  }

  return (
    <form onSubmit={enable} className="space-y-4">
      {error ? <Alert tone="critical">{error}</Alert> : null}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
        {qr ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={qr} alt="QR code for your authenticator app" className="size-[180px] rounded-md border border-border bg-white" />
        ) : null}
        <div className="text-sm text-muted-foreground">
          <p>Scan the QR code, or enter this key manually:</p>
          <code className="mt-2 block break-all rounded bg-muted px-2 py-1 font-mono text-xs text-foreground">{secret}</code>
        </div>
      </div>
      <Field label="6-digit code from the app" htmlFor="mfa-code">
        <Input
          id="mfa-code"
          inputMode="numeric"
          pattern="[0-9]{6}"
          maxLength={6}
          required
          value={code}
          onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
          className="tabular max-w-40 tracking-widest"
          autoComplete="one-time-code"
        />
      </Field>
      <Button type="submit" loading={busy}>
        Verify and enable
      </Button>
    </form>
  );
}

export function ChangePasswordForm({ onDone }: { onDone?: () => void }) {
  const { setUser } = useAuth();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState(false);
  const [busy, setBusy] = useState(false);
  const issues = passwordIssues(next);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (issues.length || next !== confirm) return;
    setBusy(true);
    setError(null);
    try {
      const me = await api<Me>("/api/auth/password", { method: "POST", json: { current_password: current, new_password: next } });
      setUser(me);
      setOk(true);
      setCurrent("");
      setNext("");
      setConfirm("");
      onDone?.();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Unable to change password");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="max-w-sm space-y-4">
      {error ? <Alert tone="critical">{error}</Alert> : null}
      {ok ? <Alert tone="good">Password changed. Other devices have been signed out.</Alert> : null}
      <Field label="Current password" htmlFor="cur-pw">
        <Input id="cur-pw" type="password" autoComplete="current-password" required value={current} onChange={(e) => setCurrent(e.target.value)} />
      </Field>
      <Field label="New password" htmlFor="new-pw" hint={next && issues.length ? `Needs ${issues.join(" and ")}.` : "12+ characters, mixing letters, digits and symbols."}>
        <Input id="new-pw" type="password" autoComplete="new-password" required value={next} onChange={(e) => setNext(e.target.value)} aria-invalid={!!next && issues.length > 0} />
      </Field>
      <Field label="Confirm new password" htmlFor="confirm-pw" hint={confirm && confirm !== next ? "Passwords do not match." : undefined}>
        <Input id="confirm-pw" type="password" autoComplete="new-password" required value={confirm} onChange={(e) => setConfirm(e.target.value)} aria-invalid={!!confirm && confirm !== next} />
      </Field>
      <Button type="submit" loading={busy} disabled={issues.length > 0 || next !== confirm}>
        Change password
      </Button>
    </form>
  );
}
