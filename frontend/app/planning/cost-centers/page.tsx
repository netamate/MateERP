"use client";

import { CostCentersPage } from "@/components/workspace/phase7-pages";
import { WorkspaceShell } from "@/components/workspace/workspace-shell";

export default function Page() {
  return <WorkspaceShell>{(session) => <CostCentersPage session={session} />}</WorkspaceShell>;
}
