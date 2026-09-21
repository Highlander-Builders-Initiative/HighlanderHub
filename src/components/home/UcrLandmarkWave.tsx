/* UCR Landmark Wave — the hero landmark and transitional landscape.
 *
 * Inspired by Berkeley Goggles' Sather Gate landscape wave, this component
 * establishes Highlander Hub's signature sense of place for UC Riverside:
 *
 * 1. The 161-foot Carillon Bell Tower (completed 1966), UCR's defining architectural
 *    landmark, standing proudly on the right crest with its modernist pierced concrete
 *    screen, louvers, and active Pacific clock hands.
 * 2. Box Springs Mountain range in the atmospheric background with the whitewashed "Big C".
 * 3. Sweeping multi-layered curved landscape waves in UCR's signature Highlander Blue
 *    palette (#1e3a8a, #2563eb, #38bdf8) and warm citrus gold (#f59e0b) that flow
 *    across the horizon and anchor the hero transition into the campus bulletin.
 */

type ClockHands = { hour: number; minute: number };

/* Tower geometry in local coords (viewBox 220 x 700) */
const TOWER = {
  left: 58,
  right: 162,
  capTop: 16,
  capBottom: 34,
  belfryTop: 42,
  belfryBottom: 170,
  corniceBottom: 184,
  base: 700,
  clock: { x: 78, y: 204, w: 64, h: 64, cx: 110, cy: 236, r: 23 },
} as const;

const LOUVERS = Array.from({ length: 11 }, (_, i) => 76 + i * 6.6);

