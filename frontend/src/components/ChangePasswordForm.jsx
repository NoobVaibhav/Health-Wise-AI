import { useMemo, useState } from "react";
import { CheckCircle2, Circle } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { changePassword } from "../services/authApi";
import { getErrorMessage, tokenStore } from "../services/api";
import { Button } from "./ui";
import { FormField, PasswordInput } from "./FormField";
import useValidation from "../hooks/useValidation";
import * as v from "../utils/validators";

// The password form shared by the pop-up shown after the first login and the "Change password" page.
const RULES = [
  ["At least 8 characters", (p) => p.length >= 8],
  ["At least one letter", (p) => /[A-Za-z]/.test(p)],
  ["At least one number", (p) => /\d/.test(p)],
];

/** first: the person is still using the starting password. onDone runs after the new password is saved and the session refreshed. */
export default function ChangePasswordForm({ first, onDone }) {
  const { user, refresh } = useAuth();
  const [form, setForm] = useState({ current_password: "", new_password: "", confirm: "" });
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const rules = useMemo(() => ({
    current_password: (value) => (value ? "" : "Please type your current password."),
    new_password: (value, all) => v.password(value, { email: user?.email, current: all.current_password }),
    confirm: (value, all) => v.confirmPassword(all.new_password, value),
  }), [user?.email]);
  const check = useValidation(rules);
  const checks = RULES.map(([label, test]) => [label, test(form.new_password)]);
  const ready = Object.keys(v.validateAll(rules, form)).length === 0;
  const set = (name) => (e) => { setForm({ ...form, [name]: e.target.value }); check.clear(name); if (name === "new_password" && form.confirm) check.clear("confirm"); };
  const blur = (name) => () => check.check(name, form);

  const submit = async (e) => {
    e.preventDefault();
    if (saving) return;
    if (!check.validateAll(form)) return;
    setSaving(true); setError("");
    try {
      const result = await changePassword({ current_password: form.current_password, new_password: form.new_password });
      if (result.access_token) tokenStore.set(result.access_token);      // the old token stops working after a password change
      await refresh();
      onDone?.();
    } catch (err) {
      if (!check.fromServer(err)) setError(getErrorMessage(err));        // the typed passwords stay in the boxes
    } finally { setSaving(false); }
  };

  return (
    <form onSubmit={submit} noValidate className="space-y-3" aria-busy={saving}>
      <FormField label={first ? "Starting password" : "Current password"} name="current_password" error={check.errors.current_password}>
        <PasswordInput value={form.current_password} onChange={set("current_password")} onBlur={blur("current_password")} autoFocus={first} autoComplete="current-password"
          placeholder={first ? "Starting password (the one you just used)" : "Current password"} />
      </FormField>
      <FormField label="New password" name="new_password" error={check.errors.new_password}>
        <PasswordInput meter value={form.new_password} onChange={set("new_password")} onBlur={blur("new_password")} autoComplete="new-password" placeholder="New password" />
      </FormField>
      <ul className="flex flex-wrap gap-x-4 gap-y-1 text-sm" aria-label="Password rules">
        {checks.map(([label, ok]) => <li key={label} className={`flex items-center gap-1.5 ${ok ? "text-emerald-700" : "text-slate-500"}`}>{ok ? <CheckCircle2 size={16} /> : <Circle size={16} />}{label}</li>)}
      </ul>
      <FormField label="Type the new password again" name="confirm" error={check.errors.confirm}>
        <PasswordInput value={form.confirm} onChange={set("confirm")} onBlur={blur("confirm")} autoComplete="new-password" placeholder="Type the new password again" />
      </FormField>
      {form.confirm.length > 0 && form.new_password !== form.confirm && !check.errors.confirm && <p className="text-sm font-medium text-red-600">The two passwords are not the same.</p>}
      {error && <p className="rounded-xl bg-red-50 p-2.5 text-sm font-semibold text-red-700" role="alert">{error}</p>}
      <Button className="w-full py-3 text-base" disabled={!ready || saving}>{saving ? "Saving..." : "Save my password and continue"}</Button>
    </form>
  );
}
