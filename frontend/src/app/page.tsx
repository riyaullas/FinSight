"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { SetupStatus } from "@/lib/types";

export default function Home() {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;
    if (user) {
      router.replace(user.company.onboarding_completed ? "/overview" : "/onboarding");
      return;
    }
    api<SetupStatus>("/api/setup/status")
      .then((s) => router.replace(s.initialised ? "/login" : "/setup"))
      .catch(() => router.replace("/login"));
  }, [user, loading, router]);

  return (
    <main className="flex min-h-screen items-center justify-center">
      <span className="size-5 animate-spin rounded-full border-2 border-primary border-r-transparent" aria-label="Loading" />
    </main>
  );
}
