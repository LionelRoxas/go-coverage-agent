// AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  // Scaffold wires Tailwind v4 into Turbopack through this loader rule (no postcss config); keep it.
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
