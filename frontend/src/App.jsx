import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import Header from "./components/Header";
import { AuthProvider, useAuth } from "./auth/AuthContext";
import Login from "./pages/Login";
import Signup from "./pages/Signup";

// Tiny landing — bounce to the right home once we have role-specific pages.
function Home() {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  return <div className="p-6 text-slate-600">Signed in as {user.email}.</div>;
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Header />
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/login" element={<Login />} />
          <Route path="/signup" element={<Signup />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
