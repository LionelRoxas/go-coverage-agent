// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { TokenBudget, budgetBlocked } from "./TokenBudget";

describe("TokenBudget", () => {
  it("states the tokens left plainly when there is plenty", () => {
    render(<TokenBudget left={1_600_000} />);
    expect(screen.getByText(/tokens left today/)).toHaveTextContent("About 1.6M tokens left today");
    expect(screen.queryByText(/Running low/)).not.toBeInTheDocument();
  });

  it("adds a softer note below 200K", () => {
    render(<TokenBudget left={150_000} />);
    expect(screen.getByText(/Running low/)).toHaveTextContent("Running low: about 150.0k tokens left today. A long run may stop early.");
  });

  it("explains why a run cannot start below the 20K minimum", () => {
    render(<TokenBudget left={12_000} min={20_000} id="budget" />);
    const reason = screen.getByText(/A run needs at least/);
    expect(reason).toHaveTextContent("Only 12.0k tokens left today. A run needs at least 20.0k; the budget resets at midnight UTC.");
    expect(reason).toHaveAttribute("id", "budget");
  });

  it("renders the minimum it is given", () => {
    render(<TokenBudget left={40_000} min={50_000} />);
    expect(screen.getByText(/A run needs at least/)).toHaveTextContent("A run needs at least 50.0k;");
  });

  it("blocks starting below the minimum only, defaulting to 20,000", () => {
    expect(budgetBlocked(19_999)).toBe(true);
    expect(budgetBlocked(20_000)).toBe(false);
    expect(budgetBlocked(49_999, 50_000)).toBe(true);
    expect(budgetBlocked(50_000, 50_000)).toBe(false);
  });

  it("has a labelled info button that reveals where the cap comes from", async () => {
    render(<TokenBudget left={1_600_000} />);
    const info = screen.getByRole("button", { name: "About the token budget" });
    expect(info).toHaveAttribute("aria-expanded", "false");
    const details = screen.getByText(/not a Groq limit/);
    expect(info).toHaveAttribute("aria-controls", details.id);
    expect(details).not.toBeVisible();
    await userEvent.setup().click(info);
    expect(info).toHaveAttribute("aria-expanded", "true");
    expect(details).toBeVisible();
    expect(details).toHaveTextContent(
      "Set by DAILY_TOKEN_BUDGET in .env and reset at midnight UTC. This is the app's own cap, not a Groq limit.",
    );
  });
});
