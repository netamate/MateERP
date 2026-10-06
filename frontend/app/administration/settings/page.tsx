"use client";

import { LeanSettingsPage } from "@/components/workspace/lean-settings-page";
import { WorkspaceShell } from "@/components/workspace/workspace-shell";

export default function Page() {
  return (
    <WorkspaceShell>
      {(session) => <LeanSettingsPage session={session} />}
    </WorkspaceShell>
  );
}
