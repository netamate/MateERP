"use client";

import { Suspense } from "react";
import { FiscalPeriodsProductionPage } from "@/components/workspace/accounting-production-pages";
import { WorkspaceShell } from "@/components/workspace/workspace-shell";

export default function Page() {
  return <Suspense fallback={<div />}><WorkspaceShell>{(session) => <FiscalPeriodsProductionPage session={session} />}</WorkspaceShell></Suspense>;
}
