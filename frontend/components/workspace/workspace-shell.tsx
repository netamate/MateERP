"use client";

import type { ReactNode } from "react";

import { AuthGate } from "@/components/auth/auth-gate";
import { AppShell } from "@/components/layout/app-shell";
import type { SessionPayload } from "@/lib/api";

type WorkspaceShellProps = {
  children: (session: SessionPayload) => ReactNode;
};

export function WorkspaceShell({ children }: WorkspaceShellProps) {
  return (
    <AuthGate>
      {({ session, onLogout }) => (
        <AppShell onLogout={onLogout} session={session}>
          {children(session)}
        </AppShell>
      )}
    </AuthGate>
  );
}
