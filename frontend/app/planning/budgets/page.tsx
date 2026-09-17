"use client";

import { BudgetsPage } from "@/components/workspace/phase7-pages";
import { WorkspaceShell } from "@/components/workspace/workspace-shell";

export default function Page() {
  return <WorkspaceShell>{(session) => <BudgetsPage session={session} />}</WorkspaceShell>;
}
