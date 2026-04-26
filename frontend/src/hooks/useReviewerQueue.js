// Polls /reviews/queue/ + /reviews/metrics/ on mount and every `intervalMs`.
// Returns { queue, metrics, error } so the dashboard can stay focused on
// rendering. The interval keeps the SLA flag accurate without a refresh.
import { useEffect, useState } from "react";
import client from "../api/client";
import { describeError } from "../lib/format";

const DEFAULT_INTERVAL_MS = 30_000;

export function useReviewerQueue({ intervalMs = DEFAULT_INTERVAL_MS } = {}) {
  const [queue, setQueue] = useState(null);
  const [metrics, setMetrics] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let alive = true;

    async function load() {
      try {
        const [queueResp, metricsResp] = await Promise.all([
          client.get("/reviews/queue/"),
          client.get("/reviews/metrics/"),
        ]);
        if (!alive) return;
        setQueue(queueResp.data);
        setMetrics(metricsResp.data);
      } catch (err) {
        if (alive) setError(describeError(err));
      }
    }

    load();
    const handle = setInterval(load, intervalMs);
    return () => { alive = false; clearInterval(handle); };
  }, [intervalMs]);

  return { queue, metrics, error };
}
