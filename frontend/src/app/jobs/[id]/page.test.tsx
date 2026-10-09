// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
// @vitest-environment jsdom
import { act, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import JobPage from "./page";
import { api, ApiError } from "@/lib/api";

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

  it("explains that a run no longer exists when the API returns 404", async () => {
    vi.mocked(api.job).mockRejectedValue(new ApiError(404, "not_found", "no such job"));
    render(<JobPage />);
    expect(await screen.findByText(/This run no longer exists/)).toBeInTheDocument();
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
});
