"use client";

import { useEffect, useState, type ReactNode } from "react";

import {
  ApiError,
  getSession,
  login,
  logout,
  setContext,
  type SessionPayload,
} from "@/lib/api";

import { LoginForm } from "./login-form";

type AuthGateProps = {
  children: (props: {
    session: SessionPayload;
    onLogout: () => Promise<void>;
    onContextChange: (
      organizationId: string,
      legalEntityId: string | null,
    ) => Promise<void>;
  }) => ReactNode;
};

export function AuthGate({ children }: AuthGateProps) {
  const [session, setSession] = useState<SessionPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [anonymous, setAnonymous] = useState(false);

  useEffect(() => {
    getSession()
      .then((payload) => {
        setSession(payload);
        setAnonymous(false);
      })
      .catch((error) => {
        if (error instanceof ApiError && [401, 403].includes(error.status)) {
          setAnonymous(true);
          return;
        }
        setAnonymous(true);
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <main className="grid min-h-screen place-items-center bg-[var(--color-bg)] text-sm text-[var(--color-text-muted)]">
        Loading secure session...
      </main>
    );
  }

  if (anonymous || !session) {
    return (
      <LoginForm
        onSubmit={async (email, password) => {
          const payload = await login(email, password);
          setSession(payload);
          setAnonymous(false);
        }}
      />
    );
  }

  return children({
    session,
    onLogout: async () => {
      await logout();
      setSession(null);
      setAnonymous(true);
    },
    onContextChange: async (organizationId, legalEntityId) => {
      const payload = await setContext(organizationId, legalEntityId);
      setSession(payload);
    },
  });
}
