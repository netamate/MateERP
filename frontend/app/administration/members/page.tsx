"use client";

import { Suspense } from "react";
import { MembersPage } from "@/components/workspace/pages";
import { WorkspaceShell } from "@/components/workspace/workspace-shell";

export default function Page() {
  return <Suspense fallback={<div />}><WorkspaceShell>{(session) => <MembersPage session={session} />}</WorkspaceShell></Suspense>;
}
