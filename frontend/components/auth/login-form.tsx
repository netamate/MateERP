"use client";

import { useState, type FormEvent } from "react";

type LoginFormProps = {
  onSubmit: (email: string, password: string) => Promise<void>;
};

export function LoginForm({ onSubmit }: LoginFormProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      await onSubmit(email, password);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Sign in failed.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="grid min-h-screen place-items-center bg-[var(--color-bg)] px-4">
      <section className="w-full max-w-md border border-[var(--color-border)] bg-white">
        <div className="border-b border-[var(--color-border)] px-6 py-5">
          <h1 className="text-lg font-bold tracking-wide">MateERP</h1>
          <p className="mt-1 text-xs uppercase tracking-[0.12em] text-[var(--color-text-muted)]">
            Secure workspace
          </p>
        </div>

        <form className="space-y-4 px-6 py-6" onSubmit={handleSubmit}>
          <div>
            <label className="mb-1 block text-xs font-semibold" htmlFor="email">
              Email
            </label>
            <input
              autoComplete="email"
              className="h-10 w-full border border-[var(--color-border)] px-3 text-sm outline-none focus:border-slate-700"
              id="email"
              onChange={(event) => setEmail(event.target.value)}
              required
              type="email"
              value={email}
            />
          </div>

          <div>
            <label className="mb-1 block text-xs font-semibold" htmlFor="password">
              Password
            </label>
            <input
              autoComplete="current-password"
              className="h-10 w-full border border-[var(--color-border)] px-3 text-sm outline-none focus:border-slate-700"
              id="password"
              onChange={(event) => setPassword(event.target.value)}
              required
              type="password"
              value={password}
            />
          </div>

          {error ? (
            <div
              className="border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-800"
              role="alert"
            >
              {error}
            </div>
          ) : null}

          <button
            className="h-10 w-full border border-slate-950 bg-slate-950 px-4 text-sm font-semibold text-white disabled:opacity-60"
            disabled={submitting}
            type="submit"
          >
            {submitting ? "Signing in..." : "Sign in"}
          </button>
        </form>
      </section>
    </main>
  );
}
