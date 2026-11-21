"use client";

import { ShieldAlert, ShieldCheck } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Alert, Button, Card, CardContent, Select } from "@/components/ui/primitives";
import { api, ApiError } from "@/lib/api";
import { formatDate } from "@/lib/format";

interface AuditItem {
  id: string;
  action: string;
  actor_name: string | null;
  entity_type: string | null;
  ip_address: string | null;
  details: Record<string, unknown>;
  created_at: string;
}

const PAGE = 50;

export function AuditPanel() {
  const [items, setItems] = useState<AuditItem[]>([]);
  const [total, setTotal] = useState(0);
  const [intact, setIntact] = useState<boolean | null>(null);
  const [offset, setOffset] = useState(0);
  const [action, setAction] = useState("");
  const [error, setError] = useState<string | null>(null);

  const fetchPage = useCallback(() => {
    const qs = new URLSearchParams({ limit: String(PAGE), offset: String(offset) });
    if (action) qs.set("action", action);
    return api<{ items: AuditItem[]; total: number; chain_intact: boolean }>(`/api/audit-logs?${qs}`);
  }, [offset, action]);

  useEffect(() => {
    let cancelled = false;
    fetchPage().then(
      (r) => {
        if (cancelled) return;
        setItems(r.items);
        setTotal(r.total);
        setIntact(r.chain_intact);
      },
      (err) => !cancelled && setError(err instanceof ApiError ? err.detail : "Unable to load the audit log"),
    );
    return () => {
      cancelled = true;
    };
  }, [fetchPage]);

  return (
    <div className="space-y-4">
      {error ? <Alert tone="critical">{error}</Alert> : null}
      {intact !== null ? (
        intact ? (
          <Alert tone="good" className="flex items-center gap-2">
            <ShieldCheck className="size-4 text-good-ink" aria-hidden />
            Integrity verified: the audit chain is intact.
          </Alert>
        ) : (
          <Alert tone="critical" className="flex items-center gap-2">
            <ShieldAlert className="size-4" aria-hidden />
            Integrity check failed: one or more audit entries were altered or removed.
          </Alert>
        )
      ) : null}
      <div className="flex items-center gap-2">
        <Select
          aria-label="Filter by event type"
          className="w-56"
          value={action}
          onChange={(e) => {
            setOffset(0);
            setAction(e.target.value);
          }}
        >
          <option value="">All events</option>
          <option value="auth.">Authentication</option>
          <option value="user.">Users</option>
          <option value="role.">Roles</option>
          <option value="company.">Company settings</option>
        </Select>
        <span className="text-xs text-muted-foreground">{total} events</span>
      </div>
      <Card>
        <CardContent className="overflow-x-auto px-0 py-0">
          <table className="w-full min-w-[720px] text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs text-muted-foreground">
                <th className="px-5 py-2 font-medium">Time</th>
                <th className="px-2 py-2 font-medium">Event</th>
                <th className="px-2 py-2 font-medium">User</th>
                <th className="px-2 py-2 font-medium">Details</th>
                <th className="px-5 py-2 font-medium">IP address</th>
              </tr>
            </thead>
            <tbody>
              {items.map((i) => (
                <tr key={i.id} className="border-b border-border align-top last:border-0">
                  <td className="whitespace-nowrap px-5 py-2.5 text-xs text-muted-foreground">{formatDate(i.created_at, true)}</td>
                  <td className="px-2 py-2.5 font-mono text-xs">{i.action}</td>
                  <td className="px-2 py-2.5 text-xs">{i.actor_name ?? "—"}</td>
                  <td className="max-w-[320px] truncate px-2 py-2.5 font-mono text-[11px] text-muted-foreground" title={JSON.stringify(i.details)}>
                    {Object.keys(i.details).length ? JSON.stringify(i.details) : "—"}
                  </td>
                  <td className="px-5 py-2.5 font-mono text-xs text-muted-foreground">{i.ip_address ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>
      <div className="flex justify-end gap-2">
        <Button size="sm" variant="secondary" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>
          Newer
        </Button>
        <Button size="sm" variant="secondary" disabled={offset + PAGE >= total} onClick={() => setOffset(offset + PAGE)}>
          Older
        </Button>
      </div>
    </div>
  );
}
