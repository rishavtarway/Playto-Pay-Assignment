// Owns all server interaction for the merchant's draft submission so the
// MerchantWizard component can stay focused on rendering.
//
// Exposes:
//   { submission, error, saving, setField, applyDocument, removeDocument,
//     saveProgress, submitForReview }
//
// The hook deliberately does NOT know about wizard steps, validation copy,
// or any UI concerns — it's a thin domain wrapper around the API.
import { useEffect, useState } from "react";
import client from "../api/client";
import { describeError } from "../lib/format";
import { patchPayload } from "../lib/submission";

export function useDraftSubmission() {
  const [submission, setSubmission] = useState(null);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    client.get("/submissions/me/")
      .then((r) => setSubmission(r.data))
      .catch((err) => setError(describeError(err)));
  }, []);

  function setField(key, value) {
    setSubmission((current) => ({ ...current, [key]: value }));
  }

  function applyDocument(doc) {
    setSubmission((current) => ({
      ...current,
      documents: [
        ...current.documents.filter((d) => d.kind !== doc.kind),
        doc,
      ],
    }));
  }

  function removeDocument(docId) {
    setSubmission((current) => ({
      ...current,
      documents: current.documents.filter((d) => d.id !== docId),
    }));
  }

  // Inner save: callers own the error handling because submitForReview
  // needs to short-circuit on a save failure.
  async function patchDraft() {
    const r = await client.patch("/submissions/me/", patchPayload(submission));
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

  // One save+submit unit: if the PATCH fails we never POST, and `saving`
  // stays true until the whole sequence settles.
  async function submitForReview() {
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

  return {
    submission,
    error,
    saving,
    setField,
    applyDocument,
    removeDocument,
    saveProgress,
    submitForReview,
  };
}
