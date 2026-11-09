import type { NextConfig } from "next";

const backend = process.env.BACKEND_URL ?? "http://127.0.0.1:8100";

const config: NextConfig = {
  // Only the Docker image needs the standalone bundle; `next start` and Vercel do not.
  output: process.env.STANDALONE ? "standalone" : undefined,
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
  },
};

export default config;
