// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
/** Shared class recipes for elements that are not worth a component of their own. */

/**
 * Joins class names, skipping falsy values. It does not resolve Tailwind conflicts: when two classes set the same
 * property at the same breakpoint, the order of the generated CSS decides, not their order here. So callers add
 * classes for properties the base recipe leaves open (margin, width, layout) and never override a base utility;
 * when a variant needs a different value, the primitive gets an option for it (e.g. Badge `mono`).
 */
export const cx = (...parts: (string | false | null | undefined)[]) => parts.filter(Boolean).join(" ");

/** Max width and side gutters shared by the navbar and every page. */
export const containerClass = "mx-auto w-full max-w-6xl px-4 sm:px-6 lg:px-8";

/** Text inputs and number fields. The --border-strong edge keeps the control's boundary at 3:1 or more. */
export const inputClass =
  "h-9 rounded-sm border border-border-strong bg-surface px-2.5 font-mono text-sm text-text disabled:cursor-not-allowed disabled:text-muted";

/** A link inside a sentence: always underlined, so it never relies on colour alone. */
export const inlineLinkClass = "text-accent underline underline-offset-4 hover:decoration-2";

/** A standalone action link ("Read more", "Back to How it works"): underlined on hover. */
export const actionLinkClass = "font-medium text-accent underline-offset-4 hover:underline";

/** "← All runs" and similar way-back links. */
export const backLinkClass = "inline-flex items-center gap-1 text-sm text-muted hover:text-accent";

/** Code and command output: "md" on reading pages, "sm" on app pages. */
export const codeBlockClass = (size: "sm" | "md" = "sm") =>
  cx("overflow-auto rounded-md border border-border bg-surface font-mono leading-relaxed",
     size === "md" ? "px-4 py-3 text-[0.78rem]" : "px-3 py-2.5 text-xs");
