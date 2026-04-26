import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import client from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { describeError } from "../lib/format";

export default function Signup() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ email: "", password: "", role: "merchant" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  function onChange(e) {
    setForm({ ...form, [e.target.name]: e.target.value });
  }

  async function onSubmit(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const r = await client.post("/auth/signup/", form);
      login(r.data.token, r.data.user);
      navigate(r.data.user.role === "merchant" ? "/merchant" : "/reviewer", { replace: true });
    } catch (err) {
      setError(describeError(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-full flex items-center justify-center bg-slate-50 p-6">
      <form onSubmit={onSubmit} className="w-full max-w-sm bg-white shadow rounded-lg p-6 space-y-4">
        <h1 className="text-2xl font-semibold">Create account</h1>
        <input name="email" type="email" required placeholder="Email"
          className="w-full border rounded px-3 py-2"
          value={form.email} onChange={onChange} />
        <input name="password" type="password" required placeholder="Password (min 8 chars)"
          className="w-full border rounded px-3 py-2"
          value={form.password} onChange={onChange} />
        <select name="role" className="w-full border rounded px-3 py-2"
          value={form.role} onChange={onChange}>
          <option value="merchant">Merchant</option>
          <option value="reviewer">Reviewer</option>
        </select>

        {error && <pre className="text-sm text-red-600 whitespace-pre-wrap">{error}</pre>}

        <button disabled={busy}
          className="w-full bg-slate-900 text-white py-2 rounded disabled:opacity-50">
          {busy ? "Creating…" : "Create account"}
        </button>

        <div className="text-sm text-slate-500">
          Already have an account? <Link className="text-slate-900 underline" to="/login">Sign in</Link>
        </div>
      </form>
    </div>
  );
}
