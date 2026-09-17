"use client";

import { Suspense } from "react";
import { MembersProductionPage } from "@/components/workspace/members-production-page";
import { WorkspaceShell } from "@/components/workspace/workspace-shell";

export default function Page() {
  return <Suspense fallback={<div />}><WorkspaceShell>{(session) => <MembersProductionPage session={session} />}</WorkspaceShell></Suspense>;
}
