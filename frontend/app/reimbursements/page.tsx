"use client";

import { Suspense } from "react";
import { ReimbursementsPage } from "@/components/workspace/pages";
import { WorkspaceShell } from "@/components/workspace/workspace-shell";

export default function Page() {
  return <Suspense fallback={<div />}><WorkspaceShell>{(session) => <ReimbursementsPage session={session} />}</WorkspaceShell></Suspense>;
}
