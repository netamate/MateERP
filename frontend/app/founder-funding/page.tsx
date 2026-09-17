"use client";

import { Suspense } from "react";
import { FounderFundingPage } from "@/components/workspace/extra-pages";
import { WorkspaceShell } from "@/components/workspace/workspace-shell";

export default function Page() {
  return <Suspense fallback={<div />}><WorkspaceShell>{(session) => <FounderFundingPage session={session} />}</WorkspaceShell></Suspense>;
}
