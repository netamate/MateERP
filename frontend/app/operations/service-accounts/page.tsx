"use client";

import { ServiceAccountsPage } from "@/components/workspace/service-accounts-page";
import { WorkspaceShell } from "@/components/workspace/workspace-shell";

export default function Page() {
  return (
    <WorkspaceShell>
      {(session) => <ServiceAccountsPage session={session} />}
    </WorkspaceShell>
  );
}
