// Appointments for every role, shown as cards grouped by day ("Today", "Tomorrow" ...).
// What you can do depends on the role (the backend enforces it too).
import { useState } from "react";
import { CalendarClock, Plus } from "lucide-react";
import useFetch from "../../hooks/useFetch";
import { useAuth } from "../../context/AuthContext";
import { createAppointment, listAppointments, updateAppointment } from "../../services/appointmentApi";
import { listDoctors } from "../../services/doctorApi";
import { getErrorMessage } from "../../services/api";
import PatientPicker from "../../components/PatientPicker";
import { AppointmentCard, Grouped, friendlyDay } from "../../components/DataViews";
import { Button, Field, Input, Modal, Select } from "../../components/ui";
import { EmptyState, ErrorBox, Loading, PageTitle } from "../../components/Feedback";
import { useToast } from "../../components/Toast";

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
        {staff && open && <Button variant="soft" onClick={() => act(a.id, { status: "COMPLETED" })}>Mark done</Button>}
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

function NewAppointment({ role, onClose, onSaved }) {
  const { data: doctors } = useFetch(listDoctors, []);
  const [patient, setPatient] = useState(null);
  const [form, setForm] = useState({ doctor_id: "", scheduled_at: "", reason: "" });
  const [error, setError] = useState("");
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    try {
      await createAppointment({
        patient_id: role === "PATIENT" ? null : patient?.id, doctor_id: Number(form.doctor_id),
        scheduled_at: form.scheduled_at, reason: form.reason || null,
      });
      onSaved();
      onClose();
    } catch (err) { setError(getErrorMessage(err)); }
  };

  return (
    <Modal title="Book an appointment" onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        {role !== "PATIENT" && <Field label="Who is it for?"><PatientPicker value={patient} onChange={setPatient} /></Field>}
        <Field label="Which doctor?">
          <Select required value={form.doctor_id} onChange={set("doctor_id")}>
            <option value="">Choose a doctor</option>
            {(doctors || []).map((d) => <option key={d.id} value={d.id}>{d.full_name}{d.specialization ? ` (${d.specialization})` : ""}</option>)}
          </Select>
        </Field>
        <Field label="Date and time"><Input type="datetime-local" required value={form.scheduled_at} onChange={set("scheduled_at")} /></Field>
        <Field label="Reason (optional)"><Input value={form.reason} onChange={set("reason")} placeholder="For example: discuss my blood test" /></Field>
        {error && <ErrorBox message={error} />}
        <Button disabled={role !== "PATIENT" && !patient}>Book appointment</Button>
      </form>
    </Modal>
  );
}
