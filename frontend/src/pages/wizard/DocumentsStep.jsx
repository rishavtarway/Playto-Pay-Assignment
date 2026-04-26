// Step 3: PAN / Aadhaar / bank-statement upload via DocumentDropzone.
import DocumentDropzone from "../../components/DocumentDropzone";
import { REQUIRED_DOCUMENT_KINDS } from "../../lib/submission";

const DOCUMENT_LABELS = {
  pan:            "PAN",
  aadhaar:        "Aadhaar",
  bank_statement: "Bank statement",
};

export default function DocumentsStep({
  submission, fieldsDisabled, applyDocument, removeDocument,
}) {
  const documentsByKind = indexByKind(submission.documents);

  return (
    <div className="space-y-4">
      <p className="text-xs text-slate-500">
        All three documents are required before you can submit. PDF, JPG, or
        PNG, up to 5 MB each.
      </p>
      {REQUIRED_DOCUMENT_KINDS.map((kind) => (
        <DocumentDropzone
          key={kind}
          kind={kind}
          label={`${DOCUMENT_LABELS[kind]} *`}
          existing={documentsByKind[kind]}
          disabled={fieldsDisabled}
          onUploaded={applyDocument}
          onDeleted={removeDocument}
        />
      ))}
    </div>
  );
}

function indexByKind(documents) {
  const indexed = {};
  for (const doc of documents || []) indexed[doc.kind] = doc;
  return indexed;
}
