// Appointments for every role, shown as cards grouped by day ("Today", "Tomorrow" ...).
// What you can do depends on the role (the backend enforces it too).
import { useEffect, useState } from "react";
import { CalendarClock, Plus } from "lucide-react";
import useFetch from "../../hooks/useFetch";
import { useAuth } from "../../context/AuthContext";
import { createAppointment, listAppointments, listSlots, updateAppointment } from "../../services/appointmentApi";
import { listDoctors } from "../../services/doctorApi";
import { getErrorMessage } from "../../services/api";
import PatientPicker from "../../components/PatientPicker";
import { AppointmentCard, Grouped, friendlyDay } from "../../components/DataViews";
import { Button, Field, Input, Modal, ModalActions, Select, Textarea } from "../../components/ui";
import { Chips } from "../../components/historyKit";
import { EmptyState, ErrorBox, Loading, PageTitle } from "../../components/Feedback";
import { useToast } from "../../components/Toast";
import DoctorSelect from "../../components/DoctorSelect";
import { appointmentDateBounds, appointmentTime, hospitalNow } from "../../utils/validators";

const SUBTITLE = {
  DOCTOR: "Your patients' appointments with you", PATIENT: "Your upcoming and past visits",
  EMPLOYEE: "Book, confirm and change appointments", ADMIN: "All appointments in the hospital",
};

export default function Appointments() {
  const { user } = useAuth();
  const toast = useToast();
  const { data, loading, error, reload } = useFetch(() => listAppointments(), []);
  const [creating, setCreating] = useState(false);
  const canBook = ["EMPLOYEE", "ADMIN", "PATIENT"].includes(user.role);

  const act = async (id, body) => {
    try { await updateAppointment(id, body); toast("Appointment updated"); reload(); } catch (e) { toast(getErrorMessage(e), "error"); }
  };

  if (loading) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <PageTitle title="Appointments" subtitle={SUBTITLE[user.role]} icon={CalendarClock} />
        {canBook && <Button onClick={() => setCreating(true)}><Plus size={16} className="mr-1.5 inline" /> Book an appointment</Button>}
      </div>
      {data.length === 0 ? (
        <EmptyState message="No appointments yet" hint={canBook ? 'Use "Book an appointment" to add the first one.' : "Appointments booked for you will appear here."} icon={CalendarClock} />
      ) : (
        <Grouped groups={groupAppointments(data, user.role, act)} />
      )}
      {creating && <NewAppointment role={user.role} onClose={() => setCreating(false)} onSaved={() => { toast("Appointment booked"); reload(); }} />}
    </div>
  );
}

// Upcoming ones grouped by day, then everything earlier or cancelled. Each role gets only the buttons it may use.
function groupAppointments(list, role, act) {
  const buttons = (a) => {
    const open = ["SCHEDULED", "CONFIRMED"].includes(a.status);
    const staff = ["DOCTOR", "EMPLOYEE", "ADMIN"].includes(role);
    return (
      <>
        {staff && a.status === "SCHEDULED" && <Button variant="soft" onClick={() => act(a.id, { status: "CONFIRMED" })}>Confirm</Button>}
        {staff && a.status === "CONFIRMED" && <Button variant="soft" onClick={() => act(a.id, { status: "COMPLETED" })}>Mark done</Button>}
        {open && (role === "PATIENT" || ["EMPLOYEE", "ADMIN"].includes(role)) && <Button variant="secondary" onClick={() => act(a.id, { status: "CANCELLED" })}>Cancel</Button>}
      </>
    );
  };
  const card = (a) => <AppointmentCard key={a.id} a={a} showPatient={role !== "PATIENT"} actions={buttons(a)} />;
  const sorted = [...list].sort((x, y) => new Date(x.scheduled_at) - new Date(y.scheduled_at));
  const upcoming = sorted.filter((a) => ["SCHEDULED", "CONFIRMED"].includes(a.status) && new Date(a.scheduled_at) >= Date.now() - 3600000);
  const earlier = sorted.filter((a) => !upcoming.includes(a)).reverse();

  const groups = [];
  for (const a of upcoming) {
    const title = friendlyDay(a.scheduled_at);
    let group = groups.find((g) => g.title === title);
    if (!group) groups.push((group = { title, items: [] }));
    group.items.push(card(a));
  }
  if (earlier.length) groups.push({ title: "Earlier and cancelled", items: earlier.map(card) });
  return groups;
}

