// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
import type { Health, JobSnapshot, RepoInfo, Sample, StartJobBody, UploadResult } from "./types";
import type { PickedFile } from "./upload";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: { "content-type": "application/json", ...(init?.headers ?? {}) },
      cache: "no-store",
    });
  } catch {
    throw unreachable();
  }
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new ApiError(res.status, body?.error?.code ?? "http_error", body?.error?.message ?? res.statusText);
  }
  const type = res.headers.get("content-type") ?? "";
  return (type.includes("application/json") ? res.json() : res.text()) as Promise<T>;
}

const unreachable = () =>
  new ApiError(0, "unreachable", `Can't reach the backend at ${API_URL}. Is \`docker compose up\` running? If you changed BACKEND_PORT, rebuild the frontend (\`make up\`).`);

const UPLOAD_TIMEOUT_MS = 10 * 60_000;

/** Multipart upload of a folder's files (part filename = path such as "myproj/pkg/a.go"), with upload progress 0..1. */
function uploadRepo(files: PickedFile[], name?: string, onProgress?: (fraction: number) => void): Promise<UploadResult> {
  return new Promise((resolve, reject) => {
    const form = new FormData();
    for (const f of files) form.append("files", f.file, f.path);
    if (name) form.append("name", name);
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_URL}/api/repos/upload`);
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && e.total > 0) onProgress?.(e.loaded / e.total);
    };
    xhr.timeout = UPLOAD_TIMEOUT_MS;
    xhr.onload = () => {
      let body: { error?: { code?: string; message?: string } } | null = null;
      try {
        body = JSON.parse(xhr.responseText);
      } catch {
        body = null;
      }
      const ok = xhr.status >= 200 && xhr.status < 300;
      if (ok && body) resolve(body as UploadResult);
      else if (ok) reject(new ApiError(xhr.status, "bad_response", "The backend sent an unexpected reply; the upload may not have been saved. Press Refresh to check."));
      else reject(new ApiError(xhr.status, body?.error?.code ?? "http_error", body?.error?.message ?? `Upload failed (HTTP ${xhr.status}).`));
    };
    xhr.onerror = () => reject(unreachable());
    xhr.onabort = () => reject(new ApiError(0, "aborted", "The upload was stopped before it finished. Try again."));
    xhr.ontimeout = () => reject(new ApiError(0, "timeout",
      `The upload took longer than ${UPLOAD_TIMEOUT_MS / 60_000} minutes and was stopped. Try again, or use HOST_REPOS_DIR for large projects.`));
    xhr.send(form);
  });
}

const encodePath = (p: string) => p.split("/").map(encodeURIComponent).join("/");

export const api = {
  health: () => request<Health>("/api/health"),
  repos: () => request<RepoInfo[]>("/api/repos"),
  samples: () => request<Sample[]>("/api/repos/samples"),
  downloadSample: (id: string) => request<RepoInfo>(`/api/repos/samples/${encodeURIComponent(id)}`, { method: "POST" }),
  uploadRepo,
  startJob: (body: StartJobBody) =>
    request<{ job_id: string }>("/api/jobs", { method: "POST", body: JSON.stringify(body) }),
  jobs: () => request<JobSnapshot[]>("/api/jobs"),
  job: (id: string) => request<JobSnapshot>(`/api/jobs/${encodeURIComponent(id)}`),
  cancel: (id: string) => request<JobSnapshot>(`/api/jobs/${encodeURIComponent(id)}/cancel`, { method: "POST" }),
  /** Write the AI summary of a finished run (again); its events follow on the run's event stream. */
  writeSummary: (id: string) => request<JobSnapshot>(`/api/jobs/${encodeURIComponent(id)}/summary`, { method: "POST" }),
  /** Mutation-test a finished run's kept tests; its events follow on the run's event stream. */
  mutationTest: (id: string) => request<JobSnapshot>(`/api/jobs/${encodeURIComponent(id)}/mutation`, { method: "POST" }),
  file: (id: string, path: string) => request<string>(`/api/jobs/${encodeURIComponent(id)}/files/${encodePath(path)}`),
  eventsUrl: (id: string) => `${API_URL}/api/jobs/${encodeURIComponent(id)}/events`,
};
