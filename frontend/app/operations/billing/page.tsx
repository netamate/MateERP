"use client";

import { BillingCostsPage } from "@/components/workspace/billing-costs-page";
import { WorkspaceShell } from "@/components/workspace/workspace-shell";

export default function Page() {
  return (
    <WorkspaceShell>
      {(session) => <BillingCostsPage session={session} />}
    </WorkspaceShell>
  );
}
