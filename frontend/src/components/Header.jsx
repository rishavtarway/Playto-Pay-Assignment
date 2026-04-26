import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export default function Header() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  function onLogout() {
    logout();
    navigate("/login", { replace: true });
  }

  return (
    <header className="border-b bg-white">
      <div className="max-w-5xl mx-auto px-6 py-3 flex items-center justify-between">
        <Link to="/" className="font-semibold text-slate-900">Playto Pay</Link>
        {user && (
          <div className="flex items-center gap-3 text-sm">
            <span className="text-slate-500">{user.email} · {user.role}</span>
            <button onClick={onLogout} className="text-slate-700 hover:underline">Sign out</button>
          </div>
        )}
      </div>
    </header>
  );
}
