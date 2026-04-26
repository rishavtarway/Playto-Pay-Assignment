// Tiny formatting helpers used in queue + dashboard tables.
export function formatDuration(seconds) {
  if (seconds == null) return "—";
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return `${h}h ${m}m`;
}

// Friendly state badge label.
export function stateLabel(state) {
  return state.replace(/_/g, " ");
}

// Pull a human-readable error string out of any axios error response shape.
export function describeError(err) {
  const data = err?.response?.data;
  if (!data) return err?.message || "Something went wrong.";
  if (typeof data.detail === "string") return data.detail;
  if (typeof data.detail === "object") {
    const lines = [];
    for (const [k, v] of Object.entries(data.detail)) {
      lines.push(`${k}: ${Array.isArray(v) ? v.join(", ") : v}`);
    }
    return lines.join("\n");
  }
  return JSON.stringify(data);
}
