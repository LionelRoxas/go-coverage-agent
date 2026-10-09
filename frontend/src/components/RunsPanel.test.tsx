// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
// @vitest-environment jsdom
import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { RunsPanel } from "./RunsPanel";
import { api } from "@/lib/api";
import type { JobSnapshot } from "@/lib/types";

vi.mock("@/lib/api", async (orig) => {
  const real = await orig<typeof import("@/lib/api")>();
  return { ...real, api: { jobs: vi.fn(), cancel: vi.fn() } };
});

const NOW = 1_000_000;
const req = (repo: string, target: number) => ({ repo_path: repo, target_coverage: target, options: {} });
const job = (o: Partial<JobSnapshot> & { id: string }): JobSnapshot => ({
  status: "completed", request: req("stats", 80), created_at: NOW - 720, percent: null, event_count: 3, summary: null, ...o,
} as unknown as JobSnapshot);
const summary = { baseline_percent: 12.5, final_percent: 83.2 } as JobSnapshot["summary"];

/**
 * findBy* resolves as soon as the DOM shows the text, but the useEffect that starts or clears the intervals runs
 * later: while waitFor polls, RTL turns the act environment off, so React flushes passive effects in a Scheduler
 * task (setImmediate), and RTL resumes the test after a setTimeout(0). Node runs those two in either order, so
 * under load the test used to read vi.getTimerCount() before the effects ran ("expected +0 to be 2"). act()
 * flushes React's pending work before returning, so the count is read after the effects.
 */
const flushEffects = () => act(async () => {});

