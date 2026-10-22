// The printed medical-history sheet (A4). It sits on the page all the time but only shows when printing: the app's print rule
// hides everything except elements marked "print-area". Built to be read at a glance by a doctor who has never met the patient:
// 1) a short "at a glance" box, 2) numbered sections with clear headings, 3) values as big tiles, 4) the signature with the last section.
import { habitLines } from "./EmergencyCard";
import { useAuth } from "../context/AuthContext";

const day = (iso) => (iso ? new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" }) : "");
const stamp = (iso) => (iso ? new Date(iso.endsWith("Z") ? iso : iso + "Z").toLocaleString(undefined, { day: "numeric", month: "short", year: "numeric", hour: "numeric", minute: "2-digit" }) : "");
const FLAGS = { pulse: (x) => (x < 50 ? "slow" : x > 120 ? "fast" : ""), sys: (x) => (x >= 180 ? "very high" : x < 90 ? "low" : ""), spo2: (x) => (x < 92 ? "low" : ""), temp: (x) => (x >= 100.4 ? "fever" : ""), rr: (x) => (x > 24 ? "fast" : "") };
const EXAM = { consciousness: "Consciousness", general: "General signs", respiratory: "Chest (breathing)", cardiovascular: "Heart", abdomen: "Abdomen", nervous_system: "Nervous system" };
const WHY = { safety: "Safety", vitals: "Today's readings", complaint: "Today's problem", medicine: "Medicines", condition: "Illnesses", habit: "Habits" };

/** "Long-standing high blood pressure (High blood pressure)" says the same thing twice: keep it once. */
const cleanTitle = (t) => {
  const m = /^(.*)\s\((.+)\)$/.exec(t);
  return m && (m[1].toLowerCase().includes(m[2].toLowerCase()) || m[2].toLowerCase().includes(m[1].toLowerCase())) ? m[1] : t;
};

/** A numbered section with a clear heading bar. It never splits across two pages. */
const Section = ({ n, title, children, className = "" }) => (
  <section className={`mb-3 break-inside-avoid ${className}`}>
    <h3 className="mb-1.5 flex items-center gap-2 border-l-4 border-black bg-slate-200 px-2 py-1 text-[12px] font-extrabold uppercase tracking-wide text-black">
      <span className="flex h-4 w-4 items-center justify-center rounded-full bg-black text-[9px] text-white">{n}</span>{title}
    </h3>
    <div className="px-1 text-[12.5px] leading-snug text-black">{children}</div>
  </section>
);

const Tile = ({ label, value, unit, note }) => (
  <div className="min-w-[92px] max-w-[150px] flex-1 border border-slate-400 px-2 py-1 text-center">
    <p className="text-[9.5px] font-bold uppercase tracking-wide text-slate-600">{label}</p>
    <p className="text-[17px] font-extrabold leading-tight">{value}<span className="ml-0.5 text-[10px] font-semibold text-slate-600">{unit}</span></p>
    {note && <p className="text-[10px] font-extrabold uppercase text-black">{note}</p>}
  </div>
);

const Row = ({ label, children }) => (children ? (
  <div className="flex gap-2 border-b border-slate-200 py-1"><span className="w-36 shrink-0 text-[11px] font-bold uppercase tracking-wide text-slate-600">{label}</span><span className="flex-1">{children}</span></div>
) : null);

const Empty = ({ children }) => <p className="italic text-slate-600">{children}</p>;

export default function HistoryPrintSheet({ data }) {
  const { user } = useAuth();
  const { card, history: h, points_to_check: points, latest_labs: labs, assessments } = data;
  const a = assessments?.[0];
  const v = a?.vitals || {};
  const u = card.usual_values || {};
  const p = h.current_problem || {};
  const habits = habitLines(card.habits);
  const meds = card.medicines;

  const usual = [["Pulse", u.pulse, "per min"], ["Blood pressure", u.bp_systolic ? `${u.bp_systolic}/${u.bp_diastolic ?? "-"}` : null, "mmHg"], ["Oxygen (SpO2)", u.spo2, "%"], ["Sugar, fasting", u.sugar_fasting, "mg/dL"],
    ["Sugar, after meal", u.sugar_post_meal, "mg/dL"], ["HbA1c", u.hba1c, "%"], ["Haemoglobin", u.hemoglobin, "g/dL"], ["Creatinine", u.creatinine, "mg/dL"], ...(u.others || []).map((o) => [o.name, o.value, o.unit || ""])].filter(([, x]) => x);
  const vitals = [["Pulse", v.pulse, "per min", FLAGS.pulse], ["BP", v.bp_systolic != null ? `${v.bp_systolic}/${v.bp_diastolic ?? "-"}` : null, "mmHg", () => FLAGS.sys(v.bp_systolic)], ["SpO2", v.spo2, "%", FLAGS.spo2], ["Temperature", v.temperature_f, "F", FLAGS.temp], ["Breathing", v.resp_rate, "per min", FLAGS.rr]]
    .filter(([, x]) => x != null && x !== "");
  const exams = Object.entries(a?.examination || {}).filter(([, t]) => t);

  const urgent = (points || []).filter((x) => ["safety", "vitals"].includes(x.category));
  const others = (points || []).filter((x) => !["safety", "vitals", "missing"].includes(x.category));
  const today = [p.complaint, ...(p.symptoms || [])].filter(Boolean);

  return (
    <div className="print-area hidden bg-white p-0 text-black print:block">
      {/* header */}
      <div className="mb-2 flex items-end justify-between border-b-4 border-black pb-1.5">
        <div><p className="text-[19px] font-extrabold leading-none">HealthWise AI</p><p className="text-[13px] font-bold">Medical history summary</p></div>
        <p className="text-right text-[11px] text-slate-700">Printed {new Date().toLocaleString(undefined, { day: "numeric", month: "short", year: "numeric", hour: "numeric", minute: "2-digit" })}{user?.full_name ? <><br />by {user.full_name}</> : null}</p>
      </div>

      {/* who */}
      <div className="mb-2.5 border-2 border-black px-3 py-2">
        <p className="text-[20px] font-extrabold leading-tight">{card.name}</p>
        <p className="mt-0.5 text-[12.5px]">
          {[card.age != null ? `${card.age} years` : null, card.gender, card.blood_group ? `Blood group ${card.blood_group}` : "Blood group not recorded", `ID ${card.patient_code}`,
            card.height_cm && card.weight_kg ? `${card.height_cm} cm, ${card.weight_kg} kg${card.bmi ? ` (BMI ${card.bmi})` : ""}` : null].filter(Boolean).join("   |   ")}
        </p>
        <p className="text-[12px]"><b>Emergency contact:</b> {card.emergency_contact || "not recorded"}{card.phone ? `   |   Patient's phone: ${card.phone}` : ""}</p>
      </div>

      {/* at a glance */}
      <div className="mb-3 grid break-inside-avoid grid-cols-3 gap-2 text-[12px]">
        <div className="border-2 border-black p-2"><p className="text-[10px] font-extrabold uppercase tracking-wider">Allergies</p>
          <p className="text-[14px] font-extrabold leading-tight">{card.allergies.length ? card.allergies.map((x) => x.name).join(", ") : card.no_known_allergies ? "None known" : "NOT RECORDED"}</p></div>
        <div className="border border-slate-500 p-2"><p className="text-[10px] font-extrabold uppercase tracking-wider">Takes regularly</p>
          <p className="font-bold leading-tight">{meds.length ? `${meds.length} medicine${meds.length > 1 ? "s" : ""}` : card.no_regular_medicines ? "No medicines" : "NOT RECORDED"}</p>
          {meds.length > 0 && <p className="text-[11px] leading-tight text-slate-700">{meds.slice(0, 4).map((m) => m.name.replace(/^(tab|cap|inj)\.?\s*/i, "")).join(", ")}{meds.length > 4 ? ` and ${meds.length - 4} more` : ""}</p>}</div>
        <div className="border border-slate-500 p-2"><p className="text-[10px] font-extrabold uppercase tracking-wider">Illnesses</p>
          <p className="font-bold leading-tight">{card.conditions.length ? card.conditions.map((c) => c.name).join(", ") : card.no_known_conditions ? "None known" : "NOT RECORDED"}</p>
          {today.length > 0 && <p className="mt-0.5 text-[11px] leading-tight"><b>Now:</b> {today.join(", ")}</p>}</div>
      </div>

      <Section n="1" title="Medicines taken regularly">
        {meds.length ? (
          <table className="w-full border-collapse text-[12px]">
            <thead><tr className="border-b-2 border-black text-left text-[10.5px] uppercase tracking-wide"><th className="w-6 py-0.5">#</th><th>Medicine</th><th>Strength</th><th>How often</th><th>Taken for</th><th>Since</th></tr></thead>
            <tbody>{meds.map((m, i) => <tr key={i} className={`border-b border-slate-300 ${i % 2 ? "bg-slate-100" : ""}`}><td className="py-1 pl-1 text-slate-600">{i + 1}</td><td className="py-1 font-bold">{m.name}</td><td>{m.dose || ""}</td><td>{m.frequency || ""}</td><td>{m.reason || ""}</td><td>{m.since || ""}</td></tr>)}</tbody>
          </table>
        ) : <Empty>{card.no_regular_medicines ? "The patient takes no regular medicines." : "Not recorded. Please ask the patient or the family, and check the tablet strips."}</Empty>}
      </Section>

      <Section n="2" title="Illnesses and operations">
        <div className="grid grid-cols-2 gap-x-4">
          <div><p className="mb-0.5 text-[11px] font-bold uppercase text-slate-600">Illnesses</p>
            {card.conditions.length ? <ul className="space-y-0.5">{card.conditions.map((c, i) => <li key={i}><b>{c.name}</b>{c.since ? (/^\d{4}$/.test(c.since) ? ` - since ${c.since}` : /year|month|week|day/i.test(c.since) ? ` - for ${c.since.toLowerCase()}` : ` - since ${c.since}`) : ""}{c.on_treatment ? " (on treatment)" : " (no treatment)"}</li>)}</ul> : <Empty>{card.no_known_conditions ? "None known." : "Not recorded."}</Empty>}</div>
          <div><p className="mb-0.5 text-[11px] font-bold uppercase text-slate-600">Operations and hospital stays</p>
            {card.surgeries.length ? <ul className="space-y-0.5">{card.surgeries.map((s, i) => <li key={i}><b>{s.what}</b>{s.year ? ` (${s.year})` : ""}{s.hospital ? `, ${s.hospital}` : ""}</li>)}</ul> : <Empty>{h.no_past_surgery ? "None." : "Not recorded."}</Empty>}</div>
        </div>
      </Section>

      <Section n="3" title="Usual values and latest blood tests">
        {usual.length > 0 ? (
          <><p className="mb-1 text-[11px] font-bold uppercase text-slate-600">Usual when well{u.noted_on ? ` (${u.noted_on})` : ""}</p>
            <div className="mb-2 flex flex-wrap gap-1.5">{usual.map(([k, x, unit]) => <Tile key={k} label={k} value={x} unit={unit} />)}</div></>
        ) : <Empty>Usual pulse, BP and sugar are not recorded.</Empty>}
        {labs?.length > 0 && (
          <table className="mt-1 w-full border-collapse text-[12px]">
            <thead><tr className="border-b-2 border-black text-left text-[10.5px] uppercase tracking-wide"><th className="py-0.5">Blood test</th><th>Latest result</th><th>Normal range</th><th>Date</th></tr></thead>
            <tbody>{labs.slice(0, 10).map((l, i) => {
              const off = l.status === "ABOVE_RANGE" || l.status === "BELOW_RANGE";
              return <tr key={l.name} className={`border-b border-slate-300 ${i % 2 ? "bg-slate-100" : ""}`}><td className="py-1 pl-1 font-bold">{l.name}</td>
                <td className={off ? "font-extrabold" : ""}>{l.value} {l.unit}{off ? (l.status === "ABOVE_RANGE" ? "  HIGH" : "  LOW") : ""}</td><td>{l.range || "not printed"}</td><td>{day(l.date)}</td></tr>;
            })}</tbody>
          </table>
        )}
      </Section>

      <Section n="4" title="Habits, family and background">
        <Row label="Tobacco / alcohol">{habits.length ? habits.join(", ") : null}</Row>
        <Row label="Sleep, bowel, bladder">{[h.habits?.sleep && `sleep ${h.habits.sleep.toLowerCase()}`, h.habits?.bowel_bladder && `bowel and bladder ${h.habits.bowel_bladder.toLowerCase()}`].filter(Boolean).join(", ") || null}</Row>
        <Row label="Family history">{h.family?.length ? h.family.map((x) => `${x.condition}${x.relation && x.relation !== "Family member" ? ` (${x.relation.toLowerCase()})` : " (in the family)"}`).join("; ") : h.no_family_history ? "Nothing important." : null}</Row>
        <Row label="Work and home">{h.socioeconomic}</Row><Row label="Vaccines">{h.immunization}</Row><Row label="Periods, pregnancies">{h.menstrual_obstetric}</Row>
        {!habits.length && !h.family?.length && !h.no_family_history && !h.socioeconomic && <Empty>Not recorded.</Empty>}
      </Section>

      {(today.length > 0 || p.details || (p.denies || []).length > 0) && (
        <Section n="5" title="The problem now (as told by the patient)">
          <Row label="Main complaint">{p.complaint}{p.duration ? ` (since ${p.duration.toLowerCase()})` : ""}</Row>
          <Row label="Also has">{p.symptoms?.join(", ")}</Row><Row label="Does not have">{p.denies?.join(", ")}</Row><Row label="In the patient's words">{p.details}</Row>
        </Section>
      )}

      {a && (
        <Section n="6" title="Doctor's examination">
          <p className="mb-1 text-[11px] text-slate-600">{stamp(a.created_at)} by {a.doctor_name}</p>
          {vitals.length > 0 && <div className="mb-2 flex flex-wrap gap-1.5">{vitals.map(([k, x, unit, flag]) => <Tile key={k} label={k} value={x} unit={unit} note={flag(Number(x)) ? `${flag(Number(x))}` : ""} />)}</div>}
          <Row label="Complaints">{a.chief_complaint}</Row><Row label="Story">{a.history_of_present_illness}</Row>
          {exams.map(([k, t]) => <Row key={k} label={EXAM[k]}>{t}</Row>)}
          <Row label="Provisional diagnosis (doctor)">{a.provisional_diagnosis ? <b>{a.provisional_diagnosis}</b> : null}</Row>
          <Row label="Tests advised">{a.investigations_advised}</Row>
          <Row label="Plan">{[{ MEDICAL: "Medical", SURGICAL: "Surgical", BOTH: "Medical and surgical" }[a.plan_type], a.plan_details].filter(Boolean).join(" - ")}</Row>
          <Row label="Note">{a.special_note}</Row>
        </Section>
      )}

      {/* the last block stays together with the signature, so the signature never sits alone on a page */}
      <div className="break-inside-avoid">
        {(urgent.length > 0 || others.length > 0) && (
          <Section n={a ? "7" : p.complaint ? "6" : "5"} title="Points to check (made by the computer from this history - not a diagnosis)" className="!mb-2">
            {urgent.length > 0 && <div className="mb-2 border-2 border-black p-1.5"><p className="mb-0.5 text-[11px] font-extrabold uppercase">Important first</p>
              <ul className="space-y-0.5">{urgent.map((x, i) => <li key={i}><b>{cleanTitle(x.title)}.</b> {x.detail}</li>)}</ul></div>}
            {others.length > 0 && (
              <table className="w-full border-collapse text-[11.5px]">
                <tbody>{others.map((x, i) => <tr key={i} className={`border-b border-slate-300 align-top ${i % 2 ? "bg-slate-100" : ""}`}><td className="w-28 py-0.5 pl-1 text-[10px] font-bold uppercase text-slate-600">{WHY[x.category]}</td><td className="w-52 py-0.5 pr-2 font-bold">{cleanTitle(x.title)}</td><td className="py-0.5">{x.detail}</td></tr>)}</tbody>
              </table>
            )}
          </Section>
        )}
        <div className="mt-3 flex items-end justify-between gap-6 text-[10px] text-slate-700">
          <p className="max-w-[62%]">This summary comes from the history entered by the patient and doctors in HealthWise AI. Please confirm the details with the patient or the family. It does not replace a doctor's examination.</p>
          <p className="w-60 border-t border-black pt-1 text-[11px] text-black">Doctor's name and signature</p>
        </div>
      </div>
    </div>
  );
}
