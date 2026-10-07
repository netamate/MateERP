"use client";

import { AutomationIntegrationsPage } from "@/components/workspace/automation-integrations-page";
import { WorkspaceShell } from "@/components/workspace/workspace-shell";

export default function Page() {
  return (
    <WorkspaceShell>
      {(session) => <AutomationIntegrationsPage session={session} />}
    </WorkspaceShell>
  );
}
