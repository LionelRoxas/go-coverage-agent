// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
// @vitest-environment jsdom
import { act, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { generateMetadata } from "./layout";
import JobPage from "./page";
import { api, ApiError } from "@/lib/api";
import { statsSummary } from "@/lib/fixtures/aiSummary";

vi.mock("next/navigation", () => ({ useParams: () => ({ id: "gone" }) }));
vi.mock("@/lib/api", async (orig) => {
  const real = await orig<typeof import("@/lib/api")>();
  return { ...real, api: { job: vi.fn(), cancel: vi.fn(), eventsUrl: (id: string) => `http://test/${id}/events` } };
});
// Heavy client-only widgets (Recharts / Shiki) are not needed to test the page states.
vi.mock("@/components/CoverageChart", () => ({ CoverageChart: () => null }));
vi.mock("@/components/TestFiles", () => ({ TestFiles: () => null }));

class FakeEventSource {
  static CLOSED = 2;
  static last: FakeEventSource | null = null;
  readyState = 1;
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onmessage: ((m: { data: string }) => void) | null = null;
  constructor(public url: string) {
    FakeEventSource.last = this;
  }
  close() {
    this.readyState = FakeEventSource.CLOSED;
  }
}

describe("JobPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal("EventSource", FakeEventSource);
  });
  afterEach(() => vi.unstubAllGlobals());

  it("tells the user where accepted tests were saved when a run fails", async () => {
    vi.mocked(api.job).mockResolvedValue({} as never);
    render(<JobPage />);
    await waitFor(() => expect(FakeEventSource.last).not.toBeNull());
    act(() => {
      const send = (seq: number, type: string, data: object) =>
        FakeEventSource.last!.onmessage!({ data: JSON.stringify({ seq, ts: 1, type, data }) });
      send(0, "job_started", { repo_path: "stats", target_coverage: 80, options: {}, model: "m" });
      send(1, "job_failed", { reason: "internal_error", message: "boom", output: "" });
    });
    expect(await screen.findByText("Run failed: boom")).toBeInTheDocument();
    expect(screen.getByText("Any accepted tests were saved to ./output/gone/tests.")).toBeInTheDocument();
  });

  it("shows the Interrupted chip and note when a saved run's stream ends without a result", async () => {
    vi.mocked(api.job).mockResolvedValue({ status: "interrupted", writing_summary: false } as never);
    render(<JobPage />);
    await waitFor(() => expect(FakeEventSource.last).not.toBeNull());
    act(() => {
      FakeEventSource.last!.onmessage!({ data: JSON.stringify({ seq: 0, ts: 1, type: "job_started",
                                                                data: { repo_path: "stats", target_coverage: 80, options: {}, model: "m" } }) });
      FakeEventSource.last!.onerror!();
    });
    expect(await screen.findByText("Interrupted")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent(
      "The app stopped before this run finished; the results up to that point are shown.");
    expect(screen.queryByRole("button", { name: "Cancel" })).not.toBeInTheDocument();
  });

  it("hides Cancel when a live run turns out to be interrupted after a backend restart", async () => {
    vi.mocked(api.job).mockResolvedValueOnce({ status: "running", writing_summary: false } as never)
      .mockResolvedValue({ status: "interrupted", writing_summary: false } as never);
    render(<JobPage />);
    await waitFor(() => expect(FakeEventSource.last).not.toBeNull());
    act(() => FakeEventSource.last!.onmessage!({ data: JSON.stringify({ seq: 0, ts: 1, type: "job_started",
      data: { repo_path: "stats", target_coverage: 80, options: {}, model: "m" } }) }));
    expect(screen.getByRole("button", { name: "Cancel" })).toBeInTheDocument();
    act(() => FakeEventSource.last!.onerror!());
    await waitFor(() => expect(api.job).toHaveBeenCalledTimes(2));
    act(() => {  // the reconnected stream replays the run and ends
      FakeEventSource.last!.onmessage!({ data: JSON.stringify({ seq: 0, ts: 1, type: "job_started",
        data: { repo_path: "stats", target_coverage: 80, options: {}, model: "m" } }) });
      FakeEventSource.last!.onerror!();
    });
    expect(await screen.findByText("Interrupted")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Cancel" })).not.toBeInTheDocument();
  });

  it("shows the load error instead of the loading page when a saved run replays nothing", async () => {
    vi.mocked(api.job).mockResolvedValue({ status: "completed", writing_summary: false } as never);
    render(<JobPage />);
    await waitFor(() => expect(FakeEventSource.last).not.toBeNull());
    act(() => FakeEventSource.last!.onerror!());
    expect(await screen.findByRole("alert")).toHaveTextContent("Couldn't read this run's saved events (./output/gone/events.jsonl).");
    expect(screen.queryByTestId("job-loading")).not.toBeInTheDocument();
  });

  it("explains that a run no longer exists when the API returns 404", async () => {
    vi.mocked(api.job).mockRejectedValue(new ApiError(404, "not_found", "no such job"));
    render(<JobPage />);
    expect(await screen.findByRole("heading", { level: 1, name: "This run no longer exists" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Start a new one" })).toHaveAttribute("href", "/");
    expect(screen.getByRole("link", { name: "← All runs" })).toHaveAttribute("href", "/");
  });

  it("links back to all runs from the job view", async () => {
    vi.mocked(api.job).mockResolvedValue({} as never);
    render(<JobPage />);
    expect(await screen.findByRole("link", { name: "← All runs" })).toHaveAttribute("href", "/");
  });

  it("shows a load error with a way back when the job cannot be loaded", async () => {
    vi.mocked(api.job).mockRejectedValue(new ApiError(500, "http_error", "boom"));
    render(<JobPage />);
    expect(await screen.findByRole("alert")).toHaveTextContent("boom");
    expect(screen.getByRole("link", { name: "Back to setup" })).toBeInTheDocument();
  });

  it("shows the Groq wait on the activity line until the answer arrives", async () => {
    vi.mocked(api.job).mockResolvedValue({} as never);
    render(<JobPage />);
    await waitFor(() => expect(FakeEventSource.last).not.toBeNull());
    const now = Date.now() / 1000;
    const send = (seq: number, type: string, data: object, ts = now) =>
      FakeEventSource.last!.onmessage!({ data: JSON.stringify({ seq, ts, type, data }) });
    const at = { index: 1, file: "constraints.go" };
    act(() => {
      send(0, "job_started", { repo_path: "semver", target_coverage: 100, options: {}, model: "m" });
      send(1, "iteration_started", { index: 1, percent: 0 });
      send(2, "plan_created", { index: 1, items: [{ file: "constraints.go", functions: ["A"], uncovered_statements: 1 }] });
      send(3, "llm_request", { ...at, role: "fixer", reasoning_effort: "medium", attempt: 1 }, now - 102);
    });
    const labels = await screen.findAllByText(/^Waiting for Groq · fixer · medium reasoning · 1m 4[2-4]s$/);
    const activity = labels.map((l) => l.parentElement!).find((p) => p.getAttribute("aria-live") === "polite");
    expect(activity).toHaveTextContent(/\(constraints\.go\)$/);
    act(() => send(4, "llm_call", { ...at, role: "fixer", completion_tokens: 5, total_tokens: 9 }));
    expect(screen.queryByText(/Waiting for Groq/)).not.toBeInTheDocument();
    expect(screen.getByText("Writing tests for constraints.go…")).toBeInTheDocument();
  });
  it("shows placeholders, a status message and no Cancel until the first event arrives", async () => {
    vi.mocked(api.job).mockResolvedValue({} as never);
    render(<JobPage />);
    await waitFor(() => expect(FakeEventSource.last).not.toBeNull());
    expect(screen.getByRole("status")).toHaveTextContent("Loading this run…");
    expect(screen.getByTestId("job-loading").querySelectorAll("[data-skeleton]").length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: "Cancel" })).not.toBeInTheDocument();
    expect(screen.queryByText(/0\.0%/)).not.toBeInTheDocument();
    act(() => FakeEventSource.last!.onmessage!({ data: JSON.stringify({ seq: 0, ts: 1, type: "job_started",
      data: { repo_path: "stats", target_coverage: 80, options: {}, model: "m" } }) }));
    expect(screen.queryByTestId("job-loading")).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1, name: "stats" })).toBeInTheDocument();
    expect(screen.getByText("Running")).toHaveClass("rounded-full"); // the same status chip as Run history
    expect(screen.getByRole("button", { name: "Cancel" })).toBeInTheDocument();
  });

  it("shows one token total, with the summary call broken out, in the header and the result card", async () => {
    vi.mocked(api.job).mockResolvedValue({} as never);
    render(<JobPage />);
    await waitFor(() => expect(FakeEventSource.last).not.toBeNull());
    const send = (seq: number, type: string, data: object) =>
      act(() => FakeEventSource.last!.onmessage!({ data: JSON.stringify({ seq, ts: 1, type, data }) }));
    send(0, "job_started", { repo_path: "stats", target_coverage: 80, options: { write_summary: true }, model: "m" });
    send(1, "llm_call", { index: 1, file: "a.go", role: "writer", prompt_tokens: 300_000, completion_tokens: 37_700,
      total_tokens: 337_700 });
    expect(await screen.findByText(/337\.7k tokens$/)).toBeInTheDocument();
    send(2, "job_completed", { stop_reason: "target_reached", message: "Reached the 80% coverage target.", target: 80,
      baseline_percent: 0, final_percent: 81, iterations: [], test_files: [], tests_added: [], suspected_bugs: [], per_file: [],
      tokens: { prompt_tokens: 300_000, completion_tokens: 37_700 }, duration_s: 5 });
    send(3, "llm_request", { role: "summarizer", reasoning_effort: "medium" });
    send(4, "summary_generated", { ...statsSummary, tokens: { prompt_tokens: 10_000, completion_tokens: 3_700, total_tokens: 13_700 } });
    expect(await screen.findByText(/351\.4k tokens \(337\.7k run \+ 13\.7k summary\)$/)).toBeInTheDocument();
    const card = screen.getByText("Tokens").nextSibling;
    expect(card).toHaveTextContent("351.4k337.7k run + 13.7k summary");
    // Write again: a second summary call adds to the summary part, in the header and the card alike
    send(5, "llm_request", { role: "summarizer", reasoning_effort: "medium" });
    send(6, "summary_generated", { ...statsSummary, tokens: { prompt_tokens: 10_000, completion_tokens: 3_700, total_tokens: 13_700 } });
    expect(await screen.findByText(/365\.1k tokens \(337\.7k run \+ 27\.4k across 2 summaries\)$/)).toBeInTheDocument();
    expect(screen.getByText("Tokens").nextSibling).toHaveTextContent("365.1k337.7k run + 27.4k across 2 summaries");
  });

  it("drops the live activity line once the run has a summary, so the result is not said twice", async () => {
    vi.mocked(api.job).mockResolvedValue({} as never);
    render(<JobPage />);
    await waitFor(() => expect(FakeEventSource.last).not.toBeNull());
    act(() => {
      const send = (seq: number, type: string, data: object) =>
        FakeEventSource.last!.onmessage!({ data: JSON.stringify({ seq, ts: 1, type, data }) });
      send(0, "job_started", { repo_path: "stats", target_coverage: 80, options: {}, model: "m" });
      send(1, "job_completed", { stop_reason: "target_reached", message: "Reached the 80% coverage target.", target: 80,
        baseline_percent: 0, final_percent: 81, iterations: [], test_files: [], tests_added: [], suspected_bugs: [], per_file: [],
        tokens: { prompt_tokens: 1, completion_tokens: 1 }, duration_s: 5 });
    });
    expect(await screen.findByText("Completed")).toBeInTheDocument();
    expect(screen.getAllByText("Reached the 80% coverage target.")).toHaveLength(1);
    expect(document.querySelector('[aria-live="polite"]')).toBeNull();
  });

  it.each([
    ["with", [{ file: "ttest.go", functions: ["TTest"], test: "TestTTest_Edge", lines: ["TestTTest_Edge: t_test.go:4: got 1, want 0"] }]],
    ["with an empty list of", []],
    ["without (older run)", undefined],
  ] as const)("shows the prediction disagreements section only when there are some (%s disagreements)", async (_, disagreements) => {
    vi.mocked(api.job).mockResolvedValue({} as never);
    render(<JobPage />);
    await waitFor(() => expect(FakeEventSource.last).not.toBeNull());
    act(() => {
      const send = (seq: number, type: string, data: object) =>
        FakeEventSource.last!.onmessage!({ data: JSON.stringify({ seq, ts: 1, type, data }) });
      send(0, "job_started", { repo_path: "stats", target_coverage: 80, options: {}, model: "m" });
      send(1, "job_completed", { stop_reason: "target_reached", message: "Reached the 80% coverage target.", target: 80,
        baseline_percent: 0, final_percent: 81, iterations: [], test_files: [], tests_added: [], suspected_bugs: [], per_file: [],
        tokens: { prompt_tokens: 1, completion_tokens: 1 }, duration_s: 5, ...(disagreements ? { disagreements } : {}) });
    });
    expect(await screen.findByText("Completed")).toBeInTheDocument();
    const heading = screen.queryByRole("heading", { name: /^Prediction disagreements/ });
    if (disagreements?.length) {
      expect(heading).toHaveTextContent("Prediction disagreements (1)");
      expect(screen.getByText("t_test.go:4: got 1, want 0")).toBeInTheDocument();
    } else {
      expect(heading).not.toBeInTheDocument();
    }
  });

  // A failed run's message is in the failure card and a cancelled run's in its summary, so neither keeps the line.
  it.each([
    ["job_failed", { reason: "repo_does_not_build", message: "The repository does not build.", output: "x" }, "Failed"],
    ["job_cancelled", { stop_reason: "cancelled", message: "Cancelled.", target: 80, baseline_percent: 0, final_percent: 12,
      iterations: [], test_files: [], tests_added: [], suspected_bugs: [], per_file: [],
      tokens: { prompt_tokens: 1, completion_tokens: 1 }, duration_s: 5 }, "Cancelled"],
  ] as const)("drops the live activity line after %s", async (type, data, chip) => {
    vi.mocked(api.job).mockResolvedValue({} as never);
    render(<JobPage />);
    await waitFor(() => expect(FakeEventSource.last).not.toBeNull());
    act(() => {
      const send = (seq: number, t: string, d: object) =>
        FakeEventSource.last!.onmessage!({ data: JSON.stringify({ seq, ts: 1, type: t, data: d }) });
      send(0, "job_started", { repo_path: "stats", target_coverage: 80, options: {}, model: "m" });
    });
    expect(document.querySelector('[aria-live="polite"]')).not.toBeNull();
    act(() => FakeEventSource.last!.onmessage!({ data: JSON.stringify({ seq: 1, ts: 1, type, data }) }));
    expect((await screen.findAllByText(chip)).length).toBeGreaterThan(0); // the status chip (and the card heading)
    expect(document.querySelector('[aria-live="polite"]')).toBeNull();
    expect(screen.queryByRole("button", { name: "Cancel" })).not.toBeInTheDocument();
  });

  it("titles the page after the run", async () => {
    expect(await generateMetadata({ params: Promise.resolve({ id: "e2de1ca387cb" }) })).toEqual({ title: "Run e2de1ca387cb" });
  });
});
