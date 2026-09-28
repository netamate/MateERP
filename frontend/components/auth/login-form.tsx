"use client";

import {
  ArrowRight,
  Eye,
  EyeOff,
  Fingerprint,
  LockKeyhole,
  Mail,
  ShieldAlert,
  ShieldCheck,
} from "lucide-react";
import { useState, type FormEvent } from "react";

import { MateERPBrand } from "@/components/brand/mateerp-brand";

type LoginFormProps = {
  onSubmit: (email: string, password: string) => Promise<void>;
};

export function LoginForm({ onSubmit }: LoginFormProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
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
    <main className="relative grid min-h-screen place-items-center overflow-hidden bg-[#07111f] px-4 py-10 text-white sm:px-6">
      <div className="pointer-events-none absolute inset-0 login-grid-dark opacity-30" />
      <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-[#2e78ff] to-transparent" />
      <div className="pointer-events-none absolute left-1/2 top-1/2 h-[680px] w-[680px] -translate-x-1/2 -translate-y-1/2 bg-[radial-gradient(circle,rgba(28,91,181,0.14)_0%,rgba(7,17,31,0)_68%)]" />

      <section className="relative z-10 w-full max-w-[500px] border border-[#263449] bg-[#0b1524] shadow-[0_32px_90px_rgba(0,0,0,0.42)]">
        <div className="h-[3px] bg-[#2e78ff]" />

        <div className="border-b border-[#253247] px-6 py-7 sm:px-8">
          <div className="flex items-start justify-between gap-5">
            <MateERPBrand
              className="text-white"
              heading
              logoClassName="h-10 w-11 shrink-0 text-[#4d8cff]"
              wordmarkClassName="text-[29px] tracking-[0.04em]"
            />
            <div className="mt-1 flex shrink-0 items-center gap-2 border border-[#704548] bg-[#25181d] px-2.5 py-1.5 text-[9px] font-bold uppercase tracking-[0.16em] text-[#ff9da3]">
              <span className="h-1.5 w-1.5 animate-pulse bg-[#ef5d67]" />
              Restricted
            </div>
          </div>

          <div className="mt-7 flex items-start gap-3 border-l-2 border-[#2e78ff] pl-4">
            <ShieldAlert className="mt-0.5 shrink-0 text-[#77a9ff]" size={19} strokeWidth={1.7} />
            <div>
              <h2 className="text-base font-bold uppercase tracking-[0.08em] text-white">
                Authorized Access Only
              </h2>
              <p className="mt-1.5 text-xs leading-5 text-[#8fa0b8]">
                Private enterprise resource planning system. Access is limited to approved NetaMate personnel.
              </p>
            </div>
          </div>
        </div>

        <form className="space-y-5 px-6 py-7 sm:px-8" onSubmit={handleSubmit}>
          <div>
            <label
              className="mb-2 block text-[10px] font-bold uppercase tracking-[0.13em] text-[#91a5c1]"
              htmlFor="email"
            >
              Identity / Email
            </label>
            <div className="group flex h-12 items-center border border-[#2a3b52] bg-[#07111e] focus-within:border-[#397ff1] focus-within:shadow-[inset_3px_0_0_#397ff1]">
              <Mail
                className="ml-3.5 shrink-0 text-[#60738f] group-focus-within:text-[#5b96f5]"
                size={16}
                strokeWidth={1.7}
              />
              <input
                autoComplete="email"
                className="h-full min-w-0 flex-1 border-0 bg-transparent px-3 text-sm text-[#e9eef7] outline-none placeholder:text-[#52627a]"
                id="email"
                onChange={(event) => setEmail(event.target.value)}
                placeholder="name@netamate.com"
                required
                type="email"
                value={email}
              />
            </div>
          </div>

          <div>
            <label
              className="mb-2 block text-[10px] font-bold uppercase tracking-[0.13em] text-[#91a5c1]"
              htmlFor="password"
            >
              Access Credential
            </label>
            <div className="group flex h-12 items-center border border-[#2a3b52] bg-[#07111e] focus-within:border-[#397ff1] focus-within:shadow-[inset_3px_0_0_#397ff1]">
              <LockKeyhole
                className="ml-3.5 shrink-0 text-[#60738f] group-focus-within:text-[#5b96f5]"
                size={16}
                strokeWidth={1.7}
              />
              <input
                autoComplete="current-password"
                className="h-full min-w-0 flex-1 border-0 bg-transparent px-3 text-sm text-[#e9eef7] outline-none placeholder:text-[#52627a]"
                id="password"
                onChange={(event) => setPassword(event.target.value)}
                placeholder="Enter secure password"
                required
                type={showPassword ? "text" : "password"}
                value={password}
              />
              <button
                aria-label={showPassword ? "Hide password" : "Show password"}
                className="grid h-full w-11 shrink-0 place-items-center border-l border-[#253247] text-[#65758c] hover:bg-[#101d2f] hover:text-[#8bb5ff]"
                onClick={() => setShowPassword((value) => !value)}
                type="button"
              >
                {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>

          {error ? (
            <div
              className="flex items-start gap-2.5 border border-[#703d43] bg-[#241419] px-3.5 py-3 text-xs leading-5 text-[#ffabb0]"
              role="alert"
            >
              <ShieldAlert className="mt-0.5 shrink-0" size={15} />
              <span>{error}</span>
            </div>
          ) : null}

          <button
            aria-label="Sign in"
            className="group flex h-12 w-full items-center justify-center gap-2 border border-[#3b82f6] bg-[#245fd2] px-4 text-xs font-bold uppercase tracking-[0.1em] text-white transition-colors hover:bg-[#1d53bd] disabled:opacity-60"
            disabled={submitting}
            type="submit"
          >
            {submitting ? "Verifying credentials..." : "Enter Secure Workspace"}
            {!submitting ? <ArrowRight className="transition-transform group-hover:translate-x-0.5" size={16} /> : null}
          </button>
        </form>

        <div className="border-t border-[#253247] bg-[#091320] px-6 py-5 sm:px-8">
          <div className="grid gap-px border border-[#213147] bg-[#213147] sm:grid-cols-2">
            <div className="flex items-center gap-2.5 bg-[#0b1726] px-3 py-3">
              <Fingerprint className="shrink-0 text-[#5c92eb]" size={17} strokeWidth={1.6} />
              <div>
                <div className="text-[10px] font-bold uppercase tracking-[0.08em] text-[#b7c5d9]">
                  Identity Protected
                </div>
                <div className="mt-0.5 text-[9px] text-[#64758e]">Secure authenticated session</div>
              </div>
            </div>
            <div className="flex items-center gap-2.5 bg-[#0b1726] px-3 py-3">
              <ShieldCheck className="shrink-0 text-[#37c98b]" size={17} strokeWidth={1.6} />
              <div>
                <div className="text-[10px] font-bold uppercase tracking-[0.08em] text-[#b7c5d9]">
                  Controlled System
                </div>
                <div className="mt-0.5 text-[9px] text-[#64758e]">Role and organization scoped</div>
              </div>
            </div>
          </div>

          <p className="mt-5 text-center text-[9px] font-semibold uppercase tracking-[0.12em] text-[#53647c]">
            Unauthorized access is prohibited · MateERP Internal System
          </p>
        </div>
      </section>

    </main>
  );
}
