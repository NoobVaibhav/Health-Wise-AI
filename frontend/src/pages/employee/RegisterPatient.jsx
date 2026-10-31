import { useState } from "react";
import { Link } from "react-router-dom";
import { UserCheck } from "lucide-react";
import useFetch from "../../hooks/useFetch";
import { registerPatient } from "../../services/patientApi";
import { listDoctors } from "../../services/doctorApi";
import { getErrorMessage } from "../../services/api";
import { Section } from "../../components/HealthCard";
import AccountCreatedDialog from "../../components/AccountCreatedDialog";
import { Button, Input, Select } from "../../components/ui";
import { FormField } from "../../components/FormField";
import useValidation from "../../hooks/useValidation";
import * as v from "../../utils/validators";
import { ErrorBox, PageTitle } from "../../components/Feedback";
import DoctorSelect from "../../components/DoctorSelect";

const RULES = {
  full_name: (value) => v.personName(value),
  email: (value) => v.email(value),
  date_of_birth: (value) => v.dateOfBirth(value),
  gender: (value) => v.gender(value),
  phone: (value) => v.phone(value),
  emergency_contact: (value, all) => v.emergencyContact(value, all.phone),
  address: (value) => v.address(value),
  blood_group: (value) => v.bloodGroup(value),
  allergies: (value) => v.text(value, { max: 1000 }),
};
const EMPTY = { full_name: "", email: "", date_of_birth: "", gender: "", phone: "", address: "", emergency_contact: "", blood_group: "", allergies: "", assigned_doctor_id: "" };

// Reception registers a patient. The patient's login is created at the same time.
export default function RegisterPatient() {
  const { data: doctors } = useFetch(listDoctors, []);
  const [form, setForm] = useState(EMPTY);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const check = useValidation(RULES);
  const set = (k) => (e) => { setForm({ ...form, [k]: e.target.value }); check.clear(k); if (k === "phone") check.clear("emergency_contact"); };
  const blur = (k) => () => check.check(k, form);

  const submit = async (e) => {
    e.preventDefault();
    if (busy) return;
    if (!check.validateAll(form)) return;
    setBusy(true);
    setError("");
    try {
      const payload = Object.fromEntries(Object.entries(form).map(([k, val]) => [k, String(val).trim() === "" ? null : (typeof val === "string" ? val.trim() : val)]));
      payload.email = payload.email.toLowerCase();
      if (payload.assigned_doctor_id) payload.assigned_doctor_id = Number(payload.assigned_doctor_id);
      setResult(await registerPatient(payload));
      setForm(EMPTY);
    } catch (err) {
      if (!check.fromServer(err)) setError(getErrorMessage(err));          // the typed details stay in the form
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
      <form onSubmit={submit} noValidate className="space-y-5" aria-busy={busy}>
        <p className="text-sm text-slate-500">Fields marked * are needed. Everything is checked again by the server.</p>
        <Section title="Basic information">
          <div className="grid gap-4 sm:grid-cols-2">
            <FormField label="Full name *" name="full_name" error={check.errors.full_name}>
              <Input autoComplete="off" maxLength={150} value={form.full_name} onChange={set("full_name")} onBlur={blur("full_name")} />
            </FormField>
            <FormField label="Email (used to log in) *" name="email" error={check.errors.email}>
              <Input type="email" inputMode="email" autoComplete="off" maxLength={254} value={form.email} onChange={set("email")} onBlur={blur("email")} />
            </FormField>
            <FormField label="Date of birth" name="date_of_birth" error={check.errors.date_of_birth} warning={v.ageWarning(form.date_of_birth)}>
              <Input type="date" min={v.MIN_DOB} max={v.todayISO()} value={form.date_of_birth} onChange={set("date_of_birth")} onBlur={blur("date_of_birth")} />
            </FormField>
            <FormField label="Gender" name="gender" error={check.errors.gender}>
              <Select value={form.gender} onChange={set("gender")} onBlur={blur("gender")}><option value="">Not specified</option><option>female</option><option>male</option><option>other</option></Select>
            </FormField>
            <FormField label="Phone" name="phone" error={check.errors.phone} hint="For example 98765 43210 or +91 98765 43210">
              <Input type="tel" inputMode="tel" autoComplete="off" maxLength={20} value={form.phone} onChange={set("phone")} onBlur={blur("phone")} />
            </FormField>
            <FormField label="Emergency contact" name="emergency_contact" error={check.errors.emergency_contact} hint="Someone else to call: a name and number">
              <Input autoComplete="off" maxLength={150} value={form.emergency_contact} onChange={set("emergency_contact")} onBlur={blur("emergency_contact")} />
            </FormField>
            <div className="sm:col-span-2">
              <FormField label="Address" name="address" error={check.errors.address} max={300} count={form.address.length}>
                <Input autoComplete="off" value={form.address} onChange={set("address")} onBlur={blur("address")} />
              </FormField>
            </div>
            <div className="sm:col-span-2">
              <label htmlFor="assigned_doctor_id" className="block text-sm font-semibold text-slate-700">Assigned doctor</label>
              <div className="mt-1.5"><DoctorSelect id="assigned_doctor_id" doctors={doctors} value={form.assigned_doctor_id} onChange={set("assigned_doctor_id")} emptyLabel="Choose later" showSpecialization={false} /></div>
              <p className="mt-1 text-xs text-slate-500">The doctor who will review this patient's reports</p>
            </div>
          </div>
        </Section>
        <Section title="Voluntary details (optional)">
          <div className="grid gap-4 sm:grid-cols-2">
            <FormField label="Blood group" name="blood_group" error={check.errors.blood_group}>
              <Select value={form.blood_group} onChange={set("blood_group")} onBlur={blur("blood_group")}><option value="">Not known</option>{v.BLOOD_GROUPS.map((g) => <option key={g}>{g}</option>)}</Select>
            </FormField>
            <FormField label="Known allergies" name="allergies" error={check.errors.allergies} max={1000} count={form.allergies.length}>
              <Input autoComplete="off" value={form.allergies} onChange={set("allergies")} onBlur={blur("allergies")} />
            </FormField>
          </div>
          <p className="mt-2 text-xs text-slate-500">Only the patient and their doctors can see these details.</p>
        </Section>
        {error && <ErrorBox message={error} />}
        <Button disabled={busy}>{busy ? "Registering..." : "Register patient"}</Button>
      </form>
    </div>
  );
}
