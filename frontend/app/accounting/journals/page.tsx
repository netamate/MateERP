"use client";

import { Suspense } from "react";
import { JournalsPage } from "@/components/workspace/pages";
import { WorkspaceShell } from "@/components/workspace/workspace-shell";

export default function Page() {
  return <Suspense fallback={<div />}><WorkspaceShell>{(session) => <JournalsPage session={session} />}</WorkspaceShell></Suspense>;
}
