// Two linked dropdowns: Department, then Specialization of that department. The department list is loaded once (and cached); the specializations are loaded
// again for every department, and the specialization is cleared when the department changes. Plain <select> boxes, so the keyboard and a phone's own picker work.
import { useCallback, useEffect, useState } from "react";
import { getDepartments, getSpecializations } from "../services/catalogApi";
import { getErrorMessage } from "../services/api";
import { FormField } from "./FormField";
import { Select } from "./ui";

export default function DepartmentSpecializationSelect({
  departmentId, specializationId, onChange, departmentRequired = false, disabled = false, departmentError, specializationError, legacyText, idPrefix = "", showSpecialization = true,
}) {
  const [departments, setDepartments] = useState(null);
  const [departmentsProblem, setDepartmentsProblem] = useState("");
  const [specializations, setSpecializations] = useState(null);     // null = not loaded (no department, or loading)
  const [specializationsProblem, setSpecializationsProblem] = useState("");
  const [loading, setLoading] = useState(false);

  const loadDepartments = useCallback(() => {
    setDepartmentsProblem("");
    getDepartments().then(setDepartments).catch((err) => setDepartmentsProblem(getErrorMessage(err)));
  }, []);
  useEffect(() => { loadDepartments(); }, [loadDepartments]);

  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    setSpecializationsProblem("");
    if (!departmentId || !showSpecialization) { setSpecializations(null); setLoading(false); return undefined; }
    let current = true;                                              // an older answer must not replace a newer one
    setLoading(true);
    getSpecializations(Number(departmentId))
      .then((rows) => { if (current) setSpecializations(rows); })
      .catch((err) => { if (current) setSpecializationsProblem(getErrorMessage(err)); })       // the chosen value stays
      .finally(() => { if (current) setLoading(false); });
    return () => { current = false; };
  }, [departmentId, attempt, showSpecialization]);

  const departmentName = `${idPrefix}department_id`;
  const specializationName = `${idPrefix}specialization_id`;
  const empty = departmentId && !loading && !specializationsProblem && specializations && specializations.length === 0;
  const options = specializations || [];
  const missingChosen = specializationId && !options.some((s) => String(s.id) === String(specializationId));      // a deactivated one the doctor still has

  return (
    <>
      <FormField label={departmentRequired ? "Department *" : "Department"} name={departmentName} error={departmentError || departmentsProblem}>
        <Select disabled={disabled || (!departments && !departmentsProblem)} aria-required={departmentRequired || undefined} value={departmentId || ""}
          onChange={(e) => onChange({ department_id: e.target.value, specialization_id: "" })}>
          <option value="">{departments ? "Choose a department" : departmentsProblem ? "Could not load departments" : "Loading departments..."}</option>
          {(departments || []).map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
        </Select>
      </FormField>
      {departmentsProblem && <button type="button" onClick={loadDepartments} className="-mt-2 text-sm font-semibold text-sky-700 underline">Try again</button>}

      {showSpecialization && <FormField label="Specialization" name={specializationName} error={specializationError || specializationsProblem}
        hint={empty ? "No specializations for this department yet" : !departmentId ? "Choose a department first" : legacyText && !specializationId ? `Current (old entry): ${legacyText}. Choose one from the list to replace it.` : undefined}>
        <Select disabled={disabled || !departmentId || loading} value={specializationId || ""}
          onChange={(e) => onChange({ department_id: departmentId || "", specialization_id: e.target.value })}>
          <option value="">{!departmentId ? "Choose a department first" : loading ? "Loading..." : empty ? "No specializations for this department yet" : "Choose a specialization"}</option>
          {missingChosen && <option value={specializationId}>(current choice, no longer listed)</option>}
          {options.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
        </Select>
      </FormField>}
      {showSpecialization && specializationsProblem && <button type="button" onClick={() => setAttempt((n) => n + 1)} className="-mt-2 text-sm font-semibold text-sky-700 underline">Try again</button>}
    </>
  );
}
