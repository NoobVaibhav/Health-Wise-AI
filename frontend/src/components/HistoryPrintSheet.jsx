// The printed medical-history sheet (A4). It sits on the page all the time but only shows when printing: the app's print rule
// hides everything except elements marked "print-area". Order of the sheet (a doctor reads the long-term background FIRST):
//  1 Patient identification   2 DETAILED MEDICAL HISTORY (diabetes, hypertension, other illnesses, medicines)   3 Previous hospital admissions
//  4 Allergies and medicine reconciliation   5 Family history and habits   6 Current complaint   7 Current vitals and latest laboratory results
//  8 Doctor's examination   9 Assessment and diagnosis   10 Current treatment plan   11 Follow-up plan and doctor's notes
// Sections about the PAST are marked PAST, sections about this visit are marked TODAY, so history is never read as a current finding.
// Long sections flow over several pages: only small blocks (one illness, one admission part, one table row) are kept whole.
import { habitLines } from "./EmergencyCard";
import { useAuth } from "../context/AuthContext";
import { ADHERENCE, ADMISSION_TYPE, ANSWER, CONTROL, SourceBadge, stayText } from "./history/pastKit";
import { fmtDate, fmtDateTime, fmtUtc } from "./ui";

const FLAGS = { pulse: (x) => (x < 50 ? "slow" : x > 120 ? "fast" : ""), sys: (x) => (x >= 180 ? "very high" : x < 90 ? "low" : ""), spo2: (x) => (x < 92 ? "low" : ""), temp: (x) => (x >= 100.4 ? "fever" : ""), rr: (x) => (x > 24 ? "fast" : "") };
const EXAM = { consciousness: "Consciousness", general: "General signs", respiratory: "Chest (breathing)", cardiovascular: "Heart", abdomen: "Abdomen", nervous_system: "Nervous system" };
const WHY = { safety: "Safety", vitals: "Today's readings", complaint: "Today's problem", medicine: "Medicines", condition: "Illnesses", habit: "Habits" };
const VERDICT = { MATCHES: "Same in both", DOSE_DIFFERS: "Dose differs: confirm", IN_HISTORY_ONLY: "Not on a prescription here: confirm", PRESCRIBED_ONLY: "Not in history: confirm and add" };
const LABEL = { retinopathy: "Eye (retinopathy)", neuropathy: "Nerves (neuropathy)", nephropathy: "Kidney (nephropathy)", foot: "Foot / non-healing wounds", cardiovascular: "Heart and vessels", hypoglycemia: "Low sugar episodes / emergency", heart_disease: "Heart disease", stroke: "Stroke", kidney_damage: "Kidney damage" };

/** "Long-standing high blood pressure (High blood pressure)" says the same thing twice: keep it once. */
const cleanTitle = (t) => {
  const m = /^(.*)\s\((.+)\)$/.exec(t);
  return m && (m[1].toLowerCase().includes(m[2].toLowerCase()) || m[2].toLowerCase().includes(m[1].toLowerCase())) ? m[1] : t;
};

const Nr = () => <i className="text-slate-500">Not recorded</i>;
const has = (x) => x !== null && x !== undefined && x !== "" && x !== false;

/** A numbered section with a heading bar. `big` is the prominent style used for the detailed medical history. Sections can run over several pages. */
const Section = ({ n, title, tag, big, children, className = "" }) => (
  <section className={`mb-3.5 ${className}`}>
    <h3 className={`mb-1.5 flex break-after-avoid items-center gap-2 ${big ? "border-2 border-black bg-black px-2.5 py-1.5 text-[14px] text-white" : "border-l-4 border-black bg-slate-200 px-2 py-1 text-[12px] text-black"} font-extrabold uppercase tracking-wide`}>
      <span className={`flex h-[18px] w-[18px] shrink-0 items-center justify-center rounded-full text-[10px] ${big ? "bg-white text-black" : "bg-black text-white"}`}>{n}</span>
      <span className="flex-1">{title}</span>
      {tag && <span className={`text-[9px] font-bold tracking-wider ${big ? "text-slate-200" : "text-slate-600"}`}>{tag}</span>}
    </h3>
    <div className="px-1 text-[12px] leading-snug text-black">{children}</div>
  </section>
);
const Sub = ({ children, first }) => <p className={`mb-1 break-after-avoid border-b border-black text-[11.5px] font-extrabold uppercase tracking-wide ${first ? "" : "mt-2.5"}`}>{children}</p>;

