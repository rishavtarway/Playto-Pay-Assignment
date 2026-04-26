// Loads a single submission for the reviewer detail page and exposes a
// single `runAction(action, { requireReason })` function that mirrors the
// four reviewer endpoints. Reload-on-success is built in.
import { useCallback, useEffect, useState } from "react";
import client from "../api/client";
import { describeError } from "../lib/format";

export function useSubmissionDetail(submissionId) {
  const [submission, setSubmission] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [reason, setReason] = useState("");

  const load = useCallback(() => {
    client.get(`/reviews/${submissionId}/`)
      .then((r) => setSubmission(r.data))
      .catch((err) => setError(describeError(err)));
  }, [submissionId]);

  useEffect(() => { load(); }, [load]);

  async function runAction(action, { requireReason = false } = {}) {
    if (requireReason && !reason.trim()) {
      setError("Reason is required.");
      return;
    }
    setError("");
    setBusy(true);
    try {
      await client.post(`/reviews/${submissionId}/${action}/`, { reason });
      setReason("");
      load();
    } catch (err) {
      setError(describeError(err));
    } finally {
      setBusy(false);
    }
  }

  return { submission, error, busy, reason, setReason, runAction };
}
