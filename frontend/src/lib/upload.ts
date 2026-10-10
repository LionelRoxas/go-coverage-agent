// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
// Client-side pre-filter for folder uploads. It mirrors the backend's rules (backend/app/uploads.py) so large
// folders are stopped before anything is sent; the backend re-checks everything and is authoritative.
import type { SkipCounts, SkipReason, UploadLimits } from "./types";

/** The backend's defaults; /api/health reports the configured values (UPLOAD_MAX_*). */
export const DEFAULT_UPLOAD_LIMITS: UploadLimits = { max_files: 3000, max_bytes: 25 * 1024 * 1024, max_file_bytes: 1024 * 1024 };

const SKIP_DIRS: Record<string, SkipReason> = { ".git": "git", vendor: "vendor", node_modules: "node_modules" };

export type PickedFile = { path: string; file: File };
/** A file found in the chosen folder; `load` is only called for files whose path is kept. */
export type FoundFile = { path: string; load: () => Promise<File> };
/** What was found in the chosen folder; `skippedFolders` counts folders a drop did not read at all. */
export type Found = { files: FoundFile[]; skippedFolders: SkipCounts };

export type Prepared = { name: string; files: PickedFile[]; bytes: number; skipped: SkipCounts; skippedFolders: SkipCounts };

export class PrepareError extends Error {}

export const emptySkips = (): SkipCounts => ({ git: 0, vendor: 0, node_modules: 0, hidden: 0, too_large: 0, binary: 0 });

/** Why a path ("myproj/pkg/a.go") is skipped, judged on the parts below the chosen folder; null keeps it. */
export function pathSkipReason(path: string): SkipReason | null {
  const rel = path.split("/").slice(1);
  for (const dir of rel.slice(0, -1)) if (dir in SKIP_DIRS) return SKIP_DIRS[dir];
  return rel.some((p) => p.startsWith(".")) ? "hidden" : null;
}

/** Why a folder below the chosen one is skipped as a whole, or null. */
function folderSkipReason(name: string): SkipReason | null {
  return SKIP_DIRS[name] ?? (name.startsWith(".") ? "hidden" : null);
}

export const formatMB = (bytes: number) => `${(bytes / (1024 * 1024)).toFixed(bytes < 1024 * 1024 ? 2 : 1)} MB`;
const mb = (bytes: number) => `${Number((bytes / (1024 * 1024)).toFixed(1))} MB`;

export async function prepare(found: Found, limits: UploadLimits = DEFAULT_UPLOAD_LIMITS): Promise<Prepared> {
  if (found.files.length === 0) throw new PrepareError("That folder is empty. Pick the folder that contains go.mod.");
  const name = found.files[0].path.split("/")[0];
  const skipped = emptySkips();
  const files: PickedFile[] = [];
  let bytes = 0;
  for (const f of found.files) {
    const reason = pathSkipReason(f.path);
    if (reason) {
      skipped[reason]++;
      continue;
    }
    const file = await f.load();
    if (file.size > limits.max_file_bytes) {
      skipped.too_large++;
      continue;
    }
    files.push({ path: f.path, file });
    bytes += file.size;
  }
  if (!files.some((f) => f.path === `${name}/go.mod`)) {
    throw new PrepareError("No go.mod at the top of the folder you chose. Pick the folder that contains go.mod.");
  }
  if (files.length > limits.max_files || bytes > limits.max_bytes) {
    throw new PrepareError(
      `${name} has ${files.length.toLocaleString("en-US")} files (${formatMB(bytes)}) after skipping .git, vendor, node_modules, ` +
      `hidden files and files over ${mb(limits.max_file_bytes)}. The upload limit is ${limits.max_files.toLocaleString("en-US")} files ` +
      `and ${mb(limits.max_bytes)}; for large projects, set HOST_REPOS_DIR in .env instead.`);
  }
  return { name, files, bytes, skipped, skippedFolders: found.skippedFolders };
}