const Tile = ({ label, value, unit, note }) => (
  <div className="min-w-[92px] max-w-[150px] flex-1 border border-slate-400 px-2 py-1 text-center">
    <p className="text-[9.5px] font-bold uppercase tracking-wide text-slate-600">{label}</p>
    <p className="text-[16px] font-extrabold leading-tight">{value}<span className="ml-0.5 text-[10px] font-semibold text-slate-600">{unit}</span></p>
    {note && <p className="text-[10px] font-extrabold uppercase text-black">{note}</p>}
  </div>
);

const Row = ({ label, children, wide }) => (has(children) ? (
  <div className="flex break-inside-avoid gap-2 border-b border-slate-200 py-0.5"><span className={`${wide ? "w-44" : "w-36"} shrink-0 text-[10.5px] font-bold uppercase tracking-wide text-slate-600`}>{label}</span><span className="flex-1 whitespace-pre-line">{children}</span></div>
) : null);
/** like Row, but an empty answer is printed as "Not recorded" (for the questions a doctor must see answered) */
const Ask = ({ label, children, wide }) => <Row label={label} wide={wide}>{has(children) ? children : <Nr />}</Row>;
const Empty = ({ children }) => <p className="italic text-slate-600">{children}</p>;

const Table = ({ head, children, className = "" }) => (
  <table className={`w-full border-collapse text-[11.5px] ${className}`}>
    <thead><tr className="border-b-2 border-black text-left text-[10px] uppercase tracking-wide">{head.map((h) => <th key={h} className="py-0.5 pr-2">{h}</th>)}</tr></thead>
    <tbody>{children}</tbody>
  </table>
);
const Tr = ({ i, children }) => <tr className={`break-inside-avoid border-b border-slate-300 align-top ${i % 2 ? "bg-slate-100" : ""}`}>{children}</tr>;

const medText = (m) => [m.dose, m.frequency].filter(Boolean).join(", ");
const sugar = (c) => [c.control.fasting != null && `fasting ${c.control.fasting} mg/dL`, c.control.postprandial != null && `after meal ${c.control.postprandial} mg/dL`, c.control.random != null && `random ${c.control.random} mg/dL`, c.control.hba1c != null && `HbA1c ${c.control.hba1c}%`].filter(Boolean).join(", ");
const bp = (c) => [c.control.bp_usual && `usual ${c.control.bp_usual}`, c.control.bp_recent && `recent ${c.control.bp_recent}`].filter(Boolean).join(", ");
const withDate = (text, c) => (text ? `${text}${c.control.noted_on ? ` (measured ${c.control.noted_on})` : ""}` : null);
const years = (c) => c.duration_text || (c.years_since_diagnosis != null ? `about ${c.years_since_diagnosis} years (calculated from the year of diagnosis)` : null);
const opDate = (s) => (s.operation_date ? fmtDate(s.operation_date) : s.operation_year ? String(s.operation_year) : null);

