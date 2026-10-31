// Referrals between departments. Incoming: accept (a consult visit and token are made and you can see the records), decline with a reason, or finish after you signed
// your consultation. Sent: what you asked and the plan that came back.
import { useState } from "react";
import { Link } from "react-router-dom";
import { Share2 } from "lucide-react";
import useFetch from "../../hooks/useFetch";
import useSave from "../../hooks/useSave";
import { acceptReferral, completeReferral, declineReferral, referralBox, referralDetail } from "../../services/careApi";
import { Section } from "../../components/HealthCard";
import { EmptyState, ErrorBox, Loading, PageTitle } from "../../components/Feedback";
import { Button, Input, Tabs, fmtUtc } from "../../components/ui";

const TONE = { REQUESTED: "bg-sky-100 text-sky-800", ACCEPTED: "bg-amber-100 text-amber-800", COMPLETED: "bg-emerald-100 text-emerald-800", DECLINED: "bg-slate-200 text-slate-700" };

function Box({ box }) {
  const { data, loading, error, reload } = useFetch(() => referralBox(box), [box]);
  const [open, setOpen] = useState(null);
  if (loading && !data) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  if (data.length === 0) return <EmptyState message={box === "incoming" ? "No referrals for you" : "You have not referred anybody"} icon={Share2} />;
  return (
    <ul className="divide-y">{data.map((r) => (
      <li key={r.id} className="py-3">
        <button type="button" aria-expanded={open === r.id} onClick={() => setOpen(open === r.id ? null : r.id)} className="flex w-full flex-wrap items-center justify-between gap-2 text-left">
          <span><b>{r.patient.full_name}</b> <span className="text-sm text-slate-500">{r.patient.uhid} · {box === "incoming" ? `from ${r.from_doctor}` : `to ${r.to_department}`} · {fmtUtc(r.created_at)}</span></span>
          <span className="flex items-center gap-2">{r.urgency === "URGENT" && <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs font-bold text-red-700">Urgent</span>}<span className={`rounded-full px-2 py-0.5 text-xs font-bold ${TONE[r.status]}`}>{r.status.toLowerCase()}</span></span>
        </button>
        {open === r.id && <Detail id={r.id} box={box} onChanged={reload} />}
      </li>))}</ul>
  );
}

function Detail({ id, box, onChanged }) {
  const { data: r, loading, error, reload } = useFetch(() => referralDetail(id), [id]);
  const { problem, busy, run } = useSave();
  const [note, setNote] = useState("");
  if (loading && !r) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  const act = async (fn, msg) => { if (await run(fn, msg)) { reload(); onChanged(); } };
  return (
    <div className="mt-3 space-y-3 rounded-2xl bg-slate-50 p-4 text-sm">
      <p><b>Reason:</b> {r.reason}</p>
      {r.origin_consultation && <p><b>Referring doctor's record:</b> {r.origin_consultation.complaint}{r.origin_consultation.assessment ? ` → ${r.origin_consultation.assessment}` : ""}{r.origin_consultation.plan ? ` (plan: ${r.origin_consultation.plan})` : ""}</p>}
      {r.response_note && <p><b>Note:</b> {r.response_note}</p>}
      {r.consult_note && <p className="rounded-xl bg-emerald-50 p-3"><b>Specialist's plan ({r.consult_note.doctor_name}, {r.consult_note.status.toLowerCase()}):</b> {r.consult_note.assessment}{r.consult_note.plan ? ` → ${r.consult_note.plan}` : ""}{r.consult_note.advice ? ` · advice: ${r.consult_note.advice}` : ""}</p>}
      {problem && <ErrorBox message={problem} />}
      {box === "incoming" && r.status === "REQUESTED" && (
        <div className="flex flex-wrap items-end gap-2"><Button type="button" disabled={busy} onClick={() => act(() => acceptReferral(id), "Referral accepted")}>Accept and open the consult</Button>
          <Input aria-label="Reason for declining" placeholder="Reason, if you decline" maxLength={2000} value={note} onChange={(e) => setNote(e.target.value)} /><Button type="button" variant="secondary" disabled={busy || note.trim().length < 2} onClick={() => act(() => declineReferral(id, note), "Referral declined")}>Decline</Button></div>)}
      {box === "incoming" && r.status === "ACCEPTED" && r.consult_encounter_id && (
        <div className="flex flex-wrap gap-2"><Link to={`/doctor/consultation/${r.consult_encounter_id}`} className="inline-flex min-h-11 items-center rounded-xl bg-brand-700 px-4 py-2 font-bold text-white">Open the consultation</Link>
          <Button type="button" variant="secondary" disabled={busy} onClick={() => act(() => completeReferral(id, note), "Referral completed")}>Finish and send the plan back</Button></div>)}
    </div>
  );
}

export default function ReferralRequests() {
  return (
    <div className="space-y-5">
      <PageTitle title="Referral requests" subtitle="Patients sent to or from other departments" icon={Share2} />
      <Section><Tabs tabs={[["in", "Sent to me", <Box key="in" box="incoming" />], ["out", "Sent by me", <Box key="out" box="outgoing" />]]} /></Section>
    </div>
  );
}
