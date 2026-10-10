// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
// @vitest-environment jsdom
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api, ApiError } from "@/lib/api";
import type { MutationView } from "@/lib/runState";
import type { Mutant } from "@/lib/types";
import { MUTATION_NOTE, MutationCard } from "./MutationCard";

vi.mock("@/lib/api", async (orig) => {
  const real = await orig<typeof import("@/lib/api")>();
  return { ...real, api: { mutationTest: vi.fn(), cancel: vi.fn() } };
});

const m = (index: number, status: Mutant["status"], line = 41): Mutant =>
  ({ index, file: "percentile.go", line, original: "<", mutated: "<=", op: "boundary", status, before: "i < n", after: "i <= n" });

function show(view?: MutationView, onRequested = vi.fn()) {
  render(<MutationCard view={view} jobId="abc" coverage={82.5} onRequested={onRequested} />);
  return onRequested;
}

describe("MutationCard", () => {
  beforeEach(() => vi.clearAllMocks());

  it("idle: explains the test and starts it", async () => {
    vi.mocked(api.mutationTest).mockResolvedValue({} as never);
    const onRequested = show();
    expect(screen.getByRole("heading", { name: "Test quality" })).toBeInTheDocument();
    expect(screen.getByText(MUTATION_NOTE)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Run mutation test" }));
    expect(api.mutationTest).toHaveBeenCalledWith("abc");
    expect(onRequested).toHaveBeenCalled();
  });

  it("idle: says why it could not start (busy)", async () => {
    vi.mocked(api.mutationTest).mockRejectedValue(new ApiError(409, "job_running", "Run x is busy."));
    const onRequested = show();
    await userEvent.click(screen.getByRole("button", { name: "Run mutation test" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Run x is busy.");
    expect(onRequested).not.toHaveBeenCalled();
  });

  it("running: progress, live counts, each mutant and Cancel", async () => {
    vi.mocked(api.cancel).mockResolvedValue({} as never);
    show({ status: "running", total: 4, mutants: [m(1, "killed"), m(2, "survived", 50), m(3, "timeout")] });
    expect(screen.getByText("Mutant 4 of 4 · 2 caught · 1 missed")).toBeInTheDocument();
    const items = screen.getAllByRole("listitem");
    expect(items).toHaveLength(3);
    expect(items[0]).toHaveTextContent("✓percentile.go:41i < n → i <= ncaught");
    expect(items[1]).toHaveTextContent("✗percentile.go:50i < n → i <= nmissed");
    expect(items[2]).toHaveTextContent("caught (timed out)");
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(api.cancel).toHaveBeenCalledWith("abc");
  });

  it("running: before the first event", () => {
    show({ status: "running", mutants: [] });
    expect(screen.getByText("Preparing a fresh copy and running the kept tests…")).toBeInTheDocument();
  });

  it("done: score next to coverage, per-file table and the missed bugs as mini diffs", () => {
    const mutants = [m(1, "killed"), m(2, "survived", 50), m(3, "invalid"), m(4, "timeout")];
    show({ status: "done", total: 4, mutants, result: {
      total: 4, killed: 2, survived: 1, invalid: 1, timeouts: 1, score: 66.7,
      per_file: [{ file: "percentile.go", killed: 2, survived: 1, score: 66.7 }], mutants } });
    expect(screen.getByText("mutation score").parentElement).toHaveTextContent("66.7%mutation score");
    expect(screen.getByText("82.5%")).toBeInTheDocument();
    expect(screen.getByText(/2 of 3 planted bugs caught \(1 by timing out\) · 1 skipped because they do not build/)).toBeInTheDocument();
    expect(screen.getAllByRole("row")[1]).toHaveTextContent("percentile.go2166.7%");
    const missed = within(screen.getByRole("heading", { name: "Missed bugs" }).parentElement!).getAllByRole("listitem");
    expect(missed).toHaveLength(1);
    expect(missed[0]).toHaveTextContent("percentile.go:50i < n → i <= n");
    expect(screen.getByRole("button", { name: "Run again" })).toBeInTheDocument();
  });

  it("older results without source lines show the operators", () => {
    const old = { ...m(1, "survived"), before: undefined, after: undefined };
    show({ status: "done", total: 1, mutants: [old], result: {
      total: 1, killed: 0, survived: 1, invalid: 0, timeouts: 0, score: 0, per_file: [], mutants: [old] } });
    expect(screen.getByRole("listitem")).toHaveTextContent("percentile.go:41< → <=");
  });

  it("failed and cancelled", () => {
    const { unmount } = render(<MutationCard jobId="abc" coverage={1} onRequested={vi.fn()}
      view={{ status: "failed", mutants: [], error: { reason: "baseline_failed", message: "the kept tests do not pass", output: "--- FAIL" } }} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Mutation test failed: the kept tests do not pass");
    expect(screen.getByText("--- FAIL")).toBeInTheDocument();
    unmount();
    show({ status: "failed", mutants: [], error: { reason: "cancelled", message: "Cancelled." } });
    expect(screen.getByRole("status")).toHaveTextContent("cancelled before it finished");
    expect(screen.getByRole("button", { name: "Run again" })).toBeInTheDocument();
  });
});
