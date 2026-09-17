"use client";

import { Suspense } from "react";
import { FiscalPeriodsPage } from "@/components/workspace/extra-pages";
import { WorkspaceShell } from "@/components/workspace/workspace-shell";

export default function Page() {
  return <Suspense fallback={<div />}><WorkspaceShell>{(session) => <FiscalPeriodsPage session={session} />}</WorkspaceShell></Suspense>;
}
