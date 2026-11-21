"use client";

import { Copy, KeyRound, UserPlus } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Alert, Badge, Button, Card, CardContent, CardHeader, CardTitle, Field, Input, Select } from "@/components/ui/primitives";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatDate } from "@/lib/format";

export interface RoleOut {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  is_system: boolean;
  permissions: string[];
  user_count: number;
}

interface UserOut {
  id: string;
  email: string;
  full_name: string;
  department: string | null;
  is_active: boolean;
  mfa_enabled: boolean;
  must_change_password: boolean;
  last_login_at: string | null;
  role_id: string;
  role_name: string;
}

function TempPassword({ email, password, onClose }: { email: string; password: string; onClose: () => void }) {
  const [copied, setCopied] = useState(false);
  return (
    <Alert tone="good" className="space-y-2">
      <p className="font-medium text-foreground">Temporary password for {email}</p>
      <p className="text-xs text-muted-foreground">
        Share it with the user through a secure channel. It is shown only once, and they must change it at first sign-in.
      </p>
      <div className="flex items-center gap-2">
        <code className="rounded bg-card px-2 py-1 font-mono text-sm text-foreground">{password}</code>
        <Button
          size="sm"
          variant="secondary"
          onClick={async () => {
            await navigator.clipboard.writeText(password);
            setCopied(true);
          }}
        >
          <Copy /> {copied ? "Copied" : "Copy"}
        </Button>
        <Button size="sm" variant="ghost" onClick={onClose}>
          Done
        </Button>
      </div>
    </Alert>
  );
}

function fetchUsersAndRoles() {
  return Promise.all([api<UserOut[]>("/api/users"), api<RoleOut[]>("/api/roles")]);
}

