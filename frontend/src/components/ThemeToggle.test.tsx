// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ThemeToggle } from "./ThemeToggle";

const pressed = (name: string) => screen.getByRole("button", { name }).getAttribute("aria-pressed");

describe("ThemeToggle", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
    delete document.documentElement.dataset.theme;
  });

  it("is a labelled group with System pressed by default", () => {
    render(<ThemeToggle />);
    expect(screen.getByRole("group", { name: "Theme" })).toBeInTheDocument();
    expect(pressed("System")).toBe("true");
    expect(pressed("Dark")).toBe("false");
  });

  it("selecting Dark sets data-theme and stores it; System removes it again", async () => {
    const user = userEvent.setup();
    render(<ThemeToggle />);
    await user.click(screen.getByRole("button", { name: "Dark" }));
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(localStorage.getItem("gca-theme")).toBe("dark");
    expect(pressed("Dark")).toBe("true");
    await user.click(screen.getByRole("button", { name: "System" }));
    expect(document.documentElement.dataset.theme).toBeUndefined();
    expect(localStorage.getItem("gca-theme")).toBeNull();
  });

  it("reads the initial state from storage", async () => {
    localStorage.setItem("gca-theme", "light");
    render(<ThemeToggle />);
    expect(await screen.findByRole("button", { name: "Light", pressed: true })).toBeInTheDocument();
  });

  it("does not crash when storage throws", async () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("denied"); });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("denied"); });
    const user = userEvent.setup();
    render(<ThemeToggle />);
    await user.click(screen.getByRole("button", { name: "Dark" }));
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(pressed("Dark")).toBe("true");
  });
});
