// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
/** Walkthrough sections in page order. `run`: once per run, `round`: repeated each round, `ref`: reference after the run. */
export type WalkthroughSection = { id: string; title: string; part: "run" | "round" | "ref" };

export const SECTIONS = [
  { id: "start", title: "Start a run", part: "run" },
  { id: "prepare", title: "Prepare a safe copy", part: "run" },
  { id: "measure", title: "Measure the starting point", part: "run" },
  { id: "plan", title: "Plan", part: "round" },
  { id: "write", title: "Write", part: "round" },
  { id: "validate", title: "Validate", part: "round" },
  { id: "keep", title: "Keep, repair or undo", part: "round" },
  { id: "stop", title: "Stop", part: "run" },
  { id: "results", title: "Results and outputs", part: "ref" },
  { id: "coverage", title: "How the number is computed", part: "ref" },
  { id: "safety", title: "Safety and limits", part: "ref" },
  { id: "glossary", title: "Glossary", part: "ref" },
] as const satisfies readonly WalkthroughSection[];

export type SectionId = (typeof SECTIONS)[number]["id"];

export const walkthroughHref = (id: SectionId) => `/walkthrough#${id}`;
