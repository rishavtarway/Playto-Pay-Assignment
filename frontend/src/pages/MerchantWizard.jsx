// Multi-step KYC wizard. Each step is its own small component; the wizard
// itself is just step navigation, top-level state copy, and the action bar.
//
// All server interaction + state lives in `useDraftSubmission`. All
// validation copy lives in `lib/submission.js`. This file owns layout.
import { useState } from "react";
import StateBadge from "../components/StateBadge";
import { useDraftSubmission } from "../hooks/useDraftSubmission";
import { canEdit, isInFlight, missingForSubmit } from "../lib/submission";
import BusinessStep from "./wizard/BusinessStep";
import DocumentsStep from "./wizard/DocumentsStep";
import PersonalStep from "./wizard/PersonalStep";
import ReviewStep from "./wizard/ReviewStep";

const STEPS = [
  { key: "personal",  label: "Personal",          Component: PersonalStep },
  { key: "business",  label: "Business",          Component: BusinessStep },
  { key: "documents", label: "Documents",         Component: DocumentsStep },
  { key: "review",    label: "Review & submit",   Component: ReviewStep },
];

export default function MerchantWizard() {
  const {
    submission, error, saving,
    setField, applyDocument, removeDocument,
    saveProgress, submitForReview,
  } = useDraftSubmission();
  const [stepIdx, setStepIdx] = useState(0);

  if (!submission) {
    return <div className="p-6 text-slate-500">{error || "Loading…"}</div>;
  }

  const editable = canEdit(submission);
  const inFlight = isInFlight(submission);
  const fieldsDisabled = !editable || inFlight;
  const missing = missingForSubmit(submission);
  const canSubmit = missing.length === 0;

  const step = STEPS[stepIdx];
  const StepComponent = step.Component;

  return (
    <div className="max-w-3xl mx-auto p-6 space-y-6">
      <WizardHeader state={submission.state} />
      <SubmissionBanner submission={submission} />

      <ol className="flex border rounded overflow-hidden bg-white">
        {STEPS.map((s, i) => (
          <li key={s.key}
            className={`flex-1 p-3 text-center text-sm border-r last:border-r-0 cursor-pointer
              ${i === stepIdx ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-50"}`}
            onClick={() => setStepIdx(i)}>
            <span className="font-medium">{i + 1}.</span> {s.label}
          </li>
        ))}
      </ol>

      <div className="bg-white border rounded p-6 space-y-4">
        <StepComponent
          submission={submission}
          fieldsDisabled={fieldsDisabled}
          missing={missing}
          editable={editable}
          inFlight={inFlight}
          setField={setField}
          applyDocument={applyDocument}
          removeDocument={removeDocument}
        />
        {error && <pre className="text-sm text-red-600 whitespace-pre-wrap">{error}</pre>}
      </div>

      <ActionBar
        stepIdx={stepIdx}
        onPrev={() => setStepIdx(stepIdx - 1)}
        onNext={() => setStepIdx(stepIdx + 1)}
        onSave={saveProgress}
        onSubmit={submitForReview}
        canSave={editable && !inFlight}
        canSubmit={canSubmit}
        saving={saving}
        editable={editable}
        inFlight={inFlight}
        missing={missing}
      />
    </div>
  );
}


function WizardHeader({ state }) {
  return (
    <div className="flex items-center justify-between">
      <div>
        <h1 className="text-2xl font-semibold">KYC application</h1>
        <p className="text-sm text-slate-500">
          Complete every step to start collecting payments.
        </p>
      </div>
      <StateBadge state={state} />
    </div>
  );
}


function SubmissionBanner({ submission }) {
  if (submission.state === "more_info_requested" && submission.info_request_reason) {
    return (
      <div className="bg-purple-50 border border-purple-200 text-sm rounded p-3">
        <div className="font-medium text-purple-800">Reviewer requested more info</div>
        <div className="text-purple-700">{submission.info_request_reason}</div>
      </div>
    );
  }
  if (submission.state === "rejected" && submission.rejection_reason) {
    return (
      <div className="bg-red-50 border border-red-200 text-sm rounded p-3">
        <div className="font-medium text-red-700">Rejected</div>
        <div className="text-red-700">{submission.rejection_reason}</div>
      </div>
    );
  }
  if (submission.state === "approved") {
    return (
      <div className="bg-emerald-50 border border-emerald-200 text-sm rounded p-3 text-emerald-800">
        You're approved. Welcome to Playto Pay!
      </div>
    );
  }
  return null;
}


function ActionBar({
  stepIdx, onPrev, onNext, onSave, onSubmit,
  canSave, canSubmit, saving, editable, inFlight, missing,
}) {
  const isLastStep = stepIdx === STEPS.length - 1;
  const submitTitle = !canSubmit ? `Missing: ${missing.join(", ")}` : undefined;

  return (
    <div className="flex items-center justify-between">
      <button className="px-3 py-2 text-sm text-slate-600 disabled:opacity-30"
        disabled={stepIdx === 0} onClick={onPrev}>
        ← Back
      </button>

      <div className="space-x-2">
        {canSave && (
          <button onClick={onSave} disabled={saving}
            className="px-3 py-2 text-sm border rounded">
            {saving ? "Saving…" : "Save progress"}
          </button>
        )}
        {!isLastStep ? (
          <button onClick={onNext}
            className="px-3 py-2 text-sm bg-slate-900 text-white rounded">
            Next →
          </button>
        ) : (
          <button onClick={onSubmit}
            disabled={saving || !editable || inFlight || !canSubmit}
            title={submitTitle}
            className="px-3 py-2 text-sm bg-emerald-600 text-white rounded disabled:opacity-50">
            {saving ? "Submitting…" : "Submit for review"}
          </button>
        )}
      </div>
    </div>
  );
}
