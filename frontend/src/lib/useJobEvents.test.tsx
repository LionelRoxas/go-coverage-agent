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

  it("re-checks the snapshot once per drop and keeps reconnecting while the job still runs", async () => {
    const { result } = await connected();
    vi.mocked(api.job).mockResolvedValueOnce({ status: "running", writing_summary: false } as never);
    const es = FakeEventSource.last!;
    act(() => es.onerror!());
    expect(result.current.connection).toBe("reconnecting");
    await waitFor(() => expect(api.job).toHaveBeenCalledTimes(2));
    expect(es.readyState).not.toBe(FakeEventSource.CLOSED);
    expect(result.current.connection).toBe("reconnecting");
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

describe("useJobEvents for a run reloaded from ./output", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    FakeEventSource.last = null;
    vi.stubGlobal("EventSource", FakeEventSource);
  });
  afterEach(() => vi.unstubAllGlobals());

  it("ends an interrupted run when its replay ends, instead of reconnecting", async () => {
    vi.mocked(api.job).mockResolvedValueOnce({ status: "interrupted", writing_summary: false } as never);
    const hook = renderHook(() => useJobEvents("j1"));
    await waitFor(() => expect(FakeEventSource.last).not.toBeNull());
    const es = FakeEventSource.last!;
    act(() => es.onmessage!({ data: JSON.stringify({ seq: 0, ts: 1, type: "job_started",
                                                     data: { repo_path: "stats", target_coverage: 80, options: {}, model: "m" } }) }));
    expect(hook.result.current.state.status).toBe("running");
    act(() => es.onerror!());
    expect(es.readyState).toBe(FakeEventSource.CLOSED);
    expect(hook.result.current.state.status).toBe("interrupted");
    expect(hook.result.current.connection).toBe("closed");
    expect(api.job).toHaveBeenCalledTimes(1);
  });

  it("shows an error, not a loading page, when a saved run replays nothing", async () => {
    const snap = { status: "completed", writing_summary: false } as never;
    vi.mocked(api.job).mockResolvedValueOnce(snap).mockResolvedValueOnce(snap);
    const hook = renderHook(() => useJobEvents("j1"));
    await waitFor(() => expect(FakeEventSource.last).not.toBeNull());
    const es = FakeEventSource.last!;
    act(() => es.onerror!());
    expect(es.readyState).toBe(FakeEventSource.CLOSED);
    await waitFor(() => expect(hook.result.current.error).toBe("Couldn't read this run's saved events (./output/j1/events.jsonl)."));
    expect(hook.result.current.state.status).toBe("connecting");
  });

  it("says the run is gone when it replays nothing and the job is now a 404", async () => {
    vi.mocked(api.job).mockResolvedValueOnce({ status: "interrupted", writing_summary: false } as never)
      .mockRejectedValueOnce(new ApiError(404, "not_found", "no such job"));
    const hook = renderHook(() => useJobEvents("j1"));
    await waitFor(() => expect(FakeEventSource.last).not.toBeNull());
    act(() => FakeEventSource.last!.onerror!());
    await waitFor(() => expect(hook.result.current.notFound).toBe(true));
  });

  it("retries a completed run whose replay was cut before its end, instead of calling it interrupted", async () => {
    vi.mocked(api.job).mockResolvedValueOnce({ status: "completed", writing_summary: false, ai_summary: null } as never);
    const hook = renderHook(() => useJobEvents("j1"));
    await waitFor(() => expect(FakeEventSource.last).not.toBeNull());
    const es = FakeEventSource.last!;
    act(() => es.onmessage!({ data: JSON.stringify({ seq: 0, ts: 1, type: "job_started",
                                                     data: { repo_path: "stats", target_coverage: 80, options: {}, model: "m" } }) }));
    act(() => es.onerror!());
    expect(es.readyState).not.toBe(FakeEventSource.CLOSED);
    expect(hook.result.current.state.status).toBe("running");
    expect(hook.result.current.connection).toBe("reconnecting");
    act(() => es.onmessage!({ data: JSON.stringify({ seq: 1, ts: 2, type: "job_completed",
                                                     data: { stop_reason: "target_reached", message: "done", final_percent: 81 } }) }));
    expect(hook.result.current.state.status).toBe("completed");
    expect(es.readyState).toBe(FakeEventSource.CLOSED);
  });

  it("waits for a saved summary that the replay has not reached yet", async () => {
    vi.mocked(api.job).mockResolvedValueOnce({ status: "completed", writing_summary: false, ai_summary: "generated" } as never);
    const hook = renderHook(() => useJobEvents("j1"));
    await waitFor(() => expect(FakeEventSource.last).not.toBeNull());
    const es = FakeEventSource.last!;
    const send = (seq: number, type: string, data: object) =>
      act(() => es.onmessage!({ data: JSON.stringify({ seq, ts: seq, type, data }) }));
    send(0, "job_started", { repo_path: "stats", target_coverage: 80, options: { write_summary: true }, model: "m" });
    send(1, "job_completed", { stop_reason: "target_reached", message: "done", final_percent: 81 });
    act(() => es.onerror!());
    expect(es.readyState).not.toBe(FakeEventSource.CLOSED);
    expect(hook.result.current.state.aiSummary?.status).toBe("waiting");
  });

  it("settles a live run that a backend restart turned into an interrupted one, and stops reconnecting", async () => {
    vi.mocked(api.job).mockResolvedValueOnce({ status: "running", writing_summary: false } as never)
      .mockResolvedValueOnce({ status: "interrupted", writing_summary: false } as never);
    const hook = renderHook(() => useJobEvents("j1"));
    await waitFor(() => expect(FakeEventSource.last).not.toBeNull());
    const es = FakeEventSource.last!;
    act(() => es.onmessage!({ data: JSON.stringify({ seq: 0, ts: 1, type: "job_started",
                                                     data: { repo_path: "stats", target_coverage: 80, options: {}, model: "m" } }) }));
    act(() => es.onerror!()); // the backend went away; the fresh snapshot says the run was reloaded as interrupted
    await waitFor(() => expect(api.job).toHaveBeenCalledTimes(2));
    expect(es.readyState).not.toBe(FakeEventSource.CLOSED); // not before the reopened stream replayed the run
    expect(hook.result.current.state.status).toBe("running");
    // the reconnected stream replays events.jsonl, including an event saved after the last live one, and ends
    act(() => es.onmessage!({ data: JSON.stringify({ seq: 0, ts: 1, type: "job_started",
                                                     data: { repo_path: "stats", target_coverage: 80, options: {}, model: "m" } }) }));
    act(() => es.onmessage!({ data: JSON.stringify({ seq: 1, ts: 2, type: "iteration_started", data: { index: 1, percent: 0 } }) }));
    act(() => es.onerror!());
    expect(hook.result.current.state.status).toBe("interrupted");
    expect(hook.result.current.state.lastSeq).toBe(1);
    expect(es.readyState).toBe(FakeEventSource.CLOSED);
    expect(hook.result.current.connection).toBe("closed");
    expect(FakeEventSource.last).toBe(es); // no new EventSource
    act(() => es.onerror!()); // a late error event changes nothing
    expect(api.job).toHaveBeenCalledTimes(2);
  });

  it("settles a live run found interrupted at once when the browser has given up reconnecting", async () => {
    vi.mocked(api.job).mockResolvedValueOnce({ status: "running", writing_summary: false } as never)
      .mockResolvedValueOnce({ status: "interrupted", writing_summary: false } as never);
    const hook = renderHook(() => useJobEvents("j1"));
    await waitFor(() => expect(FakeEventSource.last).not.toBeNull());
    const es = FakeEventSource.last!;
    act(() => es.onmessage!({ data: JSON.stringify({ seq: 0, ts: 1, type: "job_started",
                                                     data: { repo_path: "stats", target_coverage: 80, options: {}, model: "m" } }) }));
    act(() => {
      es.readyState = FakeEventSource.CLOSED;
      es.onerror!();
    });
    await waitFor(() => expect(hook.result.current.state.status).toBe("interrupted"));
  });

  it("settles a live run found interrupted after two silent retries if no replay ever comes", async () => {
    vi.mocked(api.job).mockResolvedValueOnce({ status: "running", writing_summary: false } as never)
      .mockResolvedValue({ status: "interrupted", writing_summary: false } as never);
    const hook = renderHook(() => useJobEvents("j1"));
    await waitFor(() => expect(FakeEventSource.last).not.toBeNull());
    const es = FakeEventSource.last!;
    act(() => es.onmessage!({ data: JSON.stringify({ seq: 0, ts: 1, type: "job_started",
                                                     data: { repo_path: "stats", target_coverage: 80, options: {}, model: "m" } }) }));
    act(() => es.onerror!());
    await waitFor(() => expect(api.job).toHaveBeenCalledTimes(2));
    act(() => es.onerror!());
    act(() => es.onerror!());
    expect(hook.result.current.state.status).toBe("running");
    act(() => es.onerror!());
    expect(hook.result.current.state.status).toBe("interrupted");
    expect(es.readyState).toBe(FakeEventSource.CLOSED);
  });

  it("lets a live run that finished while disconnected replay its end instead of settling early", async () => {
    vi.mocked(api.job).mockResolvedValueOnce({ status: "running", writing_summary: false } as never)
      .mockResolvedValueOnce({ status: "completed", writing_summary: false, ai_summary: null } as never);
    const hook = renderHook(() => useJobEvents("j1"));
    await waitFor(() => expect(FakeEventSource.last).not.toBeNull());
    const es = FakeEventSource.last!;
    const send = (seq: number, type: string, data: object) =>
      act(() => es.onmessage!({ data: JSON.stringify({ seq, ts: seq, type, data }) }));
    send(0, "job_started", { repo_path: "stats", target_coverage: 80, options: { write_summary: false }, model: "m" });
    act(() => es.onerror!());
    await waitFor(() => expect(api.job).toHaveBeenCalledTimes(2));
    expect(es.readyState).not.toBe(FakeEventSource.CLOSED); // job_completed has not been replayed yet
    send(1, "job_completed", { stop_reason: "target_reached", message: "done", final_percent: 81 });
    expect(hook.result.current.state.status).toBe("completed");
    expect(es.readyState).toBe(FakeEventSource.CLOSED);
  });

  it("stops replaying a saved run whose replays bring nothing new", async () => {
    vi.mocked(api.job).mockResolvedValueOnce({ status: "completed", writing_summary: false, ai_summary: "generated" } as never);
    const hook = renderHook(() => useJobEvents("j1"));
    await waitFor(() => expect(FakeEventSource.last).not.toBeNull());
    const es = FakeEventSource.last!;
    const replay = () => {
      act(() => es.onmessage!({ data: JSON.stringify({ seq: 0, ts: 1, type: "job_started",
                                                       data: { repo_path: "stats", target_coverage: 80, options: { write_summary: true }, model: "m" } }) }));
      act(() => es.onmessage!({ data: JSON.stringify({ seq: 1, ts: 2, type: "job_completed",
                                                       data: { stop_reason: "target_reached", message: "done", final_percent: 81 } }) }));
      act(() => es.onerror!());
    };
    replay(); // the file lacks the summary event its snapshot promised: retried
    expect(es.readyState).not.toBe(FakeEventSource.CLOSED);
    replay();
    replay();
    expect(es.readyState).toBe(FakeEventSource.CLOSED);
    expect(hook.result.current.connection).toBe("closed");
  });

  it("keeps reconnecting a running job when its stream drops", async () => {
    vi.mocked(api.job).mockResolvedValue({ status: "running", writing_summary: false } as never);
    const hook = renderHook(() => useJobEvents("j1"));
    await waitFor(() => expect(FakeEventSource.last).not.toBeNull());
    act(() => FakeEventSource.last!.onerror!());
    expect(FakeEventSource.last!.readyState).not.toBe(FakeEventSource.CLOSED);
    expect(hook.result.current.connection).toBe("reconnecting");
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
