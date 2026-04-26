// Drag-and-drop document uploader (bonus). Uses react-dropzone, validates on
// the server side too — the client check is just to fail fast.
import { useState } from "react";
import { useDropzone } from "react-dropzone";
import client from "../api/client";
import { describeError } from "../lib/format";

const ACCEPT = {
  "application/pdf": [".pdf"],
  "image/jpeg": [".jpg", ".jpeg"],
  "image/png": [".png"],
};

export default function DocumentDropzone({ kind, label, existing, onUploaded, onDeleted, disabled }) {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function uploadFile(file) {
    setError("");
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("kind", kind);
      fd.append("file", file);
      const r = await client.post("/submissions/me/documents/", fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      onUploaded?.(r.data);
    } catch (err) {
      setError(describeError(err));
    } finally {
      setBusy(false);
    }
  }

  async function deleteExisting() {
    if (!existing) return;
    setBusy(true);
    try {
      await client.delete(`/submissions/me/documents/${existing.id}/`);
      onDeleted?.(existing.id);
    } catch (err) {
      setError(describeError(err));
    } finally {
      setBusy(false);
    }
  }

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    accept: ACCEPT,
    maxFiles: 1,
    disabled: disabled || busy,
    onDrop: (files) => files[0] && uploadFile(files[0]),
  });

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <div className="text-sm font-medium text-slate-700">{label}</div>
        {existing && !disabled && (
          <button type="button" onClick={deleteExisting}
            className="text-xs text-red-600 hover:underline">Remove</button>
        )}
      </div>

      {existing ? (
        <a href={existing.file_url} target="_blank" rel="noreferrer"
          className="block border rounded p-3 text-sm bg-emerald-50 border-emerald-200 hover:bg-emerald-100">
          <div className="font-medium text-emerald-800">{existing.original_name}</div>
          <div className="text-xs text-emerald-700">
            {(existing.size_bytes / 1024).toFixed(1)} KB · uploaded
          </div>
        </a>
      ) : (
        <div {...getRootProps()}
          className={`border-2 border-dashed rounded p-4 text-center cursor-pointer text-sm
            ${isDragActive ? "bg-slate-100 border-slate-400" : "border-slate-300"}
            ${disabled ? "opacity-50 cursor-not-allowed" : ""}`}>
          <input {...getInputProps()} />
          {busy ? "Uploading…" : "Drop a PDF / JPG / PNG (max 5 MB) or click to choose"}
        </div>
      )}

      {error && <pre className="text-xs text-red-600 whitespace-pre-wrap">{error}</pre>}
    </div>
  );
}
