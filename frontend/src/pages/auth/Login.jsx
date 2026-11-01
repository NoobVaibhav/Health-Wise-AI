import { useEffect, useRef, useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { Check, FileSearch, Loader2, Lock, Mail, Mic, ShieldCheck } from "lucide-react";
import { ROLE_HOME, useAuth } from "../../context/AuthContext";
import { getErrorMessage } from "../../services/api";
import { getSetupStatus } from "../../services/authApi";
import DisclaimerBanner from "../../components/DisclaimerBanner";
import AuthField from "../../components/auth/AuthField";
import { Backdrop, Floaters, Heartbeat, LogoMark, Trust, useReducedMotion } from "../../components/auth/AuthArt";
import useValidation from "../../hooks/useValidation";
import * as v from "../../utils/validators";

const HIGHLIGHTS = [
  [FileSearch, "AI report analysis", "Upload a report and see every value explained with a clear gauge."],
  [Mic, "Voice assistant", "Ask about your health in English, Hindi or Marathi."],
  [ShieldCheck, "Secure records", "Private, doctor-reviewed, and never a diagnosis on its own."],
];

/** The page around every sign-in form: a brand panel (desktop) or a compact header (phone) and a soft glass card. `shake` plays once after a failed login,
 *  `success` shows the check mark before the redirect. */
export function AuthShell({ title, subtitle, children, shake = false, onShakeEnd, success = false }) {
  const reduced = useReducedMotion();
  const root = useRef(null);
  const [paused, setPaused] = useState(false);
  useEffect(() => {                                           // nothing animates in a hidden tab
    const on = () => setPaused(document.hidden);
    document.addEventListener("visibilitychange", on);
    return () => document.removeEventListener("visibilitychange", on);
  }, []);
  const move = (e) => {                                       // a little parallax on a big screen with a mouse
    if (reduced || !root.current || e.pointerType === "touch" || window.innerWidth < 1024) return;
    root.current.style.setProperty("--px", ((e.clientX / window.innerWidth) - 0.5).toFixed(3));
    root.current.style.setProperty("--py", ((e.clientY / window.innerHeight) - 0.5).toFixed(3));
  };
  const rise = (n) => (reduced ? "" : `hw-rise hw-d${n}`);
  return (
    <div ref={root} onPointerMove={move} data-paused={paused ? "true" : "false"} data-reduced={reduced ? "true" : "false"} className="relative grid min-h-screen overflow-hidden bg-gradient-to-br from-cyan-50 via-white to-sky-50 lg:grid-cols-[1.05fr_1fr]">
      <Backdrop reduced={reduced} />
      <div className="relative hidden overflow-hidden bg-gradient-to-br from-brand-900 via-brand-700 to-sky-700 p-12 text-white lg:flex lg:flex-col lg:justify-center">
        <Floaters reduced={reduced} />
        <div className="relative z-10 max-w-lg">
          <LogoMark reduced={reduced} />
          <h1 className={`mt-6 text-5xl font-extrabold tracking-tight ${rise(1)}`}>HealthWise AI</h1>
          <p className={`mt-3 text-xl text-brand-100 ${rise(2)}`}>Understand your health reports, without the confusing medical language.</p>
          <Heartbeat reduced={reduced} className="my-8 h-24 w-full max-w-md" />
          <ul className="space-y-5">
            {HIGHLIGHTS.map(([Icon, head, text], i) => (
              <li key={head} className={`flex gap-4 ${rise(i + 3)}`}>
                <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-white/15 ring-1 ring-white/20"><Icon size={22} aria-hidden="true" /></span>
                <span><span className="block text-lg font-bold">{head}</span><span className="text-brand-100">{text}</span></span>
              </li>))}
          </ul>
          <div className="mt-10"><Trust reduced={reduced} /></div>
        </div>
      </div>

      <div className="relative z-10 flex items-center justify-center p-5 sm:p-10">
        <div className="w-full max-w-md">
          <div className={`mb-6 text-center lg:hidden ${rise(1)}`}>
            <span className="inline-flex rounded-2xl bg-gradient-to-br from-brand-500 to-brand-700 p-1"><LogoMark reduced={reduced} size={26} box="h-12 w-12" /></span>
            <h1 className="mt-2 text-3xl font-extrabold text-slate-900">HealthWise AI</h1>
            <p className="text-sm text-slate-600">Your health reports, explained simply.</p>
          </div>
          <div onAnimationEnd={(e) => { if (shake && e.animationName === "hw-shake") onShakeEnd?.(); }}
            className={`relative rounded-3xl border border-white/70 bg-white/80 p-7 shadow-2xl shadow-cyan-900/10 ring-1 ring-slate-200/70 backdrop-blur-xl ${shake && !reduced ? "hw-shake" : ""} ${reduced ? "" : "hw-rise hw-d2"}`}>
            <h2 className={`text-2xl font-extrabold text-slate-900 ${rise(3)}`}>{title}</h2>
            {subtitle && <p className={`mb-5 mt-1 text-slate-600 ${rise(4)}`}>{subtitle}</p>}
            {children}
            {success && (
              <div role="status" aria-label="Signed in" className="hw-pop absolute inset-0 z-20 grid place-items-center rounded-3xl bg-white/95">
                <span className="grid h-20 w-20 place-items-center rounded-full bg-emerald-500 text-white shadow-lg shadow-emerald-500/40">
                  <svg viewBox="0 0 24 24" className="h-10 w-10" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M5 12.5l4.5 4.5L19 7.5" pathLength="1" className="hw-check" /></svg>
                </span>
              </div>)}
          </div>
          <div className={`mt-4 ${rise(7)}`}><DisclaimerBanner /></div>
        </div>
      </div>
    </div>
  );
}

// Demo shortcuts are shown ONLY when running `npm run dev` (never in a production build).
const DEMO = [
  ["Patient", "rahul.patil@healthwise.demo.com"], ["Doctor", "anjali.sharma@healthwise.demo.com"],
  ["Employee", "priya.joshi@healthwise.demo.com"], ["Pharmacy", "pharmacy@healthwise.demo.com"], ["Lab", "lab@healthwise.demo.com"], ["Nurse", "nurse@healthwise.demo.com"], ["Intern", "intern@healthwise.demo.com"], ["PG resident", "pg.student@healthwise.demo.com"], ["Admin", "admin@healthwise.demo.com"],
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
  const reduced = useReducedMotion();
  const [form, setForm] = useState({ email: "", password: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [shake, setShake] = useState(false);
  const [success, setSuccess] = useState(false);
  const [needsSetup, setNeedsSetup] = useState(false);
  const holdRedirect = useRef(false);                           // the success check mark is shown before the page changes
  const check = useValidation(LOGIN_RULES);

  useEffect(() => { getSetupStatus().then((s) => setNeedsSetup(s.needs_setup)).catch(() => {}); }, []);
  if (user && !holdRedirect.current) return <Navigate to={ROLE_HOME[user.role]} replace />;

  const submit = async (e) => {
    e.preventDefault();
    if (busy) return;
    if (!check.validateAll(form)) return;
    setBusy(true);
    setError("");
    holdRedirect.current = true;
    try {
      const u = await login(form.email.trim().toLowerCase(), form.password);
      setSuccess(true);
      setTimeout(() => navigate(ROLE_HOME[u.role]), reduced ? 150 : 550);        // a starting password shows the change-password pop-up there
    } catch (err) {
      holdRedirect.current = false;
      setError(getErrorMessage(err));
      setShake(true);
      setBusy(false);
    }
  };

  return (
    <AuthShell title="Welcome back" subtitle="Log in with the email and password the hospital gave you." shake={shake} onShakeEnd={() => setShake(false)} success={success}>
      <form onSubmit={submit} noValidate className="space-y-4" aria-busy={busy}>
        <AuthField id="email" label="Email" icon={Mail} type="email" inputMode="email" autoComplete="email" maxLength={254} value={form.email} error={check.errors.email}
          onChange={(e) => { setForm({ ...form, email: e.target.value }); check.clear("email"); }} onBlur={() => check.check("email", form)} />
        <AuthField id="password" label="Password" icon={Lock} password autoComplete="current-password" value={form.password} error={check.errors.password}
          onChange={(e) => { setForm({ ...form, password: e.target.value }); check.clear("password"); }} onBlur={() => check.check("password", form)} />
        <div aria-live="assertive">{error && <p role="alert" className="hw-fade rounded-xl border-l-4 border-red-500 bg-red-50 p-3 text-sm font-semibold text-red-800">{error}</p>}</div>
        <button type="submit" disabled={busy || success} className="hw-btn">
          {busy && !success ? (<><Loader2 size={20} className={reduced ? "" : "animate-spin"} aria-hidden="true" /><span>Logging in...</span></>) : success ? (<><Check size={20} aria-hidden="true" /><span>Welcome</span></>) : "Log in"}
        </button>
      </form>
      <p className="mt-4 text-center text-sm text-slate-600">
        New patient? Please ask hospital reception to create your account. {needsSetup && <Link to="/register" className="font-bold text-brand-700 underline">Set up the first administrator</Link>}
      </p>
      {import.meta.env.DEV && (
        <div className="mt-5 rounded-2xl border border-dashed border-slate-300 p-3">
          <p className="mb-2 text-xs font-bold uppercase tracking-wide text-slate-500">Demo mode: fill in a demo account</p>
          <div className="flex flex-wrap gap-2">
            {DEMO.map(([label, email]) => (
              <button key={label} type="button" onClick={() => setForm({ email, password: "Demo@12345" })}
                className="min-h-9 rounded-full bg-slate-100 px-3 py-1 text-xs font-bold text-slate-700 hover:bg-brand-100 hover:text-brand-800">{label}</button>
            ))}
          </div>
        </div>
      )}
    </AuthShell>
  );
}
