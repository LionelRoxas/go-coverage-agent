// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
"use client";
import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import { api, ApiError } from "./api";
import { initialState, mutationRunning, reduce, summaryWaiting } from "./runState";

const TERMINAL = new Set(["completed", "failed", "cancelled", "interrupted"]);
const END_EVENTS = new Set(["job_completed", "job_cancelled", "job_failed"]);
const SUMMARY_EVENTS = new Set(["summary_generated", "summary_failed"]);
// A run that is not running: after this many replays in a row that bring no new event, its replay is as complete as
// it will get (e.g. a summary its snapshot reports never reached events.jsonl), so the stream is closed.
const MAX_STALE_REPLAYS = 2;

export type Connection = "open" | "reconnecting" | "closed";

type Ui = { jobId: string; notFound: boolean; error: string | null; connection: "open" | "reconnecting" };

export function useJobEvents(jobId: string) {
  const [state, dispatch] = useReducer(reduce, initialState);
  // Keyed by jobId: state left over from a previous job is ignored, so nothing leaks across jobs.
  const [ui, setUi] = useState<Ui>({ jobId, notFound: false, error: null, connection: "open" });
  const source = useRef<EventSource | null>(null);
  // Bumped to open the stream again after the run ended (Write summary): replayed events are ignored by seq.
  const [reopened, setReopened] = useState(0);
  const opened = useRef<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let warned = false;
    const patch = (p: Partial<Ui>) =>
      setUi((u) => ({ ...(u.jobId === jobId ? u : { jobId, notFound: false, error: null, connection: "open" }), ...p }));
    if (opened.current !== jobId) dispatch({ type: "reset" }); // a reopened stream keeps the state it extends
    opened.current = jobId;
    api.job(jobId).then(
      (first) => {
        if (cancelled) return;
        const isEnded = (j: typeof first | undefined) => !!j && TERMINAL.has(j.status) && !j.writing_summary && !j.mutating;
        // Not running and not writing its summary (e.g. reloaded from ./output): the stream replays and then ends.
        // A live run can become one after a backend restart (it reloads as interrupted): a later snapshot says so.
        let job = first, ended = isEnded(first);
        // What this stream replayed: whether it reached the run's end (and its summary, when the snapshot says one exists).
        let received = false, sawEnd = false, sawSummary = false;
        let lastSeq = -1, seqAtLastError = -1, staleReplays = 0;
        // A live run found ended by a later snapshot: settle only once the reopened stream has replayed something, so
        // events saved after the last live one are shown (null: the run was not live when the page opened).
        let sinceEnded: number | null = null;
        const es = new EventSource(api.eventsUrl(jobId));
        source.current = es;
        let settled = false;
        // The replay is complete: EventSource would otherwise replay it again and again.
        const settle = () => {
          settled = true;
          es.close();
          dispatch({ type: "stream_ended", saved: job.status });
        };
        const replayComplete = () => (sinceEnded === null || sinceEnded > 0)
          && (job.status === "interrupted" || (sawEnd && (sawSummary || !job.ai_summary)));
        es.onopen = () => patch({ connection: "open", error: null });
        es.onerror = () => {
          if (settled) return; // a late error event after the stream was closed
          if (ended && !received) {
            // Nothing was replayed: the saved events were deleted or can't be read (or the run is gone).
            es.close();
            api.job(jobId).then(
              () => { if (!cancelled) patch({ error: `Couldn't read this run's saved events (./output/${jobId}/events.jsonl).` }); },
              (e) => {
                if (cancelled) return;
                if (e instanceof ApiError && e.status === 404) patch({ notFound: true });
                else patch({ error: e instanceof Error ? e.message : String(e) });
              });
            return;
          }
          if (ended) {
            staleReplays = lastSeq === seqAtLastError ? staleReplays + 1 : 0;
            seqAtLastError = lastSeq;
            if (replayComplete() || staleReplays >= MAX_STALE_REPLAYS) return settle();
          }
          // A live job's stream dropped, or a finished run's replay was cut before its end: the browser retries and
          // replays it again (already-seen events are ignored).
          patch({ connection: "reconnecting" });
          if (ended && es.readyState !== EventSource.CLOSED) return; // the browser is retrying by itself
          // A live job: ask whether it still runs (after a backend restart it is reloaded as interrupted, and its
          // stream would replay and end forever). Also when the browser gave up (e.g. its folder was deleted from
          // ./output, or it is older than the runs reloaded on startup): find out whether it still exists.
          api.job(jobId).then(
            (fresh) => {
              if (cancelled || settled || ended || !isEnded(fresh)) return;
              job = fresh;
              ended = true;
              // The browser gave up: nothing more will be replayed. Otherwise its retry replays the run first.
              if (es.readyState === EventSource.CLOSED) return settle();
              sinceEnded = 0;
            },
            (e) => {
              if (!cancelled && e instanceof ApiError && e.status === 404) patch({ notFound: true });
            });
        };
        es.onmessage = (m) => {
          try {
            const ev = JSON.parse(m.data);
            dispatch(ev);
            received = true;
            if (sinceEnded !== null) sinceEnded++;
            if (typeof ev.seq === "number" && ev.seq > lastSeq) lastSeq = ev.seq;
            if (END_EVENTS.has(ev.type)) sawEnd = true;
            if (SUMMARY_EVENTS.has(ev.type)) sawSummary = true;
          } catch {
            if (!warned) {
              warned = true;
              console.warn("Ignoring malformed event frame from the backend");
            }
          }
        };
      },
      (e) => {
        if (cancelled) return;
        if (e instanceof ApiError && e.status === 404) return patch({ notFound: true });
        patch({
          error: e instanceof Error ? e.message : String(e),
          connection: e instanceof ApiError && e.status === 0 ? "reconnecting" : "open",
        });
      },
    );
    return () => {
      cancelled = true;
      source.current?.close();
      source.current = null;
    };
  }, [jobId, reopened]);

  // The run has ended and nothing more is coming: its summary (if any) is written, failed or off.
  const terminal = TERMINAL.has(state.status) && !summaryWaiting(state) && !mutationRunning(state);
  useEffect(() => {
    if (terminal) source.current?.close(); // stop EventSource from reconnecting forever
  }, [terminal]);

  const cur = ui.jobId === jobId ? ui : { notFound: false, error: null, connection: "open" as const };
  const connection: Connection = terminal ? "closed" : cur.connection;
  /** After POST /api/jobs/{id}/summary succeeded: wait for the summary and reopen the stream to receive it. */
  const summaryRequested = useCallback(() => {
    dispatch({ type: "summary_requested" });
    setReopened((n) => n + 1);
  }, []);
  /** After POST /api/jobs/{id}/mutation succeeded: reopen the stream to receive the mutation test's events. */
  const mutationRequested = useCallback(() => {
    dispatch({ type: "mutation_requested" });
    setReopened((n) => n + 1);
  }, []);
  return { state, notFound: cur.notFound, error: cur.error, connection, summaryRequested, mutationRequested };
}
