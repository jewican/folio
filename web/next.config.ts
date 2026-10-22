import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Use the compiler API: CLI output capture fails in restricted build environments.
  experimental: {
    useTypeScriptCli: false,
    // Branch switches can restore stale CSS from the custom Tailwind loader.
    // Recompile development assets on startup instead of restoring that cache.
    turbopackFileSystemCacheForDev: false,
  },
  cacheComponents: true,
  partialPrefetching: true,
  // Use the same Tailwind loader for the Webpack build fallback. This avoids
  // Turbopack's CSS worker port requirement in restricted environments.
  webpack(config) {
    config.module.rules.push({
      test: /globals\.css$/,
      enforce: "pre",
      use: ["@tailwindcss/turbopack"],
    });
    return config;
  },
  // Tailwind CSS v4 runs as a loader, so no PostCSS config is needed.
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
