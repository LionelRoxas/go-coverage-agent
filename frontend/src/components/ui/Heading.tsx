// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
import type { ReactNode } from "react";
import { cx } from "./classes";

/** Every page's h1. */
export const pageTitleClass = "text-[1.75rem] font-semibold leading-tight tracking-tight sm:text-[2.25rem]";
/** The paragraph under a page title. */
export const ledeClass = "max-w-[42rem] text-lg leading-relaxed text-muted";
/** h2 on app pages (New run steps, run page sections, Run history). */
export const sectionHeadingClass = "text-base font-semibold leading-6";
/** h2 on reading pages (How it works, Walkthrough). */
export const readingHeadingClass = "text-xl font-semibold tracking-tight sm:text-2xl";

export function PageHeader({ title, lede, className, titleClassName, children }: {
  title: ReactNode; lede?: ReactNode; className?: string; titleClassName?: string; children?: ReactNode;
}) {
  return (
    <header className={cx("min-w-0 space-y-4", className)}>
      <h1 className={cx(pageTitleClass, titleClassName)}>{title}</h1>
      {lede && <p className={ledeClass}>{lede}</p>}
      {children}
    </header>
  );
}

export function SectionHeading({ id, className, children }: { id?: string; className?: string; children: ReactNode }) {
  return <h2 id={id} className={cx(sectionHeadingClass, className)}>{children}</h2>;
}
