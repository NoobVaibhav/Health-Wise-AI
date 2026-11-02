import { lazy, Suspense, useCallback, useEffect, useRef, useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { AlertCircle, ArrowLeft, Check, HeartPulse, KeyRound, Loader2, Lock, Mail, Phone, Send, Smartphone, Sparkles } from "lucide-react";
import { ROLE_HOME, useAuth } from "../../context/AuthContext";
import { getErrorMessage } from "../../services/api";
import { getSetupStatus, requestOtp } from "../../services/authApi";
import DisclaimerBanner from "../../components/DisclaimerBanner";
import AuthField from "../../components/auth/AuthField";
import OtpInput from "../../components/auth/OtpInput";
import DemoDropdown from "../../components/auth/DemoDropdown";
import { DEMO_PASSWORD } from "../../components/auth/demoAccounts";
import { Backdrop, CompactBrand, useDesktop, useReducedMotion } from "../../components/auth/AuthArt";
import useValidation from "../../hooks/useValidation";
import * as v from "../../utils/validators";

// The big brand panel is decoration: it is built only on a desktop-sized screen and is its own downloaded piece, so the login form never waits for it.
const BrandPanel = lazy(() => import("../../components/auth/BrandPanel"));

/** The page around every sign-in form. Desktop: the brand panel on the left, the card on the right, all in one screen. Phone and tablet: a compact animated header above the card.
 *  `shake` plays once after a failed login; `success` plays the check mark and fades the card out before the redirect. `footer` goes under the card. */
export function AuthShell({ title, subtitle, children, shake = false, onShakeEnd, success = false, wide = false, footer = null }) {
  const reduced = useReducedMotion();
  const desktop = useDesktop();
  const [paused, setPaused] = useState(false);
  useEffect(() => {                                           // nothing animates in a hidden tab
    const on = () => setPaused(document.hidden);
    document.addEventListener("visibilitychange", on);
    return () => document.removeEventListener("visibilitychange", on);
  }, []);
  const rise = (n) => (reduced ? "" : `hw-rise hw-d${n}`);
  return (
    <div data-paused={paused ? "true" : "false"} data-reduced={reduced ? "true" : "false"} className="relative flex min-h-screen flex-col bg-gradient-to-br from-cyan-50 via-white to-sky-100 lg:grid lg:h-screen lg:grid-cols-[minmax(0,1.05fr)_minmax(0,1fr)] lg:overflow-hidden">
      {desktop ? (
        <Suspense fallback={<div className="bg-gradient-to-br from-brand-900 via-brand-800 to-sky-800" aria-hidden="true" />}><BrandPanel reduced={reduced} paused={paused} /></Suspense>
      ) : <CompactBrand reduced={reduced} paused={paused} />}

      <main className="relative flex min-h-0 flex-1 items-start justify-center overflow-y-auto px-4 py-6 sm:px-8 lg:items-center lg:py-8">
        <Backdrop />
        <div className={`relative z-10 w-full ${wide ? "max-w-lg" : "max-w-md"}`}>
          <div className={`hw-card ${reduced ? "" : "hw-card-in"} ${success ? "hw-card-out" : ""} ${shake && !reduced ? "hw-shake" : ""}`} data-static={reduced ? "true" : "false"}
            onAnimationEnd={(e) => { if (shake && e.animationName === "hw-shake") onShakeEnd?.(); }}>
            {!reduced && <span className="hw-card-glow hw-loop" aria-hidden="true" />}
            <span className={`hw-card-edge ${reduced ? "" : "hw-loop"}`} aria-hidden="true" />
            <div className="hw-card-body p-6 sm:p-7">
              <div className={`mb-6 text-center ${rise(3)}`}>
                <span className="mx-auto mb-3 grid h-12 w-12 place-items-center rounded-2xl bg-gradient-to-br from-brand-500 to-sky-600 text-white shadow-lg shadow-cyan-500/30" aria-hidden="true"><HeartPulse size={24} /></span>
                <h2 className="text-3xl font-extrabold tracking-tight text-slate-900">{title}</h2>
                {subtitle && <p className="mx-auto mt-2 max-w-sm text-base leading-snug text-slate-600">{subtitle}</p>}
                <span className="mx-auto mt-4 block h-1 w-14 rounded-full bg-gradient-to-r from-cyan-400 via-sky-500 to-blue-600" aria-hidden="true" />
              </div>
              {children}
              {success && <span role="status" aria-label="Signed in" className="sr-only">Signed in</span>}
            </div>
          </div>
          {footer && <div className={`mt-4 space-y-3 ${rise(6)}`}>{footer}</div>}
          <div className={`mt-4 ${rise(7)}`}><DisclaimerBanner /></div>
        </div>
      </main>
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
  const [demoOpen, setDemoOpen] = useState(false);                        // the demo dropdown is closed until asked for
  const [flash, setFlash] = useState(0);                                  // counts the fills by the demo picker (each one flashes the fields)
  const closeDemo = useCallback(() => setDemoOpen(false), []);
  const holdRedirect = useRef(false);                                 // the success check mark is shown before the page changes
  const check = useValidation(LOGIN_RULES);

  useEffect(() => { getSetupStatus().then((s) => setNeedsSetup(s.needs_setup)).catch(() => {}); }, []);
  useEffect(() => {                                                    // the two countdowns of the code step
    if (step !== "code") return undefined;
    const t = setInterval(() => { setLeft((n) => Math.max(0, n - 1)); setResend((n) => Math.max(0, n - 1)); }, 1000);
    return () => clearInterval(t);
  }, [step]);
  if (user && !holdRedirect.current) return <Navigate to={ROLE_HOME[user.role]} replace />;

  const fail = (err) => { holdRedirect.current = false; setError(getErrorMessage(err)); setShake(true); setBusy(false); };
  const done = (u) => { setSuccess(true); setTimeout(() => navigate(ROLE_HOME[u.role]), reduced ? 150 : 600); };      // a starting password shows the change-password pop-up there

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

  const pick = (acc) => { setDemoOpen(false); setFlash((n) => n + 1); setPicked(acc.email); setForm({ email: acc.email, password: DEMO_PASSWORD }); setPhone(acc.phone); setPhoneError(""); check.clear("email"); check.clear("password"); if (step === "code") back(); };

  const footer = import.meta.env.DEV ? (
    <>
      <DemoDropdown open={demoOpen} onToggle={() => setDemoOpen((o) => !o)} onClose={closeDemo} picked={picked} onPick={pick} reduced={reduced} />
      {picked && (
        <div className={`flex flex-wrap items-center justify-between gap-2 rounded-2xl bg-white p-2.5 text-sm shadow-sm ring-1 ring-cyan-200 ${reduced ? "" : "hw-slide-down"}`}>
          <span className="min-w-0 truncate text-slate-700">Ready: <b>{picked}</b></span>
          <button type="button" disabled={busy || success} onClick={() => (tab === "password" ? doLogin(picked, DEMO_PASSWORD) : sendCode())} className="hw-btn-ghost">{tab === "password" ? "Log in now" : "Send the code"}</button>
        </div>)}
    </>
  ) : null;
  const errorBox = (
    <div aria-live="assertive">{error && <p role="alert" className={`flex items-start gap-2 rounded-xl border-l-4 border-red-500 bg-red-50 p-3 text-sm font-semibold text-red-800 ${reduced ? "" : "hw-slide-down"}`}><AlertCircle size={18} className="mt-0.5 shrink-0" aria-hidden="true" />{error}</p>}</div>
  );
  // the button: its label, a spinner while it works, a check and a ripple when it is done
  const label = (idle, working) => (busy && !success ? (<><Loader2 size={20} className={reduced ? "" : "animate-spin"} aria-hidden="true" /><span>{working}</span></>)
    : success ? (<>{!reduced && <span className="hw-ripple" aria-hidden="true" />}<Check size={22} aria-hidden="true" /><span>Welcome</span></>) : idle);
  const state = success ? "done" : busy ? "busy" : "idle";

  return (
    <>
    <AuthShell title="Welcome back" subtitle={tab === "password" ? "Log in with the email and password the hospital gave you." : "Log in with the mobile number saved in your hospital record."} shake={shake} onShakeEnd={() => setShake(false)} success={success} wide footer={footer}>
      <div className="hw-tabs mb-5" data-tab={tab === "password" ? "password" : "otp"} role="tablist" aria-label="How do you want to log in?">
        <span className="hw-tabs-pill" aria-hidden="true" />
        <button type="button" role="tab" id="tab-password" aria-selected={tab === "password"} aria-controls="panel-login" className="hw-tab" onClick={() => switchTab("password")}><KeyRound size={17} aria-hidden="true" />Email login</button>
        <button type="button" role="tab" id="tab-otp" aria-selected={tab === "otp"} aria-controls="panel-login" className="hw-tab" onClick={() => switchTab("otp")}><Smartphone size={17} aria-hidden="true" />Mobile code</button>
      </div>

      <div id="panel-login" role="tabpanel" aria-labelledby={tab === "password" ? "tab-password" : "tab-otp"}>
        {tab === "password" ? (
          <form key="pw" onSubmit={submit} noValidate className={`space-y-4 ${reduced ? "" : "hw-slide-in-left"}`} aria-busy={busy}>
            <AuthField id="email" label="Email" icon={Mail} type="email" inputMode="email" autoComplete="email" maxLength={254} value={form.email} error={check.errors.email} flash={flash}
              valid={form.email.trim() !== "" && v.email(form.email) === ""} onChange={(e) => { setForm({ ...form, email: e.target.value }); check.clear("email"); }} onBlur={() => check.check("email", form)} />
            <AuthField id="password" label="Password" icon={Lock} password autoComplete="current-password" value={form.password} error={check.errors.password} flash={flash}
              onChange={(e) => { setForm({ ...form, password: e.target.value }); check.clear("password"); }} onBlur={() => check.check("password", form)} />
            {errorBox}
            <button type="submit" disabled={busy || success} data-state={state} className="hw-btn">{label("Log in", "Logging in...")}</button>
          </form>
        ) : step === "phone" ? (
          <form key="otp1" onSubmit={sendCode} noValidate className={`space-y-4 ${reduced ? "" : "hw-slide-in"}`} aria-busy={busy}>
            <AuthField id="phone" label="Mobile number" icon={Phone} type="tel" inputMode="tel" autoComplete="tel" maxLength={16} value={phone} error={phoneError} flash={flash}
              onChange={(e) => { setPhone(e.target.value); setPhoneError(""); }} />
            <p className="-mt-2 text-sm text-slate-600">We send a 6-digit code to this number. It works for 5 minutes.</p>
            {errorBox}
            <button type="submit" disabled={busy || success} data-state={state} className="hw-btn">{busy ? (<><Loader2 size={20} className={reduced ? "" : "animate-spin"} aria-hidden="true" /><span>Sending...</span></>) : (<><Send size={19} aria-hidden="true" /><span>Send the code</span></>)}</button>
          </form>
        ) : (
          <div key="otp2" className={`space-y-4 ${reduced ? "" : "hw-slide-in"}`} aria-busy={busy}>
            <p className="text-slate-700">Enter the 6-digit code for <b>+91 {tenDigits(phone)}</b>. <button type="button" onClick={back} className="inline-flex min-h-11 items-center gap-1 font-bold text-brand-700 underline"><ArrowLeft size={14} aria-hidden="true" />Change number</button></p>
            <OtpInput value={code} onChange={(c) => { setCode(c); setError(""); }} onComplete={verify} disabled={busy || success} invalid={!!error} />
            {demoCode && (
              <button type="button" onClick={() => { setCode(demoCode); verify(demoCode); }} className="hw-fade flex min-h-11 w-full items-center gap-2 rounded-xl border border-dashed border-amber-500 bg-amber-50 p-2.5 text-left text-sm text-amber-900">
                <Sparkles size={16} aria-hidden="true" /><span><b>Demo mode:</b> no SMS is sent, so your code is <b className="font-mono text-base tracking-widest">{demoCode}</b>. Tap to use it.</span>
              </button>)}
            {errorBox}
            <button type="button" disabled={busy || success || code.length !== 6} onClick={() => verify(code)} data-state={state} className="hw-btn">{label("Verify and log in", "Checking...")}</button>
            <div className="flex items-center justify-between text-sm text-slate-700">
              <span>{left > 0 ? `Code valid for ${clock(left)}` : "The code has expired."}</span>
              <button type="button" disabled={busy || resend > 0} onClick={sendCode} className="min-h-11 font-bold text-brand-700 underline disabled:cursor-not-allowed disabled:text-slate-500 disabled:no-underline">{resend > 0 ? `Send again in ${resend}s` : "Send a new code"}</button>
            </div>
          </div>
        )}
      </div>

      <p className="mt-4 text-center text-sm text-slate-700">
        New patient? Please ask hospital reception to create your account. {needsSetup && <Link to="/register" className="font-bold text-brand-700 underline">Set up the first administrator</Link>}
      </p>
    </AuthShell>
    </>
  );
}
