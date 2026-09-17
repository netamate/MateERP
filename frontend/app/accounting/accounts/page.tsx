"use client";

import { Suspense } from "react";
import { LedgerAccountsPage } from "@/components/workspace/pages";
import { WorkspaceShell } from "@/components/workspace/workspace-shell";

export default function Page() {
  return <Suspense fallback={<div />}><WorkspaceShell>{(session) => <LedgerAccountsPage session={session} />}</WorkspaceShell></Suspense>;
}
