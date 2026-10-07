"use client";

import { DirectEmailPage } from "@/components/workspace/direct-email-page";
import { WorkspaceShell } from "@/components/workspace/workspace-shell";

export default function Page() {
  return (
    <WorkspaceShell>
      {(session) => <DirectEmailPage session={session} />}
    </WorkspaceShell>
  );
}
