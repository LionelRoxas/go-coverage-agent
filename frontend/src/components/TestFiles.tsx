// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { EmptyState, LoadingStatus, Skeleton } from "./ui";

export function TestFiles({ jobId, files }: { jobId: string; files: string[] }) {
  const [active, setActive] = useState(files[0]);
  // Result is keyed by the file it belongs to, so switching files never shows stale code or errors.
  const [result, setResult] = useState<{ key: string; html?: string; error?: string } | null>(null);
  const key = `${jobId}/${active}`;

  useEffect(() => {
    if (!active) return;
    let stale = false;
    (async () => {
      try {
        const code = await api.file(jobId, active);
        const { codeToHtml } = await import("shiki");
        const out = await codeToHtml(code, { lang: "go", themes: { light: "github-light", dark: "github-dark" } });
        if (!stale) setResult({ key, html: out });
      } catch (e) {
        if (!stale) setResult({ key, error: (e as Error).message });
      }
    })();
    return () => { stale = true; };
  }, [jobId, active, key]);

  const current = result?.key === key ? result : null;
  if (files.length === 0) return <EmptyState>No tests were accepted.</EmptyState>;
  return (
    <div className="grid gap-4 md:grid-cols-[14rem_1fr]">
      {/* Below md the list sits above the code, so it scrolls in its own box instead of pushing the code a screen down. */}
      <ul className="max-h-48 space-y-1 overflow-y-auto font-mono text-sm md:max-h-none md:overflow-visible">
        {files.map((f) => (
          <li key={f}>
            <button type="button" onClick={() => setActive(f)} aria-current={f === active}
                    className={`w-full truncate rounded-sm px-2 py-1 text-left ${f === active ? "bg-surface text-text shadow-[inset_2px_0_0_var(--accent)]" : "text-muted hover:text-text"}`}>
              {f}
            </button>
          </li>
        ))}
      </ul>
      <div className="min-w-0 overflow-auto rounded-md border border-border bg-surface text-xs [&_pre]:p-4">
        {current?.error ? <p role="alert" className="p-4 text-danger">{current.error}</p>
          : current?.html ? <div dangerouslySetInnerHTML={{ __html: current.html }} />
          : (
            <div data-testid="code-loading" className="space-y-2.5 p-4">
              <LoadingStatus>Loading the test file…</LoadingStatus>
              {[40, 64, 52, 72, 30, 58, 46].map((w, i) => <Skeleton key={i} className="h-3" style={{ width: `${w}%` }} />)}
            </div>
          )}
      </div>
    </div>
  );
}
