"use client";

import { Suspense } from "react";

import { WorkspaceShell } from "@/components/workspace/workspace-shell";
import { LeanDashboardPage } from "@/components/workspace/lean-dashboard-page";

export default function Home() {
  return (
    <Suspense fallback={<main className="grid min-h-screen place-items-center">Loading MateERP...</main>}>
      <WorkspaceShell>{(session) => <LeanDashboardPage session={session} />}</WorkspaceShell>
    </Suspense>
  );
}
