"use client";

import { LeanSubscriptionsPage } from "@/components/workspace/lean-subscriptions-page";
import { WorkspaceShell } from "@/components/workspace/workspace-shell";

export default function Page() {
  return (
    <WorkspaceShell>
      {(session) => <LeanSubscriptionsPage session={session} />}
    </WorkspaceShell>
  );
}
