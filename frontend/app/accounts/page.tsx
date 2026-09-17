"use client";

import { Suspense } from "react";
import { FinancialAccountsPage } from "@/components/workspace/pages";
import { WorkspaceShell } from "@/components/workspace/workspace-shell";

export default function Page() {
  return <Suspense fallback={<div />}><WorkspaceShell>{(session) => <FinancialAccountsPage session={session} />}</WorkspaceShell></Suspense>;
}
