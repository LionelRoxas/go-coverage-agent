// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import PageError from "./error";
import NotFound, { metadata } from "./not-found";

describe("app/error.tsx", () => {
  afterEach(() => vi.restoreAllMocks());

  it("explains the crash in the app's design and retries on Try again", async () => {
    const log = vi.spyOn(console, "error").mockImplementation(() => {});
    const retry = vi.fn();
    const error = Object.assign(new Error("jobs is not iterable"), { digest: "abc123" });
    render(<PageError error={error} retry={retry} />);
    const panel = screen.getByRole("alert");
    expect(panel).toHaveClass("border-danger");
    expect(screen.getByRole("heading", { level: 1, name: "This page stopped working" })).toBeInTheDocument();
    expect(panel).toHaveTextContent("Error reference: abc123");
    expect(panel).not.toHaveTextContent("jobs is not iterable"); // the raw message goes to the console, not the page
    expect(log).toHaveBeenCalledWith(error);
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(retry).toHaveBeenCalledOnce();
    expect(screen.getByRole("link", { name: "Go to New run" })).toHaveAttribute("href", "/");
  });

  it("leaves out the reference line when there is no digest", () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    render(<PageError error={new Error("x")} retry={() => {}} />);
    expect(screen.queryByText(/Error reference/)).not.toBeInTheDocument();
  });
});

describe("app/not-found.tsx", () => {
  it("has its own title and links back into the app", () => {
    expect(metadata.title).toBe("Page not found");
    render(<NotFound />);
    expect(screen.getByRole("heading", { level: 1, name: "Page not found" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Go to New run" })).toHaveAttribute("href", "/");
    expect(screen.getByRole("link", { name: "How it works" })).toHaveAttribute("href", "/how-it-works");
  });
});
