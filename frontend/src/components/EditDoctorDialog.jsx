// The admin changes a doctor's department and specialization (the same two linked dropdowns as when the doctor is created).
import { useState } from "react";
import { updateUser } from "../services/adminApi";
import { getErrorMessage } from "../services/api";
import DepartmentSpecializationSelect from "./DepartmentSpecializationSelect";
import { ErrorBox } from "./Feedback";
import { Button, Modal, ModalActions } from "./ui";

export default function EditDoctorDialog({ person, onClose, onSaved }) {
  const [choice, setChoice] = useState({ department_id: person.department_id ? String(person.department_id) : "", specialization_id: person.specialization_id ? String(person.specialization_id) : "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [missing, setMissing] = useState("");
  const junior = person.grade && person.grade !== "CONSULTANT";
  const [independent, setIndependent] = useState(Boolean(person.can_prescribe_independently));
  const save = async (e) => {
    e.preventDefault();
    if (busy) return;
    if (!choice.department_id) { setMissing("Please choose a department."); return; }
    setBusy(true);
    setError("");
    try {
      await updateUser(person.id, { department_id: Number(choice.department_id), specialization_id: choice.specialization_id ? Number(choice.specialization_id) : null, ...(junior ? { can_prescribe_independently: independent } : {}) });
      onSaved();
      onClose();
    } catch (err) { setError(getErrorMessage(err)); }                    // the choice stays in the boxes
    finally { setBusy(false); }
  };
  return (
    <Modal title={`Department and specialization of ${person.full_name}`} onClose={onClose}>
      <form onSubmit={save} noValidate className="space-y-4" aria-busy={busy}>
        <DepartmentSpecializationSelect departmentRequired showSpecialization={person.grade !== "INTERN"} departmentId={choice.department_id} specializationId={choice.specialization_id} departmentError={missing}
          legacyText={person.legacy_specialization} onChange={(next) => { setChoice(next); setMissing(""); }} />
        {junior && person.grade !== "INTERN" && (
          <label className="flex items-start gap-3 rounded-2xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-950">
            <input type="checkbox" className="mt-0.5 h-5 w-5" checked={independent} onChange={(e) => setIndependent(e.target.checked)} />
            <span><b>Can prescribe independently</b><br />Off (the safe default): a consultant countersigns every prescription this doctor writes, and the pharmacy cannot dispense it before. On: the prescription goes straight to the pharmacy. Only the administrator can change this.</span>
          </label>)}
        {error && <ErrorBox message={error} />}
        <ModalActions><Button disabled={busy}>{busy ? "Saving..." : "Save"}</Button></ModalActions>
      </form>
    </Modal>
  );
}
