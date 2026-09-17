"use client";

import { Suspense } from "react";
import { TransactionsPage } from "@/components/workspace/extra-pages";
import { WorkspaceShell } from "@/components/workspace/workspace-shell";

export default function Page() {
  return <Suspense fallback={<div />}><WorkspaceShell>{(session) => <TransactionsPage session={session} />}</WorkspaceShell></Suspense>;
}
