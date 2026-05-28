"use client";

import React, { useState, useTransition } from "react";
import { loginAdmin } from "../actions";
import { useRouter } from "next/navigation";

export default function AdminLoginPage() {
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();
  const router = useRouter();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!password.trim()) {
      setError("Please enter the administrator password.");
      return;
    }

    startTransition(async () => {
      try {
        const result = await loginAdmin(password);
        if (result.success) {
          router.push("/admin");
          router.refresh();
        } else {
          setError(result.error || "Login failed.");
        }
      } catch (err) {
        setError("An unexpected error occurred. Please try again.");
      }
    });
  };

  return (
    <main className="min-h-screen bg-surface flex flex-col items-center justify-center p-4 sm:p-6 select-none">
      {/* Visual background accents - very minimal */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden opacity-5 flex items-center justify-center">
        <span className="font-display text-[20vw] font-bold text-ink select-none tracking-tighter">
          UCR
        </span>
      </div>

      <div className="w-full max-w-[420px] bg-canvas border border-ink/10 rounded-xl p-8 shadow-card animate-fade-up relative z-10">
        <header className="mb-8">
          <div className="flex items-center gap-1 text-[11px] font-mono tracking-wider text-muted uppercase mb-2">
            <span>Highlander Builders Initiative</span>
            <span className="text-coral">·</span>
            <span>HBI</span>
          </div>
          <h1 className="font-display text-3xl font-semibold text-ink leading-tight tracking-tight">
            Highlander Hub
          </h1>
          <p className="text-xs text-muted mt-1.5 font-sans leading-relaxed">
            Sign in to review community event submissions and manage what appears on the public calendar.
          </p>
        </header>

        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="space-y-2">
            <label
              htmlFor="password"
              className="block text-[13px] font-sans text-muted"
            >
              Admin password
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={isPending}
              placeholder="••••••••"
              className="w-full bg-canvas text-ink border border-ink/15 rounded-md py-3 px-3.5 text-base font-mono placeholder:text-muted/40 transition-colors focus:border-ink interactive-focus outline-none"
              required
              autoFocus
            />
          </div>

          {error && (
            <div className="p-3.5 bg-coral/10 border border-deep-coral/20 rounded-md animate-field-reveal">
              <p className="text-[13px] text-deep-coral leading-normal font-sans">
                {error}
              </p>
            </div>
          )}

          <button
            type="submit"
            disabled={isPending}
            className="w-full min-h-12 bg-ink text-canvas rounded-md font-sans text-sm font-semibold hover:bg-ink/90 active:scale-[0.99] transition-all flex items-center justify-center gap-2 interactive-focus outline-none disabled:opacity-50"
          >
            {isPending ? (
              <span className="flex items-center gap-1.5 font-sans">
                <svg
                  className="animate-spin h-4 w-4 text-canvas"
                  fill="none"
                  viewBox="0 0 24 24"
                >
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  />
                </svg>
                Verifying...
              </span>
            ) : (
              "Sign in"
            )}
          </button>
        </form>
      </div>

      <footer className="mt-8 text-[11px] font-mono text-muted/60 tracking-wider">
        <span>© {new Date().getFullYear()} HIGHLANDER HUB · UCR CAMPUS</span>
      </footer>
    </main>
  );
}
