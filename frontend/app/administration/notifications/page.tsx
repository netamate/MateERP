"use client";

import { NotificationsPage } from "@/components/workspace/phase8-admin-pages";
import { WorkspaceShell } from "@/components/workspace/workspace-shell";

export default function Page() {
  return <WorkspaceShell>{(session) => <NotificationsPage session={session} />}</WorkspaceShell>;
}
