"use client";

import { Construction } from "lucide-react";
import Link from "next/link";
import { notFound, useParams } from "next/navigation";
import { Badge, Button, Card, EmptyState } from "@/components/ui/primitives";
import { NAV } from "@/lib/nav";

/** Modules scheduled for later phases. Shown honestly as not yet available — no placeholder figures. */
export default function ModulePage() {
  const { module } = useParams<{ module: string }>();
  const item = NAV.find((n) => n.href === `/${module}`);
  if (!item || !item.phase) notFound();

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <h1 className="text-xl font-semibold tracking-tight">{item.label}</h1>
        <Badge tone="info">Phase {item.phase}</Badge>
      </div>
      <Card>
        <EmptyState
          icon={<Construction className="size-5" />}
          title={`${item.label} is not available yet`}
          description={`${item.summary} This module is scheduled for development phase ${item.phase}.`}
          action={
            <Button variant="secondary" asChild>
              <Link href="/overview">Back to overview</Link>
            </Button>
          }
        />
      </Card>
    </div>
  );
}