describe("RunsPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers({ toFake: ["setInterval", "clearInterval", "Date"] });
    vi.setSystemTime(NOW * 1000);
  });
  afterEach(() => vi.useRealTimers());

  it("shows placeholder rows with a status message until the first answer, then the list", async () => {
    let answer!: (j: JobSnapshot[]) => void;
    vi.mocked(api.jobs).mockReturnValue(new Promise((r) => { answer = r; }));
    render(<RunsPanel />);
    expect(screen.getByRole("status")).toHaveTextContent("Loading runs…");
    expect(screen.getByTestId("runs-loading").querySelectorAll("[data-skeleton]").length).toBeGreaterThan(0);
    await act(async () => answer([job({ id: "a", summary })]));
    expect(screen.queryByTestId("runs-loading")).not.toBeInTheDocument();
    expect(screen.getByText("Completed")).toBeInTheDocument();
  });

  it("drops the placeholders when the list can't be loaded", async () => {
    vi.mocked(api.jobs).mockRejectedValue(new Error("down"));
    render(<RunsPanel />);
    expect(await screen.findByText("Couldn't load runs: down")).toBeInTheDocument();
    expect(screen.queryByTestId("runs-loading")).not.toBeInTheDocument();
  });

  it("shows the empty state and the retention note", async () => {
    vi.mocked(api.jobs).mockResolvedValue([]);
    render(<RunsPanel />);
    expect(await screen.findByText("Pick a repository and press Start — your runs appear here.")).toBeInTheDocument();
    expect(screen.getByText(/files stay in \.\/output/)).toBeInTheDocument();
  });

  it("renders a running card with bar, target, Open and Cancel", async () => {
    vi.mocked(api.jobs).mockResolvedValue([job({ id: "r1", status: "running", percent: 42.5, created_at: NOW - 65 })]);
    vi.mocked(api.cancel).mockResolvedValue({} as never);
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<RunsPanel />);
    expect(await screen.findByText("Running")).toBeInTheDocument();
    expect(screen.getByText("42.5%")).toBeInTheDocument();
    expect(screen.getByText("target 80.0%")).toBeInTheDocument();
    expect(screen.getByRole("meter")).toHaveAttribute("aria-valuenow", "42.5");
    expect(screen.getByTestId("target-marker")).toHaveStyle({ left: "80%" });
    expect(screen.getByText("1m 5s")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open" })).toHaveAttribute("href", "/jobs/r1");
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(api.cancel).toHaveBeenCalledWith("r1");
  });

  it("shows Measuring baseline when percent is null, and the error when cancelling fails", async () => {
    vi.mocked(api.jobs).mockResolvedValue([job({ id: "r1", status: "running" })]);
    vi.mocked(api.cancel).mockRejectedValue(new Error("nope"));
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<RunsPanel />);
    expect(await screen.findByText("Measuring baseline…")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Couldn't cancel: nope");
    expect(screen.getByRole("button", { name: "Cancel" })).toBeEnabled();
  });

  it("renders past runs newest first with chips, coverage and relative time", async () => {
    vi.mocked(api.jobs).mockResolvedValue([
      job({ id: "old", status: "cancelled", created_at: NOW - 7200, request: req("oldrepo", 70) as never }),
      job({ id: "done", status: "completed", summary }),
      job({ id: "bad", status: "failed", created_at: NOW - 30, request: req("badrepo", 90) as never }),
    ]);
    render(<RunsPanel />);
    const rows = await screen.findAllByRole("link");
    expect(rows.map((r) => r.getAttribute("href"))).toEqual(["/jobs/bad", "/jobs/done", "/jobs/old"]);
    expect(screen.getByText("Completed")).toBeInTheDocument();
    expect(screen.getByText("Cancelled")).toBeInTheDocument();
    expect(screen.getByText("Failed")).toBeInTheDocument();
    expect(screen.getByText("12.5% → 83.2%")).toBeInTheDocument();
    expect(screen.getAllByText("—")).toHaveLength(2);
    expect(screen.getByText("12 min ago")).toBeInTheDocument();
    expect(screen.getByText("2 h ago")).toBeInTheDocument();
    expect(screen.getByText("just now")).toBeInTheDocument();
  });

  it("polls every 3 s while a job is running and stops once none is", async () => {
    vi.mocked(api.jobs).mockResolvedValue([job({ id: "r1", status: "running", percent: 5 })]);
    render(<RunsPanel />);
    await screen.findByText("Running");
    expect(api.jobs).toHaveBeenCalledTimes(1);
    vi.mocked(api.jobs).mockResolvedValue([job({ id: "r1", status: "completed", summary })]);
    await act(async () => { await vi.advanceTimersByTimeAsync(3000); });
    expect(api.jobs).toHaveBeenCalledTimes(2);
    expect(await screen.findByText("Completed")).toBeInTheDocument();
    await act(async () => { await vi.advanceTimersByTimeAsync(10000); });
    expect(api.jobs).toHaveBeenCalledTimes(2);
  });

  it("stops polling on unmount", async () => {
    vi.mocked(api.jobs).mockResolvedValue([job({ id: "r1", status: "running" })]);
    const { unmount } = render(<RunsPanel />);
    await screen.findByText("Running");
    unmount();
    await act(async () => { await vi.advanceTimersByTimeAsync(9000); });
    expect(api.jobs).toHaveBeenCalledTimes(1);
  });

  it("does not start an overlapping fetch while one is still pending", async () => {
    const running = [job({ id: "r1", status: "running", percent: 5 })];
    vi.mocked(api.jobs).mockResolvedValueOnce(running);
    render(<RunsPanel />);
    await screen.findByText("Running");
    let release!: (j: JobSnapshot[]) => void;
    vi.mocked(api.jobs).mockImplementation(() => new Promise((r) => { release = r; }));
    await act(async () => { await vi.advanceTimersByTimeAsync(3000); });
    expect(api.jobs).toHaveBeenCalledTimes(2);
    await act(async () => { await vi.advanceTimersByTimeAsync(9000); });
    expect(api.jobs).toHaveBeenCalledTimes(2);
    await act(async () => { release(running); await vi.advanceTimersByTimeAsync(0); });
    await act(async () => { await vi.advanceTimersByTimeAsync(3000); });
    expect(api.jobs).toHaveBeenCalledTimes(3);
  });

  it("stops the 1 s ticker once nothing is running", async () => {
    vi.mocked(api.jobs).mockResolvedValue([job({ id: "r1", status: "running", percent: 5 })]);
    render(<RunsPanel />);
    await screen.findByText("Running");
    await flushEffects();
    expect(vi.getTimerCount()).toBe(2); // 3 s poll + 1 s ticker
    vi.mocked(api.jobs).mockResolvedValue([job({ id: "r1", status: "completed", summary })]);
    await act(async () => { await vi.advanceTimersByTimeAsync(3000); });
    await screen.findByText("Completed");
    await flushEffects();
    expect(vi.getTimerCount()).toBe(0);
  });

  it("drops a response that arrives after unmount", async () => {
    let release!: (j: JobSnapshot[]) => void;
    vi.mocked(api.jobs).mockImplementation(() => new Promise((r) => { release = r; }));
    const onJobs = vi.fn();
    const { unmount } = render(<RunsPanel onJobs={onJobs} />);
    unmount();
    await act(async () => { release([job({ id: "r1", status: "running" })]); await vi.advanceTimersByTimeAsync(0); });
    expect(onJobs).not.toHaveBeenCalled();
    expect(vi.getTimerCount()).toBe(0);
  });

  it("shows an inline error when loading fails", async () => {
    vi.mocked(api.jobs).mockRejectedValue(new Error("backend down"));
    render(<RunsPanel />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Couldn't load runs: backend down");
    expect(screen.getByText(/files stay in/)).toBeInTheDocument();
  });

  it("keeps a run that is writing its summary in the busy list, with Stop summary", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    vi.mocked(api.jobs).mockResolvedValue([job({ id: "w", status: "completed", writing_summary: true, percent: 81.07, summary })]);
    vi.mocked(api.cancel).mockResolvedValue({} as never);
    render(<RunsPanel />);
    const busy = await screen.findByRole("list", { name: "Running" });
    expect(busy).toHaveTextContent("Writing summary…");
    expect(busy).toHaveTextContent("Completed");
    expect(screen.queryByRole("list", { name: "Past runs" })).toBeNull();
    await user.click(screen.getByRole("button", { name: "Stop summary" }));
    expect(api.cancel).toHaveBeenCalledWith("w");
  });

  it("after Cancel, the card of a run now writing its summary offers Stop summary again", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    const running = job({ id: "r", status: "running", percent: 40 });
    vi.mocked(api.jobs).mockResolvedValueOnce([running])
      .mockResolvedValue([{ ...running, status: "cancelled", writing_summary: true }]);
    vi.mocked(api.cancel).mockResolvedValue({} as never);
    render(<RunsPanel />);
    await user.click(await screen.findByRole("button", { name: "Cancel" }));
    expect(await screen.findByRole("button", { name: "Stop summary" })).toBeEnabled();
    expect(screen.getByRole("list", { name: "Running" })).toHaveTextContent("Writing summary…");
  });
});
