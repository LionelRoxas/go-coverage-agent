// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createRef } from "react";
import { describe, expect, it, vi } from "vitest";
import {
  Badge, Button, buttonClass, Card, cardClass, codeBlockClass, cx, EmptyState, LoadingStatus, PageHeader,
  pageTitleClass, SectionHeading, Skeleton, statementTitleClass, staticTileClass, StatusChip, StatusPanel, tileClass,
} from "./index";

describe("Button", () => {
  it("is a type=button by default and runs its click handler", async () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Refresh</Button>);
    const b = screen.getByRole("button", { name: "Refresh" });
    expect(b).toHaveAttribute("type", "button");
    await userEvent.click(b);
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("hands its ref to the DOM button", () => {
    const ref = createRef<HTMLButtonElement>();
    render(<Button ref={ref}>Next</Button>);
    expect(ref.current).toBe(screen.getByRole("button", { name: "Next" }));
  });

  it("keeps an explicit submit type", () => {
    render(<Button type="submit" variant="primary">Start</Button>);
    expect(screen.getByRole("button", { name: "Start" })).toHaveAttribute("type", "submit");
  });

  it.each([
    ["primary", "bg-accent", "text-on-accent"],
    ["secondary", "border-border-strong", "bg-surface"],
    ["danger", "not-disabled:hover:text-danger", "not-disabled:hover:border-danger"],
    ["ghost", "border-transparent", "text-muted"],
    ["link", "text-accent", "not-disabled:hover:underline"],
  ] as const)("renders the %s variant", (variant, a, b) => {
    render(<Button variant={variant}>Go</Button>);
    expect(screen.getByRole("button", { name: "Go" })).toHaveClass(a, b);
  });

  it("has two sizes, and the link variant drops the box size", () => {
    expect(buttonClass({ size: "sm" })).toContain("h-7");
    expect(buttonClass({ size: "md" })).toContain("h-9");
    expect(buttonClass({ variant: "link" })).not.toMatch(/\bh-9\b|\bpx-4\b/);
  });

  it("looks unavailable when disabled, without fading the accent, and ignores clicks", async () => {
    const onClick = vi.fn();
    render(<Button variant="primary" disabled onClick={onClick}>Start</Button>);
    const b = screen.getByRole("button", { name: "Start" });
    expect(b).toBeDisabled();
    expect(b).toHaveClass("disabled:bg-border/60", "disabled:text-muted", "disabled:cursor-not-allowed");
    expect(b.className).not.toMatch(/opacity/);
    await userEvent.click(b);
    expect(onClick).not.toHaveBeenCalled();
  });

  it("takes keyboard focus; the ring comes from the global :focus-visible rule, which no variant turns off", async () => {
    render(<Button>Copy</Button>);
    await userEvent.tab();
    expect(screen.getByRole("button", { name: "Copy" })).toHaveFocus();
    for (const v of ["primary", "secondary", "danger", "ghost", "link"] as const) {
      expect(buttonClass({ variant: v })).not.toMatch(/outline-none|focus-visible:outline-0|focus:outline-none/);
      // the colour transition leaves outline-color out, so the ring never fades in from the text colour
      expect(buttonClass({ variant: v })).toContain("transition-[color,background-color,border-color]");
    }
  });

  it("gives elements without a disabled attribute the same unavailable look", () => {
    const cls = buttonClass({ variant: "primary", unavailable: true });
    expect(cls).toContain("pointer-events-none");
    expect(cls).toContain("text-muted");
    expect(cls).not.toContain("bg-accent");
  });

  it("merges extra classes", () => {
    render(<Button className="w-full">Wide</Button>);
    expect(screen.getByRole("button", { name: "Wide" })).toHaveClass("w-full", "rounded-sm");
  });
});

