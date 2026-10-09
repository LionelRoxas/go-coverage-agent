// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
// @vitest-environment jsdom
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import HowItWorksPage from "./page";

const STEP_TITLES = [
  "Make a safe copy and measure",
  "Pick what to work on (no AI)",
  "Write the checks (AI)",
  "Try them out",
  "Keep, repair or undo",
];

describe("HowItWorksPage", () => {
  it("explains the tool and coverage in plain words", () => {
    render(<HowItWorksPage />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(/writes those checks for a project written in Go \(a programming language\) by itself/);
    expect(screen.getByRole("heading", { name: "What “coverage” means" })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "8 of 10 lines run by a test: 80% coverage" })).toBeInTheDocument();
  });

  it("lists the five plain steps in order, each with a collapsed Technical detail", () => {
    render(<HowItWorksPage />);
    const steps = screen.getAllByRole("listitem").filter((li) => li.hasAttribute("data-step"));
    expect(steps.map((li) => within(li).getByRole("heading", { level: 3 }).textContent)).toEqual(STEP_TITLES);
    for (const li of steps) {
      const details = li.querySelector("details");
      expect(details).not.toBeNull();
      expect(details).not.toHaveAttribute("open");
      const title = within(li).getByRole("heading", { level: 3 }).textContent;
      expect(details!.querySelector("summary")).toHaveTextContent(`Technical detail: ${title}`);
    }
    // the precise version still names the real values
    expect(within(steps[1]).getByText(/up to 3 items per round/)).toBeInTheDocument();
    expect(within(steps[2]).getByText(/openai\/gpt-oss-120b/)).toBeInTheDocument();
    expect(within(steps[3]).getByText(/-count=2/)).toBeInTheDocument();
    expect(within(steps[4]).getByText(/history of every earlier attempt/)).toBeInTheDocument();
  });

  it("shows the repeat connector from step 5 back to step 2", () => {
    render(<HowItWorksPage />);
    expect(screen.getByTestId("repeat-connector")).toHaveTextContent("Back to step 2: repeat until the goal or a stop rule");
    expect(screen.getByText(/starts again from step 2/)).toBeInTheDocument();
  });

  it("shows the stop rules, the trust notes, the measured results and the links", () => {
    render(<HowItWorksPage />);
    for (const t of ["It reached the goal", "The last rounds added very little", "It ran out of rounds (20 by default)",
                     "It used up its AI budget", "Nothing is left that it can work on"]) {
      expect(screen.getByText(t)).toBeInTheDocument();
    }
    expect(screen.getByText(/re-run in a fresh copy of the project/)).toBeInTheDocument();
    const stats = screen.getByTestId("result-stats");
    expect(stats).toHaveTextContent("0% → 80.75%");
    expect(stats).toHaveTextContent("12 rounds");
    expect(stats).toHaveTextContent("about 4 minutes");
    const semver = screen.getByTestId("result-semver");
    expect(semver).toHaveTextContent("1.4% → 84.6%");
    expect(semver).toHaveTextContent("4 rounds");
    expect(semver).toHaveTextContent("about 2 minutes");
    expect(screen.getByRole("link", { name: /Start a run/ })).toHaveAttribute("href", "/");
    const w = screen.getByRole("link", { name: "Full walkthrough" });
    expect(w).toHaveAttribute("href", "https://claude.ai/artifact/RxXGC2s7651iEFZDF3kYQ8");
    expect(w).toHaveAttribute("rel", expect.stringContaining("noopener"));
  });
});
