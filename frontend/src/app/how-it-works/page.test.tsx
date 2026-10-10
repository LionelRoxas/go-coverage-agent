// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
// @vitest-environment jsdom
import { cleanup, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import WalkthroughPage from "../walkthrough/page";
import HowItWorksPage from "./page";

const STEP_TITLES = [
  "Make a safe copy and measure",
  "Pick what to work on (no AI)",
  "Write the checks (AI)",
  "Try them out",
  "Keep, repair or undo",
];

const steps = () => screen.getAllByRole("listitem").filter((li) => li.hasAttribute("data-step"));

describe("HowItWorksPage", () => {
  it("explains the tool and coverage in plain words", () => {
    render(<HowItWorksPage />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(/writes those checks for a project written in Go \(a programming language\) by itself/);
    expect(screen.getByRole("heading", { name: "What “coverage” means" })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "8 of 10 lines run by a test: 80% coverage" })).toBeInTheDocument();
  });

  it("lists the five plain steps in one ordered list, in order", () => {
    render(<HowItWorksPage />);
    const s = steps();
    expect(s.map((li) => within(li).getByRole("heading", { level: 3 }).textContent)).toEqual(STEP_TITLES);
    expect(s.every((li) => li.parentElement === s[0].parentElement)).toBe(true);
    expect(s[0].parentElement!.tagName).toBe("OL");
    expect(s.map((li) => li.getAttribute("data-step"))).toEqual(["1", "2", "3", "4", "5"]);
  });

  it("has no Technical detail disclosures, glossary or counting detail any more", () => {
    const { container } = render(<HowItWorksPage />);
    expect(container.querySelector("details")).toBeNull();
    expect(screen.queryByText(/Technical detail/)).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Words used on this page" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "How the number is counted" })).not.toBeInTheDocument();
    expect(screen.queryByText(/strict superset|-covermode|openai\/gpt-oss-120b/)).not.toBeInTheDocument();
  });

  it("gives each step one Read more link to an existing Walkthrough section", () => {
    render(<HowItWorksPage />);
    const hrefs = steps().map((li) => {
      const links = within(li).getAllByRole("link");
      expect(links).toHaveLength(1);
      expect(links[0]).toHaveTextContent(/^Read more/);
      expect(links[0]).toHaveAccessibleName(`Read more: ${within(li).getByRole("heading", { level: 3 }).textContent}`);
      return links[0].getAttribute("href")!;
    });
    expect(hrefs).toEqual(["/walkthrough#prepare", "/walkthrough#plan", "/walkthrough#write", "/walkthrough#validate", "/walkthrough#keep"]);
    cleanup();
    const { container } = render(<WalkthroughPage />);
    for (const h of hrefs) expect(container.querySelector(`section[id="${h.split("#")[1]}"]`)).not.toBeNull();
  });

  it("marks step 1 as once and steps 2 to 5 as the repeated round", () => {
    render(<HowItWorksPage />);
    const phases = screen.getByTestId("loop-phases");
    expect(phases).toHaveAttribute("aria-hidden");
    expect(phases).toHaveTextContent("Once at the start");
    expect(phases).toHaveTextContent("Each round");
    expect(screen.getByText(/Step 1 happens once, at the start\. After step 5 it starts again from step 2/)).toHaveClass("sr-only");
  });

  it("shows the repeat connector from step 5 back to step 2, wide and narrow, hidden from screen readers", () => {
    render(<HowItWorksPage />);
    const wide = screen.getByTestId("repeat-connector");
    expect(screen.getByTestId("loop-phases")).toContainElement(wide);
    expect(wide).toHaveAttribute("aria-hidden");
    expect(wide).toHaveTextContent(/^repeat until the goal or a stop rule$/);
    const narrow = screen.getByTestId("repeat-connector-narrow");
    expect(narrow).toHaveAttribute("aria-hidden");
    expect(narrow).toHaveTextContent("Back to step 2: repeat until the goal or a stop rule");
  });

  it("keeps the stop rules, a short trust list with the no-new-coverage sentence, and the measured results", () => {
    render(<HowItWorksPage />);
    for (const t of ["It reached the goal", "The last rounds added very little", "It ran out of rounds (20 by default)",
                     "It used up its AI budget", "Nothing is left that it can work on", "The AI service could not be reached"]) {
      expect(screen.getByText(t)).toBeInTheDocument();
    }
    expect(screen.getByText(/Each new batch of tests also has to run at least one piece of code that no earlier test ran/)).toBeInTheDocument();
    expect(screen.getByText(/never checks the result is not kept/)).toBeInTheDocument();
    expect(screen.getByText(/re-run in a fresh copy of the project/)).toBeInTheDocument();
    const stats = screen.getByTestId("result-stats");
    expect(stats).toHaveTextContent("goal 80%");
    expect(stats).toHaveTextContent("0% → 81.1%");
    expect(stats).toHaveTextContent("11 rounds, about 5 minutes");
    const stats100 = screen.getByTestId("result-stats-100");
    expect(stats100).toHaveTextContent("goal 100%");
    expect(stats100).toHaveTextContent("0% → 100%");
    expect(stats100).toHaveTextContent("22 rounds, about 10 minutes (round limit raised to 30)");
    const btree = screen.getByTestId("result-btree");
    expect(btree).toHaveTextContent("0% → 87.1%");
    expect(btree).toHaveTextContent("stopped when new rounds added very little");
    expect(screen.getByText(/each starts at 0%/)).toBeInTheDocument();
    expect(screen.queryByText(/at or near 0%/)).toBeNull();
    expect(screen.queryByText(/semver/i)).toBeNull();
  });

  it("explains in plain words how a new test is judged to add coverage", () => {
    render(<HowItWorksPage />);
    expect(screen.getByRole("heading", { name: "How it knows a new test adds coverage" })).toBeInTheDocument();
    expect(screen.getByText(/The AI never decides this/)).toBeInTheDocument();
    const compare = screen.getByTestId("coverage-compare");
    expect(compare).toHaveTextContent(/KeptEverything that ran before still runs, and at least one piece that no test ran before now runs/);
    expect(compare).toHaveTextContent(/Not keptThe new tests only ran pieces that were already checked/);
    expect(screen.getByText(/a gain in one place can never hide a loss in another/)).toBeInTheDocument();
  });

  it("explains prediction disagreements and possible bugs, and what each one points at", () => {
    render(<HowItWorksPage />);
    expect(screen.getByRole("heading", { name: "What the run flags for a person to check" })).toBeInTheDocument();
    const dis = screen.getByTestId("flag-disagreements");
    expect(within(dis).getByRole("heading", { name: "Prediction disagreements" })).toBeInTheDocument();
    expect(dis).toHaveTextContent(/Points atThe tests it wrote/);
    expect(dis).toHaveTextContent(/either the AI’s prediction or the code is wrong/);
    const bugs = screen.getByTestId("flag-bugs");
    expect(within(bugs).getByRole("heading", { name: "Possible bugs found" })).toBeInTheDocument();
    expect(bugs).toHaveTextContent(/Points atYour project’s code/);
    expect(bugs).toHaveTextContent(/removed automatically/);
    expect(screen.getByText(/Neither is a confirmed bug/)).toBeInTheDocument();
  });

  it("ends with Start a run and an internal link to the full walkthrough, and no external artifact link", () => {
    const { container } = render(<HowItWorksPage />);
    expect(screen.getByRole("link", { name: /Start a run/ })).toHaveAttribute("href", "/");
    expect(screen.getByRole("link", { name: /Read the full walkthrough/ })).toHaveAttribute("href", "/walkthrough");
    expect(container.querySelector('a[href*="claude.ai"]')).toBeNull();
    expect(container.querySelector('a[target="_blank"]')).toBeNull();
  });
});
