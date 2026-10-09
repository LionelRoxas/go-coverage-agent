// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
import type { CSSProperties } from "react";
import { cx } from "./classes";

/** A grey placeholder block. Hidden from screen readers: pair it with a LoadingStatus. */
export function Skeleton({ className = "", style }: { className?: string; style?: CSSProperties }) {
  // A caller's own rounded-* replaces the default corner rather than competing with it.
  return (
    <span aria-hidden data-skeleton style={style}
          className={cx("block animate-pulse bg-border/70", !/(^|\s)rounded/.test(className) && "rounded-sm", className)} />
  );
}

/** The text a screen reader announces while skeletons are on screen. */
export function LoadingStatus({ children }: { children: string }) {
  return <p role="status" className="sr-only">{children}</p>;
}
