import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  outputFileTracingRoot: __dirname,
  output: process.env.STATIC_EXPORT === "1" ? "export" : undefined,
  reactStrictMode: true,
};

export default nextConfig;
