"use client";

import { EnterpriseReportingPage } from "@/components/workspace/phase8-reporting-page";
import { WorkspaceShell } from "@/components/workspace/workspace-shell";

export default function Page() {
  return <WorkspaceShell>{(session) => <EnterpriseReportingPage session={session} />}</WorkspaceShell>;
}
