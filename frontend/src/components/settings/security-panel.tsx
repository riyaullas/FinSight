"use client";

import { useState } from "react";
import { ChangePasswordForm, MfaSetup } from "@/components/security-forms";
import { Alert, Badge, Button, Card, CardContent, CardDescription, CardHeader, CardTitle, Field, Input } from "@/components/ui/primitives";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

function DisableMfa() {
  const { refresh } = useAuth();
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  return (
    <form
      className="mt-4 grid max-w-md gap-3 border-t border-border pt-4 sm:grid-cols-2"
      onSubmit={async (e) => {
        e.preventDefault();
        setBusy(true);
        setError(null);
        try {
          await api("/api/auth/mfa/disable", { method: "POST", json: { password, code } });
          await refresh();
        } catch (err) {
          setError(err instanceof ApiError ? err.detail : "Unable to disable MFA");
        } finally {
          setBusy(false);
        }
      }}
    >
      {error ? <Alert tone="critical" className="sm:col-span-2">{error}</Alert> : null}
      <Field label="Password" htmlFor="dm-pw">
        <Input id="dm-pw" type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
      </Field>
      <Field label="Authenticator code" htmlFor="dm-code">
        <Input id="dm-code" inputMode="numeric" required maxLength={6} value={code} onChange={(e) => setCode(e.target.value)} />
      </Field>
      <div className="sm:col-span-2">
        <Button type="submit" variant="destructive" size="sm" loading={busy}>
          Disable two-factor authentication
        </Button>
      </div>
    </form>
  );
}

function CompanyPolicy() {
  const { user, refresh } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  if (!user) return null;
  const required = user.company.require_mfa;
  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>Company security policy</CardTitle>
          <CardDescription className="mt-0.5">Applies to every user in {user.company.name}.</CardDescription>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {error ? <Alert tone="critical">{error}</Alert> : null}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-sm font-medium">Require two-factor authentication</p>
            <p className="text-xs text-muted-foreground">Users without MFA must enrol at their next sign-in before they can access any data.</p>
          </div>
          <Button
            variant={required ? "secondary" : "default"}
            size="sm"
            loading={busy}
            onClick={async () => {
              setBusy(true);
              setError(null);
              try {
                await api("/api/company", { method: "PATCH", json: { require_mfa: !required } });
                await refresh();
              } catch (err) {
                setError(err instanceof ApiError ? err.detail : "Unable to update policy");
              } finally {
                setBusy(false);
              }
            }}
          >
            {required ? "Stop requiring" : "Require for everyone"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

export function SecurityPanel() {
  const { user, can } = useAuth();
  if (!user) return null;
  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <div>
            <CardTitle>Two-factor authentication</CardTitle>
            <CardDescription className="mt-0.5">A time-based code from your phone is required in addition to your password.</CardDescription>
          </div>
          <Badge tone={user.mfa_enabled ? "good" : "warning"}>{user.mfa_enabled ? "Enabled" : "Not enabled"}</Badge>
        </CardHeader>
        <CardContent>
          {user.mfa_enabled ? (
            user.company.require_mfa ? (
              <p className="text-sm text-muted-foreground">Your company requires two-factor authentication, so it cannot be turned off.</p>
            ) : (
              <>
                <p className="text-sm text-muted-foreground">Your account is protected with an authenticator app.</p>
                <DisableMfa />
              </>
            )
          ) : (
            <MfaSetup />
          )}
        </CardContent>
      </Card>
      {can("settings:manage") ? <CompanyPolicy /> : null}
      <Card>
        <CardHeader>
          <div>
            <CardTitle>Password</CardTitle>
            <CardDescription className="mt-0.5">Changing your password signs you out on every other device.</CardDescription>
          </div>
        </CardHeader>
        <CardContent>
          <ChangePasswordForm />
        </CardContent>
      </Card>
    </div>
  );
}
