// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError } from "./api";

/** Records the request and lets each test finish it the way a browser would. */
class FakeXHR {
  static last: FakeXHR;
  status = 0;
  responseText = "";
  timeout = 0;
  method = "";
  url = "";
  body: FormData | null = null;
  upload: { onprogress: ((e: { lengthComputable: boolean; loaded: number; total: number }) => void) | null } = { onprogress: null };
  onload: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onabort: (() => void) | null = null;
  ontimeout: (() => void) | null = null;
  constructor() { FakeXHR.last = this; }
  open(method: string, url: string) { this.method = method; this.url = url; }
  send(body: FormData) { this.body = body; }
  respond(status: number, text: string) { this.status = status; this.responseText = text; this.onload?.(); }
}

const file = (path: string) => ({ path, file: new File(["package a\n"], path.split("/").pop()!) });

describe("api.uploadRepo", () => {
  afterEach(() => vi.unstubAllGlobals());

  function start(name?: string, onProgress?: (f: number) => void) {
    vi.stubGlobal("XMLHttpRequest", FakeXHR);
    const p = api.uploadRepo([file("myproj/go.mod"), file("myproj/pkg/a.go")], name, onProgress);
    return { p, xhr: FakeXHR.last };
  }

  it("posts one part per file named by its relative path, plus the name, and reports progress", async () => {
    const progress = vi.fn();
    const { p, xhr } = start("other", progress);
    expect([xhr.method, xhr.url]).toEqual(["POST", "http://localhost:8000/api/repos/upload"]);
    expect(xhr.body!.getAll("files").map((f) => (f as File).name)).toEqual(["myproj/go.mod", "myproj/pkg/a.go"]);
    expect(xhr.body!.get("name")).toBe("other");
    expect(xhr.timeout).toBeGreaterThan(0);
    xhr.upload.onprogress!({ lengthComputable: true, loaded: 5, total: 10 });
    expect(progress).toHaveBeenCalledWith(0.5);
    xhr.respond(200, JSON.stringify({ path: "uploads/other" }));
    await expect(p).resolves.toEqual({ path: "uploads/other" });
  });

  it("turns an error body into an ApiError with the server's code and message", async () => {
    const { p, xhr } = start();
    xhr.respond(409, JSON.stringify({ error: { code: "name_taken", message: "taken" } }));
    await expect(p).rejects.toMatchObject({ status: 409, code: "name_taken", message: "taken" });
  });

  it("explains a 2xx reply that isn't JSON instead of calling it a failure code", async () => {
    const { p, xhr } = start();
    xhr.respond(200, "<html>proxy</html>");
    await expect(p).rejects.toMatchObject({ code: "bad_response", message: expect.stringMatching(/unexpected reply/) });
  });

  it.each([
    ["onerror", "unreachable", /Can't reach the backend at .*If you changed BACKEND_PORT, rebuild the frontend/],
    ["onabort", "aborted", /stopped before it finished/],
    ["ontimeout", "timeout", /took longer than 10 minutes/],
  ] as const)("rejects readably on %s", async (handler, code, message) => {
    const { p, xhr } = start();
    xhr[handler]!();
    const err = await p.catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err).toMatchObject({ code, message: expect.stringMatching(message) });
  });
});
