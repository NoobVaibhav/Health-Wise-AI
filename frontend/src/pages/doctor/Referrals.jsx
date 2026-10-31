// The doctor's list of patients sent by interns and PG students (urgent first). Open one to read the history the trainee took, then verify it, correct it,
// or add a note. The trainee's original is kept. A supervising doctor can also approve or correct a PG student's referral here.
import { useState } from "react";
import useFetch from "../../hooks/useFetch";
import { editTraineeHistory, getReferral, listReferrals, markReferralCompleted, markReferralSeen, reviewReferral, verifyTraineeHistory } from "../../services/traineeApi";
import { listDoctors } from "../../services/doctorApi";
import { getErrorMessage } from "../../services/api";
import TraineeHistoryView from "../../components/TraineeHistoryView";
import { EmptyState, ErrorBox, Loading, PageTitle } from "../../components/Feedback";
import { Section } from "../../components/HealthCard";
import { Button, Field, Modal, Select, Textarea, Input, fmtUtc } from "../../components/ui";
import { useToast } from "../../components/Toast";
import { ReferralStatus } from "../trainee/MyReferrals";
import { Link } from "react-router-dom";

function EditHistory({ detail, onClose, onSaved }) {
  const d = detail.history.data;
  const [form, setForm] = useState({ chief_complaint: d.chief_complaint || "", duration: d.duration || "", present_illness: d.present_illness || "", past_medical: d.past_medical || "", medications: d.medications || "" });
  const [note, setNote] = useState(detail.history.doctor_notes || "");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  const save = async (e) => {
    e.preventDefault();
    if (!form.chief_complaint.trim() || !form.duration.trim()) { setError("The main complaint and the duration cannot be empty."); return; }
    setBusy(true); setError("");
    try {
      await editTraineeHistory(detail.history.id, { data: { ...d, ...form, allergies: d.allergies ?? null }, note });
      onSaved(); onClose();
    } catch (err) { setError(getErrorMessage(err)); } finally { setBusy(false); }
  };
  return (
    <Modal title="Correct the history or add a note" onClose={onClose} wide>
      <form onSubmit={save} noValidate className="space-y-3">
        <p className="text-sm text-slate-600">The trainee's original version is kept and can be seen under "Earlier versions".</p>
        <Field label="Main complaint"><Input maxLength={300} value={form.chief_complaint} onChange={set("chief_complaint")} /></Field>
        <Field label="Duration"><Input maxLength={60} value={form.duration} onChange={set("duration")} /></Field>
        <Field label="History of present illness"><Textarea rows={3} maxLength={3000} value={form.present_illness} onChange={set("present_illness")} /></Field>
        <Field label="Past medical history"><Textarea rows={2} maxLength={2000} value={form.past_medical} onChange={set("past_medical")} /></Field>
        <Field label="Medicines"><Textarea rows={2} maxLength={1500} value={form.medications} onChange={set("medications")} /></Field>
        <Field label="Your note"><Textarea rows={2} maxLength={2000} value={note} onChange={(e) => setNote(e.target.value)} /></Field>
        {error && <ErrorBox message={error} />}
        <Button disabled={busy}>{busy ? "Saving..." : "Save"}</Button>
      </form>
    </Modal>
  );
}

function SupervisorReview({ detail, onClose, onSaved }) {
  const { data: doctors } = useFetch(listDoctors, []);
  const [note, setNote] = useState("");
  const [doctorId, setDoctorId] = useState("");
  const [error, setError] = useState("");
  const send = async (approved) => {
    try { await reviewReferral(detail.id, { approved, note: note.trim() || null, doctor_id: !approved && doctorId ? Number(doctorId) : null }); onSaved(); onClose(); } catch (err) { setError(getErrorMessage(err)); }
  };
  return (
    <Modal title={`Review the referral of ${detail.trainee_name}`} onClose={onClose}>
      <div className="space-y-3">
        <p className="text-sm text-slate-600">Sent to <b>{detail.doctor_name}</b>: {detail.reason}</p>
        <Field label="Your note (optional)"><Textarea rows={2} maxLength={500} value={note} onChange={(e) => setNote(e.target.value)} /></Field>
        <Field label="To correct: send to another doctor"><Select value={doctorId} onChange={(e) => setDoctorId(e.target.value)}><option value="">Keep {detail.doctor_name}</option>{(doctors || []).map((d) => <option key={d.id} value={d.id}>{d.full_name}</option>)}</Select></Field>
        {error && <ErrorBox message={error} />}
        <div className="flex gap-2"><Button type="button" onClick={() => send(true)}>Approve</Button><Button type="button" variant="secondary" onClick={() => send(false)}>Save as correction</Button></div>
      </div>
    </Modal>
  );
}

