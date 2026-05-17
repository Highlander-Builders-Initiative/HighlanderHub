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
      <body
        style={{
          margin: 0,
          padding: "64px 24px",
          fontFamily:
            "ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, sans-serif",
          background: "#fbf9f5",
          color: "#1c1a17",
        }}
      >
        <main style={{ maxWidth: 560, margin: "0 auto" }}>
          <p
            style={{
              fontFamily: "ui-monospace, SFMono-Regular, monospace",
              fontSize: 11,
              letterSpacing: "0.14em",
              textTransform: "uppercase",
              color: "#6b6760",
              margin: 0,
            }}
          >
            Fatal error
          </p>
          <h1
            style={{
              fontSize: 28,
              fontWeight: 600,
              letterSpacing: "-0.02em",
              margin: "8px 0 0",
            }}
          >
            Something broke loading the app.
          </h1>
          <p style={{ fontSize: 14, color: "#6b6760", marginTop: 12 }}>
            {error.message || "Unknown error."}
          </p>
          <button
            type="button"
            onClick={reset}
            style={{
              marginTop: 24,
              minHeight: 48,
              padding: "12px 20px",
              borderRadius: 8,
              background: "#1c1a17",
              color: "#fff",
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
