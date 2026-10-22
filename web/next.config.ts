import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Use the compiler API: CLI output capture fails in restricted build environments.
  experimental: { useTypeScriptCli: false },
  cacheComponents: true,
  partialPrefetching: true,
};

export default nextConfig;
