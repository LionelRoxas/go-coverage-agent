// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CoverageMeter } from "./CoverageMeter";

describe("CoverageMeter", () => {
  it("exposes the percent and target as an accessible meter", () => {
    render(<CoverageMeter percent={42.34} target={80} baseline={10} />);
    const meter = screen.getByRole("meter", { name: /target 80\.0%/ });
    expect(meter).toHaveAttribute("aria-valuenow", "42.3");
    expect(meter).toHaveAttribute("aria-valuemin", "0");
    expect(meter).toHaveAttribute("aria-valuemax", "100");
    expect(screen.getByText(/baseline 10\.0%/)).toBeInTheDocument();
  });
});
