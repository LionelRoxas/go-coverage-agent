// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
"use client";
import { useState } from "react";
import { ApiError } from "@/lib/api";
import type { UploadResult } from "@/lib/types";
import {
  describeSkips, formatMB, foundFromDrop, foundFromInput, prepare, type FoundFile, type PickedFile, type Prepared,
} from "@/lib/upload";

export type UploadFn = (files: PickedFile[], name: string | undefined, onProgress: (fraction: number) => void) => Promise<UploadResult>;

type State =
  | { kind: "idle" }
  | { kind: "reading" }
  | { kind: "uploading"; count: number; bytes: number; progress: number | null }
  | { kind: "done"; text: string }
  | { kind: "error"; text: string; retry?: Prepared };

const NAME_CODES = new Set(["name_taken", "invalid_name"]);
const toName = (s: string) => s.toLowerCase().replace(/[^a-z0-9._-]+/g, "-").replace(/^[-.]+|[-.]+$/g, "");

export function FolderUpload({ onUpload }: { onUpload: UploadFn }) {
  const [state, setState] = useState<State>({ kind: "idle" });
  const [over, setOver] = useState(false);
  const [rename, setRename] = useState("");
  const busy = state.kind === "reading" || state.kind === "uploading";

  async function send(p: Prepared, name?: string) {
    setState({ kind: "uploading", count: p.files.length, bytes: p.bytes, progress: null });
    try {
      const r = await onUpload(p.files, name, (progress) =>
        setState((s) => (s.kind === "uploading" ? { ...s, progress } : s)));
      const skips = describeSkips(p.skipped, r.skipped);
      const go = r.go_files + r.test_files;
      setState({ kind: "done", text: `Uploaded ${r.path.split("/").pop()} (${go} Go ${go === 1 ? "file" : "files"}).${skips ? ` Skipped: ${skips}.` : ""}` });
    } catch (e) {
      const err = e as Error;
      if (e instanceof ApiError && NAME_CODES.has(e.code)) {
        setRename(e.code === "name_taken" ? `${toName(name ?? p.name) || "project"}-2` : (name ?? ""));
        setState({ kind: "error", text: err.message, retry: p });
      } else {
        setState({ kind: "error", text: err.message });
      }
    }
  }

  async function start(found: () => Promise<FoundFile[]> | FoundFile[]) {
    setState({ kind: "reading" });
    let p: Prepared;
    try {
      p = await prepare(await found());
    } catch (e) {
      setState({ kind: "error", text: (e as Error).message });
      return;
    }
    await send(p);
  }

  function onDrop(e: React.DragEvent) {
    e.preventDefault();
    setOver(false);
    if (busy) return;
    const items = e.dataTransfer.items;
    // webkitGetAsEntry only works during the drop event, so foundFromDrop reads the entries synchronously first.
    const found = foundFromDrop(items);
    void start(() => found);
  }

  return (
    <div onDragOver={(e) => { e.preventDefault(); if (!busy) setOver(true); }} onDragLeave={() => setOver(false)} onDrop={onDrop}
         data-testid="folder-drop" data-over={over || undefined}
         className={`space-y-3 rounded-sm border-2 px-4 py-4 transition-colors ${
           over ? "border-solid border-accent bg-surface" : "border-dashed border-border"}`}>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <label className={`inline-flex cursor-pointer items-center rounded-sm bg-accent px-3 py-1.5 text-sm font-medium text-bg focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-accent ${
          busy ? "pointer-events-none opacity-50" : "hover:opacity-90"}`}>
          Choose a folder…
          <input type="file" multiple disabled={busy} className="sr-only" data-testid="folder-input"
                 ref={(el) => { if (el) el.webkitdirectory = true; }}
                 onChange={(e) => {
                   const list = Array.from(e.target.files ?? []);
                   e.target.value = "";
                   if (list.length) void start(() => foundFromInput(list));
                 }} />
        </label>
        <span className="text-sm text-muted">or drag the project folder here</span>
      </div>
      <p className="text-xs leading-relaxed text-muted">
        Your files are copied into the app&apos;s repos folder; your original folder is never changed. Re-upload to refresh.
      </p>

      {state.kind === "reading" && <p role="status" className="text-sm text-muted">Reading the folder…</p>}
      {state.kind === "uploading" && (
        <div role="status" className="space-y-1.5">
          <p className="text-sm">Uploading {state.count.toLocaleString("en-US")} {state.count === 1 ? "file" : "files"} ({formatMB(state.bytes)})…</p>
          <div role="progressbar" aria-label="Upload progress" aria-valuemin={0} aria-valuemax={100}
               aria-valuenow={state.progress == null ? undefined : Math.round(state.progress * 100)}
               className="h-1 overflow-hidden rounded-full bg-border">
            <div className={`h-full bg-accent transition-[width] ${state.progress == null ? "w-full animate-pulse" : ""}`}
                 style={state.progress == null ? undefined : { width: `${Math.round(state.progress * 100)}%` }} />
          </div>
        </div>
      )}
      {state.kind === "done" && <p role="status" className="text-sm">{state.text}</p>}
      {state.kind === "error" && (
        <div className="space-y-2">
          <p role="alert" className="text-sm text-danger">{state.text}</p>
          {state.retry && (
            <form className="flex flex-wrap items-center gap-2"
                  onSubmit={(e) => { e.preventDefault(); if (rename.trim()) void send(state.retry!, rename.trim()); }}>
              <label htmlFor="upload-name" className="text-xs text-muted">Upload as</label>
              <input id="upload-name" value={rename} onChange={(e) => setRename(e.target.value)} maxLength={64}
                     className="min-w-0 flex-1 rounded-sm border border-border bg-bg px-2 py-1 font-mono text-sm" />
              <button type="submit" disabled={!rename.trim()}
                      className="rounded-sm border border-accent px-2.5 py-1 text-xs text-accent hover:bg-surface disabled:opacity-50">
                Rename and upload
              </button>
            </form>
          )}
        </div>
      )}
    </div>
  );
}
