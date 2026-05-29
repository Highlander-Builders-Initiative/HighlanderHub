const isDev = process.env.NODE_ENV !== "production";

// Supabase origin drives connect-src (direct flyer uploads + storage reads) and
// the storage remotePattern. Derived from the same env the client uses so a
// staging/preview project can't make CSP lie while the client talks elsewhere.
const supabaseUrl = new URL(
  process.env.NEXT_PUBLIC_SUPABASE_URL ?? "https://qyxlojftdtjasxhzyqil.supabase.co"
);
const SUPABASE_ORIGIN = supabaseUrl.origin;

// next/image optimizer allowlist. Kept tight on purpose: the optimizer fetches
// these URLs server-side, so an open list is an SSRF/abuse vector. Flyer policy
// allows arbitrary HTTPS hosts to *render* (see CSP img-src below); arbitrary
// hosts are served via plain <img> client-side instead of through the optimizer.
const imageRemotePatterns = [
  { protocol: "https", hostname: "*.cdninstagram.com" },
  {
    protocol: "https",
    hostname: "se-images.campuslabs.com",
    pathname: "/clink/images/**",
  },
  { protocol: "https", hostname: "localist-images.azureedge.net" },
  {
    protocol: "https",
    hostname: supabaseUrl.hostname,
    pathname: "/storage/v1/object/public/submission-flyers/**",
  },
];

const csp = [
  `default-src 'self'`,
  `base-uri 'self'`,
  `object-src 'none'`,
  `frame-ancestors 'none'`,
  `form-action 'self'`,
  `font-src 'self'`,
  `style-src 'self' 'unsafe-inline'`,
  // Flyers come from arbitrary user-supplied hosts; allow any HTTPS image.
  // Referrer-Policy below limits the referer leak to cross-origin requests.
  `img-src 'self' data: blob: https:`,
  // Next's app runtime still emits inline bootstrap scripts here. A nonce-based
  // CSP would be a larger framework-wide change, so keep this tradeoff explicit.
  // 'unsafe-eval' is only needed by the dev/HMR runtime.
  `script-src 'self' 'unsafe-inline' https://va.vercel-scripts.com${
    isDev ? " 'unsafe-eval'" : ""
  }`,
  `connect-src 'self' ${SUPABASE_ORIGIN} https://vitals.vercel-insights.com${
    isDev ? " ws:" : ""
  }`,
  // Don't force https upgrades on http://localhost during development.
  ...(isDev ? [] : ["upgrade-insecure-requests"]),
].join("; ");

const securityHeaders = [
  {
    key: "Content-Security-Policy",
    value: csp,
  },
  ...(isDev
    ? []
    : [
        {
          key: "Strict-Transport-Security",
          value: "max-age=63072000; includeSubDomains; preload",
        },
      ]),
  {
    key: "X-Content-Type-Options",
    value: "nosniff",
  },
  {
    key: "Referrer-Policy",
    value: "strict-origin-when-cross-origin",
  },
  {
    key: "Permissions-Policy",
    value: "camera=(), microphone=(), geolocation=(), interest-cohort=()",
  },
];

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async headers() {
    return [
      {
        source: "/:path*",
        headers: securityHeaders,
      },
    ];
  },
  images: {
    remotePatterns: imageRemotePatterns,
  },
};

module.exports = nextConfig;
