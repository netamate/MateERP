"use client";

import { ReconciliationPage } from "@/components/workspace/phase8-reconciliation-page";
import { WorkspaceShell } from "@/components/workspace/workspace-shell";

export default function Page() {
  return <WorkspaceShell>{(session) => <ReconciliationPage session={session} />}</WorkspaceShell>;
}
