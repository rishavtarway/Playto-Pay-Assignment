// Multi-step KYC wizard for merchants. Steps: personal -> business -> documents -> review.
// Saves are sent to /submissions/me/ with PATCH so progress sticks across reloads.
import { useEffect, useMemo, useState } from "react";
import client from "../api/client";
import DocumentDropzone from "../components/DocumentDropzone";
import StateBadge from "../components/StateBadge";
import { describeError } from "../lib/format";

const STEPS = [
  { key: "personal", label: "Personal" },
  { key: "business", label: "Business" },
  { key: "documents", label: "Documents" },
  { key: "review", label: "Review & submit" },
];

const REQUIRED_KINDS = ["pan", "aadhaar", "bank_statement"];

export default function MerchantWizard() {
  const [submission, setSubmission] = useState(null);
  const [stepIdx, setStepIdx] = useState(0);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  // Load (or create) the merchant's draft on mount.
  useEffect(() => {
    client.get("/submissions/me/")
      .then((r) => setSubmission(r.data))
      .catch((err) => setError(describeError(err)));
  }, []);

  const docsByKind = useMemo(() => {
    const map = {};
    (submission?.documents || []).forEach((d) => { map[d.kind] = d; });
    return map;
  }, [submission]);

  const isLocked = submission && !["draft", "more_info_requested"].includes(submission.state);
  const isUnderReview = submission?.state === "under_review" || submission?.state === "submitted";

  function setField(key, value) {
    setSubmission((s) => ({ ...s, [key]: value }));
  }

  // Inner save: just hits the API and updates state. No try/catch — callers
  // own the error handling so submitAll() can short-circuit on a save failure.
  async function patchDraft() {
    const payload = {
      full_name: submission.full_name || "",
      email: submission.email || "",
      phone: submission.phone || "",
      business_name: submission.business_name || "",
      business_type: submission.business_type || "",
      expected_monthly_volume_usd: submission.expected_monthly_volume_usd || 0,
    };
    const r = await client.patch("/submissions/me/", payload);
    setSubmission(r.data);
  }

  async function saveProgress() {
    setError("");
    setSaving(true);
    try {
      await patchDraft();
    } catch (err) {
      setError(describeError(err));
    } finally {
      setSaving(false);
    }
  }

  // One save+submit unit: if the PATCH fails we never fire the POST, and the
  // saving flag stays true until the whole thing settles.
  async function submitAll() {
    setError("");
    setSaving(true);
    try {
      await patchDraft();
      const r = await client.post("/submissions/me/submit/");
      setSubmission(r.data);
    } catch (err) {
      setError(describeError(err));
    } finally {
      setSaving(false);
    }
  }

  if (!submission) {
    return <div className="p-6 text-slate-500">{error || "Loading…"}</div>;
  }

  const step = STEPS[stepIdx];

  // What's still missing? Drives the Review-step checklist and the disabled
  // Submit button. Mirrors the server-side required-field check so the UI
  // never lets the user click Submit only to get a 400 back.
  const missing = [];
  if (!submission.full_name) missing.push("Full name");
  if (!submission.email) missing.push("Email");
  if (!submission.phone) missing.push("Phone");
  if (!submission.business_name) missing.push("Business name");
  if (!submission.business_type) missing.push("Business type");
  // Match server: only blank/null is missing — explicit 0 is valid.
  if (submission.expected_monthly_volume_usd === null || submission.expected_monthly_volume_usd === "" || submission.expected_monthly_volume_usd === undefined) {
    missing.push("Expected monthly volume");
  }
  REQUIRED_KINDS.forEach((k) => {
    if (!docsByKind[k]) missing.push(`${k.replace("_", " ")} document`);
  });
  const canSubmit = missing.length === 0;

  return (
    <div className="max-w-3xl mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">KYC application</h1>
          <p className="text-sm text-slate-500">Complete every step to start collecting payments.</p>
        </div>
        <StateBadge state={submission.state} />
      </div>

      {submission.state === "more_info_requested" && submission.info_request_reason && (
        <div className="bg-purple-50 border border-purple-200 text-sm rounded p-3">
          <div className="font-medium text-purple-800">Reviewer requested more info</div>
          <div className="text-purple-700">{submission.info_request_reason}</div>
        </div>
      )}
      {submission.state === "rejected" && submission.rejection_reason && (
        <div className="bg-red-50 border border-red-200 text-sm rounded p-3">
          <div className="font-medium text-red-700">Rejected</div>
          <div className="text-red-700">{submission.rejection_reason}</div>
        </div>
      )}
      {submission.state === "approved" && (
        <div className="bg-emerald-50 border border-emerald-200 text-sm rounded p-3 text-emerald-800">
          You're approved. Welcome to Playto Pay!
        </div>
      )}

      {/* Step nav */}
      <ol className="flex border rounded overflow-hidden bg-white">
        {STEPS.map((s, i) => (
          <li key={s.key} className={`flex-1 p-3 text-center text-sm border-r last:border-r-0 cursor-pointer
            ${i === stepIdx ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-50"}`}
            onClick={() => setStepIdx(i)}>
            <span className="font-medium">{i + 1}.</span> {s.label}
          </li>
        ))}
      </ol>

      <div className="bg-white border rounded p-6 space-y-4">
        {step.key === "personal" && (
          <>
            <Field label="Full name" value={submission.full_name}
              onChange={(v) => setField("full_name", v)} disabled={isLocked || isUnderReview} />
            <Field label="Email" type="email" value={submission.email}
              onChange={(v) => setField("email", v)} disabled={isLocked || isUnderReview} />
            <Field label="Phone" value={submission.phone}
              onChange={(v) => setField("phone", v)} disabled={isLocked || isUnderReview} />
          </>
        )}

        {step.key === "business" && (
          <>
            <Field label="Business name" value={submission.business_name}
              onChange={(v) => setField("business_name", v)} disabled={isLocked || isUnderReview} />
            <SelectField label="Business type" value={submission.business_type}
              onChange={(v) => setField("business_type", v)} disabled={isLocked || isUnderReview}
              options={[
                ["", "Choose…"],
                ["freelance", "Freelancer"],
                ["agency", "Agency"],
                ["company", "Company"],
              ]} />
            <Field label="Expected monthly volume (USD)" type="number"
              value={submission.expected_monthly_volume_usd}
              onChange={(v) => setField("expected_monthly_volume_usd", Number(v) || 0)}
              disabled={isLocked || isUnderReview} />
          </>
        )}

        {step.key === "documents" && (
          <div className="space-y-4">
            <p className="text-xs text-slate-500">
              All three documents are required before you can submit. PDF, JPG, or PNG, up to 5 MB each.
            </p>
            {[
              ["pan", "PAN"],
              ["aadhaar", "Aadhaar"],
              ["bank_statement", "Bank statement"],
            ].map(([kind, label]) => (
              <DocumentDropzone key={kind} kind={kind} label={`${label} *`}
                existing={docsByKind[kind]}
                disabled={isLocked || isUnderReview}
                onUploaded={(doc) => setSubmission((s) => ({
                  ...s,
                  documents: [...s.documents.filter((d) => d.kind !== kind), doc],
                }))}
                onDeleted={(id) => setSubmission((s) => ({
                  ...s,
                  documents: s.documents.filter((d) => d.id !== id),
                }))} />
            ))}
          </div>
        )}

        {step.key === "review" && (
          <div className="space-y-3 text-sm">
            <ReviewRow label="Name" value={submission.full_name} />
            <ReviewRow label="Email" value={submission.email} />
            <ReviewRow label="Phone" value={submission.phone} />
            <ReviewRow label="Business" value={`${submission.business_name} (${submission.business_type})`} />
            <ReviewRow label="Monthly volume" value={`$${submission.expected_monthly_volume_usd}`} />
            <ReviewRow label="Documents"
              value={REQUIRED_KINDS.map((k) => `${k}: ${docsByKind[k] ? "✓" : "—"}`).join("  ")} />
            {!canSubmit && !isLocked && !isUnderReview && (
              <div className="mt-4 bg-amber-50 border border-amber-200 rounded p-3 text-amber-800">
                <div className="font-medium mb-1">Still needed before you can submit:</div>
                <ul className="list-disc list-inside text-xs space-y-0.5">
                  {missing.map((m) => <li key={m}>{m}</li>)}
                </ul>
              </div>
            )}
          </div>
        )}

        {error && <pre className="text-sm text-red-600 whitespace-pre-wrap">{error}</pre>}
      </div>

      <div className="flex items-center justify-between">
        <button className="px-3 py-2 text-sm text-slate-600 disabled:opacity-30"
          disabled={stepIdx === 0} onClick={() => setStepIdx(stepIdx - 1)}>← Back</button>

        <div className="space-x-2">
          {!isLocked && !isUnderReview && (
            <button onClick={saveProgress} disabled={saving}
              className="px-3 py-2 text-sm border rounded">
              {saving ? "Saving…" : "Save progress"}
            </button>
          )}
          {stepIdx < STEPS.length - 1 ? (
            <button onClick={() => setStepIdx(stepIdx + 1)}
              className="px-3 py-2 text-sm bg-slate-900 text-white rounded">Next →</button>
          ) : (
            <button onClick={submitAll}
              disabled={saving || isLocked || isUnderReview || !canSubmit}
              title={!canSubmit ? `Missing: ${missing.join(", ")}` : undefined}
              className="px-3 py-2 text-sm bg-emerald-600 text-white rounded disabled:opacity-50">
              {saving ? "Submitting…" : "Submit for review"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function Field({ label, value, onChange, type = "text", disabled }) {
  return (
    <label className="block">
      <div className="text-sm font-medium text-slate-700 mb-1">{label}</div>
      <input className="w-full border rounded px-3 py-2 disabled:bg-slate-50"
        type={type} value={value ?? ""} disabled={disabled}
        onChange={(e) => onChange(e.target.value)} />
    </label>
  );
}

function SelectField({ label, value, onChange, options, disabled }) {
  return (
    <label className="block">
      <div className="text-sm font-medium text-slate-700 mb-1">{label}</div>
      <select className="w-full border rounded px-3 py-2 disabled:bg-slate-50"
        value={value ?? ""} disabled={disabled} onChange={(e) => onChange(e.target.value)}>
        {options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
      </select>
    </label>
  );
}

function ReviewRow({ label, value }) {
  return (
    <div className="flex border-b py-2">
      <div className="w-40 text-slate-500">{label}</div>
      <div className="flex-1 text-slate-900">{value || "—"}</div>
    </div>
  );
}
