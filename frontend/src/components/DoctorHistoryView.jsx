// A doctor's view of one patient's medical history: the one-page summary, the points to check, earlier assessments.
import { useState } from "react";
import { Link } from "react-router-dom";
import { ClipboardPen, Printer } from "lucide-react";
import useFetch from "../hooks/useFetch";
import { getPatientHistoryForm } from "../services/historyApi";
import { Section } from "./HealthCard";
import EmergencyCard from "./EmergencyCard";
import HistoryPrintSheet from "./HistoryPrintSheet";
import PointsToCheck from "./PointsToCheck";
import PastHistory from "./history/PastHistory";
import { Button, fmtDate, fmtUtc } from "./ui";
import { ErrorBox, Loading } from "./Feedback";

const VITAL_LABEL = { pulse: ["Pulse", "/min"], bp: ["BP", "mmHg"], spo2: ["SpO2", "%"], temperature_f: ["Temp", "F"], resp_rate: ["RR", "/min"], weight_kg: ["Weight", "kg"], height_cm: ["Height", "cm"] };
const EXAM_LABEL = { consciousness: "Consciousness", general: "General", respiratory: "Respiratory", cardiovascular: "Heart and vessels", abdomen: "Abdomen", nervous_system: "Nervous system" };

function AssessmentCard({ a }) {
  const v = a.vitals || {};
  const chips = [];
  if (v.pulse != null) chips.push(["Pulse", `${v.pulse} /min`]);
  if (v.bp_systolic != null) chips.push(["BP", `${v.bp_systolic}/${v.bp_diastolic ?? "?"} mmHg`]);
  ["spo2", "temperature_f", "resp_rate", "weight_kg", "height_cm"].forEach((k) => v[k] != null && chips.push([VITAL_LABEL[k][0], `${v[k]} ${VITAL_LABEL[k][1]}`]));
  const exams = Object.entries(a.examination || {}).filter(([, text]) => text);
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4">
      <p className="text-sm text-slate-500">{fmtUtc(a.created_at)} - {a.doctor_name}</p>
      {a.chief_complaint && <p className="mt-1 font-bold text-slate-900">{a.chief_complaint}</p>}
      {a.history_of_present_illness && <p className="mt-1 text-slate-700">{a.history_of_present_illness}</p>}
      {chips.length > 0 && <div className="mt-2 flex flex-wrap gap-2">{chips.map(([k, val]) => <span key={k} className="rounded-lg bg-slate-100 px-2.5 py-1 text-sm"><span className="text-slate-500">{k}: </span><b>{val}</b></span>)}</div>}
      {exams.length > 0 && <dl className="mt-3 grid gap-x-6 gap-y-1 text-sm sm:grid-cols-2">{exams.map(([k, text]) => <div key={k}><dt className="inline font-bold text-slate-500">{EXAM_LABEL[k]}: </dt><dd className="inline text-slate-700">{text}</dd></div>)}</dl>}
      {a.provisional_diagnosis && <p className="mt-3 rounded-xl bg-violet-50 p-2.5 text-sm"><b className="text-violet-800">Provisional diagnosis (doctor): </b>{a.provisional_diagnosis}</p>}
      {a.investigations_advised && <p className="mt-2 text-sm"><b className="text-slate-600">Investigations advised: </b>{a.investigations_advised}</p>}
      {(a.plan_type || a.plan_details) && <p className="mt-1 text-sm"><b className="text-slate-600">Plan: </b>{{ MEDICAL: "Medical", SURGICAL: "Surgical", BOTH: "Medical and surgical" }[a.plan_type] || ""} {a.plan_details}</p>}
      {a.special_note && <p className="mt-1 text-sm"><b className="text-slate-600">Note: </b>{a.special_note}</p>}
    </div>
  );
}

