"use client";

import { Suspense } from "react";
import { DocumentsApprovalsPage } from "@/components/workspace/extra-pages";
import { WorkspaceShell } from "@/components/workspace/workspace-shell";

export default function Page() {
  return <Suspense fallback={<div />}><WorkspaceShell>{(session) => <DocumentsApprovalsPage session={session} />}</WorkspaceShell></Suspense>;
}
