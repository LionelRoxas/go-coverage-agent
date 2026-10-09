// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
import type { HTMLAttributes } from "react";
import { cx } from "./classes";

export type CardTone = "default" | "danger" | "warn";
const TONE: Record<CardTone, string> = { default: "border-border", danger: "border-danger", warn: "border-warn" };

/** A container panel: one radius, border, surface fill and padding everywhere. */
export function cardClass({ tone = "default", padded = true }: { tone?: CardTone; padded?: boolean } = {}) {
  return cx("rounded-md border bg-surface", TONE[tone], padded && "p-4 sm:p-5");
}

type Props = HTMLAttributes<HTMLElement> & { as?: "div" | "section" | "aside" | "figure"; tone?: CardTone; padded?: boolean };

export function Card({ as: Tag = "div", tone, padded, className, ...rest }: Props) {
  return <Tag className={cx(cardClass({ tone, padded }), className)} {...rest} />;
}

/** A selectable or clickable tile inside a list (sample repos, folders, past runs). */
export function tileClass(selected = false) {
  return cx(
    "relative w-full rounded-md border px-3 py-2.5 text-left text-sm transition-[color,background-color,border-color]",
    "disabled:cursor-not-allowed disabled:opacity-60",
    selected ? "border-accent bg-surface shadow-[inset_3px_0_0_var(--accent)]" : "border-border bg-bg not-disabled:hover:border-accent",
  );
}
