"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { AuditPanel } from "@/components/settings/audit-panel";
import { CompanyForm } from "@/components/settings/company-form";
import { RolesPanel } from "@/components/settings/roles-panel";
import { SecurityPanel } from "@/components/settings/security-panel";
import { UsersPanel } from "@/components/settings/users-panel";
import { Card, CardContent } from "@/components/ui/primitives";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

const TABS = [
  { key: "company", label: "Company", permission: null },
  { key: "users", label: "Users", permission: "users:manage" },
  { key: "roles", label: "Roles", permission: "users:manage" },
  { key: "security", label: "Security", permission: null },
  { key: "audit", label: "Audit log", permission: "audit:read" },
] as const;

function SettingsInner() {
  const { can } = useAuth();
  const params = useSearchParams();
  const router = useRouter();
  const tabs = TABS.filter((t) => !t.permission || can(t.permission));
  const requested = params.get("tab");
  const active = tabs.find((t) => t.key === requested)?.key ?? tabs[0].key;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Settings</h1>
        <p className="mt-0.5 text-sm text-muted-foreground">Company profile, team access, security and audit trail.</p>
      </div>
      <div role="tablist" aria-label="Settings sections" className="flex gap-1 overflow-x-auto border-b border-border">
        {tabs.map((t) => (
          <button
            key={t.key}
            role="tab"
            aria-selected={active === t.key}
            onClick={() => router.replace(`/settings?tab=${t.key}`)}
            className={cn(
              "-mb-px whitespace-nowrap border-b-2 px-3 py-2 text-sm transition-colors",
              active === t.key ? "border-primary font-medium text-foreground" : "border-transparent text-muted-foreground hover:text-foreground",
            )}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div role="tabpanel">
        {active === "company" ? (
          <Card>
            <CardContent className="pt-5">
              <CompanyForm />
            </CardContent>
          </Card>
        ) : null}
        {active === "users" ? <UsersPanel /> : null}
        {active === "roles" ? <RolesPanel /> : null}
        {active === "security" ? <SecurityPanel /> : null}
        {active === "audit" ? <AuditPanel /> : null}
      </div>
    </div>
  );
}

export default function SettingsPage() {
  return (
    <Suspense>
      <SettingsInner />
    </Suspense>
  );
}
