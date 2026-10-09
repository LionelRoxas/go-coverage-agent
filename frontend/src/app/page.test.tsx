// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
// @vitest-environment jsdom
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import SetupPage from "./page";
import { api, ApiError } from "@/lib/api";
import type { Health, JobSnapshot, RepoInfo, Sample } from "@/lib/types";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
vi.mock("@/lib/api", async (orig) => {
  const real = await orig<typeof import("@/lib/api")>();
  return {
    ...real,
    api: { health: vi.fn(), repos: vi.fn(), jobs: vi.fn(), startJob: vi.fn(), samples: vi.fn(), downloadSample: vi.fn() },
  };
});

const mocked = vi.mocked(api);
const health = (llm: boolean): Health => ({
  status: "ok", go_version: "1.27", model: "m", llm_configured: llm, tokens_left_today: 5000, storage_writable: true,
});
const repo: RepoInfo = { path: "stats", module: "github.com/x/stats", go_files: 3, test_files: 1 };
const sampleList = (downloaded: string[] = ["stats"]): Sample[] =>
  ["stats", "semver"].map((id) => ({
    id, name: `o/${id}`, description: `${id} lib`, license: "MIT", ref: null, path: id, downloaded: downloaded.includes(id),
  }));
const runningJob = {
  id: "job-1", status: "running", request: { repo_path: "stats", target_coverage: 80, options: {} },
  created_at: 0, percent: 10, event_count: 1, summary: null,
} as unknown as JobSnapshot;

function setup(opts: { llm?: boolean; repos?: RepoInfo[]; jobs?: JobSnapshot[]; samples?: Sample[] } = {}) {
  mocked.samples.mockResolvedValue(opts.samples ?? sampleList());
  mocked.health.mockResolvedValue(health(opts.llm ?? true));
  mocked.repos.mockResolvedValue(opts.repos ?? [repo]);
  mocked.jobs.mockResolvedValue(opts.jobs ?? []);
}
const startButton = () => screen.getByRole("button", { name: "Start" });

describe("SetupPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it("warns about a missing Groq key and disables Start", async () => {
    setup({ llm: false });
    render(<SetupPage />);
    expect(await screen.findByRole("alert")).toHaveTextContent("No Groq API key configured");
    expect(startButton()).toBeDisabled();
  });

  it("names the model that writes the tests", async () => {
    setup();
    render(<SetupPage />);
    expect(await screen.findByText("m")).toBeInTheDocument();
    expect(screen.getByText(/Tests are written by/)).toHaveTextContent("Tests are written by m on Groq.");
  });

  it("enables Start with a key and a repo, and disables it for an invalid target", async () => {
    setup();
    const user = userEvent.setup();
    render(<SetupPage />);
    await waitFor(() => expect(startButton()).toBeEnabled());

    const target = screen.getByRole("spinbutton", { name: "Target coverage percent" });
    await user.clear(target);
    await user.type(target, "0");
    expect(startButton()).toBeDisabled();
    expect(screen.getByText("Enter a target between 1 and 100.")).toBeInTheDocument();
  });

  it("disables Start while a job runs and points to Run history, without the old banner", async () => {
    setup({ jobs: [runningJob] });
    render(<SetupPage />);
    expect(await screen.findByText(/Follow it in Run history/)).toBeInTheDocument();
    expect(screen.queryByText(/A run is in progress on/)).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open" })).toHaveAttribute("href", "/jobs/job-1");
    expect(startButton()).toBeDisabled();
  });

  it("starts a job and navigates to it", async () => {
    setup();
    mocked.startJob.mockResolvedValue({ job_id: "abc" });
    const user = userEvent.setup();
    render(<SetupPage />);
    await waitFor(() => expect(startButton()).toBeEnabled());
    await user.click(startButton());
    await waitFor(() => expect(push).toHaveBeenCalledWith("/jobs/abc"));
    expect(mocked.startJob).toHaveBeenCalledWith(expect.objectContaining({ repo_path: "stats", target_coverage: 80 }));
  });

  it("shows the API error message in an alert when starting fails", async () => {
    setup();
    mocked.startJob.mockRejectedValue(new ApiError(400, "invalid_repo", "Path must be inside ./repos"));
    const user = userEvent.setup();
    render(<SetupPage />);
    await waitFor(() => expect(startButton()).toBeEnabled());
    await user.click(startButton());
    expect(await screen.findByRole("alert")).toHaveTextContent("Path must be inside ./repos");
    expect(push).not.toHaveBeenCalled();
    expect(startButton()).toBeEnabled();
  });

  it("downloads a sample on click, then selects it", async () => {
    setup({ repos: [repo], samples: sampleList() });
    mocked.downloadSample.mockResolvedValue({ ...repo, path: "semver", module: "github.com/o/semver" });
    const user = userEvent.setup();
    render(<SetupPage />);
    const card = await screen.findByRole("button", { name: /o\/semver/ });
    mocked.repos.mockResolvedValue([repo, { ...repo, path: "semver", module: "github.com/o/semver" }]);
    mocked.samples.mockResolvedValue(sampleList(["stats", "semver"]));
    await user.click(card);
    await waitFor(() => expect(mocked.downloadSample).toHaveBeenCalledWith("semver"));
    await waitFor(() => expect(screen.getByRole("button", { name: /o\/semver/ })).toHaveAttribute("aria-pressed", "true"));
    expect(screen.getByText(/Selected:/)).toHaveTextContent("Selected: semver · github.com/o/semver · 3 source files");
  });

  it("opens on Sample repos when only samples exist, and shows the selection summary", async () => {
    setup();
    render(<SetupPage />);
    expect(await screen.findByRole("tab", { name: "Sample repos" })).toHaveAttribute("aria-selected", "true");
    await waitFor(() => expect(screen.getByText(/Selected:/)).toHaveTextContent("Selected: stats · github.com/x/stats · 3 source files"));
  });

  it("opens on Your folders when the user has their own module and remembers a tab change", async () => {
    setup({ repos: [repo, { ...repo, path: "mine", module: "example.com/mine" }] });
    const user = userEvent.setup();
    const { unmount } = render(<SetupPage />);
    expect(await screen.findByRole("tab", { name: "Your folders" })).toHaveAttribute("aria-selected", "true");
    await user.click(screen.getByRole("tab", { name: "Sample repos" }));
    unmount();
    render(<SetupPage />);
    expect(await screen.findByRole("tab", { name: "Sample repos" })).toHaveAttribute("aria-selected", "true");
  });
});
