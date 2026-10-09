// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
"use client";
import { useRef, useState } from "react";
import type { RepoInfo, Sample } from "@/lib/types";
import { FolderUpload, type UploadFn } from "./FolderUpload";

export type PickerTab = "samples" | "folders";
const TABS: { id: PickerTab; label: string }[] = [
  { id: "samples", label: "Sample repos" },
  { id: "folders", label: "Your folders" },
];

const ENV_LINE = "HOST_REPOS_DIR=C:\\Users\\you\\code";

type Props = {
  tab: PickerTab;
  onTabChange: (tab: PickerTab) => void;
  samples: Sample[];
  folders: RepoInfo[];
  value: string;
  onChange: (path: string) => void;
  /** Downloads a sample and resolves once it can be selected. Rejects with a readable message. */
  onDownload: (id: string) => Promise<void>;
  onRefresh: () => Promise<void>;
  /** Uploads a chosen folder's files; resolves once the new module is listed and selected. */
  onUpload: UploadFn;
  hostDir: string | null;
  samplesFailed?: boolean;
};

const cardCls = (selected: boolean) =>
  `relative flex w-full flex-col gap-1.5 rounded-sm border px-3 py-2.5 text-left text-sm transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${
    selected ? "border-accent bg-surface shadow-[inset_3px_0_0_var(--accent)]" : "border-border hover:border-accent hover:bg-surface"
  }`;

function Spinner() {
  return <span aria-hidden className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-border border-t-accent" />;
}

function SampleCard({ sample, selected, busy, anyBusy, error, onPick }: {
  sample: Sample; selected: boolean; busy: boolean; anyBusy: boolean; error: string | null; onPick: () => void;
}) {
  return (
    <li>
      <button type="button" onClick={onPick} disabled={anyBusy} aria-busy={busy} aria-pressed={selected} className={cardCls(selected)}>
        <span className="flex items-start justify-between gap-2">
          <span className="min-w-0 break-all font-mono text-sm font-medium">{sample.name}</span>
          {busy ? (
            <span className="inline-flex shrink-0 items-center gap-1.5 text-xs text-muted"><Spinner />Downloading…</span>
          ) : (
            <span className={`shrink-0 rounded-full border px-2 py-0.5 text-xs ${sample.downloaded ? "border-accent text-accent" : "border-border text-muted"}`}>
              {sample.downloaded ? "Ready" : "Download"}
            </span>
          )}
        </span>
        <span className="text-xs leading-snug text-muted">{sample.description}</span>
        <span className="font-mono text-xs text-muted">{sample.license}{sample.ref ? ` · ${sample.ref}` : ""}</span>
        {error && <span role="alert" className="text-xs text-danger">{error}</span>}
      </button>
    </li>
  );
}

function CopyLine({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      setCopied(false);
    }
  }
  return (
    <div className="flex items-center gap-2 rounded-sm border border-border bg-bg px-2 py-1.5">
      <code className="min-w-0 flex-1 overflow-x-auto whitespace-nowrap font-mono text-xs">{text}</code>
      <button type="button" onClick={copy} className="shrink-0 rounded-sm border border-border px-2 py-0.5 text-xs hover:border-accent hover:text-accent">
        {copied ? "Copied" : "Copy"}
      </button>
    </div>
  );
}

