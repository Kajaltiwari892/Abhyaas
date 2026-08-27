import type { NextConfig } from "next";

const backendApiOrigin = process.env.BACKEND_API_ORIGIN?.replace(/\/$/, "");

const nextConfig: NextConfig = {
  async rewrites() {
    if (!backendApiOrigin) {
      return [];
    }

    return [
      {
        source: "/backend-api/:path*",
        destination: `${backendApiOrigin}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
