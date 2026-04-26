// AuthContext keeps the current user + token in React state and in
// localStorage so a hard refresh keeps you logged in.
import { createContext, useContext, useEffect, useMemo, useState } from "react";
import client from "../api/client";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    const raw = localStorage.getItem("user");
    return raw ? JSON.parse(raw) : null;
  });
  const [loading, setLoading] = useState(false);

  // Lightweight sanity check on mount — if we have a token, refresh /me/.
  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token || user) return;
    setLoading(true);
    client
      .get("/auth/me/")
      .then((r) => {
        setUser(r.data);
        localStorage.setItem("user", JSON.stringify(r.data));
      })
      .catch(() => {
        localStorage.removeItem("token");
        localStorage.removeItem("user");
      })
      .finally(() => setLoading(false));
  }, []); // run once

  function login(token, userData) {
    localStorage.setItem("token", token);
    localStorage.setItem("user", JSON.stringify(userData));
    setUser(userData);
  }

  function logout() {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    setUser(null);
  }

  const value = useMemo(() => ({ user, loading, login, logout }), [user, loading]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
