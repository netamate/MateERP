"use client";

import { Suspense } from "react";

import { WorkspaceShell } from "@/components/workspace/workspace-shell";
import { DashboardPage } from "@/components/workspace/pages";

export default function Home() {
  return (
    <Suspense fallback={<main className="grid min-h-screen place-items-center">Loading MateERP...</main>}>
      <WorkspaceShell>{(session) => <DashboardPage session={session} />}</WorkspaceShell>
    </Suspense>
  );
}
