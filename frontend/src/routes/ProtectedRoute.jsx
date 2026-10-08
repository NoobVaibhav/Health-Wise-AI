import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { Loading } from "../components/Feedback";

// Only logged-in users get through. Users with a temporary password must change it first.
export default function ProtectedRoute() {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <Loading text="Starting HealthWise AI..." />;
  if (!user) return <Navigate to="/login" replace />;
  if (user.must_change_password && location.pathname !== "/change-password") return <Navigate to="/change-password" replace />;
  return <Outlet />;
}
