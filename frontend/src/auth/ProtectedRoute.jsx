// Bounce unauthenticated visitors to /login. If a `role` prop is given we also
// check that the logged-in user has that role.
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "./AuthContext";

export default function ProtectedRoute({ role, children }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <div className="p-6 text-slate-500">Loading…</div>;
  if (!user) return <Navigate to="/login" replace state={{ from: location }} />;
  if (role && user.role !== role) {
    return <Navigate to={user.role === "merchant" ? "/merchant" : "/reviewer"} replace />;
  }
  return children;
}
