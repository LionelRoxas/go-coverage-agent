// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
import type { ComponentPropsWithRef } from "react";
import { cx } from "./classes";

export type ButtonVariant = "primary" | "secondary" | "danger" | "ghost" | "link";
export type ButtonSize = "sm" | "md";

const BASE =
  "inline-flex shrink-0 items-center justify-center gap-1.5 whitespace-nowrap rounded-sm border font-medium " +
  "transition-[color,background-color,border-color] disabled:cursor-not-allowed";
const SIZE: Record<ButtonSize, string> = { sm: "h-7 px-2.5 text-xs", md: "h-9 px-4 text-sm" };
// Disabled buttons go flat grey with a muted label (5:1 in both themes) instead of fading the accent; with no edge
// they can't be mistaken for an enabled secondary button.
const UNAVAILABLE = "border-transparent bg-border/60 text-muted";
const DISABLED = "disabled:border-transparent disabled:bg-border/60 disabled:text-muted";
const VARIANT: Record<ButtonVariant, string> = {
  primary: `border-transparent bg-accent text-on-accent not-disabled:hover:bg-accent/90 ${DISABLED}`,
  secondary: `border-border-strong bg-surface text-text not-disabled:hover:border-accent not-disabled:hover:text-accent ${DISABLED}`,
  // Cancel and similar: quiet until hovered, then the danger colour says what it does.
  danger: `border-border-strong bg-surface text-text not-disabled:hover:border-danger not-disabled:hover:text-danger ${DISABLED}`,
  ghost: "border-transparent text-muted not-disabled:hover:bg-surface not-disabled:hover:text-text disabled:text-muted",
  link: "border-transparent text-accent underline-offset-4 not-disabled:hover:underline disabled:text-muted",
};

/**
 * Classes for a button, or for a Link (or a file-input label) that should look like one. "link" keeps only the
 * size's text size. `unavailable` gives the disabled look to elements that have no disabled attribute.
 */
export function buttonClass({ variant = "secondary", size = "md", unavailable = false }:
  { variant?: ButtonVariant; size?: ButtonSize; unavailable?: boolean } = {}) {
  const box = variant === "link" ? (size === "sm" ? "text-xs" : "text-sm") : SIZE[size];
  if (unavailable) return cx(BASE, box, "pointer-events-none cursor-not-allowed", variant === "link" ? "border-transparent text-muted" : UNAVAILABLE);
  return cx(BASE, box, VARIANT[variant]);
}

/** Every native button prop, `ref` included (React 19 passes it through as a prop). */
type Props = ComponentPropsWithRef<"button"> & { variant?: ButtonVariant; size?: ButtonSize };

export function Button({ variant, size, className, type = "button", ...rest }: Props) {
  return <button type={type} className={cx(buttonClass({ variant, size }), className)} {...rest} />;
}
