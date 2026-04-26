// Tiny coloured pill for the current state.
const STYLES = {
  draft: "bg-slate-100 text-slate-700",
  submitted: "bg-blue-100 text-blue-700",
  under_review: "bg-amber-100 text-amber-800",
  approved: "bg-emerald-100 text-emerald-800",
  rejected: "bg-red-100 text-red-700",
  more_info_requested: "bg-purple-100 text-purple-700",
};

export default function StateBadge({ state }) {
  const cls = STYLES[state] || "bg-slate-100 text-slate-700";
  return (
    <span className={`inline-block text-xs font-medium px-2 py-0.5 rounded ${cls}`}>
      {state.replace(/_/g, " ")}
    </span>
  );
}
