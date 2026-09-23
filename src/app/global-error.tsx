"use client";

import { useEffect } from "react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <html lang="en">
      {/* This page replaces the root layout, so globals.css is not loaded:
          it carries its own light/dark palette, following the device. */}
      <style>{`
        :root {
          color-scheme: light dark;
          --ge-canvas: #ffffff;
          --ge-ink: #0f1115;
          --ge-muted: #6b7280;
        }
        @media (prefers-color-scheme: dark) {
          :root {
            --ge-canvas: #1e1f22;
            --ge-ink: #eceef1;
            --ge-muted: #bec0c4;
          }
        }
      `}</style>
      <body
        style={{
          margin: 0,
          minHeight: "100vh",
          padding: "56px 24px",
          fontFamily:
            "var(--font-body), \"Bricolage Grotesque\", ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, sans-serif",
          background: "var(--ge-canvas)",
          color: "var(--ge-ink)",
        }}
      >
        <main style={{ maxWidth: 720, margin: "0 auto" }}>
          <p
            style={{
              fontFamily:
                "var(--font-body), ui-sans-serif, system-ui, sans-serif",
              fontSize: 13,
              color: "var(--ge-muted)",
              margin: 0,
            }}
          >
            Highlander Hub
          </p>
          <h1
            style={{
              maxWidth: 620,
              fontFamily:
                "var(--font-display), ui-sans-serif, system-ui, sans-serif",
              fontSize: "clamp(34px, 7vw, 56px)",
              fontWeight: 600,
              lineHeight: 1.05,
              letterSpacing: "-0.03em",
              margin: "16px 0 0",
            }}
          >
            Campus events hit a snag.
          </h1>
          <p
            aria-live="polite"
            style={{
              maxWidth: 560,
              fontSize: 16,
              lineHeight: 1.6,
              color: "var(--ge-muted)",
              marginTop: 16,
            }}
          >
            {error.message || "Unknown error."}
          </p>
          <button
            type="button"
            onClick={reset}
            style={{
              marginTop: 32,
              minHeight: 48,
              padding: "12px 22px",
              borderRadius: 8,
              background: "var(--ge-ink)",
              color: "var(--ge-canvas)",
              border: 0,
              fontSize: 14,
              fontWeight: 500,
              cursor: "pointer",
            }}
          >
            Try again
          </button>
        </main>
      </body>
    </html>
  );
}
