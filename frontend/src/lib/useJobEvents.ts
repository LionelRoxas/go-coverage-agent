// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
"use client";
import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import { api, ApiError } from "./api";
import { initialState, reduce, summaryWaiting } from "./runState";

const TERMINAL = new Set(["completed", "failed", "cancelled", "interrupted"]);

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
      (job) => {
        if (cancelled) return;
        // Not running and not writing its summary (e.g. reloaded from ./output): the stream replays and then ends.
        const ended = !!job && TERMINAL.has(job.status) && !job.writing_summary;
        const es = new EventSource(api.eventsUrl(jobId));
        source.current = es;
        es.onopen = () => patch({ connection: "open", error: null });
        es.onerror = () => {
          if (ended) {
            es.close(); // the replay is complete; EventSource would otherwise replay it again and again
            dispatch({ type: "stream_ended" });
            return;
          }
          patch({ connection: "reconnecting" });
          if (es.readyState !== EventSource.CLOSED) return; // the browser is retrying by itself
          // The browser gave up (e.g. the backend restarted and forgot the job): find out whether it still exists.
          api.job(jobId).catch((e) => {
            if (!cancelled && e instanceof ApiError && e.status === 404) patch({ notFound: true });
          });
        };
        es.onmessage = (m) => {
          try {
            dispatch(JSON.parse(m.data));
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
  const terminal = TERMINAL.has(state.status) && !summaryWaiting(state);
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
  return { state, notFound: cur.notFound, error: cur.error, connection, summaryRequested };
}
