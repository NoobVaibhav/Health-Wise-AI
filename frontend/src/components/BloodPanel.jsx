// For a doctor, on the patient's page: ask the blood bank for blood, and see this patient's blood requests and transfusions.
// An intern cannot ask for blood. The blood group must match the patient's record; only an emergency can go without a known group.
import { useState } from "react";
import { Droplets } from "lucide-react";
import useFetch from "../hooks/useFetch";
import useSave from "../hooks/useSave";
import { useAuth } from "../context/AuthContext";
import { getBloodRequests, getPatientTransfusions, requestBlood, cancelBloodRequest } from "../services/operationsApi";
import { ErrorBox } from "./Feedback";
import { Section } from "./HealthCard";
import { Button, Field, Input, Modal, Select } from "./ui";

const COMPONENTS = [["PRBC", "Red cells"], ["WHOLE_BLOOD", "Whole blood"], ["FFP", "Plasma"], ["PLATELETS", "Platelets"]];
const GROUPS = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"];

export default function BloodPanel({ patientId }) {
  const { user } = useAuth();
  const allowed = (user.permissions || []).includes("bloodbank.request") && user.grade !== "INTERN";
  const reqs = useFetch(() => (allowed ? getBloodRequests() : Promise.resolve([])), [patientId]);
  const trans = useFetch(() => (allowed ? getPatientTransfusions(patientId).catch(() => []) : Promise.resolve([])), [patientId]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ component: "PRBC", units_requested: "1", urgency: "ROUTINE", indication: "", blood_group: "" });
  const { problem, busy, run } = useSave();
  if (!allowed) return null;
  const mine = (reqs.data || []).filter((r) => r.patient_id === patientId);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  return (
    <Section title="Blood" action={<Button variant="secondary" onClick={() => setOpen(true)}><Droplets size={16} /> Request blood</Button>}>
      {mine.length === 0 && (trans.data || []).length === 0 ? <p className="text-sm text-slate-500">No blood request or transfusion for this patient.</p> : (
        <ul className="divide-y text-sm">
          {mine.map((r) => <li key={`r${r.id}`} className="flex flex-wrap items-center justify-between gap-2 py-2"><span>{r.units_requested} x {COMPONENTS.find(([k]) => k === r.component)?.[1]} ({r.urgency.toLowerCase()}): {r.indication}</span>
            <span className="flex items-center gap-2"><b>{r.status}</b>{["PENDING", "CROSSMATCHED"].includes(r.status) && <Button variant="soft" onClick={async () => { await run(() => cancelBloodRequest(r.id), "Request cancelled"); reqs.reload(); }}>Cancel</Button>}</span></li>)}
          {(trans.data || []).map((t) => <li key={`t${t.id}`} className="py-2">Transfusion of unit {t.unit_number} ({t.blood_group}): <b>{t.status.replace("_", " ")}</b>{t.volume_given_ml ? `, ${t.volume_given_ml} ml given` : ""}{t.reaction ? `. Reaction: ${t.reaction_note}` : ""}</li>)}
        </ul>)}
      {open && (
        <Modal title="Request blood" onClose={() => setOpen(false)}>
          <div className="space-y-3">
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Component"><Select value={form.component} onChange={set("component")}>{COMPONENTS.map(([k, n]) => <option key={k} value={k}>{n}</option>)}</Select></Field>
              <Field label="Units"><Input inputMode="numeric" value={form.units_requested} onChange={set("units_requested")} /></Field>
              <Field label="How urgent"><Select value={form.urgency} onChange={set("urgency")}><option value="ROUTINE">Routine</option><option value="URGENT">Urgent</option><option value="EMERGENCY">Emergency</option></Select></Field>
              <Field label="Patient's blood group" hint="Leave empty to use the record. It must match the record."><Select value={form.blood_group} onChange={set("blood_group")}><option value="">From the record</option>{GROUPS.map((g) => <option key={g}>{g}</option>)}</Select></Field>
            </div>
            <Field label="Why is blood needed? *"><Input maxLength={300} value={form.indication} onChange={set("indication")} /></Field>
            {problem && <ErrorBox message={problem} />}
            <div className="flex justify-end gap-2"><Button variant="secondary" onClick={() => setOpen(false)}>Cancel</Button>
              <Button disabled={busy || form.indication.trim().length < 3 || !(Number(form.units_requested) > 0)} onClick={async () => { if (await run(() => requestBlood({ patient_id: patientId, component: form.component, units_requested: Number(form.units_requested), urgency: form.urgency, indication: form.indication.trim(), blood_group: form.blood_group || null }), "Request sent to the blood bank")) { setOpen(false); reqs.reload(); } }}>Send</Button></div>
          </div>
        </Modal>)}
    </Section>
  );
}
