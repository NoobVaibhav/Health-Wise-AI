// Operation theatre: the schedule, booking without clashes, and the record of each operation (pre-op, consent, safety checklist, anaesthesia,
// operation note, events, consumables, recovery). The server refuses a clash and every step that is not allowed yet, and says why.
import { useState } from "react";
import { Scissors } from "lucide-react";
import useFetch from "../../hooks/useFetch";
import useSave from "../../hooks/useSave";
import { useAuth } from "../../context/AuthContext";
import { listDoctors } from "../../services/doctorApi";
import api from "../../services/api";
import { bookSurgery, cancelSurgery, getItems, getSurgeries, getSurgery, getTheatres, otAction } from "../../services/operationsApi";
import { EmptyState, ErrorBox, Loading, PageTitle } from "../../components/Feedback";
import { Button, Field, Input, Modal, Select, Textarea, fmtDateTime } from "../../components/ui";

const TONE = { SCHEDULED: "bg-sky-100 text-sky-900", IN_PROGRESS: "bg-violet-100 text-violet-900", RECOVERY: "bg-indigo-100 text-indigo-900", COMPLETED: "bg-emerald-100 text-emerald-900", CANCELLED: "bg-slate-200 text-slate-700" };
const ANAESTHESIA = ["GENERAL", "SPINAL", "EPIDURAL", "REGIONAL", "LOCAL", "SEDATION"];
const today = () => new Date().toISOString().slice(0, 10);
const findPatients = (q) => api.get("/ot/patients", { params: { q } }).then((r) => r.data);
const Mark = ({ ok, text }) => <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-bold ${ok ? "bg-emerald-100 text-emerald-900" : "bg-slate-100 text-slate-600"}`}>{ok ? "Done" : "Not yet"}: {text}</span>;

export default function Schedule() {
  const { user } = useAuth();
  const canBook = (user.permissions || []).includes("ot.schedule");
  const [day, setDay] = useState("");
  const [dialog, setDialog] = useState(null);
  const { data, loading, error, reload } = useFetch(() => getSurgeries(day ? { day } : undefined), [day]);
  return (
    <div className="space-y-5">
      <PageTitle title="Operation theatre" subtitle="Booking never clashes. A surgery cannot start without a fit pre-op assessment, consent and the sign-in checklist." icon={Scissors} />
      <div className="flex flex-wrap items-end gap-3">
        <Field label="Day"><Input type="date" value={day} onChange={(e) => setDay(e.target.value)} /></Field>
        {day && <Button variant="secondary" onClick={() => setDay("")}>All days</Button>}
        {canBook && <Button onClick={() => setDialog({ kind: "book" })}>Book a surgery</Button>}
      </div>
      {loading && !data ? <Loading /> : error ? <ErrorBox message={error} onRetry={reload} /> : data.length === 0 ? <EmptyState message="No surgery" hint={day ? "Nothing is booked on this day." : "Nothing is booked yet."} icon={Scissors} /> : (
        <div className="space-y-3">{data.map((s) => (
          <div key={s.id} className="rounded-3xl border-2 border-brand-200 bg-white p-5 shadow-sm">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-lg font-extrabold">{s.procedure} {s.priority !== "ELECTIVE" && <span className="ml-1 rounded-full bg-red-600 px-2 py-0.5 text-xs font-bold text-white">{s.priority}</span>}</p>
                <p className="text-slate-700">{s.patient_name} <span className="text-slate-500">({s.patient_code})</span></p>
                <p className="text-sm text-slate-500">{s.theatre}, {fmtDateTime(s.scheduled_start)} to {fmtDateTime(s.scheduled_end)}. Surgeon {s.surgeon}{s.anaesthetist ? `, anaesthetist ${s.anaesthetist}` : ", no anaesthetist yet"}.</p>
              </div>
              <span className={`rounded-full px-3 py-1 text-sm font-bold ${TONE[s.status]}`}>{s.status.replace("_", " ")}</span>
            </div>
            <div className="mt-2 flex flex-wrap gap-1.5"><Mark ok={s.preop_fit === true} text="pre-op fit" /><Mark ok={s.consent_given === true} text="consent" /><Mark ok={s.sign_in_done} text="sign-in" /><Mark ok={s.time_out_done} text="time-out" /><Mark ok={s.sign_out_done} text="sign-out" /><Mark ok={s.op_note_final} text="operation note" /></div>
            <div className="mt-3"><Button variant="secondary" onClick={() => setDialog({ kind: "record", id: s.id })}>Open the record</Button></div>
          </div>))}</div>)}
      {dialog?.kind === "book" && <BookDialog onClose={() => setDialog(null)} onDone={() => { setDialog(null); reload(); }} />}
      {dialog?.kind === "record" && <RecordDialog id={dialog.id} user={user} onClose={() => { setDialog(null); reload(); }} />}
    </div>
  );
}

function BookDialog({ onClose, onDone }) {
  const doctors = useFetch(listDoctors);
  const theatres = useFetch(getTheatres);
  const [q, setQ] = useState("");
  const [found, setFound] = useState([]);
  const [form, setForm] = useState({ patient: null, theatre_id: "", procedure: "", priority: "ELECTIVE", surgeon_id: "", anaesthetist_id: "", scheduled_start: "", scheduled_end: "" });
  const { problem, busy, run } = useSave();
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  const ready = form.patient && form.theatre_id && form.procedure.trim().length >= 3 && form.surgeon_id && form.scheduled_start && form.scheduled_end;
  return (
    <Modal title="Book a surgery" onClose={onClose} wide>
      <div className="space-y-3">
        <Field label="Patient *" hint={form.patient ? `${form.patient.full_name} (${form.patient.patient_code})` : "Type a name, patient ID or UHID"}>
          <Input value={q} placeholder="Search" onChange={async (e) => { setQ(e.target.value); setFound(e.target.value.trim().length >= 2 ? await findPatients(e.target.value).catch(() => []) : []); }} />
        </Field>
        {found.length > 0 && !form.patient && <ul className="rounded-xl border bg-white">{found.map((p) => <li key={p.id}><button type="button" className="w-full px-3 py-2 text-left hover:bg-slate-50" onClick={() => { setForm({ ...form, patient: p }); setFound([]); }}>{p.full_name} ({p.patient_code})</button></li>)}</ul>}
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Procedure *"><Input maxLength={200} value={form.procedure} onChange={set("procedure")} /></Field>
          <Field label="Theatre *"><Select value={form.theatre_id} onChange={set("theatre_id")}><option value="">Choose</option>{(theatres.data || []).filter((t) => t.is_active).map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}</Select></Field>
          <Field label="Surgeon *"><Select value={form.surgeon_id} onChange={set("surgeon_id")}><option value="">Choose</option>{(doctors.data || []).filter((d) => d.grade !== "INTERN").map((d) => <option key={d.id} value={d.id}>{d.full_name}</option>)}</Select></Field>
          <Field label="Anaesthetist"><Select value={form.anaesthetist_id} onChange={set("anaesthetist_id")}><option value="">Not yet</option>{(doctors.data || []).filter((d) => d.grade !== "INTERN" && String(d.id) !== form.surgeon_id).map((d) => <option key={d.id} value={d.id}>{d.full_name}</option>)}</Select></Field>
          <Field label="Starts *"><Input type="datetime-local" value={form.scheduled_start} onChange={set("scheduled_start")} /></Field>
          <Field label="Ends *"><Input type="datetime-local" value={form.scheduled_end} onChange={set("scheduled_end")} /></Field>
          <Field label="Priority"><Select value={form.priority} onChange={set("priority")}><option value="ELECTIVE">Elective</option><option value="URGENT">Urgent</option><option value="EMERGENCY">Emergency</option></Select></Field>
        </div>
        {problem && <ErrorBox message={problem} />}
        <div className="flex justify-end gap-2"><Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button disabled={busy || !ready} onClick={async () => { if (await run(() => bookSurgery({ patient_id: form.patient.id, theatre_id: Number(form.theatre_id), procedure: form.procedure.trim(), priority: form.priority, surgeon_id: Number(form.surgeon_id), anaesthetist_id: form.anaesthetist_id ? Number(form.anaesthetist_id) : null, scheduled_start: form.scheduled_start, scheduled_end: form.scheduled_end }), "Surgery booked")) onDone(); }}>Book</Button></div>
      </div>
    </Modal>
  );
}

function Step({ title, done, children }) {
  return <div className="rounded-2xl border border-slate-200 p-3"><p className="mb-2 flex items-center justify-between font-bold">{title}<Mark ok={done} text="" /></p>{children}</div>;
}

function RecordDialog({ id, user, onClose }) {
  const { data: s, loading, error, reload } = useFetch(() => getSurgery(id), [id]);
  const items = useFetch(() => getItems().catch(() => []));
  const { problem, busy, run } = useSave();
  const [f, setF] = useState({ notes: "", by_name: "", findings: "", procedure_done: "", complications: "", blood_loss: "", anaesthesia: "GENERAL", event: "", item: "", qty: "1", recovery: "", reason: "" });
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  if (loading && !s) return <Modal title="Surgery record" onClose={onClose}><Loading /></Modal>;
  if (error) return <Modal title="Surgery record" onClose={onClose}><ErrorBox message={error} /></Modal>;
  const act = (action, body, message) => async () => { if (await run(() => otAction(id, action, body), message)) reload(); };
  const closed = ["COMPLETED", "CANCELLED"].includes(s.status);
  const tick = (phase) => async () => { const open = s.checklist[phase].filter((i) => !i.done).map((i) => i.item); if (open.length && await run(() => otAction(id, "checklist", { phase, items: open }), "Checklist saved")) reload(); };
  return (
    <Modal title={`${s.procedure}: ${s.patient_name}`} onClose={onClose} wide>
      <div className="space-y-3">
        <p className="text-sm text-slate-600">{s.theatre}, {fmtDateTime(s.scheduled_start)}. Status: <b>{s.status.replace("_", " ")}</b>.{s.cancel_reason ? ` Cancelled: ${s.cancel_reason}` : ""}</p>
        {problem && <ErrorBox message={problem} />}
        <Step title="Pre-operative assessment (the anaesthetist)" done={s.preop?.fit === true}>
          <p className="text-sm">{s.preop?.fit == null ? "Not done." : s.preop.fit ? "Fit for surgery." : "Not fit."} {s.preop?.notes}</p>
          {s.status === "SCHEDULED" && <div className="mt-2 flex flex-wrap items-end gap-2"><Field label="Notes"><Input maxLength={2000} value={f.notes} onChange={set("notes")} /></Field>
            <Button disabled={busy} onClick={act("preop", { fit: true, notes: f.notes || null }, "Marked fit")}>Fit</Button><Button variant="secondary" disabled={busy} onClick={act("preop", { fit: false, notes: f.notes || null }, "Marked not fit")}>Not fit</Button></div>}
        </Step>
        <Step title="Consent for this surgery" done={s.consent?.given === true}>
          <p className="text-sm">{s.consent?.given == null ? "Not recorded." : `${s.consent.given ? "Given" : "Refused"} by ${s.consent.by_name}.`}</p>
          {s.status === "SCHEDULED" && <div className="mt-2 flex flex-wrap items-end gap-2"><Field label="Signed by (patient or relative)"><Input maxLength={150} value={f.by_name} onChange={set("by_name")} /></Field>
            <Button disabled={busy || f.by_name.trim().length < 2} onClick={act("consent", { given: true, by_name: f.by_name.trim() }, "Consent recorded")}>Consent given</Button><Button variant="secondary" disabled={busy || f.by_name.trim().length < 2} onClick={act("consent", { given: false, by_name: f.by_name.trim() }, "Refusal recorded")}>Refused</Button></div>}
        </Step>
        {["SIGN_IN", "TIME_OUT", "SIGN_OUT"].map((phase) => (
          <Step key={phase} title={`Safety checklist: ${phase.replace("_", "-").toLowerCase()}`} done={s[`${phase.toLowerCase()}_done`]}>
            <ul className="text-sm">{s.checklist[phase].map((i) => <li key={i.item}>{i.done ? "Done" : "To do"}: {i.item}{i.by ? ` (${i.by})` : ""}</li>)}</ul>
            {!closed && !s[`${phase.toLowerCase()}_done`] && <Button className="mt-2" variant="secondary" disabled={busy} onClick={tick(phase)}>Tick all that are open</Button>}
          </Step>))}
        {s.status === "SCHEDULED" && <Button disabled={busy} onClick={act("start", {}, "Surgery started")}>Start the surgery</Button>}
        {["IN_PROGRESS", "RECOVERY"].includes(s.status) && (
          <>
            <Step title="Anaesthesia record (the anaesthetist)" done={!!s.anaesthesia?.type}>
              <p className="text-sm">{s.anaesthesia?.type ? `${s.anaesthesia.type}. ${s.anaesthesia.notes || ""}` : "Not written."}</p>
              <div className="mt-2 flex flex-wrap items-end gap-2"><Field label="Type"><Select value={f.anaesthesia} onChange={set("anaesthesia")}>{ANAESTHESIA.map((a) => <option key={a}>{a}</option>)}</Select></Field><Field label="Notes"><Input maxLength={3000} value={f.notes} onChange={set("notes")} /></Field>
                <Button disabled={busy} onClick={act("anaesthesia", { type: f.anaesthesia, notes: f.notes || null }, "Anaesthesia record saved")}>Save</Button></div>
            </Step>
            <Step title="Operation note (the surgeon)" done={s.op_note?.final}>
              {s.op_note?.findings && <p className="text-sm"><b>Findings:</b> {s.op_note.findings} <b>Done:</b> {s.op_note.procedure_done} {s.op_note.final ? "(final)" : "(draft)"}</p>}
              {!s.op_note?.final && <div className="mt-2 space-y-2"><Field label="Findings *"><Textarea rows={2} maxLength={4000} value={f.findings} onChange={set("findings")} /></Field><Field label="Procedure done *"><Textarea rows={2} maxLength={4000} value={f.procedure_done} onChange={set("procedure_done")} /></Field>
                <div className="grid gap-2 sm:grid-cols-2"><Field label="Complications"><Input maxLength={2000} value={f.complications} onChange={set("complications")} /></Field><Field label="Blood loss (ml)"><Input inputMode="numeric" value={f.blood_loss} onChange={set("blood_loss")} /></Field></div>
                <div className="flex gap-2">{[false, true].map((final) => <Button key={String(final)} variant={final ? "primary" : "secondary"} disabled={busy || f.findings.trim().length < 3 || f.procedure_done.trim().length < 3}
                  onClick={act("op-note", { findings: f.findings, procedure_done: f.procedure_done, complications: f.complications || null, blood_loss_ml: f.blood_loss ? Number(f.blood_loss) : null, final }, final ? "Operation note finalised" : "Draft saved")}>{final ? "Save as final" : "Save draft"}</Button>)}</div></div>}
            </Step>
            <Step title="Events in theatre" done={s.events.length > 0}>
              <ul className="text-sm">{s.events.map((e, i) => <li key={i}>{fmtDateTime(e.at)}: {e.text} ({e.by})</li>)}</ul>
              <div className="mt-2 flex flex-wrap items-end gap-2"><Field label="What happened"><Input maxLength={500} value={f.event} onChange={set("event")} /></Field><Button disabled={busy || f.event.trim().length < 3} onClick={async () => { if (await run(() => otAction(id, "events", { text: f.event.trim() }), "Event noted")) { setF({ ...f, event: "" }); reload(); } }}>Add</Button></div>
            </Step>
            <Step title="Consumables used" done={s.consumables.length > 0}>
              <ul className="text-sm">{s.consumables.map((c, i) => <li key={i}>{c.item} x {c.quantity} ({c.by})</li>)}</ul>
              <div className="mt-2 flex flex-wrap items-end gap-2"><Field label="Item"><Select value={f.item} onChange={set("item")}><option value="">Choose</option>{(items.data || []).map((i) => <option key={i.id} value={i.id}>{i.name} ({i.quantity} left)</option>)}</Select></Field><Field label="Quantity"><Input inputMode="numeric" value={f.qty} onChange={set("qty")} /></Field>
                <Button disabled={busy || !f.item} onClick={async () => { if (await run(() => otAction(id, "consumables", { inventory_item_id: Number(f.item), quantity: Number(f.qty) || 1 }), "Recorded: the store is updated")) reload(); }}>Add</Button></div>
            </Step>
          </>)}
        {s.status === "IN_PROGRESS" && <div className="flex flex-wrap items-end gap-2"><Field label="Recovery notes"><Input maxLength={2000} value={f.recovery} onChange={set("recovery")} /></Field><Button disabled={busy} onClick={act("recovery", { notes: f.recovery || null }, "Patient moved to recovery")}>Move to recovery</Button></div>}
        {s.status === "RECOVERY" && <Button disabled={busy} onClick={act("complete", {}, "Surgery completed")}>Complete the surgery</Button>}
        {s.status === "SCHEDULED" && (user.permissions || []).includes("ot.schedule") && <div className="flex flex-wrap items-end gap-2 border-t pt-3"><Field label="Cancel this surgery: reason"><Input maxLength={300} value={f.reason} onChange={set("reason")} /></Field>
          <Button variant="secondary" disabled={busy || f.reason.trim().length < 3} onClick={async () => { if (await run(() => cancelSurgery(id, f.reason.trim()), "Surgery cancelled")) reload(); }}>Cancel the surgery</Button></div>}
      </div>
    </Modal>
  );
}
