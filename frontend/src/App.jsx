import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import Header from "./components/Header";
import { AuthProvider, useAuth } from "./auth/AuthContext";
import ProtectedRoute from "./auth/ProtectedRoute";
import Login from "./pages/Login";
import Signup from "./pages/Signup";
import MerchantWizard from "./pages/MerchantWizard";
import ReviewerDashboard from "./pages/ReviewerDashboard";
import ReviewerDetail from "./pages/ReviewerDetail";

// Tiny landing — bounce to the right home for the role.
function Home() {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  return <Navigate to={user.role === "merchant" ? "/merchant" : "/reviewer"} replace />;
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
          <Route path="/merchant" element={
            <ProtectedRoute role="merchant"><MerchantWizard /></ProtectedRoute>
          } />
          <Route path="/reviewer" element={
            <ProtectedRoute role="reviewer"><ReviewerDashboard /></ProtectedRoute>
          } />
          <Route path="/reviewer/:id" element={
            <ProtectedRoute role="reviewer"><ReviewerDetail /></ProtectedRoute>
          } />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
