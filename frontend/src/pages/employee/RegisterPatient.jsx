import { useState } from "react";
import { Link } from "react-router-dom";
import { UserCheck } from "lucide-react";
import useFetch from "../../hooks/useFetch";
import { registerPatient } from "../../services/patientApi";
import { listDoctors } from "../../services/doctorApi";
import { getErrorMessage } from "../../services/api";
import { Section } from "../../components/HealthCard";
import AccountCreatedDialog from "../../components/AccountCreatedDialog";
import { Button, Field, Input, Select } from "../../components/ui";
import { ErrorBox, PageTitle } from "../../components/Feedback";

const EMPTY = { full_name: "", email: "", date_of_birth: "", gender: "", phone: "", address: "", emergency_contact: "", blood_group: "", allergies: "", assigned_doctor_id: "" };

// Reception registers a patient. The patient's login is created at the same time.
export default function RegisterPatient() {
  const { data: doctors } = useFetch(listDoctors, []);
  const [form, setForm] = useState(EMPTY);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const payload = Object.fromEntries(Object.entries(form).map(([k, v]) => [k, v === "" ? null : v]));
      if (payload.assigned_doctor_id) payload.assigned_doctor_id = Number(payload.assigned_doctor_id);
      setResult(await registerPatient(payload));
      setForm(EMPTY);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <PageTitle title="Register Patient" subtitle="Creates the patient record and a login for the patient" />
      {result && (
        <AccountCreatedDialog kind="patient" name={result.patient.full_name} code={result.patient.patient_code} email={result.patient.email} password={result.temporary_password}
          onClose={() => setResult(null)}
          actions={<Link to="/employee/upload" className="inline-flex min-h-11 items-center rounded-xl border-2 border-brand-700 bg-white px-5 py-2.5 text-base font-bold text-brand-800 hover:bg-brand-50">Upload a report for this patient</Link>} />
      )}
      <form onSubmit={submit} className="space-y-5">
        <Section title="Basic information">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Full name"><Input required value={form.full_name} onChange={set("full_name")} /></Field>
            <Field label="Email (used to log in)"><Input type="email" required value={form.email} onChange={set("email")} /></Field>
            <Field label="Date of birth"><Input type="date" value={form.date_of_birth} onChange={set("date_of_birth")} /></Field>
            <Field label="Gender"><Select value={form.gender} onChange={set("gender")}><option value="">Not specified</option><option>female</option><option>male</option><option>other</option></Select></Field>
            <Field label="Phone"><Input value={form.phone} onChange={set("phone")} /></Field>
            <Field label="Emergency contact"><Input value={form.emergency_contact} onChange={set("emergency_contact")} /></Field>
            <div className="sm:col-span-2"><Field label="Address"><Input value={form.address} onChange={set("address")} /></Field></div>
            <Field label="Assigned doctor" hint="The doctor who will review this patient's reports">
              <Select value={form.assigned_doctor_id} onChange={set("assigned_doctor_id")}>
                <option value="">Choose later</option>{(doctors || []).map((d) => <option key={d.id} value={d.id}>{d.full_name}</option>)}</Select></Field>
          </div>
        </Section>
        <Section title="Voluntary details (optional)">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Blood group"><Input value={form.blood_group} onChange={set("blood_group")} /></Field>
            <Field label="Known allergies"><Input value={form.allergies} onChange={set("allergies")} /></Field>
          </div>
          <p className="mt-2 text-xs text-slate-500">Only the patient and their doctors can see these details.</p>
        </Section>
        {error && <ErrorBox message={error} />}
        <Button disabled={busy}>{busy ? "Registering..." : "Register patient"}</Button>
      </form>
    </div>
  );
}
