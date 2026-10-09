// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
"use client";
import { useEffect, useState } from "react";

export const THEME_KEY = "gca-theme";
type Theme = "system" | "light" | "dark";
const OPTIONS: { value: Theme; label: string }[] = [
  { value: "system", label: "System" },
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
];

function readStored(): Theme {
  try {
    const v = localStorage.getItem(THEME_KEY);
    return v === "light" || v === "dark" ? v : "system";
  } catch {
    return "system";
  }
}

function apply(theme: Theme) {
  if (theme === "system") delete document.documentElement.dataset.theme;
  else document.documentElement.dataset.theme = theme;
}

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>("system");

  // The pre-paint script already applied the stored theme; this only syncs the control's state.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setTheme(readStored());
  }, []);

  function choose(next: Theme) {
    setTheme(next);
    apply(next);
    try {
      if (next === "system") localStorage.removeItem(THEME_KEY);
      else localStorage.setItem(THEME_KEY, next);
    } catch {
      /* storage unavailable: the choice still applies for this page view */
    }
  }

  return (
    <div role="group" aria-label="Theme" className="inline-flex rounded-sm border border-border bg-surface p-0.5 text-xs">
      {OPTIONS.map((o) => (
        <button key={o.value} type="button" aria-pressed={theme === o.value} onClick={() => choose(o.value)}
                className="rounded-[3px] px-2 py-1 text-muted hover:text-text aria-pressed:bg-accent aria-pressed:text-on-accent">
          {o.label}
        </button>
      ))}
    </div>
  );
}
