// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
import path from "node:path";
import { defineConfig } from "vitest/config";

export default defineConfig({
  // Lib tests run in node; component tests (*.test.tsx) opt into jsdom via a per-file docblock.
  test: { environment: "node", include: ["src/**/*.test.{ts,tsx}"], setupFiles: ["./vitest.setup.ts"] },
  resolve: { alias: { "@": path.resolve(import.meta.dirname, "src") } },
});
