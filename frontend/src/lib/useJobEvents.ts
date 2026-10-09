// AI-assisted: drafted with Claude Code from the implementation plan; reviewed by <author>.
"use client";
import { useEffect, useReducer, useRef, useState } from "react";
import { api, ApiError } from "./api";
import { initialState, reduce } from "./runState";

const TERMINAL = new Set(["completed", "failed", "cancelled"]);

export function useJobEvents(jobId: string) {
  const [state, dispatch] = useReducer(reduce, initialState);
  const [notFound, setNotFound] = useState(false);
  const [connection, setConnection] = useState<"open" | "reconnecting">("open");
  const source = useRef<EventSource | null>(null);

  useEffect(() => {
    let cancelled = false;
    api.job(jobId).then(
      () => {
        if (cancelled) return;
        const es = new EventSource(api.eventsUrl(jobId));
        source.current = es;
        es.onopen = () => setConnection("open");
        es.onerror = () => setConnection("reconnecting");
        es.onmessage = (m) => dispatch(JSON.parse(m.data));
      },
      (e) => { if (e instanceof ApiError && e.status === 404) setNotFound(true); },
    );
    return () => {
      cancelled = true;
      source.current?.close();
    };
  }, [jobId]);

  useEffect(() => {
    if (TERMINAL.has(state.status)) source.current?.close(); // stop EventSource from reconnecting forever
  }, [state.status]);

  return { state, notFound, connection };
}
