"use client";

import { Plus } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Alert, Badge, Button, Card, CardContent, CardHeader, CardTitle, Field, Input } from "@/components/ui/primitives";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { RoleOut } from "./users-panel";

interface PermissionOut {
  code: string;
  module: string;
  description: string;
}

export function RolesPanel() {
  const { can, user } = useAuth();
  const [roles, setRoles] = useState<RoleOut[]>([]);
  const [perms, setPerms] = useState<PermissionOut[]>([]);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const canManageRoles = can("roles:manage");
  const fetchAll = useCallback(
    () =>
      Promise.all([
        api<RoleOut[]>("/api/roles"),
        canManageRoles ? api<PermissionOut[]>("/api/permissions") : Promise.resolve([] as PermissionOut[]),
      ]),
    [canManageRoles],
  );

  const load = useCallback(() => {
    return fetchAll().then(
      ([r, p]) => {
        setRoles(r);
        setPerms(p);
      },
      (err) => setError(err instanceof ApiError ? err.detail : "Unable to load roles"),
    );
  }, [fetchAll]);

  useEffect(() => {
    let cancelled = false;
    fetchAll().then(
      ([r, p]) => {
        if (cancelled) return;
        setRoles(r);
        setPerms(p);
      },
      (err) => !cancelled && setError(err instanceof ApiError ? err.detail : "Unable to load roles"),
    );
    return () => {
      cancelled = true;
    };
  }, [fetchAll]);

  const label = Object.fromEntries(perms.map((p) => [p.code, p.description]));
  const modules = Array.from(new Set(perms.map((p) => p.module)));

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api("/api/roles", { method: "POST", json: { name, description: description || null, permissions: Array.from(selected) } });
      setCreating(false);
      setName("");
      setDescription("");
      setSelected(new Set());
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Unable to create role");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      {error ? <Alert tone="critical">{error}</Alert> : null}
      {can("roles:manage") ? (
        <div className="flex justify-end">
          <Button size="sm" onClick={() => setCreating((v) => !v)}>
            <Plus /> Custom role
          </Button>
        </div>
      ) : null}
      {creating ? (
        <Card>
          <CardContent className="pt-5">
            <form onSubmit={create} className="space-y-4">
              <div className="grid gap-3 sm:grid-cols-2">
                <Field label="Role name" htmlFor="r-name">
                  <Input id="r-name" required minLength={2} value={name} onChange={(e) => setName(e.target.value)} />
                </Field>
                <Field label="Description" htmlFor="r-desc">
                  <Input id="r-desc" value={description} onChange={(e) => setDescription(e.target.value)} />
                </Field>
              </div>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {modules.map((m) => (
                  <fieldset key={m} className="rounded-md border border-border p-3">
                    <legend className="px-1 text-xs font-medium capitalize">{m}</legend>
                    {perms
                      .filter((p) => p.module === m)
                      .map((p) => {
                        const held = user?.permissions.includes(p.code);
                        return (
                          <label key={p.code} className="flex items-start gap-2 py-1 text-xs">
                            <input
                              type="checkbox"
                              disabled={!held}
                              checked={selected.has(p.code)}
                              onChange={(e) => {
                                const next = new Set(selected);
                                if (e.target.checked) next.add(p.code);
                                else next.delete(p.code);
                                setSelected(next);
                              }}
                              className="mt-0.5 accent-[var(--primary)]"
                            />
                            <span className={held ? "" : "text-subtle"}>{p.description}</span>
                          </label>
                        );
                      })}
                  </fieldset>
                ))}
              </div>
              <div className="flex gap-2">
                <Button type="submit" loading={busy} disabled={!selected.size}>
                  Create role
                </Button>
                <Button type="button" variant="ghost" onClick={() => setCreating(false)}>
                  Cancel
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      ) : null}
      <div className="grid gap-3 md:grid-cols-2">
        {roles.map((r) => (
          <Card key={r.id}>
            <CardHeader>
              <div>
                <CardTitle>{r.name}</CardTitle>
                <p className="mt-0.5 text-xs text-muted-foreground">{r.description}</p>
              </div>
              <div className="flex shrink-0 gap-1">
                {r.is_system ? <Badge>System</Badge> : <Badge tone="info">Custom</Badge>}
                <Badge>{r.user_count} users</Badge>
              </div>
            </CardHeader>
            <CardContent>
              <ul className="flex flex-wrap gap-1">
                {r.permissions.map((p) => (
                  <li key={p}>
                    <span className="rounded bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground" title={label[p]}>
                      {p}
                    </span>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
