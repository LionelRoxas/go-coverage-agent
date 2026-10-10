// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
"use client";
import { useState } from "react";
import type { RepoInfo, Sample, UploadLimits } from "@/lib/types";
import { FolderUpload, type UploadFn } from "./FolderUpload";
import { Badge, Button, EmptyState, LoadingStatus, Skeleton, staticTileClass, Tabs, tileClass } from "./ui";

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
  /** Upload limits reported by /api/health; the defaults are used when absent. */
  uploadLimits?: UploadLimits;
  hostDir: string | null;
  samplesFailed?: boolean;
  /** True until the first samples request settles: the samples tab shows placeholders. */
  loading?: boolean;
};

const cardCls = (selected: boolean) => `${tileClass(selected)} flex flex-col gap-1.5`;

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
            <Badge tone={sample.downloaded ? "accent" : "neutral"}>{sample.downloaded ? "Ready" : "Download"}</Badge>
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
    <div className="flex items-center gap-2 rounded-md border border-border bg-bg py-1 pl-2.5 pr-1">
      <code className="min-w-0 flex-1 overflow-x-auto whitespace-nowrap font-mono text-xs">{text}</code>
      <Button size="sm" onClick={copy}>{copied ? "Copied" : "Copy"}</Button>
    </div>
  );
}

export function RepoPicker({ tab, onTabChange, samples, folders, value, onChange, onDownload, onRefresh, onUpload, uploadLimits, hostDir, samplesFailed, loading = false }: Props) {
  const [downloading, setDownloading] = useState<string | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [refreshing, setRefreshing] = useState(false);

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

  return (
    <div className="space-y-3">
      <Tabs label="Repository source" tabs={TABS} value={tab} onChange={onTabChange} />

      {tab === "samples" && (
        <div role="tabpanel" id="panel-samples" aria-labelledby="tab-samples" className="space-y-3">
          {samplesFailed && (
            <EmptyState role="status">Sample list unavailable (rebuild the backend?). Your folders still work.</EmptyState>
          )}
          {loading && (
            <div data-testid="samples-loading" className="grid gap-2 sm:grid-cols-2">
              <LoadingStatus>Loading sample repositories…</LoadingStatus>
              {[0, 1, 2, 3].map((i) => (
                <div key={i} aria-hidden className={`space-y-2 ${staticTileClass()}`}>
                  <span className="flex justify-between gap-4"><Skeleton className="h-4 w-36" /><Skeleton className="h-4 w-12 rounded-full" /></span>
                  <Skeleton className="h-3 w-44" />
                  <Skeleton className="h-3 w-20" />
                </div>
              ))}
            </div>
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
          <FolderUpload onUpload={onUpload} limits={uploadLimits} />
          <div className="flex items-center justify-between gap-3">
            <p className="text-xs text-muted">
              {hostDir ? <>Go modules in <code className="break-all font-mono text-text">{hostDir}</code></> : <>Go modules in <code className="font-mono text-text">./repos</code></>}
            </p>
            <Button size="sm" onClick={() => void refresh()} disabled={refreshing}>
              {refreshing ? "Refreshing…" : "Refresh"}
            </Button>
          </div>
          {folders.length === 0 ? (
            <EmptyState>No Go modules of your own yet. Upload a project folder above.</EmptyState>
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
