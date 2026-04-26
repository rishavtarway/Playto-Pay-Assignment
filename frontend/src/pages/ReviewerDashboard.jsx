// Reviewer dashboard: metrics row + queue (oldest first, with SLA flag).
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import client from "../api/client";
import StateBadge from "../components/StateBadge";
import { describeError, formatDuration } from "../lib/format";

export default function ReviewerDashboard() {
  const [queue, setQueue] = useState(null);
  const [metrics, setMetrics] = useState(null);
  const [error, setError] = useState("");

  // Refresh on mount and every 30s so the SLA flag stays accurate.
  useEffect(() => {
    let alive = true;
    function load() {
      Promise.all([client.get("/reviews/queue/"), client.get("/reviews/metrics/")])
        .then(([q, m]) => {
          if (!alive) return;
          setQueue(q.data);
          setMetrics(m.data);
        })
        .catch((err) => alive && setError(describeError(err)));
    }
    load();
    const t = setInterval(load, 30000);
    return () => { alive = false; clearInterval(t); };
  }, []);

  return (
    <div className="max-w-6xl mx-auto p-6 space-y-6">
      <h1 className="text-2xl font-semibold">Review queue</h1>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Stat label="In queue" value={metrics?.in_queue ?? "—"} />
        <Stat label="Avg time in queue" value={metrics ? formatDuration(metrics.avg_time_in_queue_seconds) : "—"} />
        <Stat label="Approval rate (7d)"
          value={metrics ? `${(metrics.approval_rate_7d * 100).toFixed(0)}%` : "—"}
          sub={metrics ? `${metrics.decided_last_7d} decided` : ""} />
      </div>

      {error && <pre className="text-sm text-red-600 whitespace-pre-wrap">{error}</pre>}

      <div className="bg-white border rounded overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-600">
            <tr>
              <th className="text-left px-4 py-2">Merchant</th>
              <th className="text-left px-4 py-2">Business</th>
              <th className="text-left px-4 py-2">State</th>
              <th className="text-left px-4 py-2">Waiting</th>
              <th className="text-left px-4 py-2">Reviewer</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {queue == null && (
              <tr><td colSpan={6} className="px-4 py-6 text-center text-slate-400">Loading…</td></tr>
            )}
            {queue && queue.length === 0 && (
              <tr><td colSpan={6} className="px-4 py-6 text-center text-slate-400">Queue is empty.</td></tr>
            )}
            {queue && queue.map((row) => (
              <tr key={row.id} className="border-t">
                <td className="px-4 py-3">
                  <div className="font-medium">{row.full_name || row.merchant_email}</div>
                  <div className="text-xs text-slate-500">{row.merchant_email}</div>
                </td>
                <td className="px-4 py-3">{row.business_name || "—"}</td>
                <td className="px-4 py-3"><StateBadge state={row.state} /></td>
                <td className="px-4 py-3">
                  <span className={row.is_at_risk ? "text-red-700 font-medium" : ""}>
                    {formatDuration(row.time_in_queue_seconds)}
                  </span>
                  {row.is_at_risk && (
                    <span className="ml-2 text-xs bg-red-100 text-red-700 px-1.5 py-0.5 rounded">AT RISK</span>
                  )}
                </td>
                <td className="px-4 py-3 text-slate-600">{row.assigned_reviewer_email || "—"}</td>
                <td className="px-4 py-3">
                  <Link to={`/reviewer/${row.id}`} className="text-slate-900 underline">Open</Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Stat({ label, value, sub }) {
  return (
    <div className="bg-white border rounded p-4">
      <div className="text-xs text-slate-500">{label}</div>
      <div className="text-2xl font-semibold mt-1">{value}</div>
      {sub && <div className="text-xs text-slate-400">{sub}</div>}
    </div>
  );
}
