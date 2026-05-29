const isDev = process.env.NODE_ENV !== "production";

// Origins the browser legitimately talks to:
// - Supabase: direct flyer uploads + storage public URLs (qyxlojftdtjasxhzyqil)
// - Image CDNs mirror next.config images.remotePatterns
// - Vercel: analytics script + web-vitals beacon
const SUPABASE_ORIGIN = "https://qyxlojftdtjasxhzyqil.supabase.co";
const IMG_HOSTS = [
  "https://*.cdninstagram.com",
  "https://se-images.campuslabs.com",
  "https://localist-images.azureedge.net",
  SUPABASE_ORIGIN,
];

const csp = [
  `default-src 'self'`,
  `base-uri 'self'`,
  `object-src 'none'`,
  `frame-ancestors 'none'`,
  `form-action 'self'`,
  `font-src 'self'`,
  `style-src 'self' 'unsafe-inline'`,
  `img-src 'self' data: blob: ${IMG_HOSTS.join(" ")}`,
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
    remotePatterns: [
      {
        protocol: "https",
        hostname: "*.cdninstagram.com",
      },
      {
        protocol: "https",
        hostname: "se-images.campuslabs.com",
        pathname: "/clink/images/**",
      },
      {
        protocol: "https",
        hostname: "localist-images.azureedge.net",
      },
      {
        protocol: "https",
        hostname: "qyxlojftdtjasxhzyqil.supabase.co",
        pathname: "/storage/v1/object/public/submission-flyers/**",
      },
    ],
  },
};

module.exports = nextConfig;