/** Files from <input type="file" webkitdirectory>: webkitRelativePath already starts with the folder name. */
export function foundFromInput(list: FileList | File[]): Found {
  const files = Array.from(list).map((file) => ({ path: file.webkitRelativePath || file.name, load: async () => file }));
  return { files, skippedFolders: emptySkips() };
}

function readBatch(reader: FileSystemDirectoryReader): Promise<FileSystemEntry[]> {
  return new Promise((resolve, reject) => reader.readEntries(resolve, reject));
}

async function walk(entry: FileSystemEntry, out: Found, isTop: boolean): Promise<void> {
  if (entry.isFile) {
    const fileEntry = entry as FileSystemFileEntry;
    out.files.push({
      path: entry.fullPath.replace(/^\/+/, ""),
      load: () => new Promise<File>((resolve, reject) => fileEntry.file(resolve, reject)),
    });
    return;
  }
  if (!entry.isDirectory) return;
  const reason = isTop ? null : folderSkipReason(entry.name);
  if (reason) { // .git, node_modules and the like can hold many thousands of files: don't read them at all
    out.skippedFolders[reason]++;
    return;
  }
  const reader = (entry as FileSystemDirectoryEntry).createReader();
  // readEntries returns at most ~100 entries per call; keep reading until it returns none.
  for (let batch = await readBatch(reader); batch.length > 0; batch = await readBatch(reader)) {
    for (const child of batch) await walk(child, out, false);
  }
}

/** Files from a drop: exactly one folder, read recursively. */
export async function foundFromDrop(items: DataTransferItemList): Promise<Found> {
  const entries = Array.from(items)
    .filter((i) => i.kind === "file")
    .map((i) => i.webkitGetAsEntry())
    .filter((e): e is FileSystemEntry => e !== null);
  if (entries.length !== 1 || !entries[0].isDirectory) {
    throw new PrepareError("Drop one project folder (the folder that contains go.mod), not single files.");
  }
  const out: Found = { files: [], skippedFolders: emptySkips() };
  await walk(entries[0], out, true);
  return out;
}

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

const skipText = (maxFileBytes: number): Record<SkipReason, (n: number) => string> => ({
  git: (n) => `${plural(n, "file", "files")} in .git`,
  vendor: (n) => `${n} in vendor`,
  node_modules: (n) => `${n} in node_modules`,
  hidden: (n) => plural(n, "hidden file", "hidden files"),
  too_large: (n) => `${plural(n, "file", "files")} over ${mb(maxFileBytes)}`,
  binary: (n) => plural(n, "binary", "binaries"),
});

const FOLDER_TEXT: Partial<Record<SkipReason, (n: number) => string>> = {
  git: (n) => (n === 1 ? "the .git folder" : `${n} .git folders`),
  vendor: (n) => (n === 1 ? "the vendor folder" : `${n} vendor folders`),
  node_modules: (n) => plural(n, "node_modules folder", "node_modules folders"),
  hidden: (n) => plural(n, "hidden folder", "hidden folders"),
};

const KEYS = Object.keys(emptySkips()) as SkipReason[];

/** "120 files in .git, 3 binaries" for files, then "the .git folder" for folders a drop never read; "" if nothing. */
export function describeSkips(files: SkipCounts[], folders: SkipCounts = emptySkips(),
                              maxFileBytes = DEFAULT_UPLOAD_LIMITS.max_file_bytes): string {
  const total = emptySkips();
  for (const c of files) for (const k of KEYS) total[k] += c[k] ?? 0;
  const text = skipText(maxFileBytes);
  const parts = KEYS.filter((k) => total[k] > 0).map((k) => text[k](total[k]));
  for (const k of KEYS) if (folders[k] > 0 && FOLDER_TEXT[k]) parts.push(FOLDER_TEXT[k]!(folders[k]));
  return parts.join(", ");
}
