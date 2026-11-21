"use client";

import { FlaskConical, LogOut, Menu, X } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Logo } from "@/components/logo";
import { ChangePasswordForm, MfaSetup } from "@/components/security-forms";
import { ThemeToggle } from "@/components/theme-toggle";
import { Badge, Button, Card, CardContent } from "@/components/ui/primitives";
import { useAuth } from "@/lib/auth";
import { visibleNav } from "@/lib/nav";
import { cn } from "@/lib/utils";

function PolicyGate({ title, description, children }: { title: string; description: string; children: React.ReactNode }) {
  return (
    <main className="flex min-h-screen items-center justify-center p-6">
      <Card className="w-full max-w-lg">
        <CardContent className="space-y-4 pt-6">
          <Logo />
          <div>
            <h1 className="text-lg font-semibold">{title}</h1>
            <p className="mt-1 text-sm text-muted-foreground">{description}</p>
          </div>
          {children}
        </CardContent>
      </Card>
    </main>
  );
}

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { user, loading, logout, can } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  if (loading || !user) {
    return (
      <main className="flex min-h-screen items-center justify-center">
        <span className="size-5 animate-spin rounded-full border-2 border-primary border-r-transparent" aria-label="Loading" />
      </main>
    );
  }

  if (user.must_change_password) {
    return (
      <PolicyGate title="Choose a new password" description="Your account was created with a temporary password. Set your own before continuing.">
        <ChangePasswordForm />
      </PolicyGate>
    );
  }
  if (user.company.require_mfa && !user.mfa_enabled) {
    return (
      <PolicyGate title="Two-factor authentication required" description={`${user.company.name} requires every user to enable two-factor authentication.`}>
        <MfaSetup />
      </PolicyGate>
    );
  }

  const nav = visibleNav(can);
  const initials = user.full_name
    .split(" ")
    .map((p) => p[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();

  const sidebar = (
    <nav className="flex h-full flex-col" aria-label="Main">
      <div className="flex h-14 items-center justify-between px-4">
        <Logo />
        <Button variant="ghost" size="icon" className="lg:hidden" onClick={() => setOpen(false)} aria-label="Close menu">
          <X />
        </Button>
      </div>
      <div className="px-3 pb-2">
        <div className="truncate rounded-md border border-border bg-background px-2.5 py-1.5 text-xs font-medium text-foreground" title={user.company.name}>
          {user.company.name}
        </div>
      </div>
      <ul className="flex-1 space-y-0.5 overflow-y-auto px-3 py-2">
        {nav.map((item) => {
          const active = pathname === item.href || pathname.startsWith(item.href + "/");
          return (
            <li key={item.href}>
              <Link
                href={item.href}
                onClick={() => setOpen(false)}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-[13px] transition-colors",
                  active ? "bg-muted font-medium text-foreground" : "text-muted-foreground hover:bg-muted/60 hover:text-foreground",
                )}
              >
                <item.icon className="size-4 shrink-0" aria-hidden />
                <span className="flex-1">{item.label}</span>
                {item.phase ? <span className="text-[10px] text-subtle">Soon</span> : null}
              </Link>
            </li>
          );
        })}
      </ul>
      <div className="border-t border-border p-3">
        <div className="flex items-center gap-2.5">
          <div className="flex size-8 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary">{initials}</div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-[13px] font-medium">{user.full_name}</p>
            <p className="truncate text-[11px] text-muted-foreground">{user.role_name}</p>
          </div>
          <Button
            variant="ghost"
            size="icon"
            aria-label="Sign out"
            onClick={async () => {
              await logout();
              router.replace("/login");
            }}
          >
            <LogOut />
          </Button>
        </div>
      </div>
    </nav>
  );

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[232px_1fr]">
      <aside className="sticky top-0 hidden h-screen border-r border-border bg-card lg:block">{sidebar}</aside>
      {open ? (
        <div className="fixed inset-0 z-40 lg:hidden">
          <button className="absolute inset-0 bg-black/40" aria-label="Close menu" onClick={() => setOpen(false)} />
          <aside className="absolute inset-y-0 left-0 w-64 border-r border-border bg-card">{sidebar}</aside>
        </div>
      ) : null}
      <div className="min-w-0">
        {user.company.is_demo ? (
          <div className="flex items-center justify-center gap-2 border-b border-warning/40 bg-warning/15 px-4 py-1.5 text-xs font-medium">
            <FlaskConical className="size-3.5" aria-hidden />
            Demo mode — every figure in this company is synthetic sample data.
          </div>
        ) : null}
        <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-border bg-background/85 px-4 backdrop-blur sm:px-6">
          <Button variant="ghost" size="icon" className="lg:hidden" onClick={() => setOpen(true)} aria-label="Open menu">
            <Menu />
          </Button>
          <div className="flex-1" />
          {!user.mfa_enabled ? (
            <Link href="/settings?tab=security" className="hidden sm:block">
              <Badge tone="warning">Two-factor authentication is off</Badge>
            </Link>
          ) : null}
          <ThemeToggle />
        </header>
        <main className="mx-auto w-full max-w-[1400px] px-4 py-6 sm:px-6 lg:px-8">{children}</main>
      </div>
    </div>
  );
}
