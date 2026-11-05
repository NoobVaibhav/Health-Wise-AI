// The side of the consultation that the doctor reads while writing: History, Reports, Medicines and Vitals of this patient, one tap apart.
// Reports and medicines come from the same patient record the doctor already opens with "Full record"; nothing here changes any data.
import { useState } from "react";
import { Link } from "react-router-dom";
import useFetch from "../../hooks/useFetch";
import { getPatientHistory } from "../../services/doctorApi";
import { PrescriptionCard, ReportsTable } from "../Cards";
import { ErrorBox, Loading } from "../Feedback";
import { fmtUtc } from "../ui";

export const VITAL_FIELDS = [["pulse", "Pulse"], ["bp_systolic", "BP upper"], ["bp_diastolic", "BP lower"], ["spo2", "Oxygen %"], ["temperature_f", "Temp °F"], ["resp_rate", "Breathing"], ["weight_kg", "Weight kg"], ["height_cm", "Height cm"]];
const TABS = [["history", "History"], ["reports", "Reports"], ["medicines", "Medicines"], ["vitals", "Vitals"]];

function Record({ patientId, children }) {
  const { data, loading, error, reload } = useFetch(() => getPatientHistory(patientId, ""), [patientId]);
  if (loading && !data) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  return children(data);
}

export default function ConsultReference({ ws }) {
  const [tab, setTab] = useState("history");
  const p = ws.patient;
  return (
    <div className="rounded-3xl border border-slate-200/70 bg-white p-3 shadow-card">
      <div role="tablist" aria-label="Patient information" className="mb-3 grid grid-cols-4 gap-1 rounded-2xl bg-slate-100 p-1">
        {TABS.map(([key, label]) => (
          <button key={key} type="button" role="tab" id={`ref-tab-${key}`} aria-selected={tab === key} aria-controls="ref-panel" onClick={() => setTab(key)}
            className={`min-h-11 rounded-xl px-1 text-sm font-bold ${tab === key ? "bg-brand-700 text-white shadow-sm" : "text-slate-700 hover:bg-white"}`}>{label}</button>
        ))}
      </div>
      <div role="tabpanel" id="ref-panel" aria-labelledby={`ref-tab-${tab}`} className="min-w-0 text-sm">
        {tab === "history" && (
          <div className="space-y-3">
            {ws.previous_consultations.length === 0 ? <p className="text-slate-600">No earlier consultations.</p> : (
              <ul className="space-y-2">{ws.previous_consultations.map((c) => <li key={c.id} className="rounded-xl bg-slate-50 p-2.5"><b>{fmtUtc(c.signed_at)}</b> · {c.doctor_name}<br />{c.complaint}{c.assessment ? ` → ${c.assessment}` : ""}</li>)}</ul>
            )}
            {ws.charges.length > 0 && (
              <div><p className="font-bold text-slate-800">Charges (to be billed)</p>
                <ul>{ws.charges.map((c) => <li key={c.id}>{c.description}: <span className="num">Rs {c.amount}</span> <span className="text-slate-600">({c.status.toLowerCase()})</span></li>)}</ul></div>
            )}
            <Link to={`/doctor/patients/${p.id}`} className="inline-flex min-h-11 items-center font-bold text-brand-800 underline">Open the full record</Link>
          </div>
        )}
        {tab === "reports" && <Record patientId={p.id}>{(d) => (d.reports.length === 0 ? <p className="text-slate-600">No reports yet.</p> : <ReportsTable reports={d.reports} base="/doctor/reports" showPatient={false} />)}</Record>}
        {tab === "medicines" && (
          <div className="space-y-3">
            <p><span className="font-bold text-slate-800">Taking now:</span> {p.current_medications || "not recorded"}</p>
            {ws.prescriptions.length > 0 && <p className="text-slate-700">Prescriptions in this visit: <span className="num">{ws.prescriptions.length}</span></p>}
            <Record patientId={p.id}>{(d) => (d.prescriptions.length === 0 ? <p className="text-slate-600">No earlier prescriptions.</p> : <div className="space-y-2">{d.prescriptions.slice(0, 5).map((x) => <PrescriptionCard key={x.id} rx={x} />)}</div>)}</Record>
          </div>
        )}
        {tab === "vitals" && (
          ws.vitals.length === 0 ? <p className="text-slate-600">No vital signs recorded yet.</p> : (
            <ul className="space-y-2">{ws.vitals.slice(0, 6).map((v) => (
              <li key={v.id ?? v.recorded_at} className="rounded-xl bg-slate-50 p-2.5">
                <p className="text-xs text-slate-600">{fmtUtc(v.recorded_at)} · {v.recorded_by}</p>
                <p className="num">{VITAL_FIELDS.filter(([k]) => v[k] != null).map(([k, l]) => `${l} ${v[k]}`).join(" · ")}</p>
              </li>))}</ul>
          )
        )}
      </div>
    </div>
  );
}
