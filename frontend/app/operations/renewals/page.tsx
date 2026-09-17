"use client";

import { RenewalsPage } from "@/components/workspace/phase7-pages";
import { WorkspaceShell } from "@/components/workspace/workspace-shell";

export default function Page() {
  return <WorkspaceShell>{(session) => <RenewalsPage session={session} />}</WorkspaceShell>;
}
