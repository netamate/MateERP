"use client";

import { Suspense } from "react";
import { VendorsPage } from "@/components/workspace/pages";
import { WorkspaceShell } from "@/components/workspace/workspace-shell";

export default function Page() {
  return <Suspense fallback={<div />}><WorkspaceShell>{(session) => <VendorsPage session={session} />}</WorkspaceShell></Suspense>;
}
