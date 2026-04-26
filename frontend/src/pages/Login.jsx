import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import client from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { describeError } from "../lib/format";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  // Hit /auth/login/, stash token, route based on role.
  async function onSubmit(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const r = await client.post("/auth/login/", { email, password });
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
        <h1 className="text-2xl font-semibold">Sign in</h1>
        <p className="text-sm text-slate-500">Playto Pay KYC console</p>

        <input className="w-full border rounded px-3 py-2" type="email" required
          value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Email" />
        <input className="w-full border rounded px-3 py-2" type="password" required
          value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Password" />

        {error && <pre className="text-sm text-red-600 whitespace-pre-wrap">{error}</pre>}

        <button disabled={busy}
          className="w-full bg-slate-900 text-white py-2 rounded disabled:opacity-50">
          {busy ? "Signing in…" : "Sign in"}
        </button>

        <div className="text-sm text-slate-500">
          New here? <Link className="text-slate-900 underline" to="/signup">Create an account</Link>
        </div>

        <details className="text-xs text-slate-400 pt-2">
          <summary className="cursor-pointer">Test credentials</summary>
          <div className="pt-2 space-y-1">
            <div>reviewer@playto.test / reviewer123</div>
            <div>draft@playto.test / merchant123</div>
            <div>review@playto.test / merchant123</div>
          </div>
        </details>
      </form>
    </div>
  );
}
