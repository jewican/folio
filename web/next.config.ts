import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Use the compiler API: CLI output capture fails in restricted build environments.
  experimental: { useTypeScriptCli: false },
  cacheComponents: true,
  partialPrefetching: true,
  // Tailwind CSS v4 runs as a Turbopack loader, so no PostCSS config is needed.
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
