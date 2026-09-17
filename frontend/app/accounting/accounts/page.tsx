"use client";

import { Suspense } from "react";
import { ChartOfAccountsProductionPage } from "@/components/workspace/accounting-production-pages";
import { WorkspaceShell } from "@/components/workspace/workspace-shell";

export default function Page() {
  return <Suspense fallback={<div />}><WorkspaceShell>{(session) => <ChartOfAccountsProductionPage session={session} />}</WorkspaceShell></Suspense>;
}
