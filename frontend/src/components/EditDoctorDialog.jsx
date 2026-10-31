// The admin changes a doctor's department and specialization (the same two linked dropdowns as when the doctor is created).
import { useState } from "react";
import { updateUser } from "../services/adminApi";
import { getErrorMessage } from "../services/api";
import DepartmentSpecializationSelect from "./DepartmentSpecializationSelect";
import { ErrorBox } from "./Feedback";
import { Button, Modal } from "./ui";

export default function EditDoctorDialog({ person, onClose, onSaved }) {
  const [choice, setChoice] = useState({ department_id: person.department_id ? String(person.department_id) : "", specialization_id: person.specialization_id ? String(person.specialization_id) : "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [missing, setMissing] = useState("");
  const save = async (e) => {
    e.preventDefault();
    if (busy) return;
    if (!choice.department_id) { setMissing("Please choose a department."); return; }
    setBusy(true);
    setError("");
    try {
      await updateUser(person.id, { department_id: Number(choice.department_id), specialization_id: choice.specialization_id ? Number(choice.specialization_id) : null });
      onSaved();
      onClose();
    } catch (err) { setError(getErrorMessage(err)); }                    // the choice stays in the boxes
    finally { setBusy(false); }
  };
  return (
    <Modal title={`Department and specialization of ${person.full_name}`} onClose={onClose}>
      <form onSubmit={save} noValidate className="space-y-4" aria-busy={busy}>
        <DepartmentSpecializationSelect departmentRequired departmentId={choice.department_id} specializationId={choice.specialization_id} departmentError={missing}
          legacyText={person.legacy_specialization} onChange={(next) => { setChoice(next); setMissing(""); }} />
        {error && <ErrorBox message={error} />}
        <Button disabled={busy}>{busy ? "Saving..." : "Save"}</Button>
      </form>
    </Modal>
  );
}
