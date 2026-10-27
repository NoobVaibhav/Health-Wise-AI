import { useNavigate } from "react-router-dom";
import { ROLE_HOME, useAuth } from "../../context/AuthContext";
import ChangePasswordForm from "../../components/ChangePasswordForm";
import { AuthShell } from "./Login";

// Someone who already has their own password changes it here (Account menu). The first-login case is the pop-up (ChangePasswordDialog).
export default function ChangePassword() {
  const { user } = useAuth();
  const navigate = useNavigate();
  return (
    <AuthShell title="Change your password">
      <p className="mb-4 text-slate-600">Enter your current password and choose a new one.</p>
      <ChangePasswordForm onDone={() => navigate(ROLE_HOME[user.role])} />
    </AuthShell>
  );
}
