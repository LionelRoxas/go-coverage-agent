// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
// Client-side pre-filter for folder uploads. It mirrors the backend's rules (backend/app/uploads.py) so large
// folders are stopped before anything is sent; the backend re-checks everything and is authoritative.
import type { SkipCounts, SkipReason } from "./types";

export const UPLOAD_MAX_FILES = 3000;
export const UPLOAD_MAX_BYTES = 25 * 1024 * 1024;
export const UPLOAD_MAX_FILE_BYTES = 1024 * 1024;

const SKIP_DIRS: Record<string, SkipReason> = { ".git": "git", vendor: "vendor", node_modules: "node_modules" };

export type PickedFile = { path: string; file: File };
/** A file found in the chosen folder; `load` is only called for files whose path is kept. */
export type FoundFile = { path: string; load: () => Promise<File> };

export type Prepared = { name: string; files: PickedFile[]; bytes: number; skipped: SkipCounts };

export class PrepareError extends Error {}

export const emptySkips = (): SkipCounts => ({ git: 0, vendor: 0, node_modules: 0, hidden: 0, too_large: 0, binary: 0 });

/** Why a path ("myproj/pkg/a.go") is skipped, judged on the parts below the chosen folder; null keeps it. */
export function pathSkipReason(path: string): SkipReason | null {
  const rel = path.split("/").slice(1);
  for (const dir of rel.slice(0, -1)) if (dir in SKIP_DIRS) return SKIP_DIRS[dir];
  return rel.some((p) => p.startsWith(".")) ? "hidden" : null;
}

export const formatMB = (bytes: number) => `${(bytes / (1024 * 1024)).toFixed(bytes < 1024 * 1024 ? 2 : 1)} MB`;

export async function prepare(found: FoundFile[]): Promise<Prepared> {
  if (found.length === 0) throw new PrepareError("That folder is empty. Pick the folder that contains go.mod.");
  const name = found[0].path.split("/")[0];
  const skipped = emptySkips();
  const files: PickedFile[] = [];
  let bytes = 0;
  for (const f of found) {
    const reason = pathSkipReason(f.path);
    if (reason) {
      skipped[reason]++;
      continue;
    }
    const file = await f.load();
    if (file.size > UPLOAD_MAX_FILE_BYTES) {
      skipped.too_large++;
      continue;
    }
    files.push({ path: f.path, file });
    bytes += file.size;
  }
  if (!files.some((f) => f.path === `${name}/go.mod`)) {
    throw new PrepareError("No go.mod at the top of the folder you chose. Pick the folder that contains go.mod.");
  }
  if (files.length > UPLOAD_MAX_FILES || bytes > UPLOAD_MAX_BYTES) {
    throw new PrepareError(
      `${name} has ${files.length.toLocaleString("en-US")} files (${formatMB(bytes)}) after skipping .git, vendor, node_modules, ` +
      `hidden files and files over 1 MB. The upload limit is ${UPLOAD_MAX_FILES.toLocaleString("en-US")} files and 25 MB; ` +
      "for large projects, set HOST_REPOS_DIR in .env instead.");
  }
  return { name, files, bytes, skipped };
}

/** Files from <input type="file" webkitdirectory>: webkitRelativePath already starts with the folder name. */
export function foundFromInput(list: FileList | File[]): FoundFile[] {
  return Array.from(list).map((file) => ({ path: file.webkitRelativePath || file.name, load: async () => file }));
}

function readBatch(reader: FileSystemDirectoryReader): Promise<FileSystemEntry[]> {
  return new Promise((resolve, reject) => reader.readEntries(resolve, reject));
}

async function walk(entry: FileSystemEntry, out: FoundFile[]): Promise<void> {
  if (entry.isFile) {
    const fileEntry = entry as FileSystemFileEntry;
    out.push({
      path: entry.fullPath.replace(/^\/+/, ""),
      load: () => new Promise<File>((resolve, reject) => fileEntry.file(resolve, reject)),
    });
    return;
  }
  if (!entry.isDirectory) return;
  const reader = (entry as FileSystemDirectoryEntry).createReader();
  // readEntries returns at most ~100 entries per call; keep reading until it returns none.
  for (let batch = await readBatch(reader); batch.length > 0; batch = await readBatch(reader)) {
    for (const child of batch) await walk(child, out);
  }
}

/** Files from a drop: exactly one folder, read recursively. */
export async function foundFromDrop(items: DataTransferItemList): Promise<FoundFile[]> {
  const entries = Array.from(items)
    .filter((i) => i.kind === "file")
    .map((i) => i.webkitGetAsEntry())
    .filter((e): e is FileSystemEntry => e !== null);
  if (entries.length !== 1 || !entries[0].isDirectory) {
    throw new PrepareError("Drop one project folder (the folder that contains go.mod), not single files.");
  }
  const out: FoundFile[] = [];
  await walk(entries[0], out);
  return out;
}

const SKIP_TEXT: Record<SkipReason, (n: number) => string> = {
  git: (n) => `${n} ${n === 1 ? "file" : "files"} in .git`,
  vendor: (n) => `${n} in vendor`,
  node_modules: (n) => `${n} in node_modules`,
  hidden: (n) => `${n} hidden ${n === 1 ? "file" : "files"}`,
  too_large: (n) => `${n} ${n === 1 ? "file" : "files"} over 1 MB`,
  binary: (n) => `${n} ${n === 1 ? "binary" : "binaries"}`,
};

/** "120 files in .git, 3 binaries", or "" when nothing was skipped. */
export function describeSkips(...counts: SkipCounts[]): string {
  const total = emptySkips();
  for (const c of counts) for (const k of Object.keys(total) as SkipReason[]) total[k] += c[k] ?? 0;
  return (Object.keys(total) as SkipReason[]).filter((k) => total[k] > 0).map((k) => SKIP_TEXT[k](total[k])).join(", ");
}
