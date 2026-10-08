import { Navigate, Outlet } from "react-router-dom";
import { ROLE_HOME, useAuth } from "../context/AuthContext";

// Only the listed roles may open the pages inside. Anyone else is sent to their own home page.
// (The backend enforces the same rules; this just avoids showing pages that would fail.)
export default function RoleRoute({ roles }) {
  const { user } = useAuth();
  if (!roles.includes(user.role)) return <Navigate to={ROLE_HOME[user.role]} replace />;
  return <Outlet />;
}
