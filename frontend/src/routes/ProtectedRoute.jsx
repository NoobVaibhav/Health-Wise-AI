import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { Loading } from "../components/Feedback";
import ChangePasswordDialog from "../components/ChangePasswordDialog";

// Only logged-in users get through. Users with a temporary password must change it first.
export default function ProtectedRoute() {
  const { user, loading } = useAuth();
  if (loading) return <Loading text="Starting HealthWise AI..." />;
  if (!user) return <Navigate to="/login" replace />;
  if (user.must_change_password) return <ChangePasswordDialog />;        // pop-up over a blank page until the starting password is replaced
  return <Outlet />;
}
