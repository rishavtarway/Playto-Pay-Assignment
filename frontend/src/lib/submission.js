// Domain helpers for KYC submissions.
//
// Mirrors the server-side rules in backend/kyc/views.py so the UI can warn
// before the merchant clicks Submit and gets a 400 back.

export const REQUIRED_DOCUMENT_KINDS = ["pan", "aadhaar", "bank_statement"];

export const BUSINESS_TYPE_OPTIONS = [
  ["", "Choose…"],
  ["freelance", "Freelancer"],
  ["agency", "Agency"],
  ["company", "Company"],
];

// Submission states in which the merchant can still edit fields / docs.
const EDITABLE_STATES = ["draft", "more_info_requested"];

// States where the submission is locked while a reviewer is looking at it.
const IN_FLIGHT_STATES = ["submitted", "under_review"];

export function canEdit(submission) {
  return !!submission && EDITABLE_STATES.includes(submission.state);
}

export function isInFlight(submission) {
  return !!submission && IN_FLIGHT_STATES.includes(submission.state);
}

// Return human-readable labels for everything still missing from a submission.
// Drives the "Still needed before you can submit" checklist + the disabled
// Submit button. Match the server: explicit 0 monthly volume is valid.
export function missingForSubmit(submission) {
  if (!submission) return [];
  const missing = [];

  if (!submission.full_name)     missing.push("Full name");
  if (!submission.email)         missing.push("Email");
  if (!submission.phone)         missing.push("Phone");
  if (!submission.business_name) missing.push("Business name");
  if (!submission.business_type) missing.push("Business type");

  const volume = submission.expected_monthly_volume_usd;
  if (volume === null || volume === "" || volume === undefined) {
    missing.push("Expected monthly volume");
  }

  const uploadedKinds = new Set((submission.documents || []).map((d) => d.kind));
  for (const kind of REQUIRED_DOCUMENT_KINDS) {
    if (!uploadedKinds.has(kind)) {
      missing.push(`${kind.replace("_", " ")} document`);
    }
  }
  return missing;
}

// Build the PATCH payload for /submissions/me/ from the current draft.
export function patchPayload(submission) {
  return {
    full_name:                  submission.full_name || "",
    email:                      submission.email || "",
    phone:                      submission.phone || "",
    business_name:              submission.business_name || "",
    business_type:              submission.business_type || "",
    expected_monthly_volume_usd: submission.expected_monthly_volume_usd || 0,
  };
}
