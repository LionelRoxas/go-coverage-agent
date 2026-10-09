// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
// @vitest-environment jsdom
import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, ApiError } from "./api";
import { useJobEvents } from "./useJobEvents";

vi.mock("./api", async (orig) => {
  const real = await orig<typeof import("./api")>();
  return { ...real, api: { job: vi.fn(), eventsUrl: (id: string) => `http://test/${id}/events` } };
});

class FakeEventSource {
  static CLOSED = 2;
  static last: FakeEventSource | null = null;
  readyState = 0;
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onmessage: ((m: { data: string }) => void) | null = null;
  constructor(public url: string) {
    FakeEventSource.last = this;
  }
  close() {
    this.readyState = FakeEventSource.CLOSED;
  }
}

describe("useJobEvents error handling", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    FakeEventSource.last = null;
    vi.stubGlobal("EventSource", FakeEventSource);
  });
  afterEach(() => vi.unstubAllGlobals());

  async function connected() {
    vi.mocked(api.job).mockResolvedValueOnce({} as never);
    const hook = renderHook(() => useJobEvents("j1"));
    await waitFor(() => expect(FakeEventSource.last).not.toBeNull());
    return hook;
  }

  it("keeps reconnecting without re-querying while the browser is still retrying", async () => {
    const { result } = await connected();
    act(() => FakeEventSource.last!.onerror!());
    expect(result.current.connection).toBe("reconnecting");
    expect(api.job).toHaveBeenCalledTimes(1);
  });

  it("marks the run as gone when the stream closed for good and the job is a 404", async () => {
    const { result } = await connected();
    vi.mocked(api.job).mockRejectedValueOnce(new ApiError(404, "not_found", "no such job"));
    act(() => {
      FakeEventSource.last!.readyState = FakeEventSource.CLOSED;
      FakeEventSource.last!.onerror!();
    });
    await waitFor(() => expect(result.current.notFound).toBe(true));
  });

  it("stays reconnecting when the stream closed but the job lookup fails another way", async () => {
    const { result } = await connected();
    vi.mocked(api.job).mockRejectedValueOnce(new ApiError(0, "network", "offline"));
    act(() => {
      FakeEventSource.last!.readyState = FakeEventSource.CLOSED;
      FakeEventSource.last!.onerror!();
    });
    await waitFor(() => expect(api.job).toHaveBeenCalledTimes(2));
    expect(result.current.notFound).toBe(false);
    expect(result.current.connection).toBe("reconnecting");
  });
});

describe("useJobEvents and the AI summary", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    FakeEventSource.last = null;
    vi.stubGlobal("EventSource", FakeEventSource);
  });
  afterEach(() => vi.unstubAllGlobals());

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const send = (es: FakeEventSource, seq: number, type: string, data: Record<string, any>) =>
    act(() => es.onmessage!({ data: JSON.stringify({ seq, ts: 1000 + seq, type, data }) }));
  const result = { business: {}, technical: {}, dropped_sentences: 0, tokens: { total_tokens: 10 } };

  it("keeps the stream open after job_completed until the summary arrives", async () => {
    vi.mocked(api.job).mockResolvedValueOnce({} as never);
    const hook = renderHook(() => useJobEvents("j1"));
    await waitFor(() => expect(FakeEventSource.last).not.toBeNull());
    const es = FakeEventSource.last!;
    send(es, 0, "job_started", { repo_path: "stats", target_coverage: 80, options: { write_summary: true }, model: "m" });
    send(es, 1, "job_completed", { stop_reason: "target_reached", message: "done", final_percent: 81 });
    expect(es.readyState).not.toBe(FakeEventSource.CLOSED);
    expect(hook.result.current.connection).toBe("open");
    send(es, 2, "summary_generated", result);
    expect(es.readyState).toBe(FakeEventSource.CLOSED);
    expect(hook.result.current.connection).toBe("closed");
  });

  it("summaryRequested reopens the stream and keeps the state it extends", async () => {
    vi.mocked(api.job).mockResolvedValueOnce({} as never);
    const hook = renderHook(() => useJobEvents("j1"));
    await waitFor(() => expect(FakeEventSource.last).not.toBeNull());
    const first = FakeEventSource.last!;
    send(first, 0, "job_started", { repo_path: "stats", target_coverage: 80, options: { write_summary: false }, model: "m" });
    send(first, 1, "job_completed", { stop_reason: "target_reached", message: "done", final_percent: 81 });
    expect(first.readyState).toBe(FakeEventSource.CLOSED);
    expect(hook.result.current.state.aiSummary?.status).toBe("off");

    vi.mocked(api.job).mockResolvedValueOnce({} as never);
    act(() => hook.result.current.summaryRequested());
    expect(hook.result.current.state.aiSummary?.status).toBe("waiting");
    await waitFor(() => expect(FakeEventSource.last).not.toBe(first));
    const second = FakeEventSource.last!;
    expect(hook.result.current.state.status).toBe("completed"); // not reset
    send(second, 0, "job_started", { repo_path: "stats", target_coverage: 80, options: { write_summary: false }, model: "m" });
    send(second, 1, "job_completed", { stop_reason: "target_reached", message: "done", final_percent: 81 });
    expect(hook.result.current.state.aiSummary?.status).toBe("waiting"); // replayed events are ignored
    send(second, 2, "llm_request", { role: "summarizer", reasoning_effort: "medium" });
    send(second, 3, "summary_generated", result);
    expect(hook.result.current.state.aiSummary?.status).toBe("done");
    expect(second.readyState).toBe(FakeEventSource.CLOSED);
  });
});
