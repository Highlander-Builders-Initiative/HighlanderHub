/* Campus skyline — the hero's sense of place.
 *
 * The Bell Tower (the 1966 carillon) is UCR's one unmistakable landmark, so it
 * carries the hero the way Sather Gate carries Berkeley's. It stands on the
 * horizon line that doubles as the hairline above the flyer wall: campus ground
 * level, with the bulletin pinned up just beneath it.
 *
 * Drawn as an engraving rather than a flat vector illustration, because the rest
 * of the system reads as an edited campus paper (see DESIGN.md, "The Quad"). The
 * tower is line work plus its real signature texture, the pierced concrete
 * screen, rendered as an SVG pattern. Behind it, the Box Springs ridge with the
 * Big C cut into the hillside, and a Riverside grove at its feet.
 *
 * Pure SVG + CSS, no client JS and no SVG filters: filters re-render on the CPU
 * every frame and were already caught stealing budget from the marquee. Nothing
 * here animates, so the scrolling wall below stays the only thing in motion.
 */

type ClockHands = { hour: number; minute: number };

/* ---------- Tower geometry (viewBox 220 x 700, base sits on y=700) ---------- */

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

/** Vertical slats across the open bell chamber. */
const LOUVERS = Array.from({ length: 11 }, (_, i) => 76 + i * 6.6);

/* ---------- Landscape (viewBox 1440 x 220, ground sits on y=220) ---------- */

/**
 * The far grove, as overlapping circles rather than individual trees. Same
 * fill and no strokes, so the overlaps vanish and the whole run reads as one
 * lumpy canopy line: a grove, not a row of lollipops. Hardcoded rather than
 * randomized so server and client render the same tree.
 */
const GROVE: [number, number, number][] = [
  [-50, 210.2, 16.5], [-32.5, 211.5, 26.9], [-12.2, 213.5, 22.9],
  [6.1, 212.4, 29.2], [30.3, 207.6, 11.2], [47.7, 210.2, 13.6],
  [67.1, 212.6, 27.4], [88.9, 212.6, 26.2], [114, 207.5, 28.4],
  [134.1, 207.5, 30.6], [153.5, 208.2, 20.5], [178.4, 202.7, 11],
  [192.7, 199.6, 12.9], [212.3, 205, 15.5], [233.4, 209.8, 16.5],
  [245, 214.1, 20.3], [271.3, 212.3, 15.2], [293.2, 210.9, 11.1],
  [306.3, 209.6, 26.1], [335.5, 205.5, 9.9], [348.4, 205.7, 15.3],
  [369.3, 216.5, 24.5], [397, 210.5, 14.2], [417.2, 206, 10.1],
  [436.7, 207, 12.9], [454.6, 215.6, 27.3], [475.6, 209.3, 8.7],
  [489.2, 210.2, 12.2], [500.2, 208.6, 30.2], [528.6, 208.4, 28.9],
  [552, 212.7, 21.1], [575.8, 207.3, 12.9], [590, 214, 8.8],
  [606.5, 204.5, 14.1], [621, 214, 23.9], [643.1, 212.6, 25.5],
  [666.9, 198.9, 10.3], [680.3, 209.9, 31.1], [699.6, 210.7, 21.6],
  [722.9, 206.7, 10.3], [744.7, 207.2, 8.4], [759.7, 207.9, 30.9],
  [786.5, 210.8, 28.8], [805.5, 212.2, 13.9], [826.5, 215.4, 20.2],
  [846.2, 214.1, 12.2], [865.7, 211.1, 13.4], [878.1, 214.3, 31.1],
  [901.2, 218.4, 28.1], [929.6, 220.8, 24.7], [956.5, 225.8, 10.8],
  [978.3, 223.8, 24.9], [1006.3, 224.1, 25.1], [1033.4, 212.4, 9.9],
  [1047.8, 223.5, 30.7], [1070.8, 224.4, 24.1], [1094.2, 223.4, 30.7],
  [1123.8, 219, 13.6], [1144.9, 212.1, 13.9], [1165.1, 217.6, 25],
  [1183.5, 223.2, 32.7], [1210, 214.6, 10.5], [1221.7, 211.9, 12.6],
  [1233.5, 221, 21.9], [1255.2, 216.5, 14.8], [1268.4, 216.7, 32.7],
  [1289.8, 220.9, 27.1], [1311.3, 217.3, 8.2], [1332.2, 221.6, 29],
  [1358.2, 221.5, 32], [1377.6, 213, 8.7], [1396.5, 210.6, 13.7],
  [1413.8, 213, 13.8], [1432.9, 212.4, 8.6], [1446.3, 214.2, 28.6],
  [1476, 220.1, 30.5],
];

