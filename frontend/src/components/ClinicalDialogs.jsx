// Two small dialogs a doctor opens from a consultation: refer the patient to another department, and admit the patient to a ward.
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import useFetch from "../hooks/useFetch";
import useSave from "../hooks/useSave";
import { admit, askReferral, listWards } from "../services/careApi";
import { listDoctors } from "../services/doctorApi";
import { getDepartments } from "../services/catalogApi";
import { ErrorBox } from "./Feedback";
import { Button, Field, Input, Modal, Select, Textarea } from "./ui";

export function ReferDialog({ patientId, encounterId, onClose }) {
  const { data: departments } = useFetch(getDepartments, []);
  const { data: doctors } = useFetch(listDoctors, []);
  const { problem, busy, run } = useSave();
  const [form, setForm] = useState({ to_department_id: "", to_doctor_id: "", reason: "", urgency: "ROUTINE" });
  const [sent, setSent] = useState(false);
  const there = (doctors || []).filter((d) => String(d.department_id) === String(form.to_department_id));
  const send = async (e) => {
    e.preventDefault();
    const body = { patient_id: patientId, from_encounter_id: encounterId, to_department_id: Number(form.to_department_id), to_doctor_id: form.to_doctor_id ? Number(form.to_doctor_id) : null, reason: form.reason.trim(), urgency: form.urgency };
    if (await run(() => askReferral(body), "Referral sent")) setSent(true);
  };
  return (
    <Modal title="Refer to another department" onClose={onClose}>
      {sent ? <div className="space-y-3"><p className="rounded-xl bg-emerald-50 p-3 font-semibold text-emerald-900">The referral was sent. The specialist sees the records once they accept it, and their plan comes back to you under Referral requests.</p><Button type="button" onClick={onClose}>Close</Button></div> : (
        <form onSubmit={send} className="space-y-3" noValidate>
          <Field label="Department *"><Select value={form.to_department_id} onChange={(e) => setForm({ ...form, to_department_id: e.target.value, to_doctor_id: "" })}><option value="">Choose a department</option>{(departments || []).map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}</Select></Field>
          <Field label="A particular doctor (optional)"><Select disabled={!form.to_department_id} value={form.to_doctor_id} onChange={(e) => setForm({ ...form, to_doctor_id: e.target.value })}><option value="">Any doctor of the department</option>{there.map((d) => <option key={d.id} value={d.id}>{d.full_name}</option>)}</Select></Field>
          <Field label="Why? *" hint="At least 5 characters"><Textarea rows={3} maxLength={500} value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} /></Field>
          <label className="flex items-center gap-2 font-semibold text-red-700"><input type="checkbox" className="h-5 w-5" checked={form.urgency === "URGENT"} onChange={(e) => setForm({ ...form, urgency: e.target.checked ? "URGENT" : "ROUTINE" })} /> Urgent</label>
          {problem && <ErrorBox message={problem} />}
          <Button disabled={busy || !form.to_department_id || form.reason.trim().length < 5}>{busy ? "Sending..." : "Send the referral"}</Button>
        </form>)}
    </Modal>
  );
}

export function AdmitDialog({ patientId, encounterId, onClose }) {
  const navigate = useNavigate();
  const { data: wards } = useFetch(listWards, []);
  const { problem, busy, run } = useSave();
  const [form, setForm] = useState({ diagnosis: "", bed_id: "", expected_discharge: "" });
  const beds = (wards || []).flatMap((w) => w.beds.filter((b) => b.status === "AVAILABLE").map((b) => ({ ...b, ward: w.name })));
  const go = async (e) => {
    e.preventDefault();
    const a = await run(() => admit({ patient_id: patientId, source_encounter_id: encounterId || null, diagnosis: form.diagnosis.trim() || null, bed_id: form.bed_id ? Number(form.bed_id) : null, expected_discharge: form.expected_discharge || null }), "Patient admitted");
    if (a && a !== true) navigate(`/doctor/inpatients/${a.id}`);
  };
  return (
    <Modal title="Admit to a ward" onClose={onClose}>
      <form onSubmit={go} className="space-y-3" noValidate>
        <Field label="Reason for admission (diagnosis)"><Input maxLength={300} value={form.diagnosis} onChange={(e) => setForm({ ...form, diagnosis: e.target.value })} /></Field>
        <Field label="Bed (can be given later)"><Select value={form.bed_id} onChange={(e) => setForm({ ...form, bed_id: e.target.value })}><option value="">No bed yet</option>{beds.map((b) => <option key={b.id} value={b.id}>{b.ward}: {b.code}</option>)}</Select></Field>
        <Field label="Expected discharge"><Input type="date" min={new Date().toISOString().slice(0, 10)} value={form.expected_discharge} onChange={(e) => setForm({ ...form, expected_discharge: e.target.value })} /></Field>
        {problem && <ErrorBox message={problem} />}
        <Button disabled={busy}>{busy ? "Admitting..." : "Admit the patient"}</Button>
      </form>
    </Modal>
  );
}
