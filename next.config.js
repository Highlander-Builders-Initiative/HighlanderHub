/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
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
    ],
  },
};

module.exports = nextConfig;
