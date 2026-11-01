import { useEffect, useMemo, useRef, useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { ArrowLeft, Check, FileSearch, KeyRound, Loader2, Lock, Mail, Mic, Phone, Search, Send, ShieldCheck, Smartphone, Sparkles } from "lucide-react";
import { ROLE_HOME, useAuth } from "../../context/AuthContext";
import { getErrorMessage } from "../../services/api";
import { getSetupStatus, requestOtp } from "../../services/authApi";
import DisclaimerBanner from "../../components/DisclaimerBanner";
import AuthField from "../../components/auth/AuthField";
import OtpInput from "../../components/auth/OtpInput";
import { ALL_DEMO, DEMO_GROUPS, DEMO_PASSWORD } from "../../components/auth/demoAccounts";
import { Aurora, Backdrop, Floaters, Heartbeat, LogoMark, Particles, Rotator, Trust, useReducedMotion } from "../../components/auth/AuthArt";
import useValidation from "../../hooks/useValidation";
import * as v from "../../utils/validators";

const HIGHLIGHTS = [
  [FileSearch, "AI report analysis", "Upload a report and see every value explained with a clear gauge."],
  [Mic, "Voice assistant", "Ask about your health in English, Hindi or Marathi."],
  [ShieldCheck, "Secure records", "Private, doctor-reviewed, and never a diagnosis on its own."],
];
const MODULES = ["OPD", "Inpatient", "Emergency", "Laboratory", "Radiology", "Pharmacy", "Operation theatre", "Blood bank", "Billing", "Insurance"];
const PIECES = [["-120px", "-110px", "35deg", "#22d3ee"], ["110px", "-120px", "-40deg", "#34d399"], ["-150px", "10px", "70deg", "#60a5fa"], ["150px", "20px", "-65deg", "#fbbf24"], ["-70px", "120px", "20deg", "#f472b6"],
  ["80px", "130px", "-25deg", "#a78bfa"], ["0px", "-150px", "50deg", "#2dd4bf"], ["-40px", "150px", "-50deg", "#fb923c"]];

/** The page around every sign-in form: a brand panel (desktop) or a compact header (phone) and a soft glass card. `shake` plays once after a failed login,
 *  `success` shows the check mark (and a small burst) before the redirect. */
export function AuthShell({ title, subtitle, children, shake = false, onShakeEnd, success = false, wide = false }) {
  const reduced = useReducedMotion();
  const root = useRef(null);
  const [paused, setPaused] = useState(false);
  useEffect(() => {                                           // nothing animates in a hidden tab
    const on = () => setPaused(document.hidden);
    document.addEventListener("visibilitychange", on);
    return () => document.removeEventListener("visibilitychange", on);
  }, []);
  const move = (e) => {                                       // a little parallax and a leaning card on a big screen with a mouse
    if (reduced || !root.current || e.pointerType === "touch" || window.innerWidth < 1024) return;
    const x = (e.clientX / window.innerWidth) - 0.5, y = (e.clientY / window.innerHeight) - 0.5;
    root.current.style.setProperty("--px", x.toFixed(3));
    root.current.style.setProperty("--py", y.toFixed(3));
    root.current.style.setProperty("--tx", Math.max(-1, Math.min(1, x * 2)).toFixed(3));
    root.current.style.setProperty("--ty", Math.max(-1, Math.min(1, y * 2)).toFixed(3));
  };
  const rise = (n) => (reduced ? "" : `hw-rise hw-d${n}`);
  return (
    <div ref={root} onPointerMove={move} data-paused={paused ? "true" : "false"} data-reduced={reduced ? "true" : "false"} className="relative grid min-h-screen overflow-hidden bg-gradient-to-br from-cyan-50 via-white to-sky-100 lg:grid-cols-[1.05fr_1fr]">
      <Backdrop reduced={reduced} />
      <div className="relative hidden overflow-hidden bg-gradient-to-br from-brand-900 via-brand-700 to-sky-700 p-12 text-white lg:flex lg:flex-col lg:justify-center">
        <Aurora reduced={reduced} />
        <Particles reduced={reduced} />
        <Floaters reduced={reduced} />
        <div className="relative z-10 max-w-lg">
          <LogoMark reduced={reduced} />
          <h1 className={`mt-6 text-5xl font-extrabold tracking-tight ${rise(1)}`}>HealthWise AI</h1>
          <p className={`mt-3 text-2xl font-semibold text-brand-100 ${rise(2)}`}>
            <span className="sr-only">Understand your health reports, without the confusing medical language.</span>
            <span aria-hidden="true">Understand your <Rotator reduced={reduced} />,<br />without the confusing medical language.</span>
          </p>
          <Heartbeat reduced={reduced} className="my-6 h-20 w-full max-w-md" />
          <ul className="space-y-4">
            {HIGHLIGHTS.map(([Icon, head, text], i) => (
              <li key={head} className={`flex gap-4 ${rise(i + 3)}`}>
                <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-white/15 ring-1 ring-white/20"><Icon size={22} aria-hidden="true" /></span>
                <span><span className="block text-lg font-bold">{head}</span><span className="text-brand-100">{text}</span></span>
              </li>))}
          </ul>
          <ul className={`mt-7 flex flex-wrap gap-2 ${rise(6)}`} aria-label="What the hospital system covers">
            {MODULES.map((m, i) => <li key={m} className={`rounded-full bg-white/10 px-3 py-1 text-xs font-bold text-white/90 ring-1 ring-white/20 ${reduced ? "" : "hw-count"}`} style={reduced ? undefined : { animationDelay: `${0.5 + i * 0.07}s` }}>{m}</li>)}
          </ul>
          <div className="mt-8"><Trust reduced={reduced} /></div>
        </div>
      </div>

      <div className="relative z-10 flex items-start justify-center p-5 sm:p-8 lg:items-center lg:p-10">
        <div className={`w-full ${wide ? "max-w-xl" : "max-w-md"}`}>
          <div className={`mb-6 text-center lg:hidden ${rise(1)}`}>
            <span className="inline-flex rounded-2xl bg-gradient-to-br from-brand-500 to-brand-700 p-1"><LogoMark reduced={reduced} size={26} box="h-12 w-12" /></span>
            <h1 className="mt-2 text-3xl font-extrabold text-slate-900">HealthWise AI</h1>
            <p className="text-sm text-slate-600">Your health reports, explained simply.</p>
          </div>
          <div className={reduced ? "" : "hw-tilt"}>
            <div onAnimationEnd={(e) => { if (shake && e.animationName === "hw-shake") onShakeEnd?.(); }}
              className={`relative rounded-3xl border border-white/70 bg-white/80 p-6 shadow-2xl shadow-cyan-900/10 ring-1 ring-slate-200/70 backdrop-blur-xl sm:p-7 ${shake && !reduced ? "hw-shake" : ""} ${reduced ? "" : "hw-rise hw-d2"}`}>
              <h2 className={`text-2xl font-extrabold text-slate-900 ${rise(3)}`}>{title}</h2>
              {subtitle && <p className={`mb-5 mt-1 text-slate-600 ${rise(4)}`}>{subtitle}</p>}
              {children}
              {success && (
                <div role="status" aria-label="Signed in" className="hw-pop absolute inset-0 z-20 grid place-items-center overflow-hidden rounded-3xl bg-white/95">
                  {!reduced && PIECES.map(([dx, dy, rot, color], i) => <span key={i} aria-hidden="true" className="hw-piece" style={{ "--dx": dx, "--dy": dy, "--rot": rot, background: color, animationDelay: `${i * 0.02}s` }} />)}
                  <span className="grid h-20 w-20 place-items-center rounded-full bg-emerald-500 text-white shadow-lg shadow-emerald-500/40">
                    <svg viewBox="0 0 24 24" className="h-10 w-10" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M5 12.5l4.5 4.5L19 7.5" pathLength="1" className="hw-check" /></svg>
                  </span>
                </div>)}
            </div>
          </div>
          <div className={`mt-4 ${rise(7)}`}><DisclaimerBanner /></div>
        </div>
      </div>
    </div>
  );
}

// Login: the e-mail must look like an e-mail and the password must not be empty. Whether the account and password are right is the server's answer,
// and it is the same sentence for a wrong e-mail and a wrong password ("Incorrect email or password").
const LOGIN_RULES = {
  email: (value) => v.email(value),
  password: (value) => (String(value ?? "") === "" ? "Please enter your password." : String(value).length > 128 ? "The password is too long (128 characters at most)." : ""),
};

/** A mobile number as the server wants it: 10 digits (a leading +91, 91 or 0 is dropped). Returns "" when it cannot be a mobile number. */
export function tenDigits(raw) {
  let d = String(raw ?? "").replace(/\D/g, "");
  if (d.length === 12 && d.startsWith("91")) d = d.slice(2);
  if (d.length === 11 && d.startsWith("0")) d = d.slice(1);
  return /^[6-9]\d{9}$/.test(d) ? d : "";
}
const clock = (s) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

export default function Login() {
  const { user, login, loginWithOtp } = useAuth();
  const navigate = useNavigate();
  const reduced = useReducedMotion();
  const [tab, setTab] = useState("password");
  const [form, setForm] = useState({ email: "", password: "" });
  const [phone, setPhone] = useState("");
  const [phoneError, setPhoneError] = useState("");
  const [step, setStep] = useState("phone");                          // phone -> code
  const [code, setCode] = useState("");
  const [demoCode, setDemoCode] = useState("");
  const [left, setLeft] = useState(0);                                // seconds the code is still valid
  const [resend, setResend] = useState(0);                            // seconds until a new code may be asked for
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [shake, setShake] = useState(false);
  const [success, setSuccess] = useState(false);
  const [needsSetup, setNeedsSetup] = useState(false);
  const [picked, setPicked] = useState("");
  const [filter, setFilter] = useState("");
  const holdRedirect = useRef(false);                                 // the success check mark is shown before the page changes
  const check = useValidation(LOGIN_RULES);

  useEffect(() => { getSetupStatus().then((s) => setNeedsSetup(s.needs_setup)).catch(() => {}); }, []);
  useEffect(() => {                                                    // the two countdowns of the code step
    if (step !== "code") return undefined;
    const t = setInterval(() => { setLeft((n) => Math.max(0, n - 1)); setResend((n) => Math.max(0, n - 1)); }, 1000);
    return () => clearInterval(t);
  }, [step]);
  const shown = useMemo(() => {
    const needle = filter.trim().toLowerCase();
    return DEMO_GROUPS.map(([group, rows]) => [group, rows.filter(([role, name, email]) => !needle || `${role} ${name} ${email}`.toLowerCase().includes(needle))]).filter(([, rows]) => rows.length);
  }, [filter]);
  if (user && !holdRedirect.current) return <Navigate to={ROLE_HOME[user.role]} replace />;

  const fail = (err) => { holdRedirect.current = false; setError(getErrorMessage(err)); setShake(true); setBusy(false); };
  const done = (u) => { setSuccess(true); setTimeout(() => navigate(ROLE_HOME[u.role]), reduced ? 150 : 900); };      // a starting password shows the change-password pop-up there

  const doLogin = async (email, password) => {
    setBusy(true); setError(""); holdRedirect.current = true;
    try { done(await login(email.trim().toLowerCase(), password)); } catch (err) { fail(err); }
  };
  const submit = (e) => {
    e.preventDefault();
    if (busy || !check.validateAll(form)) return;
    doLogin(form.email, form.password);
  };

  const sendCode = async (e) => {
    e?.preventDefault();
    if (busy) return;
    const ten = tenDigits(phone);
    if (!ten) { setPhoneError("Please enter a 10-digit mobile number."); return; }
    setPhoneError(""); setBusy(true); setError("");
    try {
      const r = await requestOtp(ten);
      setDemoCode(r.demo_code || ""); setCode(""); setLeft(r.expires_in || 300); setResend(30); setStep("code"); setBusy(false);
    } catch (err) { fail(err); }
  };
  const verify = async (value) => {
    if (busy || value.length !== 6) return;
    setBusy(true); setError(""); holdRedirect.current = true;
    try { done(await loginWithOtp(tenDigits(phone), value)); } catch (err) { setCode(""); fail(err); }
  };
  const back = () => { setStep("phone"); setCode(""); setDemoCode(""); setError(""); };
  const switchTab = (next) => { setTab(next); setError(""); };

  const pick = (acc) => { setPicked(acc.email); setForm({ email: acc.email, password: DEMO_PASSWORD }); setPhone(acc.phone); setPhoneError(""); check.clear("email"); check.clear("password"); if (step === "code") back(); };

  return (
    <AuthShell title="Welcome back" subtitle={tab === "password" ? "Log in with the email and password the hospital gave you." : "Log in with the mobile number saved in your hospital record."} shake={shake} onShakeEnd={() => setShake(false)} success={success}>
      <div className="hw-tabs mb-5" data-tab={tab === "password" ? "password" : "otp"} role="tablist" aria-label="How do you want to log in?">
        <span className="hw-tabs-pill" aria-hidden="true" />
        <button type="button" role="tab" id="tab-password" aria-selected={tab === "password"} aria-controls="panel-login" className="hw-tab" onClick={() => switchTab("password")}><KeyRound size={17} aria-hidden="true" />Email login</button>
        <button type="button" role="tab" id="tab-otp" aria-selected={tab === "otp"} aria-controls="panel-login" className="hw-tab" onClick={() => switchTab("otp")}><Smartphone size={17} aria-hidden="true" />Mobile code</button>
      </div>

      <div id="panel-login" role="tabpanel" aria-labelledby={tab === "password" ? "tab-password" : "tab-otp"}>
        {tab === "password" ? (
          <form key="pw" onSubmit={submit} noValidate className={`space-y-4 ${reduced ? "" : "hw-slide-in-left"}`} aria-busy={busy}>
            <AuthField id="email" label="Email" icon={Mail} type="email" inputMode="email" autoComplete="email" maxLength={254} value={form.email} error={check.errors.email}
              onChange={(e) => { setForm({ ...form, email: e.target.value }); check.clear("email"); }} onBlur={() => check.check("email", form)} />
            <AuthField id="password" label="Password" icon={Lock} password autoComplete="current-password" value={form.password} error={check.errors.password}
              onChange={(e) => { setForm({ ...form, password: e.target.value }); check.clear("password"); }} onBlur={() => check.check("password", form)} />
            <div aria-live="assertive">{error && <p role="alert" className="hw-fade rounded-xl border-l-4 border-red-500 bg-red-50 p-3 text-sm font-semibold text-red-800">{error}</p>}</div>
            <button type="submit" disabled={busy || success} className="hw-btn">
              {busy && !success ? (<><Loader2 size={20} className={reduced ? "" : "animate-spin"} aria-hidden="true" /><span>Logging in...</span></>) : success ? (<><Check size={20} aria-hidden="true" /><span>Welcome</span></>) : "Log in"}
            </button>
          </form>
        ) : step === "phone" ? (
          <form key="otp1" onSubmit={sendCode} noValidate className={`space-y-4 ${reduced ? "" : "hw-slide-in"}`} aria-busy={busy}>
            <AuthField id="phone" label="Mobile number" icon={Phone} type="tel" inputMode="tel" autoComplete="tel" maxLength={16} value={phone} error={phoneError}
              onChange={(e) => { setPhone(e.target.value); setPhoneError(""); }} />
            <p className="-mt-2 text-sm text-slate-600">We send a 6-digit code to this number. It works for 5 minutes.</p>
            <div aria-live="assertive">{error && <p role="alert" className="hw-fade rounded-xl border-l-4 border-red-500 bg-red-50 p-3 text-sm font-semibold text-red-800">{error}</p>}</div>
            <button type="submit" disabled={busy || success} className="hw-btn">
              {busy ? (<><Loader2 size={20} className={reduced ? "" : "animate-spin"} aria-hidden="true" /><span>Sending...</span></>) : (<><Send size={19} aria-hidden="true" /><span>Send the code</span></>)}
            </button>
          </form>
        ) : (
          <div key="otp2" className={`space-y-4 ${reduced ? "" : "hw-slide-in"}`} aria-busy={busy}>
            <p className="text-slate-700">Enter the 6-digit code for <b>+91 {tenDigits(phone)}</b>. <button type="button" onClick={back} className="inline-flex items-center gap-1 font-bold text-brand-700 underline"><ArrowLeft size={14} aria-hidden="true" />Change number</button></p>
            <OtpInput value={code} onChange={(c) => { setCode(c); setError(""); }} onComplete={verify} disabled={busy || success} invalid={!!error} />
            {demoCode && (
              <button type="button" onClick={() => { setCode(demoCode); verify(demoCode); }} className="hw-fade flex w-full items-center gap-2 rounded-xl border border-dashed border-amber-400 bg-amber-50 p-2.5 text-left text-sm text-amber-900">
                <Sparkles size={16} aria-hidden="true" /><span><b>Demo mode:</b> no SMS is sent, so your code is <b className="font-mono text-base tracking-widest">{demoCode}</b>. Tap to use it.</span>
              </button>)}
            <div aria-live="assertive">{error && <p role="alert" className="hw-fade rounded-xl border-l-4 border-red-500 bg-red-50 p-3 text-sm font-semibold text-red-800">{error}</p>}</div>
            <button type="button" disabled={busy || success || code.length !== 6} onClick={() => verify(code)} className="hw-btn">
              {busy && !success ? (<><Loader2 size={20} className={reduced ? "" : "animate-spin"} aria-hidden="true" /><span>Checking...</span></>) : success ? (<><Check size={20} aria-hidden="true" /><span>Welcome</span></>) : "Verify and log in"}
            </button>
            <div className="flex items-center justify-between text-sm text-slate-600">
              <span>{left > 0 ? `Code valid for ${clock(left)}` : "The code has expired."}</span>
              <button type="button" disabled={busy || resend > 0} onClick={sendCode} className="font-bold text-brand-700 underline disabled:cursor-not-allowed disabled:text-slate-400 disabled:no-underline">{resend > 0 ? `Send again in ${resend}s` : "Send a new code"}</button>
            </div>
          </div>
        )}
      </div>

      <p className="mt-4 text-center text-sm text-slate-600">
        New patient? Please ask hospital reception to create your account. {needsSetup && <Link to="/register" className="font-bold text-brand-700 underline">Set up the first administrator</Link>}
      </p>

      {import.meta.env.DEV && (
        <div className="mt-5 rounded-2xl border border-dashed border-slate-300 bg-white/60 p-3">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <p className="text-xs font-bold uppercase tracking-wide text-slate-500">Demo mode: {ALL_DEMO.length} demo accounts</p>
            <label className="relative block"><span className="sr-only">Search the demo accounts</span><Search size={14} className="pointer-events-none absolute left-2.5 top-2.5 text-slate-400" aria-hidden="true" />
              <input value={filter} onChange={(e) => setFilter(e.target.value)} placeholder="Search a role or name" className="h-9 w-44 rounded-full border border-slate-200 bg-white pl-8 pr-3 text-xs outline-none focus:border-cyan-500" /></label>
          </div>
          <p className="mb-2 text-xs text-slate-500">Tap an account to fill it in (password and mobile number too). Password for all: <code className="rounded bg-slate-100 px-1 font-mono">{DEMO_PASSWORD}</code></p>
          <div className="max-h-72 space-y-3 overflow-y-auto pr-1">
            {shown.length === 0 && <p className="py-3 text-center text-sm text-slate-500">No demo account matches.</p>}
            {shown.map(([group, rows]) => (
              <div key={group}>
                <p className="mb-1.5 text-[11px] font-extrabold uppercase tracking-wider text-brand-700">{group}</p>
                <div className="grid gap-1.5 sm:grid-cols-2">
                  {rows.map(([role, name, email, phoneNo]) => (
                    <button key={email} type="button" className="hw-demo" data-picked={picked === email ? "true" : "false"} onClick={() => pick({ role, name, email, phone: phoneNo })} aria-label={`Fill in ${role}: ${name}`}>
                      <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-gradient-to-br from-brand-500 to-sky-600 text-xs font-extrabold text-white">{name.replace(/^Dr\. /, "").slice(0, 1)}</span>
                      <span className="min-w-0"><span className="block truncate text-sm font-bold text-slate-800">{role}</span><span className="block truncate text-xs text-slate-500">{name}</span></span>
                    </button>))}
                </div>
              </div>))}
          </div>
          {picked && (
            <div className="hw-fade mt-3 flex flex-wrap items-center justify-between gap-2 rounded-xl bg-cyan-50 p-2.5 text-sm">
              <span className="min-w-0 truncate text-slate-700">Ready: <b>{picked}</b></span>
              <button type="button" disabled={busy || success} onClick={() => (tab === "password" ? doLogin(picked, DEMO_PASSWORD) : sendCode())} className="hw-btn-ghost hw-glow">{tab === "password" ? "Log in now" : "Send the code"}</button>
            </div>)}
        </div>
      )}
    </AuthShell>
  );
}
