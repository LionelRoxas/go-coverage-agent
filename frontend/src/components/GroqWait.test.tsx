// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { GroqWait, waitManyLabel } from "./GroqWait";

describe("GroqWait", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(1_000_008_000)); // 1 000 008 s
  });
  afterEach(() => vi.useRealTimers());

  const writer = (since: number) => ({ since, role: "writer", effort: "medium" });

  it("shows one request with its role and effort", () => {
    render(<GroqWait pending={writer(1_000_000)} detailed />);
    expect(screen.getByText(/Waiting for Groq · writer/, { selector: "[aria-hidden]" })).toHaveTextContent("Waiting for Groq · writer · medium reasoning · 8s");
  });

  it("counts several requests at once, timed from the oldest", () => {
    render(<GroqWait pending={writer(1_000_000)} others={[writer(1_000_001), writer(1_000_002)]} detailed />);
    expect(screen.getByText(/requests/, { selector: "[aria-hidden]" }))
      .toHaveTextContent("Waiting for Groq · 3 requests · writer · medium · 8s");
    expect(screen.getByText(/requests/, { selector: ".sr-only" })).toHaveTextContent("Waiting for Groq · 3 requests · writer · medium");
  });

  it("names the role and effort only when every request shares them", () => {
    expect(waitManyLabel([writer(0), { since: 1, role: "fixer", effort: "high" }], 8)).toBe("Waiting for Groq · 2 requests · 8s");
  });
});
