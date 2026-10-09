// AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
"use client";
import { useEffect, useReducer, useRef, useState } from "react";
import { api, ApiError } from "./api";
import { initialState, reduce } from "./runState";

const TERMINAL = new Set(["completed", "failed", "cancelled"]);

export type Connection = "open" | "reconnecting" | "closed";

type Ui = { jobId: string; notFound: boolean; error: string | null; connection: "open" | "reconnecting" };

export function useJobEvents(jobId: string) {
  const [state, dispatch] = useReducer(reduce, initialState);
  // Keyed by jobId: state left over from a previous job is ignored, so nothing leaks across jobs.
  const [ui, setUi] = useState<Ui>({ jobId, notFound: false, error: null, connection: "open" });
  const source = useRef<EventSource | null>(null);

  useEffect(() => {
    let cancelled = false;
    let warned = false;
    const patch = (p: Partial<Ui>) =>
      setUi((u) => ({ ...(u.jobId === jobId ? u : { jobId, notFound: false, error: null, connection: "open" }), ...p }));
    dispatch({ type: "reset" });
    api.job(jobId).then(
      () => {
        if (cancelled) return;
        const es = new EventSource(api.eventsUrl(jobId));
        source.current = es;
        es.onopen = () => patch({ connection: "open", error: null });
        es.onerror = () => {
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
  }, [jobId]);

  const terminal = TERMINAL.has(state.status);
  useEffect(() => {
    if (terminal) source.current?.close(); // stop EventSource from reconnecting forever
  }, [terminal]);

  const cur = ui.jobId === jobId ? ui : { notFound: false, error: null, connection: "open" as const };
  const connection: Connection = terminal ? "closed" : cur.connection;
  return { state, notFound: cur.notFound, error: cur.error, connection };
}