function ConditionPrint({ c, title, labs }) {
  const answers = Object.entries(c.complications || {});
  const h = c.hospitalisation || {};
  const thin = c.kind === "OTHER" && !c.diagnosis_type && !c.control_status && !Object.keys(c.control || {}).length && answers.every(([, v]) => v === "UNKNOWN") && !c.complications_other
    && (!h.happened || h.happened === "UNKNOWN") && !c.other_details && !c.notes && !c.medications.length;
  if (thin) {
    const facts = [years(c), c.diagnosis_year ? `since ${c.diagnosis_year}` : null, c.on_treatment == null ? null : c.on_treatment ? "on treatment" : "no treatment"].filter(Boolean);
    return (
      <div className="mb-1.5 break-inside-avoid border border-slate-600 px-2 py-1">
        <p className="flex flex-wrap items-baseline justify-between gap-2"><span><b>{c.name}</b> - {facts.length ? facts.join(", ") : <Nr />}</span><SourceBadge item={c} print /></p>
        <p className="text-[10.5px] italic text-slate-600">Control, complications, hospital stays and medicines: not recorded.</p>
      </div>
    );
  }
  return (
    <div className="mb-2 break-inside-avoid border border-black p-2">
      <p className="mb-1 flex flex-wrap items-baseline justify-between gap-2"><span className="text-[13px] font-extrabold">{title || c.name}</span><SourceBadge item={c} print /></p>
      <Ask label={c.kind === "OTHER" ? "Diagnosis details" : "Diagnosis"}>{c.diagnosis_type}</Ask>
      <Ask label="Duration">{years(c)}</Ask><Ask label="Year of diagnosis">{c.diagnosis_year}</Ask>
      <Ask label="On treatment">{c.on_treatment == null ? null : c.on_treatment ? "Yes" : "No"}</Ask>
      <Ask label={c.kind === "OTHER" ? "Disease control" : "Overall control"}>{c.control_status ? CONTROL[c.control_status] : null}</Ask>
      {c.kind === "DIABETES" && <Ask label="Blood sugar (reported)">{withDate(sugar(c), c)}</Ask>}
      {c.kind === "DIABETES" && labs?.length > 0 && <Row label="Latest lab reports">{labs.map((l) => `${l.name} ${l.value} ${l.unit || ""} (${fmtDate(l.date)})`).join("; ")}</Row>}
      {c.kind === "HYPERTENSION" && <Ask label="Blood pressure (reported)">{withDate(bp(c), c)}</Ask>}
      {(answers.length > 0 || c.complications_other) && (
        <div className="flex gap-2 border-b border-slate-200 py-0.5"><span className="w-36 shrink-0 text-[10.5px] font-bold uppercase tracking-wide text-slate-600">Complications</span>
          <span className="grid flex-1 grid-cols-2 gap-x-3">{answers.map(([k, v]) => <span key={k} className={v === "YES" ? "font-extrabold" : ""}>{LABEL[k] || k}: {ANSWER[v]}</span>)}{c.complications_other && <span className="col-span-2 font-extrabold">Other: {c.complications_other}</span>}</span></div>
      )}
      <Ask label="Hospital stay for this">{h.happened === "YES" ? ["Yes", h.reason && `reason: ${h.reason}`, h.date_text && `when: ${h.date_text}`, h.treatment && `treatment: ${h.treatment}`, h.outcome && `outcome: ${h.outcome}`].filter(Boolean).join("; ") : h.happened === "NO" ? "No" : null}</Ask>
      <Row label="Other details">{c.other_details}</Row><Row label="Clinical notes">{c.notes}</Row>
      <Row label="Medicines for this">{c.medications.length ? c.medications.map((m) => `${m.name}${medText(m) ? ` (${medText(m)}${m.route ? `, ${m.route}` : ""})` : ""}${m.is_current ? "" : " [stopped]"}`).join("; ") : <Nr />}</Row>
    </div>
  );
}

const MedList = ({ rows }) => (rows?.length ? rows.map((m, i) => <span key={i} className="block">{m.name}{[m.dose, m.frequency, m.route && `route ${m.route}`, m.duration].filter(Boolean).length ? ` - ${[m.dose, m.frequency, m.route && `route ${m.route}`, m.duration].filter(Boolean).join(", ")}` : ""}{m.category && m.category !== "OTHER" ? ` (${m.category.replace("_", " ").toLowerCase()})` : ""}</span>) : null);

function SurgeryPrint({ s }) {
  return (
    <div className="mb-1.5 border border-slate-600 p-1.5">
      <p className="mb-0.5 flex flex-wrap items-baseline justify-between gap-2 font-extrabold"><span>Operation: {s.procedure_name}{opDate(s) ? ` (${opDate(s)})` : ""}</span><SourceBadge item={s} print /></p>
      <Ask label="Reason">{s.reason}</Ask><Row label="Site">{s.body_site}</Row><Ask label="Surgeon, hospital">{[s.surgeon, s.hospital].filter(Boolean).join(", ") || null}</Ask><Ask label="Anaesthesia">{s.anesthesia}</Ask>
      <Row label="Surgical findings">{s.findings}</Row>
      <Ask label="Implant or device">{s.implant_used === null ? "Not documented" : s.implant_used ? ["Yes", s.implant_type, s.implant_material, s.implant_serial && `ID ${s.implant_serial}`].filter(Boolean).join(" - ") : "No implant used"}</Ask>
      <Row label="Post-operative X-ray">{s.postop_xray}</Row><Row label="Post-op treatment">{s.postop_treatment}</Row><Row label="Post-op complications">{s.postop_complications}</Row><Row label="Recovery progress">{s.recovery_progress}</Row>
    </div>
  );
}

