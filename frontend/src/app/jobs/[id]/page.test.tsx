// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
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

describe("JobPage", () => {
  beforeEach(() => vi.clearAllMocks());

  it("explains that a run no longer exists when the API returns 404", async () => {
    vi.mocked(api.job).mockRejectedValue(new ApiError(404, "not_found", "no such job"));
    render(<JobPage />);
    expect(await screen.findByText(/This run no longer exists/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Start a new one" })).toHaveAttribute("href", "/");
  });

  it("shows a load error with a way back when the job cannot be loaded", async () => {
    vi.mocked(api.job).mockRejectedValue(new ApiError(500, "http_error", "boom"));
    render(<JobPage />);
    expect(await screen.findByRole("alert")).toHaveTextContent("boom");
    expect(screen.getByRole("link", { name: "Back to setup" })).toBeInTheDocument();
  });
});
