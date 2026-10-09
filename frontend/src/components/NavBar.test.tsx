// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { NavBar } from "./NavBar";
import { api } from "@/lib/api";

let path = "/";
vi.mock("next/navigation", () => ({ usePathname: () => path }));
vi.mock("@/lib/api", async (orig) => {
  const real = await orig<typeof import("@/lib/api")>();
  return { ...real, api: { health: vi.fn() } };
});

describe("NavBar", () => {
  beforeEach(() => {
    path = "/";
    vi.mocked(api.health).mockResolvedValue({ model: "llama-x" } as never);
  });

  it("renders the logo, app name link and both nav links", async () => {
    render(<NavBar />);
    expect(screen.getByRole("img", { name: "Spectro Cloud" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Go Coverage Agent" })).toHaveAttribute("href", "/");
    expect(screen.getByRole("link", { name: "Runs" })).toHaveAttribute("href", "/");
    expect(screen.getByRole("link", { name: "How it works" })).toHaveAttribute("href", "/how-it-works");
    expect(await screen.findByText("llama-x")).toBeInTheDocument();
  });

  it.each([["/"], ["/jobs/abc"]])("marks Runs current on %s", (p) => {
    path = p;
    render(<NavBar />);
    expect(screen.getByRole("link", { name: "Runs" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "How it works" })).not.toHaveAttribute("aria-current");
  });

  it("marks How it works current on /how-it-works", () => {
    path = "/how-it-works";
    render(<NavBar />);
    expect(screen.getByRole("link", { name: "How it works" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Runs" })).not.toHaveAttribute("aria-current");
  });

  it("hides the model badge when health is unavailable", async () => {
    vi.mocked(api.health).mockRejectedValue(new Error("down"));
    render(<NavBar />);
    await screen.findByRole("link", { name: "Runs" });
    expect(screen.queryByTitle("Model")).not.toBeInTheDocument();
  });
});
