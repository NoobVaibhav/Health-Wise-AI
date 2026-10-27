import { useState } from "react";
import { CheckCircle2, Circle, Eye, EyeOff } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { changePassword } from "../services/authApi";
import { getErrorMessage, tokenStore } from "../services/api";
import { Button, inputClass } from "./ui";

// The password form shared by the pop-up shown after the first login and the "Change password" page.
const RULES = [
  ["At least 8 characters", (p) => p.length >= 8],
  ["At least one letter", (p) => /[A-Za-z]/.test(p)],
  ["At least one number", (p) => /\d/.test(p)],
];

function PasswordBox({ value, onChange, placeholder, autoFocus, autoComplete }) {
  const [show, setShow] = useState(false);
  return (
    <div className="relative">
      <input type={show ? "text" : "password"} placeholder={placeholder} aria-label={placeholder} required value={value} autoFocus={autoFocus} autoComplete={autoComplete} onChange={(e) => onChange(e.target.value)} className={`${inputClass} pr-12`} />
      <button type="button" onClick={() => setShow(!show)} aria-label={show ? "Hide password" : "Show password"} className="absolute right-3 top-3 text-slate-500 hover:text-slate-800">{show ? <EyeOff size={20} /> : <Eye size={20} />}</button>
    </div>
  );
}

/** first: the person is still using the starting password. onDone runs after the new password is saved and the session refreshed. */
export default function ChangePasswordForm({ first, onDone }) {
  const { refresh } = useAuth();
  const [form, setForm] = useState({ current_password: "", new_password: "", confirm: "" });
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const checks = RULES.map(([label, test]) => [label, test(form.new_password)]);
  const same = form.new_password.length > 0 && form.new_password === form.confirm;
  const ready = checks.every(([, ok]) => ok) && same && form.current_password.length > 0;

  const submit = async (e) => {
    e.preventDefault();
    if (!ready || saving) return;
    setSaving(true); setError("");
    try {
      const result = await changePassword({ current_password: form.current_password, new_password: form.new_password });
      if (result.access_token) tokenStore.set(result.access_token);      // the old token stops working after a password change
      await refresh();
      onDone?.();
    } catch (err) {
      setError(getErrorMessage(err));
    } finally { setSaving(false); }
  };

  return (
    <form onSubmit={submit} className="space-y-3">
      <PasswordBox value={form.current_password} onChange={(v) => setForm({ ...form, current_password: v })} placeholder={first ? "Starting password (the one you just used)" : "Current password"} autoFocus={first} autoComplete="current-password" />
      <PasswordBox value={form.new_password} onChange={(v) => setForm({ ...form, new_password: v })} placeholder="New password" autoComplete="new-password" />
      <ul className="flex flex-wrap gap-x-4 gap-y-1 text-sm" aria-label="Password rules">
        {checks.map(([label, ok]) => <li key={label} className={`flex items-center gap-1.5 ${ok ? "text-emerald-700" : "text-slate-500"}`}>{ok ? <CheckCircle2 size={16} /> : <Circle size={16} />}{label}</li>)}
      </ul>
      <PasswordBox value={form.confirm} onChange={(v) => setForm({ ...form, confirm: v })} placeholder="Type the new password again" autoComplete="new-password" />
      {form.confirm.length > 0 && !same && <p className="text-sm text-red-600">The two passwords are not the same.</p>}
      {error && <p className="rounded-xl bg-red-50 p-2.5 text-sm font-semibold text-red-700" role="alert">{error}</p>}
      <Button className="w-full py-3 text-base" disabled={!ready || saving}>{saving ? "Saving..." : "Save my password and continue"}</Button>
    </form>
  );
}
