const securityHeaders = [
  {
    key: "X-Frame-Options",
    value: "DENY",
  },
  {
    key: "X-Content-Type-Options",
    value: "nosniff",
  },
  {
    key: "Referrer-Policy",
    value: "strict-origin-when-cross-origin",
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
