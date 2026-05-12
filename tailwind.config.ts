import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Clean modern palette with UCR-inspired accents
        canvas: "#ffffff",
        surface: "#fafafa",
        line: "#e7e7e9",
        ink: "#0f1115",
        muted: "#6b7280",
        // Accents
        highlander: "#1e3a8a", // UCR-ish deep blue
        gold: "#f5b400",       // UCR gold
        coral: "#ef5d4f",
        leaf: "#2f9e6f",
        sky: "#3b82f6",
      },
      fontFamily: {
        display: ["var(--font-display)", "ui-sans-serif", "system-ui", "sans-serif"],
        body: ["var(--font-body)", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      boxShadow: {
        card: "0 1px 2px rgba(15, 17, 21, 0.04), 0 4px 12px rgba(15, 17, 21, 0.04)",
        cardHover: "0 4px 8px rgba(15, 17, 21, 0.06), 0 12px 28px rgba(15, 17, 21, 0.08)",
      },
    },
  },
  plugins: [],
};
export default config;
