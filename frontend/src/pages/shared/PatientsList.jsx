// Searchable patient list as friendly cards. Admin/employee see basic details only; doctors see their own authorized patients.
import { useState } from "react";
import { Link } from "react-router-dom";
import { FolderOpen, Pencil, Search } from "lucide-react";
import useFetch from "../../hooks/useFetch";
import { useAuth } from "../../context/AuthContext";
import { listPatients, updatePatient } from "../../services/patientApi";
import { listDoctors } from "../../services/doctorApi";
import { getErrorMessage } from "../../services/api";
import { PersonCard } from "../../components/DataViews";
import { Button, Field, Input, Modal, Select, inputClass } from "../../components/ui";
import { EmptyState, ErrorBox, Loading, PageTitle } from "../../components/Feedback";
import { useToast } from "../../components/Toast";

export default function PatientsList() {
  const { user } = useAuth();
  const [q, setQ] = useState("");
  const { data, loading, error, reload } = useFetch(() => listPatients(q), [q]);
  const [editing, setEditing] = useState(null);
  const toast = useToast();
  const isDoctor = user.role === "DOCTOR";
  const canEdit = ["EMPLOYEE", "ADMIN"].includes(user.role);

  return (
    <div className="space-y-5">
      <PageTitle title={isDoctor ? "My patients" : "Patients"} subtitle={isDoctor ? "People assigned to you, or who have an appointment or report with you" : "Find a patient and keep their contact details up to date"} />
      <div className="relative">
        <Search className="pointer-events-none absolute left-3.5 top-3 text-slate-400" size={18} />
        <input className={`${inputClass} pl-10`} placeholder="Search by name, patient ID, phone or email" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      {loading && !data ? <Loading /> : error ? <ErrorBox message={error} onRetry={reload} /> : data.length === 0 ? (
        <EmptyState message={q ? "No patients match your search" : "No patients yet"} hint={q ? "Check the spelling or try the patient ID." : undefined}
          actionTo={user.role === "EMPLOYEE" && !q ? "/employee/register" : undefined} actionText="Register a patient" />
      ) : (
        <div className="space-y-3">
          {data.map((p) => (
            <PersonCard key={p.id} name={p.full_name} subtitle={p.email}
              badge={<span className="rounded-full bg-brand-100 px-2.5 py-1 text-xs font-bold text-brand-800">{p.patient_code}</span>}
              facts={[
                ...(p.age != null ? [["Age", `${p.age} years`]] : []), ...(p.gender ? [["Gender", p.gender]] : []),
                ...(p.phone ? [["Phone", p.phone]] : []), ["Doctor", p.assigned_doctor_name || "not chosen yet"],
              ]}
              actions={<>
                {isDoctor && <Link to={`/doctor/patients/${p.id}`} className="rounded-xl bg-gradient-to-r from-brand-600 to-brand-700 px-4 py-2.5 text-sm font-bold text-white shadow-sm"><FolderOpen size={15} className="mr-1.5 inline" />Open record</Link>}
                {canEdit && <Button variant="secondary" onClick={() => setEditing(p)}><Pencil size={15} className="mr-1.5 inline" />Edit details</Button>}
              </>} />
          ))}
        </div>
      )}
      {editing && <EditPatient patient={editing} onClose={() => setEditing(null)} onSaved={() => { toast("Patient details saved"); reload(); }} />}
    </div>
  );
}

function EditPatient({ patient, onClose, onSaved }) {
  const { data: doctors } = useFetch(listDoctors, []);
  const [form, setForm] = useState({
    full_name: patient.full_name, phone: patient.phone || "", address: patient.address || "",
    emergency_contact: patient.emergency_contact || "", assigned_doctor_id: patient.assigned_doctor_id || "",
  });
  const [error, setError] = useState("");
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  const submit = async (e) => {
    e.preventDefault();
    try {
      await updatePatient(patient.id, { ...form, assigned_doctor_id: form.assigned_doctor_id ? Number(form.assigned_doctor_id) : null });
      onSaved();
      onClose();
    } catch (err) { setError(getErrorMessage(err)); }
  };
  return (
    <Modal title={`Edit ${patient.full_name}`} onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        <Field label="Full name"><Input required value={form.full_name} onChange={set("full_name")} /></Field>
        <Field label="Phone"><Input value={form.phone} onChange={set("phone")} /></Field>
        <Field label="Address"><Input value={form.address} onChange={set("address")} /></Field>
        <Field label="Emergency contact"><Input value={form.emergency_contact} onChange={set("emergency_contact")} /></Field>
        <Field label="Doctor who looks after this patient"><Select value={form.assigned_doctor_id} onChange={set("assigned_doctor_id")}>
          <option value="">Not chosen yet</option>{(doctors || []).map((d) => <option key={d.id} value={d.id}>{d.full_name}</option>)}</Select></Field>
        {error && <ErrorBox message={error} />}
        <Button>Save changes</Button>
      </form>
    </Modal>
  );
}
