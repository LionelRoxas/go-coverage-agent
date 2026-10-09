// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import HowItWorksPage from "./page";

describe("HowItWorksPage", () => {
  it("lists the five steps in order", () => {
    render(<HowItWorksPage />);
    const items = screen.getAllByRole("heading", { level: 3 }).map((h) => h.textContent);
    expect(items).toEqual(["Copy & measure", "Plan (no AI)", "Write (Groq)", "Validate (5 gates)", "Keep or roll back"]);
  });

  it("shows the repeat connector from step 5 back to step 2", () => {
    render(<HowItWorksPage />);
    expect(screen.getByTestId("repeat-connector")).toHaveTextContent("repeat until the target or a stop rule");
    expect(screen.getByTestId("repeat-connector-narrow")).toHaveTextContent("Back to Plan (step 2)");
    expect(screen.getByText(/repeats from step 2/)).toBeInTheDocument();
  });

  it("shows stop conditions, the measured result and the links", () => {
    render(<HowItWorksPage />);
    for (const t of ["Target reached", "Gains become marginal", "Iteration limit (20 by default)", "Token budget used", "No remaining targets"]) {
      expect(screen.getByText(t)).toBeInTheDocument();
    }
    expect(screen.getByText("0% → 80.75%")).toBeInTheDocument();
    expect(screen.getByText("12")).toBeInTheDocument();
    expect(screen.getByText("about 4 min")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Start a run/ })).toHaveAttribute("href", "/");
    const w = screen.getByRole("link", { name: "Full walkthrough" });
    expect(w).toHaveAttribute("href", "https://claude.ai/artifact/RxXGC2s7651iEFZDF3kYQ8");
    expect(w).toHaveAttribute("rel", expect.stringContaining("noopener"));
  });
});
