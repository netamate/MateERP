"use client";

import { Suspense } from "react";
import { JournalsProductionPage } from "@/components/workspace/accounting-production-pages";
import { WorkspaceShell } from "@/components/workspace/workspace-shell";

export default function Page() {
  return <Suspense fallback={<div />}><WorkspaceShell>{(session) => <JournalsProductionPage session={session} />}</WorkspaceShell></Suspense>;
}
