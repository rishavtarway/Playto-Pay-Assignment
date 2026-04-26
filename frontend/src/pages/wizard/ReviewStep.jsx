// Step 4: read-only summary + "still missing" checklist.
import { REQUIRED_DOCUMENT_KINDS } from "../../lib/submission";
import { ReviewRow } from "./Field";

export default function ReviewStep({ submission, missing, editable, inFlight }) {
  const documentsSummary = REQUIRED_DOCUMENT_KINDS
    .map((kind) => `${kind}: ${submission.documents.some((d) => d.kind === kind) ? "✓" : "—"}`)
    .join("  ");

  const showChecklist = missing.length > 0 && editable && !inFlight;

  return (
    <div className="space-y-3 text-sm">
      <ReviewRow label="Name"           value={submission.full_name} />
      <ReviewRow label="Email"          value={submission.email} />
      <ReviewRow label="Phone"          value={submission.phone} />
      <ReviewRow label="Business"
        value={`${submission.business_name} (${submission.business_type})`} />
      <ReviewRow label="Monthly volume"
        value={`$${submission.expected_monthly_volume_usd}`} />
      <ReviewRow label="Documents"      value={documentsSummary} />

      {showChecklist && <MissingChecklist items={missing} />}
    </div>
  );
}


function MissingChecklist({ items }) {
  return (
    <div className="mt-4 bg-amber-50 border border-amber-200 rounded p-3 text-amber-800">
      <div className="font-medium mb-1">Still needed before you can submit:</div>
      <ul className="list-disc list-inside text-xs space-y-0.5">
        {items.map((item) => <li key={item}>{item}</li>)}
      </ul>
    </div>
  );
}
