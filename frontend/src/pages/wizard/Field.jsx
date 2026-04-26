// Shared form-field primitives used across every wizard step.
// Plain controlled inputs — kept dumb on purpose.

export function Field({ label, value, onChange, type = "text", disabled }) {
  return (
    <label className="block">
      <div className="text-sm font-medium text-slate-700 mb-1">{label}</div>
      <input
        type={type}
        value={value ?? ""}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
        className="w-full border rounded px-3 py-2 disabled:bg-slate-50"
      />
    </label>
  );
}

export function SelectField({ label, value, onChange, options, disabled }) {
  return (
    <label className="block">
      <div className="text-sm font-medium text-slate-700 mb-1">{label}</div>
      <select
        value={value ?? ""}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
        className="w-full border rounded px-3 py-2 disabled:bg-slate-50"
      >
        {options.map(([v, l]) => (
          <option key={v} value={v}>{l}</option>
        ))}
      </select>
    </label>
  );
}

export function ReviewRow({ label, value }) {
  return (
    <div className="flex border-b py-2">
      <div className="w-40 text-slate-500">{label}</div>
      <div className="flex-1 text-slate-900">{value || "—"}</div>
    </div>
  );
}
