import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/lib/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        canvas: "#ffffff",
        surface: "#fafafa",
        line: "#e7e7e9",
        ink: "#0f1115",
        muted: "#6b7280",
        // Editorial category palette: named print-ish hues, not the
        // Tailwind/Material primary rainbow. Each color is its own
        // identity (Iris, Forest, Terracotta, Slate, Copper, Plum,
        // Sage), not a generic "blue / red / green / yellow".
        highlander: "#2a3680", // Iris
        leaf: "#4e7a52",       // Forest
        coral: "#c25e3c",      // Terracotta
        sky: "#426a9e",        // Slate Blue
        gold: "#c98429",       // Copper
        plum: "#8a3f6a",       // Plum (Arts)
        sage: "#7d9785",       // Sage (Community)
        "deep-leaf": "#2c4a30",
        "deep-coral": "#863e23",
        "deep-sky": "#2e4b73",
        "deep-gold": "#6e4612",
        "deep-plum": "#5a274a",
        "deep-sage": "#3f5644",
      },
      fontFamily: {
        sans: ["var(--font-body)", "ui-sans-serif", "system-ui", "sans-serif"],
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