/** Nearer specimen trees that break the canopy line. */
const FOREGROUND: { x: number; s: number; crown: number }[] = [
  { x: 128, s: 0.78, crown: 0 },
  { x: 366, s: 0.62, crown: 1 },
  { x: 560, s: 0.86, crown: 2 },
  { x: 848, s: 0.68, crown: 1 },
  { x: 1154, s: 0.8, crown: 0 },
  { x: 1392, s: 0.66, crown: 2 },
];

/** The palm rows along the campus walks, and half of Riverside besides. */
const PALMS: { x: number; s: number; lean: number }[] = [
  { x: 274, s: 0.95, lean: -3 },
  { x: 754, s: 1.05, lean: 2.5 },
];

export function CampusSkyline({ clock }: { clock: ClockHands }) {
  return (
    <div
      aria-hidden
      className="skyline-root pointer-events-none absolute inset-x-0 bottom-0"
    >
      {/* Late Riverside sun sitting low behind the tower. A CSS radial rather
          than an SVG gradient so it scales smoothly past either viewBox, and
          so nothing clips it into a visible rectangle. */}
      <div className="skyline-sun" />

      {/* Ridge and grove. Anchored bottom so the horizon lands exactly on the
          hairline no matter how wide the viewport gets. */}
      <svg
        viewBox="0 0 1440 220"
        preserveAspectRatio="xMidYMax slice"
        className="absolute inset-x-0 bottom-0 h-full w-full"
      >
        {/* Box Springs, the range the campus sits under. */}
        <path
          d="M-20 190 C 110 174, 196 150, 300 124 C 382 102, 444 84, 524 92
             C 602 100, 664 130, 744 142 C 824 154, 902 132, 992 140
             C 1092 150, 1182 176, 1282 184 C 1360 190, 1420 193, 1460 196
             L1460 232 L-20 232 Z"
          fill="#2a3680"
          fillOpacity="0.08"
        />
        <path
          d="M-20 190 C 110 174, 196 150, 300 124 C 382 102, 444 84, 524 92
             C 602 100, 664 130, 744 142 C 824 154, 902 132, 992 140
             C 1092 150, 1182 176, 1282 184 C 1360 190, 1420 193, 1460 196"
          fill="none"
          stroke="#2a3680"
          strokeOpacity="0.3"
          strokeWidth="1.25"
        />

        {/* The Big C, whitewashed into the hillside above campus. */}
        <path
          d="M 604 112 A 19 19 0 1 0 604 148"
          fill="none"
          stroke="#c98429"
          strokeOpacity="0.7"
          strokeWidth="5.5"
          strokeLinecap="butt"
        />

        {/* Nearer, softer fold of the range. */}
        <path
          d="M-20 214 C 140 200, 262 189, 384 185 C 522 181, 642 195, 772 199
             C 902 203, 1022 191, 1142 189 C 1262 187, 1382 197, 1460 206
             L1460 232 L-20 232 Z"
          fill="#2a3680"
          fillOpacity="0.1"
        />

        {/* The grove: one mass, so the tree line never reads as clip art. */}
        <g fill="#0f1115" fillOpacity="0.085">
          {GROVE.map(([cx, cy, r]) => (
            <circle key={`${cx}-${cy}`} cx={cx} cy={cy} r={r} />
          ))}
          <rect x="-40" y="214" width="1520" height="22" />
        </g>

        {PALMS.map((palm) => (
          <Palm key={palm.x} {...palm} />
        ))}
        {FOREGROUND.map((tree) => (
          <Specimen key={tree.x} {...tree} />
        ))}
      </svg>

      {/* The tower itself: its own layer so its scale is set in CSS and stays
          honest against the copy, instead of riding the band's slice scale. It
          overflows this root upward and is clipped by the hero section. */}
      <svg
        viewBox="0 0 220 700"
        preserveAspectRatio="xMidYMax meet"
        className="skyline-tower absolute bottom-0 right-[3%] h-[clamp(196px,34vw,500px)] w-auto sm:right-[6%] lg:right-[9%]"
      >
        <defs>
          {/* The pierced concrete screen: the tower's real signature. */}
          <pattern
            id="bt-screen"
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
              fillOpacity="0.36"
            />
          </pattern>
          {/* Faintest warm tint on the concrete piers, sun-side to shade-side. */}
          <linearGradient id="bt-pier" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="#c98429" stopOpacity="0.18" />
            <stop offset="55%" stopColor="#c98429" stopOpacity="0.06" />
            <stop offset="100%" stopColor="#2a3680" stopOpacity="0.12" />
          </linearGradient>
        </defs>

        {/* Solid concrete body behind everything, so the tower reads as an
            object standing against the sun rather than an outline over it. */}
        <rect
          x={TOWER.left}
          y={TOWER.capTop}
          width={TOWER.right - TOWER.left}
          height={TOWER.base - TOWER.capTop}
          fill="#ffffff"
          fillOpacity="0.94"
        />

        {/* --- Shaft: pier / screen / centre rib / screen / pier --- */}
        <g>
          <rect x="76" y={TOWER.corniceBottom} width="30" height="516" fill="url(#bt-screen)" />
          <rect x="114" y={TOWER.corniceBottom} width="30" height="516" fill="url(#bt-screen)" />
          <rect x="58" y={TOWER.corniceBottom} width="18" height="516" fill="url(#bt-pier)" />
          <rect x="106" y={TOWER.corniceBottom} width="8" height="516" fill="url(#bt-pier)" />
          <rect x="144" y={TOWER.corniceBottom} width="18" height="516" fill="url(#bt-pier)" />
        </g>

        {/* --- Bell chamber: open louvers, the darkest note in the drawing --- */}
        <g>
          <rect
            x="76"
            y={TOWER.belfryTop}
            width="68"
            height={TOWER.belfryBottom - TOWER.belfryTop}
            fill="#1b2033"
            fillOpacity="0.74"
          />
          {LOUVERS.map((x) => (
            <rect
              key={x}
              x={x}
              y={TOWER.belfryTop}
              width="1.9"
              height={TOWER.belfryBottom - TOWER.belfryTop}
              fill="#ffffff"
              fillOpacity="0.34"
            />
          ))}
          {/* Corner piers and the centre rib run straight through the chamber. */}
          <rect x="58" y={TOWER.belfryTop} width="18" height="128" fill="#ffffff" fillOpacity="0.94" />
          <rect x="58" y={TOWER.belfryTop} width="18" height="128" fill="url(#bt-pier)" />
          <rect x="144" y={TOWER.belfryTop} width="18" height="128" fill="#ffffff" fillOpacity="0.94" />
          <rect x="144" y={TOWER.belfryTop} width="18" height="128" fill="url(#bt-pier)" />
          <rect x="106" y={TOWER.belfryTop} width="8" height="128" fill="#ffffff" fillOpacity="0.88" />
          <rect x="106" y={TOWER.belfryTop} width="8" height="128" fill="url(#bt-pier)" />
        </g>

        {/* --- Cap and cornice --- */}
        <rect x="50" y={TOWER.capTop} width="120" height="18" fill="#ffffff" fillOpacity="0.96" />
        <rect x="50" y={TOWER.capTop} width="120" height="18" fill="url(#bt-pier)" />
        <rect x="54" y={TOWER.capBottom} width="112" height="8" fill="#0f1115" fillOpacity="0.17" />
        <rect x="52" y={TOWER.belfryBottom} width="116" height="14" fill="#ffffff" fillOpacity="0.96" />
        <rect x="52" y={TOWER.belfryBottom} width="116" height="14" fill="url(#bt-pier)" />

        {/* --- Clock face, keeping campus time --- */}
        <g>
          <rect
            x={TOWER.clock.x}
            y={TOWER.clock.y}
            width={TOWER.clock.w}
            height={TOWER.clock.h}
            fill="#ffffff"
            fillOpacity="0.98"
          />
          <rect
            x={TOWER.clock.x}
            y={TOWER.clock.y}
            width={TOWER.clock.w}
            height={TOWER.clock.h}
            fill="none"
            stroke="#0f1115"
            strokeOpacity="0.34"
            strokeWidth="1.2"
          />
          <circle
            cx={TOWER.clock.cx}
            cy={TOWER.clock.cy}
            r={TOWER.clock.r}
            fill="none"
            stroke="#0f1115"
            strokeOpacity="0.42"
            strokeWidth="1.2"
          />
          {/* Ticks at the quarters only: twelve would silt up at this size. */}
          {[0, 90, 180, 270].map((deg) => (
            <line
              key={deg}
              x1={TOWER.clock.cx}
              y1={TOWER.clock.cy - TOWER.clock.r + 3}
              x2={TOWER.clock.cx}
              y2={TOWER.clock.cy - TOWER.clock.r + 8}
              stroke="#0f1115"
              strokeOpacity="0.42"
              strokeWidth="1.6"
              transform={`rotate(${deg} ${TOWER.clock.cx} ${TOWER.clock.cy})`}
            />
          ))}
          <line
            x1={TOWER.clock.cx}
            y1={TOWER.clock.cy}
            x2={TOWER.clock.cx}
            y2={TOWER.clock.cy - 13}
            stroke="#0f1115"
            strokeOpacity="0.8"
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
            strokeOpacity="0.64"
            strokeWidth="1.7"
            strokeLinecap="round"
            transform={`rotate(${clock.minute} ${TOWER.clock.cx} ${TOWER.clock.cy})`}
          />
        </g>

        {/* --- Outline last, so every edge stays crisp over the fills --- */}
        <g fill="none" stroke="#0f1115" strokeOpacity="0.42" strokeWidth="1.2">
          <rect x="50" y={TOWER.capTop} width="120" height="18" />
          <rect x="52" y={TOWER.belfryBottom} width="116" height="14" />
          <path d={`M58 ${TOWER.capBottom} L58 ${TOWER.base} M162 ${TOWER.capBottom} L162 ${TOWER.base}`} />
          <path
            d={`M76 ${TOWER.belfryTop} L76 ${TOWER.base} M144 ${TOWER.belfryTop} L144 ${TOWER.base}
                M106 ${TOWER.belfryTop} L106 ${TOWER.base} M114 ${TOWER.belfryTop} L114 ${TOWER.base}`}
            strokeOpacity="0.24"
          />
        </g>
      </svg>
    </div>
  );
}

