// A doctor who is not assigned to a patient can open that patient in an emergency: exact UHID, a written reason, a limited time. Every use is reviewed afterwards.
import { useState } from "react";
import { Link } from "react-router-dom";
import { ShieldAlert } from "lucide-react";
import { lookupForBreakGlass, openBreakGlass } from "../../services/hospitalApi";
import { getErrorMessage } from "../../services/api";
import { Section } from "../../components/HealthCard";
import { Button, Field, Input, Textarea, fmtUtc } from "../../components/ui";
import { ErrorBox, PageTitle } from "../../components/Feedback";

export default function EmergencyAccess() {
  const [uhid, setUhid] = useState("");
  const [found, setFound] = useState(null);
  const [reason, setReason] = useState("");
  const [grant, setGrant] = useState(null);
  const [problem, setProblem] = useState("");
  const [busy, setBusy] = useState(false);
  const find = async () => { setProblem(""); setFound(null); setGrant(null); try { setFound(await lookupForBreakGlass(uhid.trim())); } catch (e) { setProblem(getErrorMessage(e)); } };
  const open = async () => {
    setBusy(true); setProblem("");
    try { setGrant(await openBreakGlass(found.id, reason.trim())); } catch (e) { setProblem(getErrorMessage(e)); } finally { setBusy(false); }
  };
  return (
    <div className="mx-auto max-w-2xl space-y-5">
      <PageTitle title="Emergency access" subtitle="Open the record of a patient who is not yet yours, for an emergency only" />
      <p className="flex items-start gap-2 rounded-2xl bg-amber-50 p-4 font-semibold text-amber-900"><ShieldAlert size={20} className="mt-0.5 shrink-0" /><span>Your name, the time and your reason are recorded and the hospital reviews every emergency access. The access ends by itself after a short time.</span></p>
      <Section>
        <div className="flex flex-wrap items-end gap-2">
          <Field label="Exact UHID of the patient"><Input maxLength={30} placeholder="HW-26-000123" value={uhid} onChange={(e) => setUhid(e.target.value)} /></Field>
          <Button type="button" disabled={uhid.trim().length < 4} onClick={find}>Find</Button>
        </div>
        {found && !grant && (
          <div className="mt-4 space-y-3">
            <p className="rounded-xl bg-slate-50 p-3"><b>{found.full_name}</b> · {found.uhid} · {found.age ?? "?"} years · {found.gender || ""}</p>
            <Field label="Why do you need this record now? *" hint="At least 10 characters"><Textarea rows={2} maxLength={500} value={reason} onChange={(e) => setReason(e.target.value)} /></Field>
            <Button type="button" variant="danger" disabled={busy || reason.trim().length < 10} onClick={open}>{busy ? "Opening..." : "Open this record"}</Button>
          </div>)}
        {grant && (
          <div className="mt-4 space-y-2 rounded-xl bg-emerald-50 p-3 text-emerald-900">
            <p>The record of <b>{grant.patient_name}</b> is open for you until <b>{fmtUtc(grant.expires_at)}</b>.</p>
            <Link to={`/doctor/patients/${grant.patient_id}`} className="inline-flex min-h-11 items-center rounded-xl bg-brand-700 px-5 py-2.5 font-bold text-white">Open the record</Link>
          </div>)}
        {problem && <div className="mt-3"><ErrorBox message={problem} /></div>}
      </Section>
    </div>
  );
}