describe("Card and tiles", () => {
  it("renders the chosen element with the shared container recipe", () => {
    const { container } = render(<Card as="section" aria-label="Summary">x</Card>);
    const el = container.querySelector("section")!;
    expect(el).toHaveClass("rounded-md", "border", "border-border", "bg-surface", "p-4");
  });

  it("has danger and warn tones and an unpadded form", () => {
    expect(cardClass({ tone: "danger" })).toContain("border-danger");
    expect(cardClass({ tone: "warn" })).toContain("border-warn");
    expect(cardClass({ padded: false })).not.toContain("p-4");
  });

  it("marks a selected tile with the accent edge", () => {
    expect(tileClass(true)).toContain("shadow-[inset_3px_0_0_var(--accent)]");
    expect(tileClass(false)).toContain("not-disabled:hover:border-accent");
  });

  it("draws an unavailable tile flat instead of faded", () => {
    render(<button type="button" disabled className={tileClass()}>o/stats</button>);
    const tile = screen.getByRole("button", { name: "o/stats" });
    expect(tile.className).not.toMatch(/opacity/);
    expect(tile).toHaveClass("disabled:bg-border/30", "disabled:text-muted");
  });

  it("gives static tiles (placeholders, the running run) the same box and fill as tiles", () => {
    const box = ["rounded-md", "border", "px-3", "py-2.5", "border-border", "bg-bg"];
    for (const c of box) expect(tileClass().split(" ")).toContain(c);
    for (const c of box) expect(staticTileClass().split(" ")).toContain(c);
    expect(staticTileClass({ accent: true })).toContain("border-l-accent");
    expect(staticTileClass()).not.toContain("hover");
  });
});

describe("Badge and StatusChip", () => {
  it.each([
    ["running", "Running", "bg-accent"],
    ["completed", "Completed", "text-accent"],
    ["cancelled", "Cancelled", "text-muted"],
    ["failed", "Failed", "text-danger"],
  ] as const)("draws %s the same everywhere", (status, label, cls) => {
    render(<StatusChip status={status} />);
    expect(screen.getByText(label)).toHaveClass("rounded-full", "text-xs", "font-medium", cls);
  });

  it("defaults to the neutral tone", () => {
    render(<Badge>Ready</Badge>);
    expect(screen.getByText("Ready")).toHaveClass("border-border-strong", "text-muted");
  });

  it("passes HTML attributes through and has a mono option instead of class overrides", () => {
    render(<Badge mono title="Model" data-testid="m">openai/gpt-oss-120b</Badge>);
    const b = screen.getByTestId("m");
    expect(b).toHaveAttribute("title", "Model");
    expect(b).toHaveClass("font-mono", "font-normal");
    expect(b).not.toHaveClass("font-medium");
  });
});

describe("headings", () => {
  it("PageHeader renders one h1 and an optional lede", () => {
    render(<PageHeader title="New run" lede="Pick a project." />);
    expect(screen.getByRole("heading", { level: 1, name: "New run" })).toHaveClass("font-semibold", "tracking-tight");
    expect(screen.getByText("Pick a project.")).toHaveClass("text-muted");
  });

  it("the sentence-length title variant is one step below the page title", () => {
    expect(statementTitleClass).toContain("text-2xl");
    expect(pageTitleClass).toContain("text-[1.75rem]");
  });

  it("SectionHeading is an h2 at the app scale", () => {
    render(<SectionHeading id="x">Activity</SectionHeading>);
    const h = screen.getByRole("heading", { level: 2, name: "Activity" });
    expect(h).toHaveAttribute("id", "x");
    expect(h).toHaveClass("text-base", "font-semibold");
  });
});

describe("states", () => {
  it("Skeleton is hidden from assistive tech and LoadingStatus speaks for it", () => {
    const { container } = render(<><Skeleton className="h-4" /><LoadingStatus>Loading runs…</LoadingStatus></>);
    expect(container.querySelector("[data-skeleton]")).toHaveAttribute("aria-hidden");
    expect(screen.getByRole("status")).toHaveTextContent("Loading runs…");
  });

  it("EmptyState is a dashed muted box", () => {
    render(<EmptyState role="status">Nothing yet.</EmptyState>);
    expect(screen.getByRole("status")).toHaveClass("border-dashed", "text-muted");
  });

  it("StatusPanel gives the page its h1, the explanation and the actions; the danger tone is an alert", () => {
    render(<StatusPanel tone="danger" role="alert" title="Couldn't load this run" actions={<a href="#back">Back</a>}>boom</StatusPanel>);
    const panel = screen.getByRole("alert");
    expect(panel).toHaveClass("border-danger");
    expect(screen.getByRole("heading", { level: 1, name: "Couldn't load this run" })).toBeInTheDocument();
    expect(panel).toHaveTextContent("boom");
    expect(screen.getByRole("link", { name: "Back" })).toBeInTheDocument();
  });
});

describe("class helpers", () => {
  it("cx skips falsy parts", () => {
    expect(cx("a", false, null, undefined, "b")).toBe("a b");
  });
  it("code blocks share one recipe in two sizes", () => {
    expect(codeBlockClass()).toContain("text-xs");
    expect(codeBlockClass("md")).toContain("px-4");
    expect(codeBlockClass("sm")).toContain("rounded-md border border-border bg-surface");
  });
});
