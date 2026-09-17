"use client";

import { DocumentIntegrityPage } from "@/components/workspace/phase8-admin-pages";
import { WorkspaceShell } from "@/components/workspace/workspace-shell";

export default function Page() {
  return <WorkspaceShell>{(session) => <DocumentIntegrityPage session={session} />}</WorkspaceShell>;
}
