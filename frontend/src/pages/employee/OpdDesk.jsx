// Reception's OPD desk: check in a booked patient or a walk-in, and watch each doctor's queue with the waiting time.
import { useEffect, useState } from "react";
import { UserCheck } from "lucide-react";
import useFetch from "../../hooks/useFetch";
import useSave from "../../hooks/useSave";
import { checkIn, closeToken, opdQueue, walkIn } from "../../services/careApi";
import { listAppointments } from "../../services/appointmentApi";
import { listDoctors } from "../../services/doctorApi";
import PatientPicker from "../../components/PatientPicker";
import { Section } from "../../components/HealthCard";
import { EmptyState, ErrorBox, Loading, PageTitle } from "../../components/Feedback";
import { Button, Field, Select, fmtDateTime } from "../../components/ui";

const STATUS = { WAITING: "Waiting", CALLED: "Called", IN_CONSULTATION: "With the doctor", DONE: "Seen", NO_SHOW: "Did not come", CANCELLED: "Cancelled" };
const TONE = { WAITING: "bg-amber-100 text-amber-800", CALLED: "bg-sky-100 text-sky-800", IN_CONSULTATION: "bg-sky-100 text-sky-800", DONE: "bg-emerald-100 text-emerald-800", NO_SHOW: "bg-slate-200 text-slate-700", CANCELLED: "bg-slate-200 text-slate-700" };

export default function OpdDesk() {
  const today = new Date().toISOString().slice(0, 10);
  const queue = useFetch(() => opdQueue(), []);
  const appointments = useFetch(() => listAppointments({ day: today }), []);
  const { data: doctors } = useFetch(listDoctors, []);
  const { problem, busy, run } = useSave();
  const [patient, setPatient] = useState(null);
  const [doctorId, setDoctorId] = useState("");
  const [urgent, setUrgent] = useState(false);
  useEffect(() => { const t = setInterval(queue.reload, 20000); return () => clearInterval(t); }, [queue.reload]);
  const refresh = () => { queue.reload(); appointments.reload(); };
  const expected = (appointments.data || []).filter((a) => ["SCHEDULED", "CONFIRMED"].includes(a.status) && !a.encounter_id);
  const byDoctor = (queue.data || []).reduce((acc, t) => { (acc[t.doctor_name] = acc[t.doctor_name] || []).push(t); return acc; }, {});

  return (
    <div className="space-y-5">
      <PageTitle title="OPD desk" subtitle="Check patients in and see who is waiting for which doctor" icon={UserCheck} />
      <Section title="Booked for today">
        {appointments.loading && !appointments.data ? <Loading /> : expected.length === 0 ? <p className="text-slate-500">Everybody booked for today has been checked in.</p> : (
          <ul className="divide-y">{expected.map((a) => (
            <li key={a.id} className="flex flex-wrap items-center justify-between gap-2 py-2.5">
              <span><b>{a.patient_name}</b> <span className="text-sm text-slate-500">{a.patient_code} · {fmtDateTime(a.scheduled_at)} · with {a.doctor_name}</span></span>
              <span className="flex gap-2"><Button type="button" disabled={busy} onClick={async () => { if (await run(() => checkIn(a.id), "Checked in")) refresh(); }}>Check in</Button>
                <Button type="button" variant="secondary" disabled={busy} onClick={async () => { if (await run(() => checkIn(a.id, true), "Checked in as urgent")) refresh(); }}>Urgent</Button></span>
            </li>))}</ul>)}
      </Section>
      <Section title="Walk-in">
        <div className="grid gap-3 sm:grid-cols-[1fr_16rem_auto] sm:items-end">
          <Field label="Patient"><PatientPicker value={patient} onChange={setPatient} /></Field>
          <Field label="Doctor"><Select value={doctorId} onChange={(e) => setDoctorId(e.target.value)}><option value="">Choose a doctor</option>{(doctors || []).map((d) => <option key={d.id} value={d.id}>{d.full_name}{d.department_name ? ` (${d.department_name})` : ""}</option>)}</Select></Field>
          <Button type="button" disabled={busy || !patient || !doctorId} onClick={async () => { if (await run(() => walkIn({ patient_id: patient.id, doctor_id: Number(doctorId), urgent }), "Token given")) { setPatient(null); refresh(); } }}>Give token</Button>
        </div>
        <label className="mt-2 flex items-center gap-2 text-sm font-semibold text-red-700"><input type="checkbox" className="h-5 w-5" checked={urgent} onChange={(e) => setUrgent(e.target.checked)} /> Urgent: goes ahead in the queue</label>
        {problem && <div className="mt-3"><ErrorBox message={problem} /></div>}
      </Section>
      <Section title="Queues of today">
        {queue.loading && !queue.data ? <Loading /> : queue.error ? <ErrorBox message={queue.error} onRetry={queue.reload} /> : Object.keys(byDoctor).length === 0 ? <EmptyState message="No tokens yet today" hint="They appear here as patients are checked in." /> : (
          <div className="grid gap-4 lg:grid-cols-2">{Object.entries(byDoctor).map(([name, tokens]) => (
            <div key={name} className="rounded-2xl border border-slate-200 p-3"><p className="mb-2 font-extrabold text-slate-900">{name}</p>
              <ul className="space-y-1.5">{tokens.map((t) => (
                <li key={t.id} className="flex items-center justify-between gap-2 text-sm"><span><b className="mr-2 inline-block min-w-8 rounded-lg bg-slate-900 px-2 py-0.5 text-center text-white">{t.number}</b>{t.patient.full_name}{t.urgent && <span className="ml-2 rounded-full bg-red-100 px-2 py-0.5 text-xs font-bold text-red-700">Urgent</span>}</span>
                  <span className="flex items-center gap-2">{t.waiting_minutes != null && <span className="text-slate-500">{t.waiting_minutes} min</span>}<span className={`rounded-full px-2 py-0.5 text-xs font-bold ${TONE[t.status]}`}>{STATUS[t.status]}</span>
                    {t.status === "WAITING" && <button type="button" className="text-xs font-semibold text-slate-500 underline" aria-label={`Mark ${t.patient.full_name} as not came`} onClick={async () => { if (await run(() => closeToken(t.id, "no-show"), "Marked as not came")) refresh(); }}>No-show</button>}</span></li>))}</ul></div>))}</div>)}
      </Section>
    </div>
  );
}
