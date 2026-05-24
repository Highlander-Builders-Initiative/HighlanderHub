/* Hero ribbon — flowing brushstroke bands on the right of the masthead.
   Pure SVG + CSS, no client JS. Crisp stroked paths with feathered
   gradient ends; no SVG filter (those rerender on the CPU every frame
   and were stealing budget from the marquee). The ribbon is promoted
   to its own compositor layer with `isolation` + `translateZ` so its
   animation can't bleed perf into neighbouring sections. */
export function HeroRibbon() {
  return (
    <div
      aria-hidden
      className="ribbon-root pointer-events-none absolute right-0 top-0 hidden w-[62%] overflow-hidden md:bottom-[360px] md:block lg:bottom-[400px] lg:w-[58%] xl:w-[55%]"
    >
      <svg
        viewBox="0 0 900 700"
        preserveAspectRatio="xMaxYMid slice"
        className="absolute inset-0 h-full w-full"
      >
        <defs>
          {/* UCR palette only — highlander navy → deep-gold → gold.
              Faded at both ends so each band reads as a brushstroke. */}
          <linearGradient id="ribbon-a" x1="0%" y1="20%" x2="100%" y2="80%">
            <stop offset="0%" stopColor="#1e3a8a" stopOpacity="0" />
            <stop offset="22%" stopColor="#1e3a8a" stopOpacity="0.95" />
            <stop offset="55%" stopColor="#8a6300" stopOpacity="0.9" />
            <stop offset="82%" stopColor="#f5b400" stopOpacity="0.9" />
            <stop offset="100%" stopColor="#f5b400" stopOpacity="0" />
          </linearGradient>
          {/* Warm secondary band — pure gold sweep. */}
          <linearGradient id="ribbon-b" x1="0%" y1="0%" x2="100%" y2="60%">
            <stop offset="0%" stopColor="#f5b400" stopOpacity="0" />
            <stop offset="30%" stopColor="#f5b400" stopOpacity="0.85" />
            <stop offset="65%" stopColor="#8a6300" stopOpacity="0.7" />
            <stop offset="100%" stopColor="#f5b400" stopOpacity="0" />
          </linearGradient>
          {/* Cool counter-band — navy arcing the other direction. */}
          <linearGradient id="ribbon-c" x1="0%" y1="80%" x2="100%" y2="10%">
            <stop offset="0%" stopColor="#1e3a8a" stopOpacity="0" />
            <stop offset="35%" stopColor="#1e3a8a" stopOpacity="0.9" />
            <stop offset="75%" stopColor="#1e3a8a" stopOpacity="0.7" />
            <stop offset="100%" stopColor="#1e3a8a" stopOpacity="0" />
          </linearGradient>
          {/* Thin inner highlight — pale band laid on top of the main
              stroke for a hint of brush striation without a real
              pattern (which would tank perf). */}
          <linearGradient id="ribbon-hi" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#ffffff" stopOpacity="0" />
            <stop offset="50%" stopColor="#ffffff" stopOpacity="0.55" />
            <stop offset="100%" stopColor="#ffffff" stopOpacity="0" />
          </linearGradient>
        </defs>

        <g className="ribbon-band ribbon-band-1">
          <path
            d="M -120 360 Q 200 100, 480 320 T 1040 240"
            stroke="url(#ribbon-a)"
            strokeWidth="96"
            strokeLinecap="round"
            fill="none"
          />
          <path
            d="M -120 360 Q 200 100, 480 320 T 1040 240"
            stroke="url(#ribbon-hi)"
            strokeWidth="22"
            strokeLinecap="round"
            fill="none"
            opacity="0.7"
          />
        </g>

        <g className="ribbon-band ribbon-band-2">
          <path
            d="M -80 480 Q 260 240, 560 470 T 1060 380"
            stroke="url(#ribbon-b)"
            strokeWidth="78"
            strokeLinecap="round"
            fill="none"
          />
        </g>

        <g className="ribbon-band ribbon-band-3">
          <path
            d="M -100 230 Q 240 460, 600 220 T 1080 320"
            stroke="url(#ribbon-c)"
            strokeWidth="86"
            strokeLinecap="round"
            fill="none"
          />
          <path
            d="M -100 230 Q 240 460, 600 220 T 1080 320"
            stroke="url(#ribbon-hi)"
            strokeWidth="18"
            strokeLinecap="round"
            fill="none"
            opacity="0.6"
          />
        </g>
      </svg>

      {/* Left-edge fade — dissolves the ribbon into the page so the
          headline copy doesn't read against hard color. */}
      <div className="ribbon-fade absolute inset-y-0 left-0 w-2/5" />
    </div>
  );
}
