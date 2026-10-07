"use client";

import { EmailTemplateDesignerPage } from "@/components/workspace/email-template-designer-page";
import { WorkspaceShell } from "@/components/workspace/workspace-shell";

export default function Page() {
  return (
    <WorkspaceShell>
      {(session) => <EmailTemplateDesignerPage session={session} />}
    </WorkspaceShell>
  );
}
