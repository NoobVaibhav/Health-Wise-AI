import { useEffect, useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { ROLE_HOME, useAuth } from "../../context/AuthContext";
import { getErrorMessage } from "../../services/api";
import { getSetupStatus } from "../../services/authApi";
import { Button, Input } from "../../components/ui";
import { FormField, PasswordInput } from "../../components/FormField";
import useValidation from "../../hooks/useValidation";
import * as v from "../../utils/validators";
import { Loading } from "../../components/Feedback";
import { AuthShell } from "./Login";

const RULES = {
  full_name: (value) => v.personName(value),
  email: (value) => v.email(value),
  password: (value, all) => v.password(value, { email: all.email }),
  confirm: (value, all) => v.confirmPassword(all.password, value),
};

// Works only while the system has no users: creates the first administrator.
export default function Register() {
  const { user, registerFirstAdmin } = useAuth();
  const navigate = useNavigate();
  const [needsSetup, setNeedsSetup] = useState(null);
  const [form, setForm] = useState({ full_name: "", email: "", password: "", confirm: "" });
  const check = useValidation(RULES);
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
    if (busy) return;
    if (!check.validateAll(form)) return;
    setBusy(true);
    setError("");
    try {
      const u = await registerFirstAdmin({ full_name: v.cleanText(form.full_name), email: form.email.trim().toLowerCase(), password: form.password });
      navigate(ROLE_HOME[u.role]);
    } catch (err) {
      if (!check.fromServer(err)) setError(getErrorMessage(err));          // what was typed stays in the boxes
    } finally {
      setBusy(false);
    }
  };
  const set = (name) => (e) => { setForm({ ...form, [name]: e.target.value }); check.clear(name); };
  const blur = (name) => () => check.check(name, form);

  return (
    <AuthShell title="Create the first administrator">
      <form onSubmit={submit} noValidate className="space-y-4" aria-busy={busy}>
        <FormField label="Full name" name="full_name" error={check.errors.full_name}>
          <Input autoComplete="name" placeholder="Full name" maxLength={150} value={form.full_name} onChange={set("full_name")} onBlur={blur("full_name")} />
        </FormField>
        <FormField label="Email" name="email" error={check.errors.email}>
          <Input type="email" inputMode="email" autoComplete="email" placeholder="you@example.com" maxLength={254} value={form.email} onChange={set("email")} onBlur={blur("email")} />
        </FormField>
        <FormField label="Password" name="password" error={check.errors.password} hint="At least 8 characters, with a letter and a number.">
          <PasswordInput meter placeholder="Password (at least 8 characters)" value={form.password} onChange={set("password")} onBlur={blur("password")} />
        </FormField>
        <FormField label="Type the password again" name="confirm" error={check.errors.confirm}>
          <PasswordInput placeholder="Type the password again" value={form.confirm} onChange={set("confirm")} onBlur={blur("confirm")} />
        </FormField>
        {error && <p role="alert" className="rounded-xl bg-red-50 p-3 text-sm font-medium text-red-700">{error}</p>}
        <Button disabled={busy} className="w-full">{busy ? "Creating..." : "Create administrator"}</Button>
      </form>
    </AuthShell>
  );
}