/** The permanent record of how the patient usually is: usual pulse, BP, sugar and blood tests, and how the vitals have been. */
function UsualAndLabs({ history, labs, assessments }) {
  const b = history.baseline || {};
  const items = [["Pulse", b.pulse, "/min"], ["BP", b.bp_systolic ? `${b.bp_systolic}/${b.bp_diastolic ?? "?"}` : null, "mmHg"], ["SpO2", b.spo2, "%"], ["Sugar, fasting", b.sugar_fasting, "mg/dL"],
    ["Sugar, after meal", b.sugar_post_meal, "mg/dL"], ["HbA1c", b.hba1c, "%"], ["Haemoglobin", b.hemoglobin, "g/dL"], ["Creatinine", b.creatinine, "mg/dL"], ...(b.others || []).map((o) => [o.name, o.value, o.unit])]
    .filter(([, value]) => value !== null && value !== undefined && value !== "");
  const trend = assessments.filter((a) => a.vitals?.pulse || a.vitals?.bp_systolic).slice(0, 6);
  if (!items.length && !labs.length && !trend.length) return null;
  return (
    <Section title="Permanent record: usual values and blood tests">
      {items.length > 0 && (
        <>
          <p className="mb-2 text-sm font-bold text-slate-600">Usual values when well{b.noted_on ? ` (${b.noted_on})` : ""}</p>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">{items.map(([k, val, unit]) => <div key={k} className="rounded-2xl bg-slate-50 p-3"><p className="text-xs font-bold text-slate-500">{k}</p><p className="text-xl font-extrabold text-slate-900">{val} <span className="text-sm font-semibold text-slate-400">{unit}</span></p></div>)}</div>
        </>
      )}
      {labs.length > 0 && (
        <>
          <p className="mb-2 mt-5 text-sm font-bold text-slate-600">Latest blood tests, from the reports</p>
          <table className="w-full text-sm"><thead><tr className="text-left text-xs text-slate-400"><th className="pb-1">Test</th><th>Latest</th><th>Normal range</th><th>Date</th></tr></thead>
            <tbody>{labs.map((l) => <tr key={l.name} className="border-t border-slate-100"><td className="py-1.5 font-semibold">{l.name}</td>
              <td className={`font-bold ${l.status === "ABOVE_RANGE" ? "text-amber-700" : l.status === "BELOW_RANGE" ? "text-sky-700" : "text-slate-800"}`}>{l.value} {l.unit}</td>
              <td className="text-slate-500">{l.range || "not printed"}</td><td className="text-slate-500">{fmtDate(l.date)}</td></tr>)}</tbody></table>
        </>
      )}
      {trend.length > 0 && (
        <>
          <p className="mb-2 mt-5 text-sm font-bold text-slate-600">Pulse and blood pressure at recent visits</p>
          <div className="flex flex-wrap gap-2">{trend.map((a) => <span key={a.id} className="rounded-xl bg-slate-50 px-3 py-1.5 text-sm"><span className="text-slate-400">{fmtUtc(a.created_at)}: </span><b>{a.vitals.pulse ?? "-"}/min</b>, <b>{a.vitals.bp_systolic ? `${a.vitals.bp_systolic}/${a.vitals.bp_diastolic ?? "?"}` : "-"}</b></span>)}</div>
        </>
      )}
    </Section>
  );
}

function MoreHistory({ h }) {
  const p = h.current_problem || {};
  const rows = [];
  if (p.complaint) rows.push(["Current problem", `${p.complaint}${p.duration ? ` (${p.duration})` : ""}`]);
  if (p.symptoms?.length) rows.push(["Has", p.symptoms.join(", ")]);
  if (p.denies?.length) rows.push(["Does not have", p.denies.join(", ")]);
  if (p.details) rows.push(["In the patient's words", p.details]);
  if (h.family?.length) rows.push(["Family history", h.family.map((x) => `${x.relation}: ${x.condition}`).join("; ")]);
  else if (h.no_family_history) rows.push(["Family history", "Nothing important"]);
  const hb = h.habits || {};
  [["Appetite", hb.appetite], ["Sleep", hb.sleep], ["Bowel and bladder", hb.bowel_bladder], ["Exercise", hb.exercise]].forEach(([k, v]) => v && rows.push([k, String(v).toLowerCase()]));
  if (h.immunization) rows.push(["Vaccinations", h.immunization]);
  if (h.socioeconomic) rows.push(["Work and home", h.socioeconomic]);
  if (!rows.length) return null;
  return (
    <Section title="More from the history">
      <dl className="space-y-2">{rows.map(([k, v]) => <div key={k} className="flex flex-col gap-0.5 sm:flex-row sm:gap-4"><dt className="w-44 shrink-0 text-sm font-bold text-slate-500">{k}</dt><dd className="text-slate-800">{v}</dd></div>)}</dl>
    </Section>
  );
}

export default function DoctorHistoryView({ patient }) {
  const { data, loading, error, reload, setData } = useFetch(() => getPatientHistoryForm(patient.id), [patient.id]);
  if (loading && !data) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;

  return (
    <div className="space-y-5">
      <Section>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-lg font-extrabold text-slate-900">Medical history</p>
            <p className="text-sm text-slate-500">{data.history.saved_before ? `${data.completeness.percent}% filled in. Last saved ${fmtUtc(data.history.updated_at)} by ${data.history.updated_by_name}.` : "The patient has not filled in the history yet. You can fill it in with the patient."}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link to={`/doctor/patients/${patient.id}/take-history`} className="inline-flex items-center rounded-xl bg-gradient-to-r from-brand-600 to-brand-700 px-4 py-2.5 text-sm font-bold text-white shadow-sm"><ClipboardPen size={15} className="mr-1.5" /> Take history / examine</Link>
            <Button variant="secondary" onClick={() => window.print()}><Printer size={15} className="mr-1 inline" /> Print</Button>
          </div>
        </div>
        <div className="mt-4 h-2.5 overflow-hidden rounded-full bg-slate-200"><div className="h-full rounded-full bg-emerald-500" style={{ width: `${data.completeness.percent}%` }} /></div>
      </Section>

      <EmergencyCard card={data.card} />
      <PastHistory patientId={patient.id} past={data.past} labs={data.diabetes_labs} editable onChange={(past) => { setData((d) => ({ ...d, past })); reload(); }} />
      <PointsToCheck points={data.points_to_check} />
      <UsualAndLabs history={data.history} labs={data.latest_labs} assessments={data.assessments} />
      <MoreHistory h={data.history} />

      <Section title={`Assessments by doctors (${data.assessments.length})`}>
        {data.assessments.length === 0 ? <p className="text-slate-500">No assessment has been written yet.</p> : <div className="space-y-3">{data.assessments.map((a) => <AssessmentCard key={a.id} a={a} />)}</div>}
      </Section>

      <HistoryPrintSheet data={data} />
    </div>
  );
}
