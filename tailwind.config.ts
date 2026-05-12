import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Sun-bleached Riverside palette
        bone: "#f4ede0",
        sand: "#e8dcc4",
        ink: "#1a1614",
        clay: "#c4502a",
        rust: "#8b3a1a",
        olive: "#5a5a2c",
        sky: "#6b8caa",
        citrus: "#d99e2b",
      },
      fontFamily: {
        display: ["var(--font-display)", "serif"],
        body: ["var(--font-body)", "serif"],
        mono: ["var(--font-mono)", "monospace"],
      },
      animation: {
        "marquee": "marquee 40s linear infinite",
        "ticker": "ticker 60s linear infinite",
      },
      keyframes: {
        marquee: {
          "0%": { transform: "translateX(0%)" },
          "100%": { transform: "translateX(-50%)" },
        },
        ticker: {
          "0%": { transform: "translateX(100%)" },
          "100%": { transform: "translateX(-100%)" },
        },
      },
    },
  },
  plugins: [],
};
export default config;
