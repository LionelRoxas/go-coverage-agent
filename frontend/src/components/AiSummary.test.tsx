// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
// @vitest-environment jsdom
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api, ApiError } from "@/lib/api";
import { toMarkdown } from "@/lib/aiSummary";
import { statsSummary } from "@/lib/fixtures/aiSummary";
import type { AiSummaryView } from "@/lib/runState";
import { AiSummary } from "./AiSummary";

vi.mock("@/lib/api", async (orig) => {
  const real = await orig<typeof import("@/lib/api")>();
  return { ...real, api: { writeSummary: vi.fn(), cancel: vi.fn() } };
});

const done: AiSummaryView = { status: "done", result: statsSummary, generatedAt: 1791547520 };

function show(view: AiSummaryView, onRequested = vi.fn()) {
  render(<AiSummary view={view} jobId="e2de1ca387cb" repo="stats" model="openai/gpt-oss-120b" onRequested={onRequested} />);
  return onRequested;
}

function mockClipboard() {
  const spy = vi.fn(() => Promise.resolve());
  Object.defineProperty(navigator, "clipboard", { value: { writeText: spy }, configurable: true });
  return spy;
}

describe("AiSummary", () => {
  beforeEach(() => vi.clearAllMocks());

  it("shows the stakeholder summary first, with the AI label and the cost", () => {
    show(done);
    expect(screen.getByRole("heading", { name: "Summary" })).toBeInTheDocument();
    expect(screen.getByText("AI-written from this run's measured data")).toBeInTheDocument();
    const tab = screen.getByRole("tab", { name: "For stakeholders" });
    expect(tab).toHaveAttribute("aria-selected", "true");
    const panel = screen.getByRole("tabpanel");
    expect(panel).toHaveAttribute("aria-labelledby", tab.id);
    expect(panel).toHaveTextContent(statsSummary.business.headline);
    expect(within(panel).getByText("Recommendation")).toBeInTheDocument();
    expect(within(panel).getAllByRole("listitem")).toHaveLength(2);
    expect(panel).toHaveTextContent("Run cost $0.07 · summary $0.0013 · total $0.07 (input $0.01, output $0.06)");
    expect(panel).toHaveAttribute("tabindex", "0");
  });

  it("switches to the engineering summary by click and by arrow key", async () => {
    const user = userEvent.setup();
    show(done);
    await user.click(screen.getByRole("tab", { name: "For engineering teams" }));
    const panel = screen.getByRole("tabpanel");
    expect(panel).toHaveTextContent(statsSummary.technical.headline);
    expect(within(panel).getByText("clip.go")).toBeInTheDocument();
    expect(within(panel).getByText("go test ./...").tagName).toBe("CODE");
    expect(panel).toHaveTextContent("None reported.");
    expect(panel).not.toHaveTextContent("Estimated cost");
    await user.keyboard("{ArrowLeft}");
    expect(screen.getByRole("tab", { name: "For stakeholders" })).toHaveFocus();
    expect(screen.getByRole("tabpanel")).toHaveTextContent(statsSummary.business.headline);
  });

  it("copies the same Markdown as SUMMARY.md", async () => {
    const user = userEvent.setup();
    show(done);
    const writeText = mockClipboard();
    await user.click(screen.getByRole("button", { name: "Copy as Markdown" }));
    expect(writeText).toHaveBeenCalledWith(
      toMarkdown(statsSummary, { repo: "stats", model: "openai/gpt-oss-120b", generatedAt: 1791547520 }));
    expect(await screen.findByRole("button", { name: "Copied" })).toBeInTheDocument();
  });

  it("says how many sentences the grounding check left out", () => {
    show({ ...done, result: { ...statsSummary, dropped_sentences: 2 } });
    expect(screen.getByText(/2 sentences were left out/)).toBeInTheDocument();
  });

  it("while writing: a Groq wait, no tabs, and Stop, which cancels only the summary", async () => {
    const user = userEvent.setup();
    vi.mocked(api.cancel).mockResolvedValueOnce({} as never);
    show({ status: "waiting", pending: { since: Date.now() / 1000, role: "summarizer", effort: "medium" }, result: statsSummary });
    expect(screen.getByText(/Writing the summary…/)).toBeInTheDocument();
    expect(screen.getAllByText(/Waiting for Groq/).length).toBeGreaterThan(0);
    expect(screen.queryByRole("tablist")).toBeNull();
    expect(screen.queryByRole("button", { name: "Write again" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Copy as Markdown" })).toBeNull();
    await user.click(screen.getByRole("button", { name: "Stop" }));
    expect(api.cancel).toHaveBeenCalledWith("e2de1ca387cb");
  });

  it("after Stop: says the summary was stopped and offers Try again, without an error", () => {
    show({ status: "failed", error: { reason: "cancelled", message: "Cancelled while the summary was being written." } });
    expect(screen.getByText("The summary was stopped before it was written.")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.getByRole("button", { name: "Try again" })).toBeEnabled();
  });

  it("a tab the grounding check emptied says so instead of showing nothing", async () => {
    const user = userEvent.setup();
    const technical = { headline: "", what_was_tested: "", where_tests_live: "", gaps: [], suspected_bugs: [],
                        rejected_or_failed: "", how_to_run: "", next_steps: [] };
    show({ ...done, result: { ...statsSummary, technical, dropped_sentences: 9 } });
    await user.click(screen.getByRole("tab", { name: "For engineering teams" }));
    expect(screen.getByRole("tabpanel")).toHaveTextContent("Nothing in this part could be checked against the run's data.");
    expect(screen.getByRole("tabpanel")).not.toHaveTextContent("None reported.");
  });

  it("when it failed: the message and a retry that asks the backend and reopens the stream", async () => {
    const user = userEvent.setup();
    vi.mocked(api.writeSummary).mockResolvedValueOnce({} as never);
    const onRequested = show({ status: "failed", error: { reason: "timeout", message: "Groq did not answer within 240 s, twice" } });
    expect(screen.getByRole("alert")).toHaveTextContent("Couldn't write the summary: Groq did not answer within 240 s, twice");
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(api.writeSummary).toHaveBeenCalledWith("e2de1ca387cb");
    expect(onRequested).toHaveBeenCalledTimes(1);
  });

  it("when it was turned off: says so and offers Write summary; a refused request shows inline", async () => {
    const user = userEvent.setup();
    vi.mocked(api.writeSummary).mockRejectedValueOnce(new ApiError(409, "job_running", "This run is still running or writing its summary."));
    const onRequested = show({ status: "off" });
    expect(screen.getByText("Summary was turned off for this run.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Write summary" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Couldn't start the summary: This run is still running or writing its summary.");
    expect(onRequested).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Write summary" })).toBeEnabled();
  });
});
