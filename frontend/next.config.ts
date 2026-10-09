// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
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