export function UcrLandmarkWave({ clock }: { clock: ClockHands }) {
  return (
    <div
      aria-hidden
      className="pointer-events-none relative w-full overflow-hidden select-none -mb-1"
    >
      <svg
        viewBox="0 0 1440 380"
        preserveAspectRatio="xMidYMax slice"
        className="block h-auto w-full min-w-[768px] transform-gpu"
      >
        <defs>
          {/* Subtle Riverside sky gradient */}
          <linearGradient id="ucr-sky-grad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#ffffff" stopOpacity="0" />
            <stop offset="60%" stopColor="#f8fafc" stopOpacity="0.4" />
            <stop offset="100%" stopColor="#e0f2fe" stopOpacity="0.75" />
          </linearGradient>

          {/* Layer 1: Sky light wave (matches Berkeley Goggles top wave tone) */}
          <linearGradient id="ucr-wave-light" x1="0" y1="0" x2="1" y2="0.4">
            <stop offset="0%" stopColor="#74CBFE" />
            <stop offset="45%" stopColor="#38bdf8" />
            <stop offset="100%" stopColor="#60a5fa" />
          </linearGradient>

          {/* Layer 2: Vibrant Highlander Royal Blue */}
          <linearGradient id="ucr-wave-mid" x1="0" y1="0" x2="1" y2="0.5">
            <stop offset="0%" stopColor="#2496F4" />
            <stop offset="50%" stopColor="#2563eb" />
            <stop offset="100%" stopColor="#1d4ed8" />
          </linearGradient>

          {/* Layer 3: Warm California Citrus Gold ribbon */}
          <linearGradient id="ucr-gold-ribbon" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="#fbbf24" stopOpacity="0.2" />
            <stop offset="35%" stopColor="#f59e0b" stopOpacity="0.95" />
            <stop offset="70%" stopColor="#d97706" stopOpacity="0.85" />
            <stop offset="100%" stopColor="#c25e3c" stopOpacity="0.3" />
          </linearGradient>

          {/* Layer 4: Deep Highlander Midnight Navy Base (seamless with next section) */}
          <linearGradient id="ucr-wave-deep" x1="0" y1="0" x2="1" y2="0.2">
            <stop offset="0%" stopColor="#1e3a8a" />
            <stop offset="40%" stopColor="#1e3a8a" />
            <stop offset="80%" stopColor="#172554" />
            <stop offset="100%" stopColor="#0b1329" />
          </linearGradient>

          {/* Tower pierced concrete lattice screen */}
          <pattern
            id="ucr-tower-screen"
            width="6"
            height="6.2"
            patternUnits="userSpaceOnUse"
          >
            <rect
              x="1.3"
              y="1.7"
              width="3.4"
              height="2.8"
              fill="#0f1115"
              fillOpacity="0.34"
            />
          </pattern>

          {/* Architectural pier lighting gradient */}
          <linearGradient id="ucr-pier-grad" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="#fbbf24" stopOpacity="0.22" />
            <stop offset="50%" stopColor="#ffffff" stopOpacity="0.96" />
            <stop offset="100%" stopColor="#2a3680" stopOpacity="0.14" />
          </linearGradient>

          {/* Warm Sun glow behind the Carillon Tower */}
          <radialGradient
            id="ucr-sun-glow"
            cx="82%"
            cy="35%"
            r="36%"
            fx="82%"
            fy="35%"
          >
            <stop offset="0%" stopColor="#fef08a" stopOpacity="0.35" />
            <stop offset="50%" stopColor="#fed7aa" stopOpacity="0.15" />
            <stop offset="100%" stopColor="#ffffff" stopOpacity="0" />
          </radialGradient>
        </defs>

        {/* Sky wash & ambient sun glow */}
        <rect width="1440" height="380" fill="url(#ucr-sky-grad)" />
        <rect width="1440" height="380" fill="url(#ucr-sun-glow)" />

        {/* Distant Mountain: Box Springs Range with the Big C */}
        <path
          d="M-20 225 C 130 200, 270 175, 430 158 C 570 144, 660 138, 790 152 C 930 168, 1070 155, 1210 175 C 1330 192, 1410 205, 1460 215 L 1460 380 L -20 380 Z"
          fill="#2a3680"
          fillOpacity="0.07"
          stroke="#2a3680"
          strokeOpacity="0.18"
          strokeWidth="1"
        />

        {/* The Big C on the Box Springs hillside */}
        <path
          d="M 672 148 A 12 12 0 1 0 672 170"
          fill="none"
          stroke="#c98429"
          strokeOpacity="0.85"
          strokeWidth="4.5"
          strokeLinecap="round"
        />

        {/* Grove & Palm silhouettes along the ridge */}
        <g fill="#2a3680" fillOpacity="0.05">
          <path d="M 160 242 Q 190 228 220 242 Q 250 224 280 242 Q 310 228 340 242 Q 380 220 420 242 Q 460 224 500 242 Q 540 226 580 242 Q 620 222 660 242 Q 700 226 740 242 L 740 380 L 160 380 Z" />
          <path
            d="M 315 244 L 316 218 M 316 218 L 306 208 M 316 218 L 326 208 M 316 218 L 304 216 M 316 218 L 328 216 M 316 218 L 316 204"
            stroke="#2a3680"
            strokeOpacity="0.18"
            strokeWidth="1.5"
            strokeLinecap="round"
          />
        </g>

        {/* Wave 1: Sky light curve (sweeping from left to crest on right) */}
        <path
          d="M 0 258 C 300 242, 580 274, 840 244 C 1010 224, 1170 188, 1440 214 L 1440 380 L 0 380 Z"
          fill="url(#ucr-wave-light)"
        />

        {/* Wave 2: Vibrant Highlander Blue */}
        <path
          d="M 0 276 C 270 262, 560 292, 870 258 C 1040 238, 1210 206, 1440 234 L 1440 380 L 0 380 Z"
          fill="url(#ucr-wave-mid)"
        />

        {/* Wave 3: Warm California Citrus Gold ribbon accent */}
        <path
          d="M 0 292 C 340 280, 670 302, 940 268 C 1070 250, 1250 222, 1440 244 L 1440 250 C 1250 228, 1070 256, 940 274 C 670 308, 340 286, 0 298 Z"
          fill="url(#ucr-gold-ribbon)"
        />

        {/* Wave 4: Deep Base Midnight Navy (provides smooth dock into next section) */}
        <path
          d="M 0 306 C 290 296, 610 316, 910 286 C 1070 270, 1240 246, 1440 268 L 1440 380 L 0 380 Z"
          fill="url(#ucr-wave-deep)"
        />

        {/* UCR CARILLON BELL TOWER atop the right crest */}
        <g transform="translate(1115, 28) scale(0.46)">
          {/* Solid concrete body */}
          <rect
            x={TOWER.left}
            y={TOWER.capTop}
            width={TOWER.right - TOWER.left}
            height={TOWER.base - TOWER.capTop}
            fill="#ffffff"
            fillOpacity="0.98"
          />

          {/* Concrete shaft: pierced lattice screens & piers */}
          <g>
            <rect
              x="76"
              y={TOWER.corniceBottom}
              width="30"
              height="516"
              fill="url(#ucr-tower-screen)"
            />
            <rect
              x="114"
              y={TOWER.corniceBottom}
              width="30"
              height="516"
              fill="url(#ucr-tower-screen)"
            />
            <rect
              x="58"
              y={TOWER.corniceBottom}
              width="18"
              height="516"
              fill="url(#ucr-pier-grad)"
            />
            <rect
              x="106"
              y={TOWER.corniceBottom}
              width="8"
              height="516"
              fill="url(#ucr-pier-grad)"
            />
            <rect
              x="144"
              y={TOWER.corniceBottom}
              width="18"
              height="516"
              fill="url(#ucr-pier-grad)"
            />
          </g>

          {/* Belfry chamber (open louvers with bells) */}
          <g>
            <rect
              x="76"
              y={TOWER.belfryTop}
              width="68"
              height={TOWER.belfryBottom - TOWER.belfryTop}
              fill="#1b2033"
              fillOpacity="0.86"
            />
            {LOUVERS.map((x) => (
              <rect
                key={x}
                x={x}
                y={TOWER.belfryTop}
                width="2.2"
                height={TOWER.belfryBottom - TOWER.belfryTop}
                fill="#ffffff"
                fillOpacity="0.38"
              />
            ))}
            <rect
              x="58"
              y={TOWER.belfryTop}
              width="18"
              height="128"
              fill="#ffffff"
              fillOpacity="0.94"
            />
            <rect
              x="58"
              y={TOWER.belfryTop}
              width="18"
              height="128"
              fill="url(#ucr-pier-grad)"
            />
            <rect
              x="144"
              y={TOWER.belfryTop}
              width="18"
              height="128"
              fill="#ffffff"
              fillOpacity="0.94"
            />
            <rect
              x="144"
              y={TOWER.belfryTop}
              width="18"
              height="128"
              fill="url(#ucr-pier-grad)"
            />
            <rect
              x="106"
              y={TOWER.belfryTop}
              width="8"
              height="128"
              fill="#ffffff"
              fillOpacity="0.9"
            />
            <rect
              x="106"
              y={TOWER.belfryTop}
              width="8"
              height="128"
              fill="url(#ucr-pier-grad)"
            />
          </g>

          {/* Tower Cap and Cornices */}
          <rect
            x="50"
            y={TOWER.capTop}
            width="120"
            height="18"
            fill="#ffffff"
            fillOpacity="0.98"
          />
          <rect
            x="50"
            y={TOWER.capTop}
            width="120"
            height="18"
            fill="url(#ucr-pier-grad)"
          />
          <rect
            x="54"
            y={TOWER.capBottom}
            width="112"
            height="8"
            fill="#0f1115"
            fillOpacity="0.18"
          />
          <rect
            x="52"
            y={TOWER.belfryBottom}
            width="116"
            height="14"
            fill="#ffffff"
            fillOpacity="0.98"
          />
          <rect
            x="52"
            y={TOWER.belfryBottom}
            width="116"
            height="14"
            fill="url(#ucr-pier-grad)"
          />

          {/* Working Carillon Clock Face */}
          <g>
            <rect
              x={TOWER.clock.x}
              y={TOWER.clock.y}
              width={TOWER.clock.w}
              height={TOWER.clock.h}
              fill="#ffffff"
              fillOpacity="0.98"
              stroke="#0f1115"
              strokeOpacity="0.36"
              strokeWidth="1.2"
            />
            <circle
              cx={TOWER.clock.cx}
              cy={TOWER.clock.cy}
              r={TOWER.clock.r}
              fill="none"
              stroke="#0f1115"
              strokeOpacity="0.46"
              strokeWidth="1.2"
            />
            {[0, 90, 180, 270].map((deg) => (
              <line
                key={deg}
                x1={TOWER.clock.cx}
                y1={TOWER.clock.cy - TOWER.clock.r + 3}
                x2={TOWER.clock.cx}
                y2={TOWER.clock.cy - TOWER.clock.r + 8}
                stroke="#0f1115"
                strokeOpacity="0.46"
                strokeWidth="1.8"
                transform={`rotate(${deg} ${TOWER.clock.cx} ${TOWER.clock.cy})`}
              />
            ))}
            <line
              x1={TOWER.clock.cx}
              y1={TOWER.clock.cy}
              x2={TOWER.clock.cx}
              y2={TOWER.clock.cy - 13}
              stroke="#0f1115"
              strokeOpacity="0.85"
              strokeWidth="2.6"
              strokeLinecap="round"
              transform={`rotate(${clock.hour} ${TOWER.clock.cx} ${TOWER.clock.cy})`}
            />
            <line
              x1={TOWER.clock.cx}
              y1={TOWER.clock.cy}
              x2={TOWER.clock.cx}
              y2={TOWER.clock.cy - 18}
              stroke="#0f1115"
              strokeOpacity="0.7"
              strokeWidth="1.8"
              strokeLinecap="round"
              transform={`rotate(${clock.minute} ${TOWER.clock.cx} ${TOWER.clock.cy})`}
            />
          </g>

          {/* Outlines */}
          <g fill="none" stroke="#0f1115" strokeOpacity="0.42" strokeWidth="1.2">
            <rect x="50" y={TOWER.capTop} width="120" height="18" />
            <rect x="52" y={TOWER.belfryBottom} width="116" height="14" />
            <path
              d={`M58 ${TOWER.capBottom} L58 ${TOWER.base} M162 ${TOWER.capBottom} L162 ${TOWER.base}`}
            />
            <path
              d={`M76 ${TOWER.belfryTop} L76 ${TOWER.base} M144 ${TOWER.belfryTop} L144 ${TOWER.base}
                  M106 ${TOWER.belfryTop} L106 ${TOWER.base} M114 ${TOWER.belfryTop} L114 ${TOWER.base}`}
              strokeOpacity="0.24"
            />
          </g>
        </g>

        {/* Foreground crest wrapping the tower base */}
        <path
          d="M 1030 380 C 1060 295, 1120 262, 1210 262 C 1300 262, 1370 290, 1440 326 L 1440 380 Z"
          fill="#0b1329"
          fillOpacity="0.95"
        />
      </svg>
    </div>
  );
}
