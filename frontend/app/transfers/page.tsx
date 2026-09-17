"use client";

import { Suspense } from "react";
import { TransfersPage } from "@/components/workspace/pages";
import { WorkspaceShell } from "@/components/workspace/workspace-shell";

export default function Page() {
  return <Suspense fallback={<div />}><WorkspaceShell>{(session) => <TransfersPage session={session} />}</WorkspaceShell></Suspense>;
}
