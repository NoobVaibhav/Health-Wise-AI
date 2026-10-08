import { useEffect, useState } from "react";
import { listPatients } from "../services/patientApi";
import { inputClass } from "./ui";

// Search box + list. The employee picks the patient a report/appointment belongs to.
export default function PatientPicker({ value, onChange }) {
  const [q, setQ] = useState("");
  const [patients, setPatients] = useState([]);

  useEffect(() => {
    const timer = setTimeout(() => listPatients(q).then(setPatients).catch(() => setPatients([])), 250);
    return () => clearTimeout(timer);
  }, [q]);

  return (
    <div>
      <input className={inputClass} placeholder="Search patient by name, patient ID, phone or email" value={q} onChange={(e) => setQ(e.target.value)} />
      <div className="mt-2 max-h-48 overflow-y-auto rounded-lg border border-slate-200">
        {patients.length === 0 && <p className="p-3 text-sm text-slate-500">No patients found.</p>}
        {patients.map((p) => (
          <button type="button" key={p.id} onClick={() => onChange(p)}
            className={`flex w-full items-center justify-between px-3 py-2 text-left text-sm hover:bg-slate-50 ${value?.id === p.id ? "bg-brand-50" : ""}`}>
            <span className="font-medium">{p.full_name}</span>
            <span className="text-xs text-slate-500">{p.patient_code}{p.phone ? ` - ${p.phone}` : ""}</span>
          </button>
        ))}
      </div>
      {value && <p className="mt-2 text-sm text-brand-700">Selected: <b>{value.full_name}</b> ({value.patient_code})</p>}
    </div>
  );
}
