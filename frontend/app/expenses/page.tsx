"use client";

import { Suspense } from "react";
import { ExpensesPage } from "@/components/workspace/pages";
import { WorkspaceShell } from "@/components/workspace/workspace-shell";

export default function Page() {
  return <Suspense fallback={<div />}><WorkspaceShell>{(session) => <ExpensesPage session={session} />}</WorkspaceShell></Suspense>;
}
