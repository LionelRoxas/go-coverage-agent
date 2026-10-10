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

const TILE_BOX = "rounded-md border px-3 py-2.5 text-sm";

/**
 * A tile that is not a control: the running-run card and the loading placeholders for tiles. Same box and fill as
 * tileClass, so a list keeps its look when it loads. `accent` adds the 4 px accent edge of a running run.
 */
export function staticTileClass({ accent = false }: { accent?: boolean } = {}) {
  return cx(TILE_BOX, "border-border bg-bg", accent && "border-l-4 border-l-accent");
}

/**
 * A selectable or clickable tile inside a list (sample repos, folders, past runs). Unavailable tiles go flat (muted
 * fill and text) rather than fading, like disabled buttons.
 */
export function tileClass(selected = false) {
  return cx(
    "relative w-full text-left transition-[color,background-color,border-color]", TILE_BOX,
    "disabled:cursor-not-allowed disabled:bg-border/30 disabled:text-muted",
    selected ? "border-accent bg-surface shadow-[inset_3px_0_0_var(--accent)]" : "border-border bg-bg not-disabled:hover:border-accent",
  );
}
