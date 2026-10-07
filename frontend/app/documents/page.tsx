"use client";

import { FinancialDocumentLibraryPage } from "@/components/workspace/financial-document-library-page";
import { WorkspaceShell } from "@/components/workspace/workspace-shell";

export default function Page() {
  return (
    <WorkspaceShell>
      {(session) => <FinancialDocumentLibraryPage session={session} />}
    </WorkspaceShell>
  );
}
