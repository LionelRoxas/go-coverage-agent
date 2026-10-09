// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
"use client";
import { useRef, type ReactNode } from "react";

export type TabItem<T extends string> = { id: T; label: ReactNode };

/** Ids that tie a tab to its panel: the caller renders the active panel with `role="tabpanel"` and these ids. */
export const tabIds = (prefix: string, id: string) => ({ tab: `${prefix}tab-${id}`, panel: `${prefix}panel-${id}` });

/**
 * A tablist with an accent underline on the active tab. Arrow keys, Home and End move the selection and the focus
 * (automatic activation); only the active tab is in the tab order.
 */
export function Tabs<T extends string>({ label, tabs, value, onChange, idPrefix = "" }: {
  label: string; tabs: readonly TabItem<T>[]; value: T; onChange: (id: T) => void; idPrefix?: string;
}) {
  const refs = useRef<Partial<Record<T, HTMLButtonElement | null>>>({});

  function onKeyDown(e: React.KeyboardEvent) {
    const i = tabs.findIndex((t) => t.id === value);
    let next = -1;
    if (e.key === "ArrowRight") next = (i + 1) % tabs.length;
    else if (e.key === "ArrowLeft") next = (i - 1 + tabs.length) % tabs.length;
    else if (e.key === "Home") next = 0;
    else if (e.key === "End") next = tabs.length - 1;
    if (next < 0) return;
    e.preventDefault();
    onChange(tabs[next].id);
    refs.current[tabs[next].id]?.focus();
  }

  return (
    <div role="tablist" aria-label={label} onKeyDown={onKeyDown} className="flex gap-1 border-b border-border">
      {tabs.map((t) => {
        const active = t.id === value;
        const ids = tabIds(idPrefix, t.id);
        return (
          <button key={t.id} ref={(el) => { refs.current[t.id] = el; }} type="button" role="tab" id={ids.tab}
                  aria-selected={active} aria-controls={active ? ids.panel : undefined} tabIndex={active ? 0 : -1}
                  onClick={() => onChange(t.id)}
                  className={`relative -mb-px px-3 py-2 text-sm transition-colors ${active ? "font-medium text-text" : "text-muted hover:text-text"}`}>
            {t.label}
            {active && <span aria-hidden className="absolute inset-x-2 bottom-0 h-0.5 rounded-full bg-accent" />}
          </button>
        );
      })}
    </div>
  );
}
