// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import SetupPage from "./page";
import { api, ApiError } from "@/lib/api";
import type { Health, JobSnapshot, RepoInfo, Sample } from "@/lib/types";
import { emptySkips } from "@/lib/upload";

const push = vi.fn();
// The wizard ignores Start for 500 ms after the review opens; tests move this clock instead of waiting.
const clock = vi.hoisted(() => ({ t: 0 }));
vi.mock("@/lib/clock", () => ({ now: () => clock.t }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
vi.mock("@/lib/api", async (orig) => {
  const real = await orig<typeof import("@/lib/api")>();
  return {
    ...real,
    api: { health: vi.fn(), repos: vi.fn(), jobs: vi.fn(), startJob: vi.fn(), samples: vi.fn(), downloadSample: vi.fn(), uploadRepo: vi.fn() },
  };
});

const mocked = vi.mocked(api);
const health = (llm: boolean, left = 1_600_000, min = 20_000): Health => ({
  status: "ok", go_version: "1.27", model: "m", llm_configured: llm, tokens_left_today: left, min_daily_tokens_to_start: min,
  storage_writable: true,
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

function setup(opts: { llm?: boolean; left?: number; min?: number; repos?: RepoInfo[]; jobs?: JobSnapshot[]; samples?: Sample[] } = {}) {
  mocked.samples.mockResolvedValue(opts.samples ?? sampleList());
  mocked.health.mockResolvedValue(health(opts.llm ?? true, opts.left, opts.min));
  mocked.repos.mockResolvedValue(opts.repos ?? [repo]);
  mocked.jobs.mockResolvedValue(opts.jobs ?? []);
}
type User = ReturnType<typeof userEvent.setup>;
const startButton = () => screen.getByRole("button", { name: "Start" });
const nextButton = () => screen.getByRole("button", { name: "Next" });
const stepper = () => screen.getByRole("navigation", { name: "Steps to start a run" });
const stepItems = () => within(within(stepper()).getByRole("list")).getAllByRole("listitem");
const states = () => stepItems().map((li) => li.getAttribute("data-state"));
/** The one-line stepper shown on phones. */
const compactStepper = () => within(stepper()).getByText(/^Step \d of 4$/).parentElement!;
const form = () => stepper().closest("form")!;
const stepHeading = () => screen.getByRole("heading", { level: 2, name: /^Step \d of 4: / });

/** Waits for the first repository to be selected, then presses Next until the review step. */
async function toReview(user: User) {
  await waitFor(() => expect(nextButton()).toBeEnabled());
  await user.click(nextButton());
  await user.click(nextButton());
  const next = nextButton();
  await user.click(next);
  await screen.findByRole("heading", { level: 2, name: "Step 4 of 4: Review & start" });
  // Start is a new element, not the Next button turned into a submit button: in a browser the click that opens the
  // review would otherwise also submit the form and start a run.
  expect(startButton()).not.toBe(next);
  expect(mocked.startJob).not.toHaveBeenCalled();
  clock.t += 1000; // the user reads the review before pressing Start
}

describe("SetupPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    clock.t = 0;
  });

  it("opens with a plain headline, one supporting line, a measured result and a How it works link, before the wizard", async () => {
    setup();
    render(<SetupPage />);
    const h1 = screen.getByRole("heading", { level: 1 });
    expect(h1).toHaveTextContent("Fill the gaps in a Go project’s tests");
    const header = h1.closest("header")!;
    expect(header).toHaveTextContent(
      "Point it at a Go project and it writes unit tests with AI, keeping only the ones that pass and test code no other test reaches.",
    );
    expect(header.textContent).not.toMatch(/autonomously|LLM/);
    // the proof uses the real run 0e1f8bf7442a (output/0e1f8bf7442a/report.json)
    expect(within(header).getByRole("img", { name: /22 rounds.*17\.2%.*100%/ })).toBeInTheDocument();
    expect(header).toHaveTextContent("Measured on montanaflynn/stats: 0% to 100% of the code tested in 22 rounds (goal 100%, up to 30 rounds), about 10 minutes.");
    expect(within(header).getByRole("link", { name: "How it works" })).toHaveAttribute("href", "/how-it-works");
    expect(header.compareDocumentPosition(stepper()) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    await screen.findByText(/Selected:/);
  });

  it("shows only step 1 at first, with a stepper of four steps: the first current, the rest upcoming and not clickable", async () => {
    setup();
    render(<SetupPage />);
    const items = stepItems();
    expect(states()).toEqual(["current", "upcoming", "upcoming", "upcoming"]);
    expect(items.map((li) => li.textContent)).toEqual([
      expect.stringContaining("Choose a repository"), expect.stringContaining("Set a target"),
      expect.stringContaining("Advanced options (optional)"), expect.stringContaining("Review & start"),
    ]);
    expect(items[0]).toHaveAttribute("aria-current", "step");
    expect(items[1]).not.toHaveAttribute("aria-current");
    for (const li of items) expect(within(li).queryByRole("button")).not.toBeInTheDocument();
    expect(stepHeading()).toHaveTextContent("Choose a repository");
    expect(compactStepper()).toHaveTextContent(/^Step 1 of 4 · Choose a repository$/);
    expect(compactStepper()).toHaveAttribute("aria-current", "step");
    expect(screen.getByText(/Pick a sample \(it downloads the first time\)/)).toHaveTextContent(
      "Pick a sample (it downloads the first time), or upload a Go project folder of your own.");
    expect(await screen.findByRole("tablist", { name: "Repository source" })).toBeInTheDocument();
    expect(screen.queryByRole("spinbutton", { name: "Target coverage percent" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Start" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Back" })).not.toBeInTheDocument();
    // the first step's heading is not focused on page load
    expect(stepHeading()).not.toHaveFocus();
  });

  it("cannot advance from step 1 until a repository is selected", async () => {
    setup({ repos: [] });
    render(<SetupPage />);
    expect(await screen.findByText("Nothing selected yet. Pick a repository above.")).toBeInTheDocument();
    await waitFor(() => expect(mocked.repos).toHaveBeenCalled());
    expect(nextButton()).toBeDisabled();
    expect(states()).toEqual(["current", "upcoming", "upcoming", "upcoming"]);
  });

  it("moves to step 2 on Next, marks step 1 done and moves focus to the announced step heading", async () => {
    setup();
    const user = userEvent.setup();
    render(<SetupPage />);
    await waitFor(() => expect(nextButton()).toBeEnabled());
    await user.click(nextButton());
    const heading = screen.getByRole("heading", { level: 2, name: "Step 2 of 4: Set a target" });
    expect(heading).toHaveFocus();
    expect(screen.getByText(/share of the code/)).toHaveTextContent(
      "The share of the code you want tests to run. 80% is a good start; higher takes longer.");
    expect(screen.queryByRole("tablist", { name: "Repository source" })).not.toBeInTheDocument();
    expect(states()).toEqual(["done", "current", "upcoming", "upcoming"]);
    expect(stepItems()[1]).toHaveAttribute("aria-current", "step");
    expect(compactStepper()).toHaveTextContent(/^Step 2 of 4 · Set a target$/);
  });

  it("blocks Next on an invalid target and Back returns to step 1 with the selection intact", async () => {
    setup({ repos: [repo, { ...repo, path: "mine", module: "example.com/mine" }] });
    const user = userEvent.setup();
    render(<SetupPage />);
    await user.click(await screen.findByRole("tab", { name: "Sample repos" }));
    await user.click(screen.getByRole("button", { name: /o\/stats/ }));
    await user.click(nextButton());
    const target = screen.getByRole("spinbutton", { name: "Target coverage percent" });
    await user.clear(target);
    await user.type(target, "0");
    expect(nextButton()).toBeDisabled();
    expect(screen.getByText("Enter a target between 1 and 100.")).toBeInTheDocument();
    await user.clear(target);
    await user.type(target, "65");
    expect(nextButton()).toBeEnabled();

    await user.click(screen.getByRole("button", { name: "Back" }));
    expect(screen.getByRole("heading", { level: 2, name: "Step 1 of 4: Choose a repository" })).toHaveFocus();
    expect(screen.getByText(/Selected:/)).toHaveTextContent("Selected: stats · github.com/x/stats · 3 source files");
    // step 2 was opened but not finished with Next, so it is not done yet
    expect(states()).toEqual(["current", "upcoming", "upcoming", "upcoming"]);
    await user.click(nextButton());
    expect(screen.getByRole("spinbutton", { name: "Target coverage percent" })).toHaveValue(65);
  });

  it("ignores a form submission that does not come from Start (Enter in a field) on every step", async () => {
    setup();
    mocked.startJob.mockResolvedValue({ job_id: "abc" });
    const user = userEvent.setup();
    render(<SetupPage />);
    await waitFor(() => expect(nextButton()).toBeEnabled());
    await user.click(nextButton());
    // In a browser Enter in the number field submits the form implicitly, with no submitter.
    fireEvent.submit(form());
    expect(stepHeading()).toHaveTextContent("Set a target");
    await user.click(nextButton());
    fireEvent.submit(form());
    expect(stepHeading()).toHaveTextContent("Advanced options (optional)");
    await user.click(nextButton());
    clock.t += 1000;
    await waitFor(() => expect(startButton()).toBeEnabled());
    fireEvent.submit(form());
    expect(mocked.startJob).not.toHaveBeenCalled();
    await user.click(startButton()); // the control: Start itself does start
    await waitFor(() => expect(mocked.startJob).toHaveBeenCalledOnce());
  });

  it("does not start a run on a double-click of Next at step 3", async () => {
    setup();
    mocked.startJob.mockResolvedValue({ job_id: "abc" });
    const user = userEvent.setup();
    render(<SetupPage />);
    await waitFor(() => expect(nextButton()).toBeEnabled());
    await user.click(nextButton());
    await user.click(nextButton());
    await waitFor(() => expect(mocked.health).toHaveBeenCalled());
    await user.click(nextButton());
    // the second click lands on Start, which now sits where Next was
    await user.click(startButton());
    expect(mocked.startJob).not.toHaveBeenCalled();
    expect(stepHeading()).toHaveTextContent("Review & start");
    // a second click of a multi-click is ignored too, whenever it comes
    clock.t += 600;
    fireEvent.click(startButton(), { detail: 2 });
    expect(mocked.startJob).not.toHaveBeenCalled();
    await user.click(startButton());
    await waitFor(() => expect(mocked.startJob).toHaveBeenCalledOnce());
  });

  it("locks Back, Edit and the stepper while a run is starting", async () => {
    setup();
    mocked.startJob.mockReturnValue(new Promise(() => {}));
    const user = userEvent.setup();
    render(<SetupPage />);
    await toReview(user);
    await waitFor(() => expect(startButton()).toBeEnabled());
    await user.click(startButton());
    expect(await screen.findByRole("button", { name: "Starting…" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Back" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Edit target" })).toBeDisabled();
    await user.click(within(stepItems()[0]).getByRole("button"));
    expect(stepHeading()).toHaveTextContent("Review & start");
  });

  it("keeps Next disabled on step 1 while a sample downloads, then enables it with the new selection", async () => {
    setup({ repos: [repo], samples: sampleList() });
    let finish!: (r: RepoInfo) => void;
    mocked.downloadSample.mockReturnValue(new Promise((r) => { finish = r; }));
    const user = userEvent.setup();
    render(<SetupPage />);
    await waitFor(() => expect(nextButton()).toBeEnabled()); // stats is preselected
    await user.click(await screen.findByRole("button", { name: /o\/semver/ }));
    expect(nextButton()).toBeDisabled();
    mocked.repos.mockResolvedValue([repo, { ...repo, path: "semver", module: "github.com/o/semver" }]);
    finish({ ...repo, path: "semver", module: "github.com/o/semver" });
    await waitFor(() => expect(nextButton()).toBeEnabled());
    expect(screen.getByText(/Selected:/)).toHaveTextContent("Selected: semver");
  });

  it("shows the four limits directly on step 3, blocks Next on an invalid value and Skip keeps the defaults", async () => {
    setup();
    const user = userEvent.setup();
    render(<SetupPage />);
    await waitFor(() => expect(nextButton()).toBeEnabled());
    await user.click(nextButton());
    await user.click(nextButton());
    expect(stepHeading()).toHaveTextContent("Advanced options (optional)");
    expect(screen.getByText(/defaults work/i)).toBeInTheDocument();
    expect(screen.getByRole("spinbutton", { name: "Fix attempts per file" })).toHaveValue(2);
    const iterations = screen.getByRole("spinbutton", { name: "Max iterations" });
    await user.clear(iterations);
    await user.type(iterations, "99");
    expect(nextButton()).toBeDisabled();
    expect(screen.getByText("Enter a whole number from 1 to 30.")).toBeInTheDocument();
    expect(iterations).toHaveAttribute("aria-invalid", "true");

    expect(screen.getByText(/discards these changes/)).toHaveTextContent(
      "You changed an option. Skip (use defaults) discards these changes.");
    expect(screen.getByRole("button", { name: "Skip (use defaults)" })).toHaveAccessibleDescription(/discards these changes/);
    await user.click(screen.getByRole("button", { name: "Skip (use defaults)" }));
    expect(stepHeading()).toHaveTextContent("Review & start");
    expect(screen.getByRole("group", { name: "Advanced options" })).toHaveTextContent("Defaults");
  });

  it("keeps edited limits with Next, lists them on the review step and sends them on Start", async () => {
    setup();
    mocked.startJob.mockResolvedValue({ job_id: "abc" });
    const user = userEvent.setup();
    render(<SetupPage />);
    await waitFor(() => expect(nextButton()).toBeEnabled());
    await user.click(nextButton());
    await user.click(nextButton());
    const iterations = screen.getByRole("spinbutton", { name: "Max iterations" });
    await user.clear(iterations);
    await user.type(iterations, "10");
    await user.click(nextButton());
    const advanced = screen.getByRole("group", { name: "Advanced options" });
    expect(advanced).toHaveTextContent("Max iterations: 10");
    expect(advanced).not.toHaveTextContent("Defaults");
    clock.t += 1000;
    await waitFor(() => expect(startButton()).toBeEnabled());
    await user.click(startButton());
    await waitFor(() => expect(mocked.startJob).toHaveBeenCalledWith(expect.objectContaining({
      options: { max_iterations: 10, min_gain: 1, targets_per_iteration: 3, max_fix_attempts: 2, write_summary: true },
    })));
  });

  it("has an AI summary checkbox on step 3, on by default, listed on the review step and sent on Start", async () => {
    setup();
    mocked.startJob.mockResolvedValue({ job_id: "abc" });
    const user = userEvent.setup();
    render(<SetupPage />);
    await waitFor(() => expect(nextButton()).toBeEnabled());
    await user.click(nextButton());
    await user.click(nextButton());
    const box = screen.getByRole("checkbox", { name: "Write an AI summary at the end" });
    expect(box).toBeChecked();
    await user.click(box);
    expect(screen.getByText(/discards these changes/)).toHaveTextContent("You changed an option.");
    await user.click(nextButton());
    const advanced = screen.getByRole("group", { name: "Advanced options" });
    expect(advanced).toHaveTextContent("Defaults");
    expect(advanced).toHaveTextContent("AI summary at the end: off");
    clock.t += 1000;
    await waitFor(() => expect(startButton()).toBeEnabled());
    await user.click(startButton());
    await waitFor(() => expect(mocked.startJob).toHaveBeenCalledWith(expect.objectContaining({
      options: expect.objectContaining({ write_summary: false }),
    })));
  });

  it("Skip turns the AI summary back on", async () => {
    setup();
    const user = userEvent.setup();
    render(<SetupPage />);
    await waitFor(() => expect(nextButton()).toBeEnabled());
    await user.click(nextButton());
    await user.click(nextButton());
    await user.click(screen.getByRole("checkbox", { name: "Write an AI summary at the end" }));
    await user.click(screen.getByRole("button", { name: "Skip (use defaults)" }));
    expect(screen.getByRole("group", { name: "Advanced options" })).toHaveTextContent("AI summary at the end: on");
  });

  it("summarises the choices on the review step, each with an Edit link that jumps to its step", async () => {
    setup();
    const user = userEvent.setup();
    render(<SetupPage />);
    await toReview(user);
    expect(screen.getByRole("group", { name: "Repository" })).toHaveTextContent("stats");
    expect(screen.getByRole("group", { name: "Repository" })).toHaveTextContent("github.com/x/stats");
    expect(screen.getByRole("group", { name: "Target" })).toHaveTextContent("80%");
    expect(screen.getByRole("group", { name: "Advanced options" })).toHaveTextContent("Defaults");
    expect(states()).toEqual(["done", "done", "done", "current"]);

    await user.click(screen.getByRole("button", { name: "Edit target" }));
    expect(screen.getByRole("heading", { level: 2, name: "Step 2 of 4: Set a target" })).toHaveFocus();
    // going back keeps the later steps done and the review reachable (visited, not done) from the stepper
    expect(states()).toEqual(["done", "current", "done", "visited"]);
    expect(within(stepItems()[3]).getByRole("button")).toHaveTextContent("Review & start");
    expect(within(stepItems()[3]).queryByText(", done")).not.toBeInTheDocument();
    await user.click(within(stepItems()[3]).getByRole("button"));
    expect(screen.getByRole("heading", { level: 2, name: "Step 4 of 4: Review & start" })).toHaveFocus();
    await user.click(screen.getByRole("button", { name: "Edit target" }));
    await user.click(within(stepItems()[0]).getByRole("button"));
    expect(stepHeading()).toHaveTextContent("Choose a repository");
    expect(stepHeading()).toHaveFocus();
    await user.click(within(stepItems()[2]).getByRole("button"));
    expect(stepHeading()).toHaveTextContent("Advanced options (optional)");
    await user.click(nextButton());
    await user.click(screen.getByRole("button", { name: "Edit repository" }));
    expect(stepHeading()).toHaveTextContent("Choose a repository");
    await user.click(within(stepItems()[2]).getByRole("button"));
    await user.click(nextButton());
    await user.click(screen.getByRole("button", { name: "Edit advanced options" }));
    expect(stepHeading()).toHaveTextContent("Advanced options (optional)");
  });

  it("stops treating later steps as done while the current step is invalid", async () => {
    setup();
    const user = userEvent.setup();
    render(<SetupPage />);
    await toReview(user);
    await user.click(screen.getByRole("button", { name: "Edit target" }));
    await user.clear(screen.getByRole("spinbutton", { name: "Target coverage percent" }));
    expect(states()).toEqual(["done", "current", "upcoming", "upcoming"]);
    expect(within(stepItems()[2]).queryByRole("button")).not.toBeInTheDocument();
    expect(within(stepItems()[3]).queryByRole("button")).not.toBeInTheDocument();
  });

  it("warns about a missing Groq key and disables Start", async () => {
    setup({ llm: false });
    const user = userEvent.setup();
    render(<SetupPage />);
    expect(await screen.findByRole("alert")).toHaveTextContent("No Groq API key configured");
    await toReview(user);
    expect(startButton()).toBeDisabled();
  });

  it("shows the token budget beside Start", async () => {
    setup();
    const user = userEvent.setup();
    render(<SetupPage />);
    await toReview(user);
    expect(await screen.findByText(/tokens left today/)).toHaveTextContent("About 1.6M tokens left today");
    expect(screen.getByRole("button", { name: "About the token budget" })).toBeInTheDocument();
    await waitFor(() => expect(startButton()).toBeEnabled());
  });

  it("disables Start with the reason when the budget is below the 20K minimum", async () => {
    setup({ left: 12_000 });
    const user = userEvent.setup();
    render(<SetupPage />);
    await toReview(user);
    const reason = await screen.findByText(/A run needs at least/);
    expect(reason).toHaveTextContent("A run needs at least 20.0k;");
    expect(startButton()).toBeDisabled();
    expect(startButton()).toHaveAttribute("aria-describedby", reason.id);
  });

  it("uses the minimum reported by health", async () => {
    setup({ left: 40_000, min: 50_000 });
    const user = userEvent.setup();
    render(<SetupPage />);
    await toReview(user);
    expect(await screen.findByText(/A run needs at least/)).toHaveTextContent("Only 40.0k tokens left today. A run needs at least 50.0k;");
    expect(startButton()).toBeDisabled();
  });

  it("falls back to 20,000 when health does not report a minimum", async () => {
    setup();
    mocked.health.mockResolvedValue({ ...health(true, 30_000), min_daily_tokens_to_start: undefined });
    const user = userEvent.setup();
    render(<SetupPage />);
    await toReview(user);
    expect(await screen.findByText(/Running low/)).toBeInTheDocument();
    await waitFor(() => expect(startButton()).toBeEnabled());
  });

  it("shows no budget line when health omits tokens_left_today", async () => {
    setup();
    const { tokens_left_today: _omit, ...partial } = health(true);
    void _omit;
    mocked.health.mockResolvedValue(partial as Health);
    const user = userEvent.setup();
    render(<SetupPage />);
    await toReview(user);
    await waitFor(() => expect(startButton()).toBeEnabled());
    expect(screen.queryByText(/tokens left/)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "About the token budget" })).not.toBeInTheDocument();
  });

  it("shows no budget and cannot reach Start while health is loading", async () => {
    setup();
    mocked.health.mockReturnValue(new Promise(() => {}));
    render(<SetupPage />);
    await waitFor(() => expect(mocked.repos).toHaveBeenCalled());
    // the first load waits for health, so nothing is selected yet and the wizard cannot move on to Start
    expect(screen.queryByText(/tokens left/)).not.toBeInTheDocument();
    expect(nextButton()).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Start" })).not.toBeInTheDocument();
  });

  it("keeps Start enabled with a softer note when the budget is low", async () => {
    setup({ left: 150_000 });
    const user = userEvent.setup();
    render(<SetupPage />);
    await toReview(user);
    expect(await screen.findByText(/Running low/)).toBeInTheDocument();
    await waitFor(() => expect(startButton()).toBeEnabled());
    expect(startButton()).not.toHaveAttribute("aria-describedby");
  });

  it("disables Start while a job runs and points to Run history, without the old banner", async () => {
    setup({ jobs: [runningJob] });
    const user = userEvent.setup();
    render(<SetupPage />);
    await toReview(user);
    expect(await screen.findByText(/Follow it in Run history/)).toBeInTheDocument();
    expect(screen.queryByText(/A run is in progress on/)).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open" })).toHaveAttribute("href", "/jobs/job-1");
    expect(startButton()).toBeDisabled();
  });

  it("explains what happens after Start on the review step, with the output path and a link to How it works", async () => {
    setup();
    const user = userEvent.setup();
    render(<SetupPage />);
    expect(screen.queryByRole("region", { name: "What happens next" })).not.toBeInTheDocument();
    await toReview(user);
    expect(screen.getByText(/1–5 minutes/)).toHaveTextContent(
      "Usually 1–5 minutes on a paid Groq key; free-trial keys take much longer. You can leave this page; the run keeps going.");
    const next = screen.getByRole("region", { name: "What happens next" });
    expect(next).toHaveTextContent("./output/<run id>/tests");
    expect(within(next).getByRole("link", { name: "How it works" })).toHaveAttribute("href", "/how-it-works");
  });

  it("starts a job from the review step and navigates to it", async () => {
    setup();
    mocked.startJob.mockResolvedValue({ job_id: "abc" });
    const user = userEvent.setup();
    render(<SetupPage />);
    await toReview(user);
    await waitFor(() => expect(startButton()).toBeEnabled());
    await user.click(startButton());
    await waitFor(() => expect(push).toHaveBeenCalledWith("/jobs/abc"));
    expect(mocked.startJob).toHaveBeenCalledWith({
      repo_path: "stats", target_coverage: 80,
      options: { max_iterations: 20, min_gain: 1, targets_per_iteration: 3, max_fix_attempts: 2, write_summary: true },
    });
  });

  it("shows the API error message in an alert when starting fails", async () => {
    setup();
    mocked.startJob.mockRejectedValue(new ApiError(400, "invalid_repo", "Path must be inside ./repos"));
    const user = userEvent.setup();
    render(<SetupPage />);
    await toReview(user);
    await waitFor(() => expect(startButton()).toBeEnabled());
    await user.click(startButton());
    expect(await screen.findByRole("alert")).toHaveTextContent("Path must be inside ./repos");
    expect(push).not.toHaveBeenCalled();
    expect(startButton()).toBeEnabled();
  });

  it("downloads a sample on click, then selects it without leaving step 1", async () => {
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
    expect(stepHeading()).toHaveTextContent("Choose a repository");
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

  it("still loads health and folders when the sample list fails", async () => {
    setup({ repos: [repo, { ...repo, path: "mine", module: "example.com/mine" }] });
    mocked.samples.mockRejectedValue(new ApiError(404, "http_error", "Not Found"));
    const user = userEvent.setup();
    render(<SetupPage />);
    await user.click(await screen.findByRole("tab", { name: "Sample repos" }));
    expect(screen.getByText(/Sample list unavailable/)).toBeInTheDocument();
    await toReview(user);
    expect(screen.getByText(/tokens left today/)).toBeInTheDocument(); // health loaded
  });

  it("selects a downloaded sample even if the reload afterwards fails", async () => {
    setup({ repos: [repo], samples: sampleList() });
    mocked.downloadSample.mockResolvedValue({ ...repo, path: "semver" });
    const user = userEvent.setup();
    render(<SetupPage />);
    const card = await screen.findByRole("button", { name: /o\/semver/ });
    mocked.repos.mockRejectedValue(new Error("down"));
    await user.click(card);
    await waitFor(() => expect(mocked.downloadSample).toHaveBeenCalled());
    await waitFor(() => expect(screen.queryByRole("alert")).not.toBeInTheDocument());
    expect(card).toHaveAttribute("aria-busy", "false");
  });

  it("uploads a chosen folder, then lists and selects it without advancing", async () => {
    setup({ repos: [repo, { ...repo, path: "mine", module: "example.com/mine" }] });
    const uploaded = { path: "uploads/myproj", module: "example.com/myproj", go_files: 2, test_files: 1, skipped: emptySkips() };
    mocked.uploadRepo.mockResolvedValue(uploaded);
    const user = userEvent.setup();
    render(<SetupPage />);
    await screen.findByRole("tab", { name: "Your folders", selected: true });
    mocked.repos.mockResolvedValue([repo, { ...repo, path: "mine", module: "example.com/mine" }, uploaded]);
    const gomod = new File(["module example.com/myproj\n"], "go.mod");
    Object.defineProperty(gomod, "webkitRelativePath", { value: "myproj/go.mod" });
    await user.upload(screen.getByTestId("folder-input"), [gomod]);
    await waitFor(() => expect(mocked.uploadRepo).toHaveBeenCalledWith([{ path: "myproj/go.mod", file: gomod }], undefined, expect.any(Function)));
    await waitFor(() => expect(screen.getByRole("button", { name: /uploads\/myproj/ })).toHaveAttribute("aria-pressed", "true"));
    expect(screen.getByText(/Selected:/)).toHaveTextContent("Selected: uploads/myproj · example.com/myproj · 2 source files");
    expect(stepHeading()).toHaveTextContent("Choose a repository");
    await toReview(user);
    expect(screen.getByRole("group", { name: "Repository" })).toHaveTextContent("uploads/myproj");
  });
});