function AdmissionPrint({ a, i }) {
  const v = a.vitals || {};
  const vit = [v.bp_systolic != null && `BP ${v.bp_systolic}/${v.bp_diastolic ?? "?"} mmHg`, v.pulse != null && `pulse ${v.pulse}/min`, v.resp_rate != null && `breathing ${v.resp_rate}/min`, v.temperature_f != null && `temp ${v.temperature_f} F`, v.spo2 != null && `SpO2 ${v.spo2}%`, v.pain_score != null && `pain ${v.pain_score}/10`].filter(Boolean).join(", ");
  const dateText = a.admitted_at ? fmtDateTime(a.admitted_at) : a.admitted_date_text;
  return (
    <div className="mb-3 border-2 border-black p-2">
      <div className="mb-1 break-after-avoid break-inside-avoid bg-slate-200 px-1.5 py-1">
        <p className="flex flex-wrap items-baseline justify-between gap-2 text-[13px] font-extrabold"><span>Admission {i + 1}: {a.main_complaint || a.reason || a.final_diagnosis || a.provisional_diagnosis || "reason not recorded"}</span><SourceBadge item={a} print /></p>
        <p className="text-[11.5px]">{[dateText || "date not recorded", a.hospital_name, a.admission_type && ADMISSION_TYPE[a.admission_type]].filter(Boolean).join("   |   ")}  -  <b>Stay: {stayText(a)}</b></p>
      </div>
      <div><Sub first>A. Admission details</Sub>
        <Ask label="Admitted">{a.admitted_at ? fmtDateTime(a.admitted_at) : a.admitted_date_text}</Ask><Ask label="Discharged">{a.discharged_at ? fmtDateTime(a.discharged_at) : null}</Ask><Ask label="Length of stay">{stayText(a)}</Ask>
        <Ask label="Main complaint">{a.main_complaint}</Ask><Row label="Other complaints">{a.secondary_complaints}</Row><Ask label="Provisional diagnosis">{a.provisional_diagnosis}</Ask><Ask label="Final diagnosis">{a.final_diagnosis}</Ask>
        <Ask label="Reason for admission">{a.reason}</Ask><Row label="Referred by">{a.referred_by}</Row></div>
      <div><Sub>B. Clinical history during the admission</Sub>
        <Ask label="Symptoms">{a.symptoms}</Ask><Ask label="Story of the illness">{a.history_of_present_illness}</Ask><Row label="Illnesses already present">{a.preexisting_conditions}</Row>
        <Ask label={`Vital signs at admission${v.recorded_at ? ` (${v.recorded_at})` : ""}`} wide>{vit}</Ask>
        <Ask label="Examination findings">{a.exam_findings}</Ask><Ask label="Tests and imaging">{a.investigations}</Ask><Row label="Complications">{a.complications}</Row></div>
      <div><Sub>C. Treatment and medicines during the stay</Sub>
        <Ask label="Treatment given">{a.treatment_given}</Ask><Ask label="Medicines given">{a.medications.length ? <MedList rows={a.medications} /> : null}</Ask>
        <Row label="IV fluids, oxygen">{a.iv_fluids_oxygen}</Row><Row label="Other procedures">{a.procedures_supportive}</Row><Row label="Medication changes">{a.medication_changes}</Row>
        <Ask label="Response to treatment">{a.response_to_treatment}</Ask><Row label="Complications in stay">{a.stay_complications}</Row></div>
      <div><Sub>D. Operations and surgical history</Sub>
        {a.surgeries.length ? a.surgeries.map((s) => <SurgeryPrint key={s.id} s={s} />) : <p className="italic text-slate-600">No operation recorded for this admission.</p>}</div>
      <div><Sub>E. Discharge summary and recovery</Sub>
        <Ask label="Condition at discharge">{a.discharge_condition}</Ask><Row label="Treatment completed">{a.treatment_completed}</Row><Ask label="Discharge medicines">{a.discharge_medications.length ? <MedList rows={a.discharge_medications} /> : null}</Ask>
        <Ask label="Instructions">{a.discharge_instructions}</Ask><Row label="Wound care, rehabilitation">{a.wound_rehab_instructions}</Row><Ask label="Follow-up date">{a.followup_date ? fmtDate(a.followup_date) : null}</Ask>
        <Row label="Specialist review">{a.specialist_review}</Row><Ask label="Recovery status">{a.recovery_status}</Ask><Row label="Remaining symptoms">{a.remaining_symptoms}</Row><Row label="After discharge">{a.readmission_notes}</Row></div>
    </div>
  );
}

