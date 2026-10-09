// AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
import type { Health, JobSnapshot, RepoInfo, StartJobBody } from "./types";

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
    throw new ApiError(0, "unreachable", `Can't reach the backend at ${API_URL}. Is \`docker compose up\` running?`);
  }
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new ApiError(res.status, body?.error?.code ?? "http_error", body?.error?.message ?? res.statusText);
  }
  const type = res.headers.get("content-type") ?? "";
  return (type.includes("application/json") ? res.json() : res.text()) as Promise<T>;
}

const encodePath = (p: string) => p.split("/").map(encodeURIComponent).join("/");

export const api = {
  health: () => request<Health>("/api/health"),
  repos: () => request<RepoInfo[]>("/api/repos"),
  cloneSample: () => request<RepoInfo>("/api/repos/sample", { method: "POST" }),
  startJob: (body: StartJobBody) =>
    request<{ job_id: string }>("/api/jobs", { method: "POST", body: JSON.stringify(body) }),
  jobs: () => request<JobSnapshot[]>("/api/jobs"),
  job: (id: string) => request<JobSnapshot>(`/api/jobs/${id}`),
  cancel: (id: string) => request<JobSnapshot>(`/api/jobs/${id}/cancel`, { method: "POST" }),
  file: (id: string, path: string) => request<string>(`/api/jobs/${id}/files/${encodePath(path)}`),
  eventsUrl: (id: string) => `${API_URL}/api/jobs/${id}/events`,
};
