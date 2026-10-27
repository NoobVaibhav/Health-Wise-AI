// The pop-up shown as soon as an account (patient or staff) has been created: who, the login email and the starting password to hand over.
import { useState } from "react";
import { Check, CheckCircle2, Copy } from "lucide-react";
import { Button, Modal } from "./ui";

function CopyButton({ text, label }) {
  const [done, setDone] = useState(false);
  const copy = async () => {
    try { await navigator.clipboard.writeText(text); setDone(true); setTimeout(() => setDone(false), 2000); } catch { /* the text can still be selected and copied by hand */ }
  };
  return (
    <button type="button" onClick={copy} aria-label={label} className="inline-flex items-center gap-1 rounded-lg border border-slate-300 bg-white px-2.5 py-1 text-sm font-bold text-slate-700 hover:bg-slate-50">
      {done ? <><Check size={14} className="text-emerald-600" /> Copied</> : <><Copy size={14} /> Copy</>}
    </button>
  );
}

const Row = ({ label, children }) => (
  <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 py-2.5">
    <span className="w-40 shrink-0 text-sm font-bold text-slate-500">{label}</span>
    <span className="flex min-w-0 flex-1 flex-wrap items-center justify-end gap-2 text-right">{children}</span>
  </div>
);

/** name, email, password (null if the creator chose one), code (patient ID), kind ("patient", "doctor" ...), actions (extra buttons). */
export default function AccountCreatedDialog({ name, email, password, code, kind = "account", onClose, actions }) {
  return (
    <Modal title="Account created" onClose={onClose}>
      <div className="mb-3 flex items-center gap-3 rounded-2xl bg-emerald-50 p-3 text-emerald-900">
        <CheckCircle2 size={28} className="shrink-0 text-emerald-600" />
        <div><p className="text-lg font-extrabold">{name}</p><p className="text-sm">The {kind} account has been created{code ? ` (${code})` : ""}.</p></div>
      </div>
      <dl>
        {code && <Row label="ID"><b>{code}</b></Row>}
        <Row label="Login email"><b className="break-all">{email}</b><CopyButton text={email} label="Copy the login email" /></Row>
        <Row label="Starting password">
          {password ? <><b className="rounded-lg bg-slate-100 px-3 py-1 font-mono text-lg tracking-wide">{password}</b><CopyButton text={password} label="Copy the starting password" /></>
            : <span className="text-slate-600">The password you chose</span>}
        </Row>
      </dl>
      {password && <p className="mt-3 rounded-xl bg-amber-50 p-3 text-sm text-amber-900">Give this password to the {kind}. They log in with it once and are then asked to choose their own password.</p>}
      <div className="mt-5 flex flex-wrap justify-end gap-2">{actions}<Button onClick={onClose}>Done</Button></div>
    </Modal>
  );
}
