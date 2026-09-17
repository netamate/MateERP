"use client";

import { Suspense } from "react";
import { ExpensesProductionPage } from "@/components/workspace/expenses-production-page";
import { WorkspaceShell } from "@/components/workspace/workspace-shell";

export default function Page() {
  return <Suspense fallback={<div />}><WorkspaceShell>{(session) => <ExpensesProductionPage session={session} />}</WorkspaceShell></Suspense>;
}
