import { useEffect, useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { Bot, FileSearch, HeartPulse, Pill, ShieldCheck, Stethoscope } from "lucide-react";
import { ROLE_HOME, useAuth } from "../../context/AuthContext";
import { getErrorMessage } from "../../services/api";
import { getSetupStatus } from "../../services/authApi";
import DisclaimerBanner from "../../components/DisclaimerBanner";
import { Button, Input } from "../../components/ui";
import { FormField, PasswordInput } from "../../components/FormField";
import useValidation from "../../hooks/useValidation";
import * as v from "../../utils/validators";

// Left: simple explanation of the product. Right: the card (login / password forms).
export function AuthShell({ title, subtitle, children }) {
  const points = [
    [FileSearch, "Upload a lab report", "The computer reads it in seconds."],
    [Bot, "Get a simple explanation", "Every test is shown with a clear gauge."],
    [Stethoscope, "Your doctor checks it", "Nothing reaches you before a doctor has looked."],
    [Pill, "Medicines and history in one place", "Prescriptions, notes and your timeline."],
  ];
  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <div className="relative hidden overflow-hidden bg-gradient-to-br from-brand-900 via-brand-700 to-sky-700 p-12 text-white lg:flex lg:flex-col lg:justify-center">
        <div className="pointer-events-none absolute -left-16 -top-16 h-72 w-72 rounded-full bg-white/10" />
        <div className="pointer-events-none absolute -bottom-20 right-10 h-80 w-80 rounded-full bg-white/10" />
        <div className="relative max-w-md">
          <span className="mb-6 flex h-16 w-16 items-center justify-center rounded-3xl bg-white/15 ring-1 ring-white/25"><HeartPulse size={34} /></span>
          <h1 className="text-5xl font-extrabold tracking-tight">HealthWise AI</h1>
          <p className="mt-3 text-xl text-brand-100">Understand your health reports, without the confusing medical language.</p>
          <ul className="mt-10 space-y-5">
            {points.map(([Icon, head, text]) => (
              <li key={head} className="flex gap-4">
                <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-white/15"><Icon size={22} /></span>
                <span><span className="block text-lg font-bold">{head}</span><span className="text-brand-100">{text}</span></span>
              </li>
            ))}
          </ul>
          <p className="mt-10 flex items-center gap-2 text-sm text-brand-100"><ShieldCheck size={16} /> Private. Doctor-reviewed. Not a diagnosis tool.</p>
        </div>
      </div>

      <div className="flex items-center justify-center bg-slate-50 p-5 sm:p-10">
        <div className="w-full max-w-md">
          <div className="mb-6 text-center lg:hidden">
            <span className="inline-flex rounded-2xl bg-gradient-to-br from-brand-500 to-brand-700 p-3 text-white"><HeartPulse size={28} /></span>
            <h1 className="mt-2 text-3xl font-extrabold text-slate-900">HealthWise AI</h1>
          </div>
          <div className="rounded-3xl border border-slate-200 bg-white p-7 shadow-xl">
            <h2 className="text-2xl font-extrabold text-slate-900">{title}</h2>
            {subtitle && <p className="mb-5 mt-1 text-slate-500">{subtitle}</p>}
            {children}
          </div>
          <div className="mt-4"><DisclaimerBanner /></div>
        </div>
      </div>
    </div>
  );
}

// Demo shortcuts are shown ONLY when running `npm run dev` (never in a production build).
const DEMO = [
  ["Patient", "rahul.patil@healthwise.demo.com"], ["Doctor", "anjali.sharma@healthwise.demo.com"],
  ["Employee", "priya.joshi@healthwise.demo.com"], ["Pharmacy", "pharmacy@healthwise.demo.com"], ["Lab", "lab@healthwise.demo.com"], ["Admin", "admin@healthwise.demo.com"],
];

// Login: the e-mail must look like an e-mail and the password must not be empty. Whether the account and password are right is the server's answer,
// and it is the same sentence for a wrong e-mail and a wrong password ("Incorrect email or password").
const LOGIN_RULES = {
  email: (value) => v.email(value),
  password: (value) => (String(value ?? "") === "" ? "Please enter your password." : String(value).length > 128 ? "The password is too long (128 characters at most)." : ""),
};

export default function Login() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ email: "", password: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [needsSetup, setNeedsSetup] = useState(false);
  const check = useValidation(LOGIN_RULES);

  useEffect(() => { getSetupStatus().then((s) => setNeedsSetup(s.needs_setup)).catch(() => {}); }, []);
  if (user) return <Navigate to={ROLE_HOME[user.role]} replace />;

  const submit = async (e) => {
    e.preventDefault();
    if (busy) return;
    if (!check.validateAll(form)) return;
    setBusy(true);
    setError("");
    try {
      const u = await login(form.email.trim().toLowerCase(), form.password);
      navigate(ROLE_HOME[u.role]);                                   // a starting password shows the change-password pop-up there
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthShell title="Welcome back" subtitle="Log in with the email and password the hospital gave you.">
      <form onSubmit={submit} noValidate className="space-y-4" aria-busy={busy}>
        <FormField label="Email" name="email" error={check.errors.email}>
          <Input type="email" inputMode="email" autoComplete="email" placeholder="you@example.com" maxLength={254} value={form.email}
            onChange={(e) => { setForm({ ...form, email: e.target.value }); check.clear("email"); }} onBlur={() => check.check("email", form)} />
        </FormField>
        <FormField label="Password" name="password" error={check.errors.password}>
          <PasswordInput autoComplete="current-password" placeholder="Your password" value={form.password}
            onChange={(e) => { setForm({ ...form, password: e.target.value }); check.clear("password"); }} onBlur={() => check.check("password", form)} />
        </FormField>
        {error && <p role="alert" className="rounded-xl bg-red-50 p-3 text-sm font-medium text-red-700">{error}</p>}
        <Button disabled={busy} className="w-full py-3 text-base">{busy ? "Logging in..." : "Log in"}</Button>
      </form>
      <p className="mt-4 text-center text-sm text-slate-500">
        New patient? Please ask hospital reception to create your account. {needsSetup && <Link to="/register" className="font-bold text-brand-700">Set up the first administrator</Link>}
      </p>
      {import.meta.env.DEV && (
        <div className="mt-5 rounded-2xl border border-dashed border-slate-300 p-3">
          <p className="mb-2 text-xs font-bold uppercase tracking-wide text-slate-400">Demo mode: fill in a demo account</p>
          <div className="flex flex-wrap gap-2">
            {DEMO.map(([label, email]) => (
              <button key={label} type="button" onClick={() => setForm({ email, password: "Demo@12345" })}
                className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold text-slate-600 hover:bg-brand-100 hover:text-brand-800">{label}</button>
            ))}
          </div>
        </div>
      )}
    </AuthShell>
  );
}