const PROBLEMS = ["Fever", "Chest pain", "Giddiness", "Fainting", "Breathlessness", "Palpitations", "Headache", "Cough", "Vomiting", "Pain in abdomen", "Weakness", "Swelling of feet", "Sweating", "Burning urine", "Joint pain"];
const SINCE = ["Today", "1 day", "2-3 days", "1 week", "2 weeks", "1 month", "More than 1 month"];

export function NewAppointment({ role, onClose, onSaved }) {
  const { data: doctors } = useFetch(listDoctors, []);
  const [patient, setPatient] = useState(null);
  const [form, setForm] = useState({ doctor_id: "", day: "", time: "", reason: "", duration: "", details: "" });
  const [symptoms, setSymptoms] = useState([]);
  const [errors, setErrors] = useState({});        // shown under the field it belongs to; what the person typed stays
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [slots, setSlots] = useState(null);        // the doctor's slots for the chosen day: { time, available, reason }
  const [slotsProblem, setSlotsProblem] = useState("");
  const set = (k) => (e) => { setForm({ ...form, [k]: e.target.value }); setErrors({ ...errors, [k]: "" }); };
  const bounds = appointmentDateBounds();        // the date box starts today (hospital date) and stops 30 days ahead

  const loadSlots = (doctorId, day) => {
    setSlots(null); setSlotsProblem("");
    if (!doctorId || !day) return () => {};
    let current = true;
    listSlots(Number(doctorId), day).then((r) => { if (current) setSlots(r.slots); }).catch((e) => { if (current) setSlotsProblem(getErrorMessage(e)); });
    return () => { current = false; };
  };
  useEffect(() => loadSlots(form.doctor_id, form.day), [form.doctor_id, form.day]);       // eslint-disable-line react-hooks/exhaustive-deps

  const submit = async (e) => {
    e.preventDefault();
    if (busy) return;
    const found = {};
    if (role !== "PATIENT" && !patient) found.patient = "Please choose the patient.";
    if (!form.doctor_id) found.doctor_id = "Please choose a doctor.";
    if (!form.day) found.day = "Please choose the date.";
    else if (form.day < bounds.min || form.day > bounds.max) found.day = form.day < bounds.min ? "That day has already passed. Please choose today or a later day." : "Appointments can be booked up to 30 days ahead.";
    else if (!form.time) found.time = "Please choose a time.";
    else { const m = appointmentTime(`${form.day}T${form.time}`); if (m) found.time = m; }
    setErrors(found); setError("");
    if (Object.keys(found).length) return;
    setBusy(true);
    try {
      await createAppointment({
        patient_id: role === "PATIENT" ? null : patient?.id, doctor_id: Number(form.doctor_id),
        scheduled_at: `${form.day}T${form.time}`, reason: form.reason || null,
        symptoms, duration: form.duration || null, details: form.details || null,
      });
      onSaved();
      onClose();
    } catch (err) {
      const message = getErrorMessage(err);
      if (/time|slot|passed|ahead|patients between|appointment at/i.test(message)) setErrors({ time: message }); else setError(message);
      if (err?.response?.status === 409) loadSlots(form.doctor_id, form.day);        // somebody else took it: show the list as it is now
    } finally { setBusy(false); }
  };

  const nowTime = hospitalNow().time;
  return (
    <Modal title="Book an appointment" onClose={onClose}>
      <form onSubmit={submit} className="space-y-4" noValidate>
        {role !== "PATIENT" && <Field label="Who is it for?" error={errors.patient}><PatientPicker value={patient} onChange={(p) => { setPatient(p); setErrors({ ...errors, patient: "" }); }} /></Field>}
        <Field label="Which doctor?" error={errors.doctor_id}>
          <DoctorSelect required doctors={doctors} value={form.doctor_id} onChange={set("doctor_id")} />
        </Field>
        <Field label="Date" error={errors.day} hint={`From today up to ${bounds.max.split("-").reverse().join("/")} (30 days ahead)`}>
          <Input type="date" required min={bounds.min} max={bounds.max} value={form.day} aria-invalid={!!errors.day} onChange={(e) => { setForm({ ...form, day: e.target.value, time: "" }); setErrors({ ...errors, day: "", time: "" }); }} />
        </Field>
        <fieldset aria-describedby={errors.time ? "slot-error" : undefined}>
          <legend className="text-sm font-semibold text-slate-700">Time</legend>
          {!form.doctor_id || !form.day ? <p className="mt-1 text-sm text-slate-600">Choose a doctor and a date to see the free times.</p>
            : slotsProblem ? <p role="alert" className="mt-1 text-sm font-semibold text-red-700">{slotsProblem}</p>
            : !slots ? <p className="mt-1 text-sm text-slate-600">Loading the times...</p>
            : (
              <div className="mt-1.5 grid grid-cols-4 gap-2 sm:grid-cols-6" role="group" aria-label="Free times">
                {slots.map((x) => (
                  <button key={x.time} type="button" disabled={!x.available} aria-pressed={form.time === x.time}
                    title={x.reason === "taken" ? "Already booked" : x.reason === "unavailable" ? "Not available" : undefined}
                    onClick={() => { setForm({ ...form, time: x.time }); setErrors({ ...errors, time: "" }); }}
                    className={`min-h-11 rounded-xl border px-1 text-sm font-bold ${form.time === x.time ? "border-brand-700 bg-brand-700 text-white" : x.available ? "border-slate-300 bg-white text-slate-900 hover:bg-brand-50" : "cursor-not-allowed border-slate-200 bg-slate-100 text-slate-400 line-through"}`}>
                    {x.time}
                  </button>))}
              </div>)}
          {slots && slots.length > 0 && slots.every((x) => !x.available) && <p className="mt-1 text-sm text-slate-600">No free time on this day{form.day === bounds.min ? ` (it is ${nowTime} at the hospital)` : ""}. Please choose another day.</p>}
          {errors.time && <span id="slot-error" role="alert" className="mt-1 block text-sm font-semibold text-red-700">{errors.time}</span>}
        </fieldset>
        <div className="rounded-2xl border border-sky-200 bg-sky-50/60 p-4">
          <p className="font-extrabold text-sky-950">What is happening? <span className="text-sm font-normal text-sky-800">(optional, but it helps the doctor prepare)</span></p>
          <Field label="The main problem, in a few words"><Input value={form.reason} onChange={set("reason")} maxLength={300} placeholder="For example: giddiness and fainting, or discuss my blood test" /></Field>
          <p className="mb-1.5 mt-3 text-sm font-bold text-slate-700">Tap anything that you have</p>
          <Chips items={PROBLEMS} selected={symptoms} onToggle={(s) => setSymptoms(symptoms.includes(s) ? symptoms.filter((x) => x !== s) : [...symptoms, s])} />
          <p className="mb-1.5 mt-3 text-sm font-bold text-slate-700">Since when?</p>
          <Chips items={SINCE} selected={[form.duration]} onToggle={(d) => setForm({ ...form, duration: form.duration === d ? "" : d })} />
          <Field label="Tell the doctor more (what happened, how long it lasted, what makes it better or worse)">
            <Textarea rows={3} value={form.details} onChange={set("details")} maxLength={1000} /></Field>
        </div>
        {error && <ErrorBox message={error} />}
        <ModalActions><Button disabled={busy || (role !== "PATIENT" && !patient)}>{busy ? "Booking..." : "Book appointment"}</Button></ModalActions>
      </form>
    </Modal>
  );
}
