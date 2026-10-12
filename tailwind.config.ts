import type { Config } from "tailwindcss";
import plugin from "tailwindcss/plugin";

const themeColor = (name: string) => `rgb(var(--color-${name}) / <alpha-value>)`;

// Ink hairlines (`border-ink/10`, `ring-ink/10`, `divide-ink/10`) take their
// opacity to a power set in globals.css: 1 in light mode (unchanged), 1.3 in
// dark, where a card already stands a tonal step off the page and the full
// hairline double-edged it. /10 becomes ~5%, /15 ~8.5%; solid `border-ink`
// stays solid (1^n = 1), so focus and hover edges keep their weight.
const edgeInk = "rgb(var(--color-ink) / pow(<alpha-value>, var(--edge-alpha-curve)))";

const config: Config = {
  // `dark:` variants follow the device setting (prefers-color-scheme).
  darkMode: "media",
  // `hover:` (and `group-hover:`) only where a real pointer can hover, so a
  // tap on a phone does not leave the hover style stuck on.
  future: { hoverOnlyWhenSupported: true },
  content: [
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/lib/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      // Every color is a CSS variable (RGB channels, defined in globals.css)
      // so the palette follows the device's light/dark setting and opacity
      // modifiers like `border-ink/10` keep working.
      colors: {
        canvas: themeColor("canvas"),
        surface: themeColor("surface"),
        line: themeColor("line"),
        ink: themeColor("ink"),
        muted: themeColor("muted"),
        // Softer than muted, below AA (3.2:1 on canvas). Event card meta and
        // the feed day headings' weekday only.
        faint: themeColor("faint"),
        // Always-dark overlay: modal backdrops and the scrims that keep white
        // captions legible over flyers. Unlike `ink`, it stays dark in dark mode.
        scrim: themeColor("scrim"),
        // Editorial category palette: named print-ish hues, not the
        // Tailwind/Material primary rainbow. Each color is its own
        // identity (Iris, Forest, Terracotta, Slate, Copper, Plum,
        // Sage), not a generic "blue / red / green / yellow".
        highlander: themeColor("highlander"), // Iris
        leaf: themeColor("leaf"),             // Forest
        coral: themeColor("coral"),           // Terracotta
        sky: themeColor("sky"),               // Slate Blue
        gold: themeColor("gold"),             // Copper
        plum: themeColor("plum"),             // Plum (Arts)
        sage: themeColor("sage"),             // Sage (Community)
        "deep-leaf": themeColor("deep-leaf"),
        "deep-coral": themeColor("deep-coral"),
        "deep-sky": themeColor("deep-sky"),
        "deep-gold": themeColor("deep-gold"),
        "deep-plum": themeColor("deep-plum"),
        "deep-sage": themeColor("deep-sage"),
        // Tag palette: the vivid category hues on event tags, the Topics
        // rail selection and the category dots (mapped in category-colors).
        // Each `-ink` is that hue's text color, >=4.9:1 on its own 18% wash
        // (lighter in dark mode, >=6.4:1 there).
        tag: {
          blue: themeColor("tag-blue"),
          "blue-ink": themeColor("tag-blue-ink"),
          violet: themeColor("tag-violet"),
          "violet-ink": themeColor("tag-violet-ink"),
          coral: themeColor("tag-coral"),
          "coral-ink": themeColor("tag-coral-ink"),
          cyan: themeColor("tag-cyan"),
          "cyan-ink": themeColor("tag-cyan-ink"),
          magenta: themeColor("tag-magenta"),
          "magenta-ink": themeColor("tag-magenta-ink"),
          green: themeColor("tag-green"),
          "green-ink": themeColor("tag-green-ink"),
          amber: themeColor("tag-amber"),
          "amber-ink": themeColor("tag-amber-ink"),
        },
      },
      borderColor: { ink: edgeInk },
      ringColor: { ink: edgeInk },
      divideColor: { ink: edgeInk },
      fontFamily: {
        sans: ["var(--font-body)", "ui-sans-serif", "system-ui", "sans-serif"],
        display: ["var(--font-display)", "ui-sans-serif", "system-ui", "sans-serif"],
        body: ["var(--font-body)", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      // Shadows read --color-shadow, which stays dark in both themes (never
      // tint a shadow from ink, which turns light in dark mode).
      boxShadow: {
        card: "0 1px 2px rgb(var(--color-shadow) / 0.04), 0 4px 12px rgb(var(--color-shadow) / 0.04)",
        cardHover: "0 4px 8px rgb(var(--color-shadow) / 0.06), 0 12px 28px rgb(var(--color-shadow) / 0.08)",
        // A pinned flyer resting on its tile.
        flyer: "0 1px 2px rgb(var(--color-shadow) / 0.08), 0 4px 12px -2px rgb(var(--color-shadow) / 0.08)",
        // Dropdowns and menus that float over the page.
        menu: "0 18px 44px rgb(var(--color-shadow) / 0.12)",
        // A bottom sheet's top edge, and a centred dialog.
        sheet: "0 -8px 28px rgb(var(--color-shadow) / 0.08)",
        dialog: "0 24px 40px rgb(var(--color-shadow) / 0.08)",
      },
      // The motion tokens in globals.css: `ease-out-expo` for state changes,
      // `ease-drawer` for parts that travel or grow.
      transitionTimingFunction: {
        "out-expo": "var(--ease-out)",
        drawer: "var(--ease-drawer)",
      },
    },
  },
  plugins: [
    // `coarse:` sizes up tightly packed controls (calendar, footer lists) to
    // 44px on touch screens, where a .hit-area would overlap the neighbour.
    plugin(({ addVariant }) => addVariant("coarse", "@media (pointer: coarse)")),
  ],
};
export default config;
