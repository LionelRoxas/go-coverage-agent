// AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

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
  if (files.length === 0) return <p className="text-sm text-muted">No tests were accepted.</p>;
  return (
    <div className="grid gap-4 md:grid-cols-[14rem_1fr]">
      <ul className="space-y-1 font-mono text-sm">
        {files.map((f) => (
          <li key={f}>
            <button type="button" onClick={() => setActive(f)} aria-current={f === active}
                    className={`w-full truncate rounded px-2 py-1 text-left ${f === active ? "bg-surface text-text" : "text-muted hover:text-text"}`}>
              {f}
            </button>
          </li>
        ))}
      </ul>
      <div className="min-w-0 overflow-auto rounded-md border border-border text-xs [&_pre]:p-4">
        {current?.error ? <p role="alert" className="p-4 text-danger">{current.error}</p>
          : current?.html ? <div dangerouslySetInnerHTML={{ __html: current.html }} />
          : <p className="p-4 text-muted">Loading…</p>}
      </div>
    </div>
  );
}