export default function HistoryPrintSheet({ data }) {
  const { user } = useAuth();
  const { card, history: h, points_to_check: points, latest_labs: labs, assessments, past, reconciliation: rec, follow_up: fu } = data;
  const a = assessments?.[0];
  const v = a?.vitals || {};
  const u = card.usual_values || {};
  const p = h.current_problem || {};
  const habits = habitLines(card.habits);
  const meds = card.medicines;
  const conditions = [past.diabetes, past.hypertension, ...past.other_conditions].filter(Boolean);

  const usual = [["Pulse", u.pulse, "per min"], ["Blood pressure", u.bp_systolic ? `${u.bp_systolic}/${u.bp_diastolic ?? "-"}` : null, "mmHg"], ["Oxygen (SpO2)", u.spo2, "%"], ["Sugar, fasting", u.sugar_fasting, "mg/dL"],
    ["Sugar, after meal", u.sugar_post_meal, "mg/dL"], ["HbA1c", u.hba1c, "%"], ["Haemoglobin", u.hemoglobin, "g/dL"], ["Creatinine", u.creatinine, "mg/dL"], ...(u.others || []).map((o) => [o.name, o.value, o.unit || ""])].filter(([, x]) => x);
  const vitals = [["Pulse", v.pulse, "per min", FLAGS.pulse], ["BP", v.bp_systolic != null ? `${v.bp_systolic}/${v.bp_diastolic ?? "-"}` : null, "mmHg", () => FLAGS.sys(v.bp_systolic)], ["SpO2", v.spo2, "%", FLAGS.spo2], ["Temperature", v.temperature_f, "F", FLAGS.temp], ["Breathing", v.resp_rate, "per min", FLAGS.rr]]
    .filter(([, x]) => x != null && x !== "");
  const exams = Object.entries(a?.examination || {}).filter(([, t]) => t);
  const urgent = (points || []).filter((x) => ["safety", "vitals"].includes(x.category));
  const others = (points || []).filter((x) => !["safety", "vitals", "missing"].includes(x.category));
  const today = [p.complaint, ...(p.symptoms || [])].filter(Boolean);
  const allSurgeries = past.counts.surgeries;

  return (
    <div className="print-area hidden bg-white p-0 text-black print:block">
      {/* header */}
      <div className="mb-2 flex items-end justify-between border-b-4 border-black pb-1.5">
        <div><p className="text-[19px] font-extrabold leading-none">HealthWise AI</p><p className="text-[13px] font-bold">Medical history summary</p></div>
        <p className="text-right text-[11px] text-slate-700">Printed {new Date().toLocaleString(undefined, { day: "numeric", month: "short", year: "numeric", hour: "numeric", minute: "2-digit" })}{user?.full_name ? <><br />by {user.full_name}</> : null}</p>
      </div>

      {/* 1 who */}
      <Section n="1" title="Patient identification" className="!mb-2">
        <div className="border-2 border-black px-3 py-2">
          <p className="text-[20px] font-extrabold leading-tight">{card.name}</p>
          <p className="mt-0.5 text-[12.5px]">
            {[card.age != null ? `${card.age} years` : null, card.gender, card.blood_group ? `Blood group ${card.blood_group}` : "Blood group not recorded", `ID ${card.patient_code}`,
              card.height_cm && card.weight_kg ? `${card.height_cm} cm, ${card.weight_kg} kg${card.bmi ? ` (BMI ${card.bmi})` : ""}` : null].filter(Boolean).join("   |   ")}
          </p>
          <p className="text-[12px]"><b>Emergency contact:</b> {card.emergency_contact || "not recorded"}{card.phone ? `   |   Patient's phone: ${card.phone}` : ""}</p>
        </div>
      </Section>

      {/* at a glance */}
      <div className="mb-3 grid break-inside-avoid grid-cols-3 gap-2 text-[12px]">
        <div className="border-2 border-black p-2"><p className="text-[10px] font-extrabold uppercase tracking-wider">Allergies</p>
          <p className="text-[14px] font-extrabold leading-tight">{card.allergies.length ? card.allergies.map((x) => x.name).join(", ") : card.no_known_allergies ? "None known" : "NOT RECORDED"}</p></div>
        <div className="border border-slate-500 p-2"><p className="text-[10px] font-extrabold uppercase tracking-wider">Takes regularly</p>
          <p className="font-bold leading-tight">{meds.length ? `${meds.length} medicine${meds.length > 1 ? "s" : ""}` : card.no_regular_medicines ? "No medicines" : "NOT RECORDED"}</p>
          {meds.length > 0 && <p className="text-[11px] leading-tight text-slate-700">{meds.slice(0, 4).map((m) => m.name.replace(/^(tab|cap|inj)\.?\s*/i, "")).join(", ")}{meds.length > 4 ? ` and ${meds.length - 4} more` : ""}</p>}</div>
        <div className="border border-slate-500 p-2"><p className="text-[10px] font-extrabold uppercase tracking-wider">Long-term illnesses</p>
          <p className="font-bold leading-tight">{conditions.length ? conditions.map((c) => c.name).join(", ") : card.no_known_conditions ? "None known" : "NOT RECORDED"}</p>
          {today.length > 0 && <p className="mt-0.5 text-[11px] leading-tight"><b>Today:</b> {today.join(", ")}</p>}</div>
      </div>

      {/* 2 detailed medical history: the most important section */}
      <Section n="2" big tag="PAST HISTORY" title="Detailed medical history">
        <Sub first>A. Diabetes mellitus</Sub>
        {past.diabetes ? <ConditionPrint c={past.diabetes} title="Diabetes mellitus" labs={data.diabetes_labs} /> : <Empty>No diabetes history recorded.</Empty>}
        <Sub>B. Hypertension (high blood pressure)</Sub>
        {past.hypertension ? <ConditionPrint c={past.hypertension} title="Hypertension" /> : <Empty>No hypertension history recorded.</Empty>}
        <Sub>C. Other chronic illnesses</Sub>
        {past.other_conditions.length ? past.other_conditions.map((c) => <ConditionPrint key={c.id} c={c} />) : <Empty>{card.no_known_conditions && !conditions.length ? "None known." : "None recorded."}</Empty>}
        <Sub>D. Medication history (medicines taken regularly)</Sub>
        {past.medications.length ? (
          <Table head={["#", "Medicine", "Dosage, frequency", "Route", "For", "Since", "Prescribed by", "Takes it", "Source"]}>
            {past.medications.map((m, i) => (
              <Tr key={m.id} i={i}><td className="w-6 py-1 pl-1 pr-1 text-slate-600">{i + 1}</td><td className="py-1 pr-2 font-bold">{m.name}{m.is_current ? "" : " [stopped]"}</td><td className="pr-2">{medText(m) || <Nr />}</td><td className="pr-2">{m.route || <Nr />}</td>
                <td className="pr-2">{conditions.find((c) => c.id === m.condition_id)?.name || m.reason || "-"}</td><td className="pr-2">{m.since || <Nr />}</td><td className="pr-2">{m.prescriber || <Nr />}</td>
                <td className="pr-2">{m.adherence ? ADHERENCE[m.adherence] : <Nr />}</td><td><SourceBadge item={m} print /></td></Tr>))}
          </Table>
        ) : <Empty>{card.no_regular_medicines ? "The patient takes no regular medicines." : "Not recorded. Please ask the patient or the family, and check the tablet strips."}</Empty>}
      </Section>

      {/* 3 previous hospital admissions */}
      <Section n="3" tag="PAST HISTORY" title="Previous hospital admission history">
        {past.admissions.length ? past.admissions.map((x, i) => <AdmissionPrint key={x.id} a={x} i={i} />) : <Empty>{h.no_past_surgery && !allSurgeries ? "No previous hospital admission or operation (as told)." : "No previous hospital admission recorded."}</Empty>}
        {past.standalone_surgeries.length > 0 && <><Sub>Operations not linked to an admission</Sub>{past.standalone_surgeries.map((s) => <SurgeryPrint key={s.id} s={s} />)}</>}
      </Section>

      {/* 4 allergies and medicine reconciliation */}
      <Section n="4" tag="PAST AND CURRENT" title="Allergies and medication reconciliation">
        <Sub first>Allergies and reactions</Sub>
        {card.allergies.length ? <ul className="mb-1 space-y-0.5">{card.allergies.map((x, i) => <li key={i}><b>{x.name}</b>{x.kind && x.kind !== "DRUG" ? ` (${x.kind.toLowerCase()})` : ""}{x.reaction ? ` - ${x.reaction}` : ""}</li>)}</ul> : <Empty>{card.no_known_allergies ? "No known allergies." : "Not recorded. Please ask about reactions to medicines, food and injections."}</Empty>}
        {rec?.allergy_flags?.map((f, i) => <p key={i} className="font-bold">For review: {f.text}</p>)}
        <Sub>Medicines in the history compared with open prescriptions of this hospital</Sub>
        {rec?.rows?.length ? (
          <Table head={["Medicine", "In the history", "On an open prescription", "Check"]}>
            {rec.rows.map((r, i) => (
              <Tr key={i} i={i}><td className="py-1 pl-1 pr-2 font-bold">{r.name}</td><td className="pr-2">{r.history ? [medText(r.history), r.history.route].filter(Boolean).join(", ") || "yes" : <Nr />}</td>
                <td className="pr-2">{r.prescribed ? `${medText(r.prescribed)} (${r.prescribed.code}, ${fmtDate(r.prescribed.prescribed_on)})` : "-"}</td><td className={r.verdict === "MATCHES" ? "" : "font-bold"}>{VERDICT[r.verdict]}</td></Tr>))}
          </Table>
        ) : <Empty>No medicine in the history and no open prescription to compare.</Empty>}
        {rec?.duplicates?.map((d, i) => <p key={i} className="mt-0.5">For review: {d.text}</p>)}
      </Section>

      {/* 5 family and habits */}
      <Section n="5" tag="PAST HISTORY" title="Family history and lifestyle habits">
        <Ask label="Tobacco / alcohol / diet">{habits.length ? habits.join(", ") : null}</Ask>
        <Row label="Sleep, bowel, bladder">{[h.habits?.sleep && `sleep ${h.habits.sleep.toLowerCase()}`, h.habits?.bowel_bladder && `bowel and bladder ${h.habits.bowel_bladder.toLowerCase()}`, h.habits?.exercise && `exercise: ${h.habits.exercise}`].filter(Boolean).join(", ") || null}</Row>
        <Ask label="Family history">{h.family?.length ? h.family.map((x) => `${x.condition}${x.relation && x.relation !== "Family member" ? ` (${x.relation.toLowerCase()})` : " (in the family)"}`).join("; ") : h.no_family_history ? "Nothing important." : null}</Ask>
        <Row label="Work and home">{h.socioeconomic}</Row><Row label="Vaccines">{h.immunization}</Row><Row label="Periods, pregnancies">{h.menstrual_obstetric}</Row>
      </Section>

      {/* 6 current complaint */}
      <Section n="6" tag="TODAY" title="Current complaint and history of the present illness">
        {today.length > 0 || p.details || (p.denies || []).length > 0 || a?.chief_complaint ? (<>
          <Row label="Main complaint">{p.complaint}{p.duration ? ` (since ${p.duration.toLowerCase()})` : ""}</Row>
          <Row label="Also has">{p.symptoms?.join(", ")}</Row><Row label="Does not have">{p.denies?.join(", ")}</Row><Row label="In the patient's words">{p.details}</Row>
          {a && <><Row label="Doctor's record">{a.chief_complaint}</Row><Row label="History of the illness">{a.history_of_present_illness}</Row></>}
        </>) : <Empty>No current complaint recorded.</Empty>}
      </Section>

      {/* 7 vitals and labs */}
      <Section n="7" tag="TODAY AND LATEST RESULTS" title="Current vital signs and latest laboratory results">
        {vitals.length > 0 ? (<><p className="mb-1 text-[11px] font-bold uppercase text-slate-600">Vital signs at this visit{a ? ` (${fmtUtc(a.created_at)})` : ""}</p>
          <div className="mb-2 flex flex-wrap gap-1.5">{vitals.map(([k, x, unit, flag]) => <Tile key={k} label={k} value={x} unit={unit} note={flag(Number(x)) ? `${flag(Number(x))}` : ""} />)}</div></>) : <p className="mb-1 italic text-slate-600">No vital signs recorded at this visit.</p>}
        {usual.length > 0 && (<><p className="mb-1 text-[11px] font-bold uppercase text-slate-600">Usual values when well (from the history{u.noted_on ? `, ${u.noted_on}` : ""}), not today's readings</p>
          <div className="mb-2 flex flex-wrap gap-1.5">{usual.map(([k, x, unit]) => <Tile key={k} label={k} value={x} unit={unit} />)}</div></>)}
        {labs?.length > 0 ? (
          <Table head={["Blood test", "Latest result", "Normal range", "Report date"]}>
            {labs.slice(0, 12).map((l, i) => {
              const off = l.status === "ABOVE_RANGE" || l.status === "BELOW_RANGE";
              return <Tr key={l.name} i={i}><td className="py-1 pl-1 font-bold">{l.name}</td><td className={off ? "font-extrabold" : ""}>{l.value} {l.unit}{off ? (l.status === "ABOVE_RANGE" ? "  HIGH" : "  LOW") : ""}</td><td>{l.range || "not printed"}</td><td>{fmtDate(l.date)}</td></Tr>;
            })}
          </Table>
        ) : <Empty>No laboratory result from reports yet.</Empty>}
      </Section>

      {/* 8 examination */}
      <Section n="8" tag="TODAY" title="Doctor's clinical examination">
        {a && exams.length > 0 ? (<><p className="mb-1 text-[11px] text-slate-600">{fmtUtc(a.created_at)} by {a.doctor_name}</p>{exams.map(([k, t]) => <Row key={k} label={EXAM[k]}>{t}</Row>)}</>) : <Empty>No examination recorded at this visit.</Empty>}
      </Section>

      {/* 9 assessment and diagnosis (the computer's points to check stay clearly separate) */}
      <Section n="9" tag="TODAY" title="Clinical assessment and diagnosis">
        {a?.provisional_diagnosis ? <Row label="Provisional diagnosis (doctor)"><b>{a.provisional_diagnosis}</b></Row> : <Empty>No diagnosis written yet. The computer never suggests one.</Empty>}
        {(urgent.length > 0 || others.length > 0) && (
          <div className="mt-2">
            <Sub first>Points to check (made by the computer from this history - not a diagnosis)</Sub>
            {urgent.length > 0 && <div className="mb-2 break-inside-avoid border-2 border-black p-1.5"><p className="mb-0.5 text-[11px] font-extrabold uppercase">Important first</p>
              <ul className="space-y-0.5">{urgent.map((x, i) => <li key={i}><b>{cleanTitle(x.title)}.</b> {x.detail}</li>)}</ul></div>}
            {others.length > 0 && <Table head={["", "Topic", "Why it is listed"]}>{others.map((x, i) => <Tr key={i} i={i}><td className="w-24 py-0.5 pl-1 text-[10px] font-bold uppercase text-slate-600">{WHY[x.category]}</td><td className="w-48 py-0.5 pr-2 font-bold">{cleanTitle(x.title)}</td><td className="py-0.5">{x.detail}</td></Tr>)}</Table>}
          </div>
        )}
      </Section>

      {/* 10 treatment */}
      <Section n="10" tag="TODAY" title="Current treatment and medication plan">
        {a ? <><Row label="Plan">{[{ MEDICAL: "Medical", SURGICAL: "Surgical", BOTH: "Medical and surgical" }[a.plan_type], a.plan_details].filter(Boolean).join(" - ")}</Row><Row label="Tests advised">{a.investigations_advised}</Row></> : null}
        {fu?.prescriptions?.length ? fu.prescriptions.map((x) => (
          <div key={x.code} className="mt-1 break-inside-avoid"><p className="font-bold">{x.code} - {fmtDate(x.date)} - {x.doctor}{x.indication ? ` (${x.indication})` : ""}</p>
            <Table head={["Medicine", "Dosage", "How often", "For how long", "Instructions"]}>{x.items.map((m, i) => <Tr key={i} i={i}><td className="py-0.5 pl-1 pr-2 font-bold">{m.name}</td><td className="pr-2">{m.dose || <Nr />}</td><td className="pr-2">{m.frequency || <Nr />}</td><td className="pr-2">{m.duration || <Nr />}</td><td>{m.instructions || ""}</td></Tr>)}</Table>
            {x.tests.length > 0 && <p className="mt-0.5"><b>Tests advised:</b> {x.tests.join(", ")}</p>}</div>)) : (!a || (!a.plan_details && !a.plan_type && !a.investigations_advised)) && <Empty>No open prescription or treatment plan recorded.</Empty>}
      </Section>

      {/* 11 follow-up; the last block stays together with the signature, so the signature never sits alone on a page */}
      <div className="break-inside-avoid">
        <Section n="11" tag="NEXT STEPS" title="Follow-up plan and doctor's notes" className="!mb-2">
          {a?.special_note && <Row label="Doctor's note (this visit)">{a.special_note}</Row>}
          {fu?.recommendations?.length > 0 && fu.recommendations.slice(0, 3).map((r, i) => <Row key={i} label={`Advice ${fmtDate(r.created_at)}`}>{r.title}: {r.text}{r.follow_up_date ? ` (follow-up: ${fmtDate(r.follow_up_date)})` : ""}</Row>)}
          {fu?.appointments?.length > 0 && <Row label="Next appointment">{fu.appointments.map((x) => `${fmtDateTime(x.scheduled_at)} with ${x.doctor}`).join("; ")}</Row>}
          {fu?.notes?.length > 0 && fu.notes.slice(0, 2).map((n, i) => <Row key={i} label={`Note ${fmtDate(n.created_at)}`}>{n.text} ({n.doctor})</Row>)}
          {!a?.special_note && !fu?.recommendations?.length && !fu?.appointments?.length && !fu?.notes?.length && <Empty>No follow-up plan or doctor's note recorded.</Empty>}
        </Section>
        <div className="mt-3 flex items-end justify-between gap-6 text-[10px] text-slate-700">
          <p className="max-w-[62%]">This summary comes from the history entered by the patient and doctors in HealthWise AI. Items marked "Told by patient" have not been checked by a doctor. Please confirm the details with the patient or the family. It does not replace a doctor's examination.</p>
          <p className="w-60 border-t border-black pt-1 text-[11px] text-black">Doctor's name and signature</p>
        </div>
      </div>
    </div>
  );
}