function Detail({ id, onChanged }) {
  const toast = useToast();
  const { data, loading, error, reload } = useFetch(() => getReferral(id), [id]);
  const [modal, setModal] = useState(null);
  if (loading && !data) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  const refresh = () => { reload(); onChanged(); };
  const act = async (fn, message) => { try { await fn(); toast(message); refresh(); } catch (err) { toast(getErrorMessage(err), "error"); } };
  const h = data.history;
  return (
    <div className="mt-3 space-y-4 rounded-2xl bg-slate-50 p-4">
      <p className="text-sm text-slate-700"><b>Reason:</b> {data.reason}{data.overridden ? " (the trainee chose a different department than suggested)" : ""}</p>
      <TraineeHistoryView history={h} />
      <div className="flex flex-wrap gap-2">
        {data.mine && data.status === "SENT" && <Button type="button" variant="secondary" onClick={() => act(() => markReferralSeen(id), "Marked as seen")}>Mark as seen</Button>}
        {h.status !== "VERIFIED" && <Button type="button" onClick={() => act(() => verifyTraineeHistory(h.id), "History verified")}>Verify history</Button>}
        <Button type="button" variant="secondary" onClick={() => setModal("edit")}>Correct or add a note</Button>
        {data.mine && data.status !== "COMPLETED" && <Button type="button" variant="secondary" onClick={() => act(() => markReferralCompleted(id), "Referral completed")}>Mark completed</Button>}
        <Link to={`/doctor/patients/${data.patient_id}`}><Button type="button" variant="secondary">Open patient</Button></Link>
        {data.as_supervisor && <Button type="button" variant="secondary" onClick={() => setModal("review")}>Supervisor review</Button>}
      </div>
      {data.supervisor_note && <p className="text-sm text-slate-600">Supervisor: {data.supervisor_note}</p>}
      {data.revisions.length > 0 && (
        <details className="text-sm"><summary className="cursor-pointer font-semibold text-slate-700">Earlier versions ({data.revisions.length})</summary>
          {data.revisions.map((r) => <div key={r.id} className="mt-2 rounded-xl bg-white p-3"><p className="text-xs text-slate-500">Saved {fmtUtc(r.changed_at)}</p><p>{r.data.chief_complaint} {r.data.duration ? `for ${r.data.duration}` : ""}</p><p className="whitespace-pre-line text-slate-600">{r.data.present_illness}</p></div>)}
        </details>)}
      {modal === "edit" && <EditHistory detail={data} onClose={() => setModal(null)} onSaved={refresh} />}
      {modal === "review" && <SupervisorReview detail={data} onClose={() => setModal(null)} onSaved={refresh} />}
    </div>
  );
}

export default function Referrals() {
  const { data, loading, error, reload } = useFetch(listReferrals);
  const [open, setOpen] = useState(null);
  return (
    <div className="space-y-5">
      <PageTitle title="Trainee referrals" subtitle="Patients sent to you by interns and PG students. Their histories wait for your review." />
      {loading && !data ? <Loading /> : error ? <ErrorBox message={error} onRetry={reload} /> : data.length === 0 ? (
        <EmptyState message="No referrals yet" hint="When an intern or PG student sends you a patient, it appears here." />
      ) : (
        <Section>
          <ul className="divide-y">{data.map((r) => (
            <li key={r.id} className="py-3">
              <button type="button" aria-expanded={open === r.id} onClick={() => setOpen(open === r.id ? null : r.id)} className="flex w-full flex-wrap items-center justify-between gap-2 text-left">
                <span><b>{r.patient_name}</b> <span className="text-sm text-slate-500">{r.patient_code}</span> · taken by {r.taken_by}{!r.mine && <span className="text-sm text-slate-500"> · sent to {r.doctor_name}</span>}</span>
                <span className="flex items-center gap-2">{r.history_status === "COMPLETE" && <span className="rounded-full bg-amber-100 px-2.5 py-1 text-xs font-bold text-amber-800">Pending your review</span>}<ReferralStatus r={r} /></span>
              </button>
              {open === r.id && <Detail id={r.id} onChanged={reload} />}
            </li>))}</ul>
        </Section>)}
    </div>
  );
}
