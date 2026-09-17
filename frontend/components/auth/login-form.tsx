"use client";

import {
  ArrowRight,
  BarChart3,
  Eye,
  EyeOff,
  Landmark,
  LockKeyhole,
  Mail,
  Network,
  ShieldCheck,
} from "lucide-react";
import { useState, type FormEvent } from "react";

import { MateERPBrand } from "@/components/brand/mateerp-brand";

type LoginFormProps = {
  onSubmit: (email: string, password: string) => Promise<void>;
};

const workspaceAreas = [
  {
    title: "Finance & Accounting",
    description: "Ledger, cash flow, expenses, income and reconciliation.",
    icon: Landmark,
  },
  {
    title: "Business Operations",
    description: "Subscriptions, infrastructure, domains and renewals.",
    icon: Network,
  },
  {
    title: "Planning & Reporting",
    description: "Budgets, projects, allocations and enterprise reporting.",
    icon: BarChart3,
  },
];

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
    <main className="min-h-screen bg-[#f4f7fb] lg:grid lg:grid-cols-[minmax(0,1.08fr)_minmax(480px,0.92fr)]">
      <section className="relative hidden min-h-screen overflow-hidden bg-[#071426] text-white lg:flex lg:flex-col">
        <div className="pointer-events-none absolute inset-0 login-grid-dark opacity-35" />
        <div className="pointer-events-none absolute -right-32 -top-36 h-[470px] w-[470px] border border-[#1d4f8f] bg-[#0a2e5c]/35 rotate-45" />
        <div className="pointer-events-none absolute -bottom-56 -left-36 h-[520px] w-[520px] border border-[#123967] bg-[#0b2444] rotate-45" />

        <div className="relative z-10 flex min-h-screen flex-col px-[7vw] py-10">
          <MateERPBrand
            className="text-white"
            heading
            logoClassName="h-11 w-12 shrink-0"
            subtitle="by NetaMate Solutions"
            wordmarkClassName="text-[32px] tracking-[0.035em]"
          />

          <div className="my-auto max-w-2xl py-14">
            <div className="mb-6 inline-flex items-center gap-2 border border-[#27496f] bg-[#0b1c32] px-3 py-2 text-[10px] font-bold uppercase tracking-[0.2em] text-[#8ebdff]">
              <span className="h-1.5 w-1.5 bg-[#2e78ff]" />
              Enterprise Resource Planning
            </div>

            <h2 className="max-w-xl text-[clamp(42px,4.3vw,68px)] font-semibold leading-[0.98] tracking-[-0.04em]">
              One workspace for the financial and operational core of NetaMate.
            </h2>
            <p className="mt-7 max-w-xl text-base leading-7 text-[#9fb0c6]">
              Keep finance, planning, renewals, infrastructure and reporting connected in one secure operating system.
            </p>

            <div className="mt-10 grid max-w-2xl gap-px border border-[#24364e] bg-[#24364e] xl:grid-cols-3">
              {workspaceAreas.map(({ title, description, icon: Icon }) => (
                <div className="bg-[#0a182a] p-5" key={title}>
                  <Icon className="text-[#4b8fff]" size={20} strokeWidth={1.7} />
                  <div className="mt-4 text-sm font-semibold text-white">{title}</div>
                  <p className="mt-2 text-xs leading-5 text-[#8293aa]">{description}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="relative z-10 flex items-center justify-between border-t border-[#24364e] pt-5 text-[10px] font-semibold uppercase tracking-[0.16em] text-[#72839a]">
            <span>Private company workspace</span>
            <span>People · Process · Progress</span>
          </div>
        </div>
      </section>

      <section className="relative flex min-h-screen items-center justify-center overflow-hidden px-5 py-10 sm:px-8 lg:px-12">
        <div className="pointer-events-none absolute inset-0 login-grid-light opacity-70" />
        <div className="pointer-events-none absolute right-0 top-0 h-56 w-56 border-b border-l border-[#d7e4f4] bg-[#eef5fd] [clip-path:polygon(100%_0,100%_100%,0_0)]" />

        <div className="relative z-10 w-full max-w-[470px]">
          <MateERPBrand
            className="mb-10 text-[#091a31] lg:hidden"
            heading
            logoClassName="h-10 w-11 shrink-0 text-[#0b4dbb]"
            subtitle="by NetaMate Solutions"
            wordmarkClassName="text-[29px] tracking-[0.035em]"
          />

          <div className="mb-8">
            <div className="mb-3 text-[11px] font-bold uppercase tracking-[0.18em] text-[#0b4dbb]">
              Secure workspace access
            </div>
            <h2 className="text-[34px] font-semibold tracking-[-0.035em] text-[#0d1727]">Welcome back</h2>
            <p className="mt-2 text-sm leading-6 text-[#68758a]">
              Sign in with your NetaMate organization account to continue to MateERP.
            </p>
          </div>

          <section className="border border-[#cdd6e2] bg-white shadow-[0_24px_70px_rgba(20,44,77,0.10)]">
            <div className="border-b border-[#e1e6ed] px-6 py-4">
              <div className="flex items-center gap-2 text-xs font-semibold text-[#445066]">
                <ShieldCheck className="text-[#0b4dbb]" size={16} />
                Authorized personnel only
              </div>
            </div>

            <form className="space-y-5 px-6 py-6 sm:px-7 sm:py-7" onSubmit={handleSubmit}>
              <div>
                <label className="mb-2 block text-[11px] font-bold uppercase tracking-[0.08em] text-[#475569]" htmlFor="email">
                  Email address
                </label>
                <div className="group flex h-12 items-center border border-[#c5ceda] bg-white focus-within:border-[#0b4dbb] focus-within:shadow-[inset_3px_0_0_#0b4dbb]">
                  <Mail className="ml-3.5 shrink-0 text-[#718096] group-focus-within:text-[#0b4dbb]" size={17} strokeWidth={1.7} />
                  <input
                    autoComplete="email"
                    className="h-full min-w-0 flex-1 border-0 bg-transparent px-3 text-sm outline-none placeholder:text-[#9aa6b5]"
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
                <label className="mb-2 block text-[11px] font-bold uppercase tracking-[0.08em] text-[#475569]" htmlFor="password">
                  Password
                </label>
                <div className="group flex h-12 items-center border border-[#c5ceda] bg-white focus-within:border-[#0b4dbb] focus-within:shadow-[inset_3px_0_0_#0b4dbb]">
                  <LockKeyhole className="ml-3.5 shrink-0 text-[#718096] group-focus-within:text-[#0b4dbb]" size={17} strokeWidth={1.7} />
                  <input
                    autoComplete="current-password"
                    className="h-full min-w-0 flex-1 border-0 bg-transparent px-3 text-sm outline-none placeholder:text-[#9aa6b5]"
                    id="password"
                    onChange={(event) => setPassword(event.target.value)}
                    placeholder="Enter your password"
                    required
                    type={showPassword ? "text" : "password"}
                    value={password}
                  />
                  <button
                    aria-label={showPassword ? "Hide password" : "Show password"}
                    className="grid h-full w-11 shrink-0 place-items-center border-l border-[#e1e6ed] text-[#718096] hover:bg-[#f7f9fc] hover:text-[#0b4dbb]"
                    onClick={() => setShowPassword((value) => !value)}
                    type="button"
                  >
                    {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </div>

              {error ? (
                <div
                  className="border border-[#efb4b4] bg-[#fff6f6] px-3.5 py-3 text-sm text-[#a51d1d]"
                  role="alert"
                >
                  {error}
                </div>
              ) : null}

              <button
                className="group flex h-12 w-full items-center justify-center gap-2 border border-[#0a438f] bg-[#0b4dbb] px-4 text-sm font-bold text-white transition-colors hover:bg-[#083b8c] disabled:opacity-60"
                disabled={submitting}
                type="submit"
              >
                {submitting ? "Signing in..." : "Sign in"}
                {!submitting ? <ArrowRight className="transition-transform group-hover:translate-x-0.5" size={16} /> : null}
              </button>
            </form>
          </section>

          <div className="mt-5 flex items-start gap-3 border-l-2 border-[#0b4dbb] bg-[#edf4fd] px-4 py-3.5">
            <ShieldCheck className="mt-0.5 shrink-0 text-[#0b4dbb]" size={16} />
            <div>
              <div className="text-xs font-semibold text-[#1d3555]">Secure organization workspace</div>
              <p className="mt-1 text-[11px] leading-5 text-[#68758a]">
                Your session and organization context are protected by MateERP access controls.
              </p>
            </div>
          </div>

          <div className="mt-8 flex items-center justify-between border-t border-[#dce3ec] pt-4 text-[10px] font-semibold uppercase tracking-[0.1em] text-[#7a8798]">
            <span>NetaMate Solutions</span>
            <span>MateERP</span>
          </div>
        </div>
      </section>
    </main>
  );
}
