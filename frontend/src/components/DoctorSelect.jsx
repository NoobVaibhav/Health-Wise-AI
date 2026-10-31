// Choose a doctor, optionally narrowed by department. The department box only lists departments that have a doctor, and the doctor list follows it.
import { useMemo, useState } from "react";
import { Select } from "./ui";

export default function DoctorSelect({ doctors, value, onChange, id, required, emptyLabel = "Choose a doctor", showSpecialization = true }) {
  const [department, setDepartment] = useState("");
  const departments = useMemo(() => {
    const seen = new Map();
    (doctors || []).forEach((d) => { if (d.department_id) seen.set(d.department_id, d.department_name); });
    return [...seen].sort((a, b) => String(a[1]).localeCompare(String(b[1])));
  }, [doctors]);
  const shown = (doctors || []).filter((d) => !department || String(d.department_id) === department || String(d.id) === String(value));
  return (
    <div className="space-y-2">
      {departments.length > 1 && (
        <Select aria-label="Filter doctors by department" value={department} onChange={(e) => setDepartment(e.target.value)}>
          <option value="">All departments</option>
          {departments.map(([deptId, name]) => <option key={deptId} value={deptId}>{name}</option>)}
        </Select>)}
      <Select id={id} required={required} value={value} onChange={onChange}>
        <option value="">{emptyLabel}</option>
        {shown.map((d) => <option key={d.id} value={d.id}>{d.full_name}{showSpecialization && d.specialization_name ? ` (${d.specialization_name})` : ""}</option>)}
      </Select>
    </div>
  );
}
