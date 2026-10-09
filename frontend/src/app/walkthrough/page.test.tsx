// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
// @vitest-environment jsdom
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import WalkthroughPage, { metadata } from "./page";
import { SECTIONS } from "./sections";

describe("WalkthroughPage", () => {
  it("is titled Walkthrough and has one h1", () => {
    render(<WalkthroughPage />);
    expect(metadata.title).toBe("Walkthrough");
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
  });

  it("has a table of contents whose links match the section ids, in page order", () => {
    const { container } = render(<WalkthroughPage />);
    const toc = screen.getByRole("navigation", { name: "On this page" });
    const hrefs = within(toc).getAllByRole("link").map((a) => a.getAttribute("href"));
    expect(hrefs).toEqual(SECTIONS.map((s) => `#${s.id}`));
    const ids = Array.from(container.querySelectorAll("section[id]")).map((s) => s.id);
    expect(ids).toEqual(SECTIONS.map((s) => s.id));
    for (const s of SECTIONS) {
      const section = container.querySelector(`section[id="${s.id}"]`)!;
      expect(within(section as HTMLElement).getByRole("heading", { level: 2 })).toHaveTextContent(s.title);
      expect(within(toc).getByRole("link", { name: s.title })).toHaveAttribute("href", `#${s.id}`);
    }
  });

  it("groups the four round sections under Each round in the table of contents", () => {
    render(<WalkthroughPage />);
    const round = screen.getByRole("group", { name: "Each round" });
    expect(within(round).getAllByRole("link").map((a) => a.textContent)).toEqual(["Plan", "Write", "Validate", "Keep, repair or undo"]);
  });

  it("shows the validation gates in order", () => {
    render(<WalkthroughPage />);
    const gates = within(screen.getByTestId("gate-chain")).getAllByRole("listitem").map((li) => li.getAttribute("data-gate"));
    expect(gates).toEqual(["imports", "guard", "merge", "compile", "vet", "test", "coverage"]);
  });

  const section = (id: string) => document.querySelector(`section[id="${id}"]`) as HTMLElement;

  it("states the current planner, model and prompt limits", () => {
    render(<WalkthroughPage />);
    const plan = section("plan");
    expect(plan).toHaveTextContent("up to 3 targets");
    expect(plan).toHaveTextContent("at most 5 functions");
    expect(plan).toHaveTextContent("100 uncovered statements");
    expect(plan).toHaveTextContent("failed twice");
    const write = section("write");
    expect(write).toHaveTextContent("openai/gpt-oss-120b");
    expect(write).toHaveTextContent("medium");
    expect(write).toHaveTextContent("65,536");
    expect(write).toHaveTextContent("MAX_PROMPT_TOKENS");
    expect(write).toHaveTextContent("12,000");
    expect(write).toHaveTextContent("240 s");
    expect(write).toHaveTextContent("the first half of the target’s functions is retried right away; the rest stay in the pool for a later round");
    expect(write).not.toHaveTextContent("each half");
  });

  it("states the validation, repair and stop rules", () => {
    render(<WalkthroughPage />);
    expect(section("validate")).toHaveTextContent("go test -count=2 -covermode=set -coverprofile");
    expect(section("validate")).toHaveTextContent("strict superset");
    const keep = section("keep");
    expect(keep).toHaveTextContent(/up to 2 attempts/i);
    expect(keep).toHaveTextContent("Example");
    expect(keep).toHaveTextContent("snapshot");
    expect(keep).toHaveTextContent("history");
    const stop = section("stop");
    for (const r of ["target_reached", "marginal_gains", "max_iterations", "no_remaining_targets", "budget_exhausted", "cancelled"]) {
      expect(stop).toHaveTextContent(r);
    }
    expect(stop).toHaveTextContent("20");
    expect(stop).toHaveTextContent("DAILY_TOKEN_BUDGET");
  });

  it("shows the outputs, an event example, the coverage profile line and the safety notes", () => {
    render(<WalkthroughPage />);
    const results = section("results");
    for (const t of ["./output/<job id>/", "events.jsonl", "report.json", "tests/", "candidate_accepted", "81.07%", "100.0%", "87.09%", "e2de1ca387cb", "0e1f8bf7442a", "80a576a4d3ad", "init()", "1.4%"]) {
      expect(results).toHaveTextContent(t);
    }
    const coverage = section("coverage");
    expect(coverage).toHaveTextContent("zz_coverage_seed_test.go");
    expect(coverage).toHaveTextContent(/mean\.go:\d+\.\d+,\d+\.\d+ \d+ [01]/);
    expect(coverage).toHaveTextContent("executed no previously uncovered statements");
    const safety = section("safety");
    expect(safety).toHaveTextContent("not a sandbox");
    expect(safety).toHaveTextContent("127.0.0.1");
    expect(safety).toHaveTextContent("allowlist");
  });

  it("links back to How it works and has no external artifact link", () => {
    const { container } = render(<WalkthroughPage />);
    expect(screen.getAllByRole("link", { name: /How it works/ })[0]).toHaveAttribute("href", "/how-it-works");
    expect(container.querySelector('a[href*="claude.ai"]')).toBeNull();
  });
});
