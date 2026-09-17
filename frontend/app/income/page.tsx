"use client";

import { Suspense } from "react";
import { IncomePage } from "@/components/workspace/pages";
import { WorkspaceShell } from "@/components/workspace/workspace-shell";

export default function Page() {
  return <Suspense fallback={<div />}><WorkspaceShell>{(session) => <IncomePage session={session} />}</WorkspaceShell></Suspense>;
}
