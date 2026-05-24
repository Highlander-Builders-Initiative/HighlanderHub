/* A slow, painterly ribbon for the hero's empty right column.
   Pure SVG + CSS — no client JS, no hydration cost.
   Hidden on small screens; brand-palette gradients (navy → sky →
   coral → gold) feathered with a heavy blur. */
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
          {/* Cool → warm sweep, faded at both ends so the bands look like
              brushstrokes rather than blocks. */}
          <linearGradient id="ribbon-a" x1="0%" y1="20%" x2="100%" y2="80%">
            <stop offset="0%" stopColor="#1e3a8a" stopOpacity="0" />
            <stop offset="22%" stopColor="#3b82f6" stopOpacity="0.55" />
            <stop offset="55%" stopColor="#ef5d4f" stopOpacity="0.55" />
            <stop offset="85%" stopColor="#f5b400" stopOpacity="0.45" />
            <stop offset="100%" stopColor="#f5b400" stopOpacity="0" />
          </linearGradient>
          <linearGradient id="ribbon-b" x1="10%" y1="0%" x2="90%" y2="100%">
            <stop offset="0%" stopColor="#ef5d4f" stopOpacity="0" />
            <stop offset="30%" stopColor="#ef5d4f" stopOpacity="0.5" />
            <stop offset="65%" stopColor="#f5b400" stopOpacity="0.55" />
            <stop offset="100%" stopColor="#f5b400" stopOpacity="0" />
          </linearGradient>
          <linearGradient id="ribbon-c" x1="0%" y1="80%" x2="100%" y2="10%">
            <stop offset="0%" stopColor="#1e3a8a" stopOpacity="0" />
            <stop offset="35%" stopColor="#1e3a8a" stopOpacity="0.45" />
            <stop offset="70%" stopColor="#3b82f6" stopOpacity="0.5" />
            <stop offset="100%" stopColor="#3b82f6" stopOpacity="0" />
          </linearGradient>
          <linearGradient id="ribbon-d" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#f5b400" stopOpacity="0" />
            <stop offset="40%" stopColor="#ef5d4f" stopOpacity="0.4" />
            <stop offset="100%" stopColor="#1e3a8a" stopOpacity="0" />
          </linearGradient>

          <filter
            id="ribbon-soften"
            x="-20%"
            y="-20%"
            width="140%"
            height="140%"
          >
            <feGaussianBlur stdDeviation="22" />
          </filter>
        </defs>

        <g filter="url(#ribbon-soften)">
          <g className="ribbon-band ribbon-band-1">
            <path
              d="M -120 380 Q 180 80, 470 320 T 1040 260"
              stroke="url(#ribbon-a)"
              strokeWidth="180"
              strokeLinecap="round"
              fill="none"
            />
          </g>
          <g className="ribbon-band ribbon-band-2">
            <path
              d="M -80 460 Q 240 220, 540 480 T 1060 380"
              stroke="url(#ribbon-b)"
              strokeWidth="140"
              strokeLinecap="round"
              fill="none"
            />
          </g>
          <g className="ribbon-band ribbon-band-3">
            <path
              d="M -100 250 Q 220 480, 560 220 T 1080 320"
              stroke="url(#ribbon-c)"
              strokeWidth="160"
              strokeLinecap="round"
              fill="none"
            />
          </g>
          <g className="ribbon-band ribbon-band-4">
            <path
              d="M -60 560 Q 280 340, 620 580 T 1080 500"
              stroke="url(#ribbon-d)"
              strokeWidth="110"
              strokeLinecap="round"
              fill="none"
            />
          </g>
        </g>
      </svg>

      {/* Left-edge fade so the ribbon dissolves into the page rather than
          cutting a hard vertical seam through the hero copy. */}
      <div className="ribbon-fade absolute inset-y-0 left-0 w-2/5" />
    </div>
  );
}
