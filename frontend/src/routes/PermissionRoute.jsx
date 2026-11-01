import { Navigate, Outlet } from "react-router-dom";
import { ROLE_HOME, useAuth } from "../context/AuthContext";

// Opens the pages inside only for a person who has at least one of the permissions (what a person may do, not which login they use).
// The backend enforces the same rules; this just avoids showing pages that would fail.
export default function PermissionRoute({ any }) {
  const { user } = useAuth();
  const mine = user.permissions || [];
  if (!any.some((p) => mine.includes(p))) return <Navigate to={ROLE_HOME[user.role]} replace />;
  return <Outlet />;
}
