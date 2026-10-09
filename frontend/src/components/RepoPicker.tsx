// AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
"use client";
import type { RepoInfo } from "@/lib/types";

type Props = {
  repos: RepoInfo[];
  value: string;
  onChange: (path: string) => void;
  onUseSample: () => void;
  cloning: boolean;
};

export function RepoPicker({ repos, value, onChange, onUseSample, cloning }: Props) {
  return (
    <fieldset className="space-y-3">
      <legend className="mb-2 text-sm font-medium">Repository</legend>
      {repos.length === 0 && (
        <p className="text-sm text-muted">
          No Go modules found in <code className="font-mono">./repos</code>. Clone one there, or use the sample.
        </p>
      )}
      <div className="grid gap-2 sm:grid-cols-2">
        {repos.map((r) => (
          <label
            key={r.path}
            className={`cursor-pointer rounded-sm border px-3 py-2 text-sm has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-accent ${
              value === r.path ? "border-accent bg-surface shadow-[inset_3px_0_0_var(--accent)]" : "border-border hover:bg-surface"
            }`}
          >
            <input type="radio" name="repo" className="sr-only" checked={value === r.path} onChange={() => onChange(r.path)} />
            <span className="block break-all font-mono">{r.path}</span>
            <span className="block text-xs text-muted">
              <span className="font-mono">{r.module}</span>, {r.go_files} source files, {r.test_files} test files
            </span>
          </label>
        ))}
      </div>
      <button
        type="button"
        onClick={onUseSample}
        disabled={cloning}
        className="text-sm text-accent underline underline-offset-4 disabled:opacity-50"
      >
        {cloning ? "Cloning montanaflynn/stats…" : "Use sample repo (montanaflynn/stats)"}
      </button>
      <label className="block space-y-1 text-sm">
        <span className="block text-muted">
          Or type a path inside <code className="font-mono">./repos</code>
        </span>
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="stats"
          spellCheck={false}
          autoCapitalize="none"
          className="w-full max-w-md rounded-sm border border-border bg-surface px-2 py-1.5 font-mono"
        />
      </label>
    </fieldset>
  );
}