export function RepoPicker({ tab, onTabChange, samples, folders, value, onChange, onDownload, onRefresh, onUpload, hostDir, samplesFailed }: Props) {
  const [downloading, setDownloading] = useState<string | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [refreshing, setRefreshing] = useState(false);
  const tabRefs = useRef<Record<PickerTab, HTMLButtonElement | null>>({ samples: null, folders: null });

  async function pick(s: Sample) {
    if (downloading) return;
    if (s.downloaded) {
      onChange(s.path);
      return;
    }
    setDownloading(s.id);
    setErrors((cur) => Object.fromEntries(Object.entries(cur).filter(([k]) => k !== s.id)));
    try {
      await onDownload(s.id);
    } catch (e) {
      setErrors((cur) => ({ ...cur, [s.id]: (e as Error).message }));
    } finally {
      setDownloading(null);
    }
  }

  async function refresh() {
    setRefreshing(true);
    try {
      await onRefresh();
    } finally {
      setRefreshing(false);
    }
  }

  function onKeyDown(e: React.KeyboardEvent) {
    const i = TABS.findIndex((t) => t.id === tab);
    let next = -1;
    if (e.key === "ArrowRight") next = (i + 1) % TABS.length;
    else if (e.key === "ArrowLeft") next = (i - 1 + TABS.length) % TABS.length;
    else if (e.key === "Home") next = 0;
    else if (e.key === "End") next = TABS.length - 1;
    if (next < 0) return;
    e.preventDefault();
    onTabChange(TABS[next].id);
    tabRefs.current[TABS[next].id]?.focus();
  }

  return (
    <div className="space-y-3">
      <div role="tablist" aria-label="Repository source" onKeyDown={onKeyDown} className="flex gap-1 border-b border-border">
        {TABS.map((t) => {
          const active = t.id === tab;
          return (
            <button key={t.id} ref={(el) => { tabRefs.current[t.id] = el; }} type="button" role="tab" id={`tab-${t.id}`}
                    aria-selected={active} aria-controls={active ? `panel-${t.id}` : undefined} tabIndex={active ? 0 : -1}
                    onClick={() => onTabChange(t.id)}
                    className={`relative -mb-px px-3 py-2 text-sm transition-colors ${active ? "font-medium text-text" : "text-muted hover:text-text"}`}>
              {t.label}
              {active && <span aria-hidden className="absolute inset-x-2 bottom-0 h-0.5 rounded-full bg-accent" />}
            </button>
          );
        })}
      </div>

      {tab === "samples" && (
        <div role="tabpanel" id="panel-samples" aria-labelledby="tab-samples" className="space-y-3">
          <p className="text-xs leading-relaxed text-muted">
            Small open-source Go libraries with no dependencies. Picking one downloads it into <code className="font-mono">./repos</code> the first time.
          </p>
          {samplesFailed && (
            <p role="status" className="rounded-sm border border-dashed border-border px-3 py-3 text-sm text-muted">
              Sample list unavailable (rebuild the backend?). Your folders still work.
            </p>
          )}
          <ul className="grid gap-2 sm:grid-cols-2">
            {samples.map((s) => (
              <SampleCard key={s.id} sample={s} selected={value === s.path} busy={downloading === s.id}
                          anyBusy={downloading !== null} error={errors[s.id] ?? null} onPick={() => void pick(s)} />
            ))}
          </ul>
        </div>
      )}

      {tab === "folders" && (
        <div role="tabpanel" id="panel-folders" aria-labelledby="tab-folders" className="space-y-4">
          <FolderUpload onUpload={onUpload} />
          <div className="flex items-center justify-between gap-3">
            <p className="text-xs text-muted">
              {hostDir ? <>Go modules in <code className="break-all font-mono text-text">{hostDir}</code></> : <>Go modules in <code className="font-mono text-text">./repos</code></>}
            </p>
            <button type="button" onClick={() => void refresh()} disabled={refreshing}
                    className="shrink-0 rounded-sm border border-border px-2.5 py-1 text-xs hover:border-accent hover:text-accent disabled:opacity-50">
              {refreshing ? "Refreshing…" : "Refresh"}
            </button>
          </div>
          {folders.length === 0 ? (
            <p className="rounded-sm border border-dashed border-border px-3 py-4 text-sm text-muted">
              No Go modules of your own yet. Upload a project folder above.
            </p>
          ) : (
            <ul className="grid gap-2 sm:grid-cols-2">
              {folders.map((r) => (
                <li key={r.path}>
                  <button type="button" onClick={() => onChange(r.path)} aria-pressed={value === r.path} className={cardCls(value === r.path)}>
                    <span className="break-all font-mono text-sm font-medium">{r.path}</span>
                    <span className="text-xs text-muted">
                      <span className="break-all font-mono">{r.module}</span>, {r.go_files} source files, {r.test_files} test files
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          <div className="space-y-1.5">
            <p className="text-xs leading-relaxed text-muted">
              For large projects or to keep a folder in sync, point <code className="font-mono">HOST_REPOS_DIR</code> in{" "}
              <code className="font-mono">.env</code> at its parent folder and run <code className="font-mono">make up</code> again.
            </p>
            <CopyLine text={ENV_LINE} />
          </div>
        </div>
      )}
    </div>
  );
}
