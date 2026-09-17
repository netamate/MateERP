"use client";

import { DomainsPage } from "@/components/workspace/phase7-pages";
import { WorkspaceShell } from "@/components/workspace/workspace-shell";

export default function Page() {
  return <WorkspaceShell>{(session) => <DomainsPage session={session} />}</WorkspaceShell>;
}
