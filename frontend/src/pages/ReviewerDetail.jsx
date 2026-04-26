// Single-submission page with the four reviewer actions.
// Data + action posting live in useSubmissionDetail; this file is layout.
import { Link, useParams } from "react-router-dom";
import StateBadge from "../components/StateBadge";
import { useSubmissionDetail } from "../hooks/useSubmissionDetail";
import { formatDuration } from "../lib/format";

// State guards for the action buttons. Mirrors backend/kyc/state_machine.py.
const STATES = {
  SUBMITTED:    "submitted",
  UNDER_REVIEW: "under_review",
};

export default function ReviewerDetail() {
  const { id } = useParams();
  const { submission, error, busy, reason, setReason, runAction } = useSubmissionDetail(id);

  if (!submission) {
    return <div className="p-6 text-slate-500">{error || "Loading…"}</div>;
  }

  const canStart  = submission.state === STATES.SUBMITTED;
  const canDecide = submission.state === STATES.UNDER_REVIEW;

  return (
    <div className="max-w-3xl mx-auto p-6 space-y-6">
      <Link to="/reviewer" className="text-sm text-slate-600 hover:underline">← Back to queue</Link>

      <DetailHeader submission={submission} />

      <Section title="Personal">
        <Row label="Name"  value={submission.full_name} />
        <Row label="Email" value={submission.email} />
        <Row label="Phone" value={submission.phone} />
      </Section>

      <Section title="Business">
        <Row label="Business name"            value={submission.business_name} />
        <Row label="Business type"            value={submission.business_type} />
        <Row label="Expected monthly volume"  value={`$${submission.expected_monthly_volume_usd}`} />
      </Section>

      <Section title="Documents"><DocumentList documents={submission.documents} /></Section>

      <ReasonBanner submission={submission} />

      <Section title="Actions">
        <textarea className="w-full border rounded px-3 py-2 text-sm" rows={2}
          placeholder="Reason (required for reject / request info)"
          value={reason}
          onChange={(e) => setReason(e.target.value)} />

        {error && <pre className="text-sm text-red-600 whitespace-pre-wrap">{error}</pre>}

        <ActionButtons
          canStart={canStart}
          canDecide={canDecide}
          busy={busy}
          runAction={runAction}
        />
      </Section>
    </div>
  );
}


function DetailHeader({ submission }) {
  return (
    <div className="flex items-start justify-between">
      <div>
        <h1 className="text-2xl font-semibold">
          {submission.full_name || submission.merchant_email}
        </h1>
        <p className="text-sm text-slate-500">{submission.merchant_email}</p>
      </div>
      <div className="text-right space-y-1">
        <StateBadge state={submission.state} />
        {submission.submitted_at && (
          <div className="text-xs text-slate-500">
            waiting {formatDuration(submission.time_in_queue_seconds)}
            {submission.is_at_risk && (
              <span className="ml-1 text-red-700 font-medium">AT RISK</span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}


function DocumentList({ documents }) {
  if (!documents.length) {
    return <div className="text-slate-400 text-sm">No documents.</div>;
  }
  return documents.map((doc) => (
    <a key={doc.id} href={doc.file_url} target="_blank" rel="noreferrer"
      className="block border rounded p-3 mb-2 text-sm bg-slate-50 hover:bg-slate-100">
      <div className="font-medium">
        {doc.kind.replace("_", " ")}: {doc.original_name}
      </div>
      <div className="text-xs text-slate-500">
        {(doc.size_bytes / 1024).toFixed(1)} KB · {doc.content_type}
      </div>
    </a>
  ));
}


function ReasonBanner({ submission }) {
  if (submission.rejection_reason) {
    return (
      <div className="bg-red-50 border border-red-200 text-sm rounded p-3">
        <div className="font-medium text-red-700">Rejection reason</div>
        <div className="text-red-700">{submission.rejection_reason}</div>
      </div>
    );
  }
  if (submission.info_request_reason) {
    return (
      <div className="bg-purple-50 border border-purple-200 text-sm rounded p-3">
        <div className="font-medium text-purple-800">Info request</div>
        <div className="text-purple-700">{submission.info_request_reason}</div>
      </div>
    );
  }
  return null;
}


function ActionButtons({ canStart, canDecide, busy, runAction }) {
  return (
    <div className="flex gap-2 flex-wrap">
      <ActionButton onClick={() => runAction("start")}
        disabled={!canStart || busy}
        className="bg-slate-900 text-white">
        Start review
      </ActionButton>
      <ActionButton onClick={() => runAction("approve")}
        disabled={!canDecide || busy}
        className="bg-emerald-600 text-white">
        Approve
      </ActionButton>
      <ActionButton onClick={() => runAction("reject", { requireReason: true })}
        disabled={!canDecide || busy}
        className="bg-red-600 text-white">
        Reject
      </ActionButton>
      <ActionButton onClick={() => runAction("request-info", { requireReason: true })}
        disabled={!canDecide || busy}
        className="bg-purple-600 text-white">
        Request more info
      </ActionButton>
    </div>
  );
}


function Section({ title, children }) {
  return (
    <div className="bg-white border rounded p-4 space-y-2">
      <div className="text-sm font-semibold text-slate-700">{title}</div>
      {children}
    </div>
  );
}


function Row({ label, value }) {
  return (
    <div className="flex text-sm border-b last:border-b-0 py-1.5">
      <div className="w-44 text-slate-500">{label}</div>
      <div className="flex-1">{value || "—"}</div>
    </div>
  );
}


function ActionButton({ children, disabled, onClick, className = "" }) {
  return (
    <button onClick={onClick} disabled={disabled}
      className={`px-3 py-2 text-sm rounded disabled:opacity-50 ${className}`}>
      {children}
    </button>
  );
}
