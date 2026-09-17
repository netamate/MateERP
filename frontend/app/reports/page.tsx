"use client";

import { Suspense } from "react";
import { ReportsPage } from "@/components/workspace/pages";
import { WorkspaceShell } from "@/components/workspace/workspace-shell";

export default function Page() {
  return <Suspense fallback={<div />}><WorkspaceShell>{(session) => <ReportsPage session={session} />}</WorkspaceShell></Suspense>;
}