/* ---------- Grove pieces (drawn from a base at the origin) ---------- */

function Specimen({ x, s, crown }: { x: number; s: number; crown: number }) {
  // Three crowns on rotation, so no two neighbours are the same tree twice.
  const crowns = [
    [
      [0, -58, 27], [-21, -43, 18], [20, -46, 19],
      [-10, -73, 16], [14, -69, 15],
    ],
    [
      [-4, -52, 23], [17, -44, 20], [-22, -47, 17],
      [6, -70, 18], [-14, -65, 13],
    ],
    [
      [2, -64, 25], [-19, -50, 20], [22, -52, 17],
      [-6, -80, 14], [12, -78, 12], [0, -40, 22],
    ],
  ][crown % 3];

  return (
    <g transform={`translate(${x} 224) scale(${s})`}>
      <path d="M-3.2 0 L-2 -38 L2 -38 L3.2 0 Z" fill="#0f1115" fillOpacity="0.24" />
      <g fill="#0f1115" fillOpacity="0.15">
        {crowns.map(([cx, cy, r]) => (
          <circle key={`${cx}-${cy}`} cx={cx} cy={cy} r={r} />
        ))}
      </g>
    </g>
  );
}

function Palm({ x, s, lean }: { x: number; s: number; lean: number }) {
  /* A palm crown is mirrored, not radial: three drooping blades per side plus
     one short lifted frond. Drawn evenly spaced around a circle it reads as a
     pinwheel, which is the tell of every stock vector palm. */
  const side = [-34, -2, 30];
  const blade =
    "M0 0 C -14 -9, -31 -10, -46 1 C -37 3, -31 7, -21 7 C -12 7, -5 4, 0 0 Z";

  return (
    <g transform={`translate(${x} 224) scale(${s}) rotate(${lean})`}>
      <path
        d="M-3.4 0 Q 1.6 -46 -2 -92 L4 -92 Q 7.6 -46 3.6 0 Z"
        fill="#0f1115"
        fillOpacity="0.22"
      />
      <g fill="#0f1115" fillOpacity="0.16" transform="translate(0 -92)">
        {side.map((deg) => (
          <path key={`l${deg}`} d={blade} transform={`rotate(${deg})`} />
        ))}
        {side.map((deg) => (
          <path
            key={`r${deg}`}
            d={blade}
            transform={`scale(-1 1) rotate(${deg})`}
          />
        ))}
        {/* One short frond standing up out of the centre of the crown. */}
        <path d={blade} transform="rotate(-68) scale(0.62)" />
        <path d={blade} transform="scale(-1 1) rotate(-74) scale(0.58)" />
        <circle cx="0" cy="0" r="4.2" />
      </g>
    </g>
  );
}