export function UsersPanel() {
  const { user: me } = useAuth();
  const [users, setUsers] = useState<UserOut[]>([]);
  const [roles, setRoles] = useState<RoleOut[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [inviting, setInviting] = useState(false);
  const [form, setForm] = useState({ email: "", full_name: "", role_id: "", department: "" });
  const [temp, setTemp] = useState<{ email: string; password: string } | null>(null);
  const [busy, setBusy] = useState(false);

  const apply = useCallback(([u, r]: [UserOut[], RoleOut[]]) => {
    setUsers(u);
    setRoles(r);
    setForm((f) => (f.role_id ? f : { ...f, role_id: r.find((x) => x.slug === "employee")?.id ?? r[0]?.id ?? "" }));
  }, []);

  const load = useCallback(
    () =>
      fetchUsersAndRoles().then(apply, (err) => setError(err instanceof ApiError ? err.detail : "Unable to load users")),
    [apply],
  );

  useEffect(() => {
    let cancelled = false;
    fetchUsersAndRoles().then(
      (d) => !cancelled && apply(d),
      (err) => !cancelled && setError(err instanceof ApiError ? err.detail : "Unable to load users"),
    );
    return () => {
      cancelled = true;
    };
  }, [apply]);

  async function invite(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const r = await api<{ user: UserOut; temporary_password: string }>("/api/users", {
        method: "POST",
        json: { ...form, department: form.department || null },
      });
      setTemp({ email: r.user.email, password: r.temporary_password });
      setForm({ email: "", full_name: "", role_id: form.role_id, department: "" });
      setInviting(false);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Unable to add user");
    } finally {
      setBusy(false);
    }
  }

  async function update(id: string, patch: Partial<Pick<UserOut, "role_id" | "is_active">>) {
    setError(null);
    try {
      await api(`/api/users/${id}`, { method: "PATCH", json: patch });
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Unable to update user");
    }
  }

  async function reset(u: UserOut) {
    if (!window.confirm(`Reset the password for ${u.email}? Their current sessions will be signed out.`)) return;
    setError(null);
    try {
      const r = await api<{ temporary_password: string }>(`/api/users/${u.id}/reset-password`, { method: "POST" });
      setTemp({ email: u.email, password: r.temporary_password });
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Unable to reset password");
    }
  }

  return (
    <div className="space-y-4">
      {error ? <Alert tone="critical">{error}</Alert> : null}
      {temp ? <TempPassword {...temp} onClose={() => setTemp(null)} /> : null}

      <Card>
        <CardHeader>
          <div>
            <CardTitle>Team members</CardTitle>
            <p className="mt-0.5 text-xs text-muted-foreground">Every person gets an individual login. Never share an account.</p>
          </div>
          <Button size="sm" onClick={() => setInviting((v) => !v)}>
            <UserPlus /> Add user
          </Button>
        </CardHeader>
        <CardContent>
          {inviting ? (
            <form onSubmit={invite} className="mb-5 grid gap-3 rounded-md border border-border bg-background p-4 sm:grid-cols-2 lg:grid-cols-4">
              <Field label="Full name" htmlFor="inv-name">
                <Input id="inv-name" required minLength={2} value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
              </Field>
              <Field label="Email" htmlFor="inv-email">
                <Input id="inv-email" type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
              </Field>
              <Field label="Role" htmlFor="inv-role">
                <Select id="inv-role" value={form.role_id} onChange={(e) => setForm({ ...form, role_id: e.target.value })}>
                  {roles.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.name}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Department" htmlFor="inv-dept">
                <Input id="inv-dept" value={form.department} onChange={(e) => setForm({ ...form, department: e.target.value })} />
              </Field>
              <div className="flex gap-2 sm:col-span-2 lg:col-span-4">
                <Button type="submit" loading={busy}>
                  Create account
                </Button>
                <Button type="button" variant="ghost" onClick={() => setInviting(false)}>
                  Cancel
                </Button>
              </div>
            </form>
          ) : null}

          <div className="-mx-5 overflow-x-auto">
            <table className="w-full min-w-[720px] text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs text-muted-foreground">
                  <th className="px-5 py-2 font-medium">Name</th>
                  <th className="px-2 py-2 font-medium">Role</th>
                  <th className="px-2 py-2 font-medium">Security</th>
                  <th className="px-2 py-2 font-medium">Last sign-in</th>
                  <th className="px-5 py-2 text-right font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id} className="border-b border-border last:border-0">
                    <td className="px-5 py-2.5">
                      <p className="font-medium">{u.full_name}</p>
                      <p className="text-xs text-muted-foreground">{u.email}</p>
                    </td>
                    <td className="px-2 py-2.5">
                      <Select
                        aria-label={`Role for ${u.full_name}`}
                        value={u.role_id}
                        disabled={u.id === me?.id}
                        onChange={(e) => update(u.id, { role_id: e.target.value })}
                        className="h-8 w-44 text-xs"
                      >
                        {roles.map((r) => (
                          <option key={r.id} value={r.id}>
                            {r.name}
                          </option>
                        ))}
                      </Select>
                    </td>
                    <td className="space-x-1 px-2 py-2.5">
                      {!u.is_active ? <Badge>Deactivated</Badge> : null}
                      {u.is_active ? <Badge tone={u.mfa_enabled ? "good" : "warning"}>{u.mfa_enabled ? "MFA on" : "MFA off"}</Badge> : null}
                      {u.must_change_password && u.is_active ? <Badge tone="info">Pending first sign-in</Badge> : null}
                    </td>
                    <td className="px-2 py-2.5 text-xs text-muted-foreground">{u.last_login_at ? formatDate(u.last_login_at, true) : "Never"}</td>
                    <td className="whitespace-nowrap px-5 py-2.5 text-right">
                      {u.id !== me?.id ? (
                        <>
                          <Button size="sm" variant="ghost" onClick={() => reset(u)} aria-label={`Reset password for ${u.full_name}`}>
                            <KeyRound />
                          </Button>
                          <Button size="sm" variant="ghost" onClick={() => update(u.id, { is_active: !u.is_active })}>
                            {u.is_active ? "Deactivate" : "Reactivate"}
                          </Button>
                        </>
                      ) : (
                        <span className="text-xs text-subtle">You</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
