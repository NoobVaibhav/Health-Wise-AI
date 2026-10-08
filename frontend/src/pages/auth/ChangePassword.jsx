import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ROLE_HOME, useAuth } from "../../context/AuthContext";
import { changePassword } from "../../services/authApi";
import { getErrorMessage } from "../../services/api";
import { Button, Input } from "../../components/ui";
import { AuthShell } from "./Login";

// Accounts created with a temporary password must set their own password at first login.
export default function ChangePassword() {
  const { user, refresh } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ current_password: "", new_password: "" });
  const [error, setError] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    try {
      await changePassword(form);
      await refresh();
      navigate(ROLE_HOME[user.role]);
    } catch (err) {
      setError(getErrorMessage(err));
    }
  };

  return (
    <AuthShell title="Set a new password">
      <p className="mb-3 text-sm text-slate-500">{user.must_change_password ? "You are using a temporary password. Please choose your own." : "Change your password."}</p>
      <form onSubmit={submit} className="space-y-4">
        <Input type="password" placeholder="Current (temporary) password" required value={form.current_password} onChange={(e) => setForm({ ...form, current_password: e.target.value })} />
        <Input type="password" placeholder="New password (at least 8 characters)" required minLength={8} value={form.new_password} onChange={(e) => setForm({ ...form, new_password: e.target.value })} />
        {error && <p className="text-sm text-red-600">{error}</p>}
        <Button className="w-full">Save password</Button>
      </form>
    </AuthShell>
  );
}
