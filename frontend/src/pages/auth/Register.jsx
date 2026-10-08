import { useEffect, useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { ROLE_HOME, useAuth } from "../../context/AuthContext";
import { getErrorMessage } from "../../services/api";
import { getSetupStatus } from "../../services/authApi";
import { Button, Input } from "../../components/ui";
import { Loading } from "../../components/Feedback";
import { AuthShell } from "./Login";

// Works only while the system has no users: creates the first administrator.
export default function Register() {
  const { user, registerFirstAdmin } = useAuth();
  const navigate = useNavigate();
  const [needsSetup, setNeedsSetup] = useState(null);
  const [form, setForm] = useState({ full_name: "", email: "", password: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => { getSetupStatus().then((s) => setNeedsSetup(s.needs_setup)).catch(() => setNeedsSetup(false)); }, []);

  if (user) return <Navigate to={ROLE_HOME[user.role]} replace />;
  if (needsSetup === null) return <Loading />;
  if (!needsSetup) {
    return (
      <AuthShell title="Registration is closed">
        <p className="text-slate-600">Accounts are created by hospital staff. Please contact the hospital reception or the administrator.</p>
        <Link to="/login" className="mt-3 inline-block font-medium text-brand-700">Back to login</Link>
      </AuthShell>
    );
  }

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const u = await registerFirstAdmin(form);
      navigate(ROLE_HOME[u.role]);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthShell title="Create the first administrator">
      <form onSubmit={submit} className="space-y-4">
        <Input placeholder="Full name" required value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
        <Input type="email" placeholder="Email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
        <Input type="password" placeholder="Password (at least 8 characters)" required minLength={8} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
        {error && <p className="text-sm text-red-600">{error}</p>}
        <Button disabled={busy} className="w-full">{busy ? "Creating..." : "Create administrator"}</Button>
      </form>
    </AuthShell>
  );
}
