"use client";

import { Suspense } from "react";
import { SettingsPage } from "@/components/workspace/pages";
import { WorkspaceShell } from "@/components/workspace/workspace-shell";

export default function Page() {
  return <Suspense fallback={<div />}><WorkspaceShell>{(session) => <SettingsPage session={session} />}</WorkspaceShell></Suspense>;
}
