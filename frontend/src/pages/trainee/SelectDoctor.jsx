// After the history: the department that fits the complaint is suggested with its reason and its doctors. The trainee can always choose differently
// (Department, Specialization, Doctor), mark the referral urgent, optionally book a time, and confirm.
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Lightbulb } from "lucide-react";
import useFetch from "../../hooks/useFetch";
import { createReferral, getDoctorSuggestion, listDepartmentDoctors } from "../../services/traineeApi";
import { getSpecializations } from "../../services/catalogApi";
import { getErrorMessage } from "../../services/api";
import DepartmentSpecializationSelect from "../../components/DepartmentSpecializationSelect";
import { Section } from "../../components/HealthCard";
import { ErrorBox, Loading, PageTitle } from "../../components/Feedback";
import { FormField } from "../../components/FormField";
import { Button, Input, Textarea } from "../../components/ui";
import { appointmentTime } from "../../utils/validators";

function DoctorCard({ d, chosen, onChoose }) {
  return (
    <li>
      <button type="button" aria-pressed={chosen} onClick={() => onChoose(d.id)}
        className={`w-full rounded-2xl border p-3 text-left transition ${chosen ? "border-brand-600 bg-brand-50 ring-2 ring-brand-200" : "border-slate-200 bg-white hover:border-brand-300"}`}>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="font-bold text-slate-900">{d.full_name}</span>
          <span className={`rounded-full px-2.5 py-0.5 text-xs font-bold ${d.availability === "Available" ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-800"}`}>{d.availability}</span>
        </div>
        <p className="text-sm text-slate-600">{d.specialization_name || d.department_name || "General"}</p>
        <p className="text-xs text-slate-500">{d.today_appointments} appointment{d.today_appointments === 1 ? "" : "s"} today · {d.waiting_referrals} referral{d.waiting_referrals === 1 ? "" : "s"} waiting</p>
      </button>
    </li>
  );
}

export default function SelectDoctor() {
  const { historyId } = useParams();
  const navigate = useNavigate();
  const { data: s, loading, error, reload } = useFetch(() => getDoctorSuggestion(Number(historyId)), [historyId]);
  const [override, setOverride] = useState(false);
  const [choice, setChoice] = useState({ department_id: "", specialization_id: "" });
  const [overrideDoctors, setOverrideDoctors] = useState(null);
  const [specNames, setSpecNames] = useState({});
  const [doctorId, setDoctorId] = useState(null);
  const [reason, setReason] = useState("");
  const [reasonEdited, setReasonEdited] = useState(false);
  const [urgent, setUrgent] = useState(false);
  const [bookAt, setBookAt] = useState("");
  const [problem, setProblem] = useState("");
  const [errors, setErrors] = useState({});
  const [busy, setBusy] = useState(false);

  useEffect(() => { if (s && !reason) setReason(`${s.reason}, so ${s.department_name}`.slice(0, 300)); }, [s]);       // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {                                              // doctors of the department the trainee picked by hand
    if (!override || !choice.department_id) { setOverrideDoctors(null); return undefined; }
    let current = true;
    setOverrideDoctors(null);
    listDepartmentDoctors(Number(choice.department_id)).then((rows) => { if (current) setOverrideDoctors(rows); }).catch((e) => { if (current) setProblem(getErrorMessage(e)); });
    getSpecializations(Number(choice.department_id)).then((rows) => { if (current) setSpecNames(Object.fromEntries(rows.map((r) => [String(r.id), r.name]))); }).catch(() => {});
    return () => { current = false; };
  }, [override, choice.department_id]);

  const shown = useMemo(() => {
    const list = override ? (overrideDoctors || []) : (s?.doctors || []);
    const wanted = override && choice.specialization_id ? (specNames[choice.specialization_id] || "").toLowerCase() : "";
    return wanted ? list.filter((d) => (d.specialization_name || "").toLowerCase() === wanted) : list;
  }, [override, overrideDoctors, s, choice.specialization_id, specNames]);

  const confirm = async () => {
    const e = {};
    if (!doctorId) e.doctor = "Please choose a doctor.";
    if (String(reason).trim().length < 2) e.reason = "Please write the reason for the referral.";
    const slot = bookAt ? appointmentTime(bookAt) : "";
    if (slot) e.book_at = slot;
    setErrors(e);
    if (Object.keys(e).length) return;
    setBusy(true);
    setProblem("");
    try {
      await createReferral({ history_id: Number(historyId), doctor_id: doctorId, reason: reason.trim(), urgent, suggested_department_id: s.department_id || null, book_at: bookAt || null });
      navigate("/trainee/referrals");
    } catch (err) { setProblem(getErrorMessage(err)); } finally { setBusy(false); }
  };

  if (loading) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  return (
    <div className="space-y-5 pb-6">
      <PageTitle title="Choose a doctor" subtitle="The history is complete. Pick the doctor who should see this patient." />
      <Section>
        <div className="flex items-start gap-3 rounded-2xl bg-sky-50 p-4 text-sky-950">
          <Lightbulb className="mt-0.5 shrink-0" size={20} />
          <div><p className="font-extrabold">Suggested: {s.department_name}{s.specialization ? ` (${s.specialization})` : ""}</p><p className="text-sm">{s.reason}. This is only a suggestion based on the main complaint; you can choose any department.</p></div>
        </div>
        <label className="mt-4 flex items-center gap-2 text-sm font-semibold text-slate-700">
          <input type="checkbox" checked={override} onChange={(e) => { setOverride(e.target.checked); setDoctorId(null); }} className="h-5 w-5" /> Choose a different department myself
        </label>
        {override && <div className="mt-3 space-y-4"><DepartmentSpecializationSelect departmentRequired departmentId={choice.department_id} specializationId={choice.specialization_id} onChange={(next) => { setChoice(next); setDoctorId(null); }} /></div>}
      </Section>

      <Section title={override ? "Doctors" : `Doctors in ${s.department_name}`}>
        {override && !choice.department_id ? <p className="text-slate-500">Choose a department above.</p>
          : override && overrideDoctors === null ? <Loading />
          : shown.length === 0 ? <p className="text-slate-500">No doctor found here. Try another department{override ? "" : " (tick the box above)"}.</p> : (
            <ul className="grid gap-3 sm:grid-cols-2" aria-label="Doctors">{shown.map((d) => <DoctorCard key={d.id} d={d} chosen={doctorId === d.id} onChoose={(id) => { setDoctorId(id); setErrors((x) => ({ ...x, doctor: "" })); const dept = shown.find((x) => x.id === id)?.department_name; if (!reasonEdited && dept) setReason(`${s.reason}, so ${dept}`.slice(0, 300)); }} />)}</ul>)}
        {errors.doctor && <p role="alert" className="mt-2 text-sm font-medium text-red-600">{errors.doctor}</p>}
      </Section>

      <Section title="Details">
        <div className="space-y-4">
          <FormField label="Reason for the referral *" name="reason" error={errors.reason}><Textarea rows={2} maxLength={300} value={reason} onChange={(e) => { setReason(e.target.value); setReasonEdited(true); }} /></FormField>
          <label className="flex items-center gap-2 font-semibold text-red-700"><input type="checkbox" checked={urgent} onChange={(e) => setUrgent(e.target.checked)} className="h-5 w-5" /> Urgent: show at the top of the doctor's list</label>
          <FormField label="Book an appointment time (optional)" name="book_at" error={errors.book_at} hint="Leave empty to only send the patient and the history to the doctor."><Input type="datetime-local" value={bookAt} onChange={(e) => setBookAt(e.target.value)} /></FormField>
        </div>
      </Section>
      {problem && <ErrorBox message={problem} />}
      <Button type="button" disabled={busy} onClick={confirm}>{busy ? "Sending..." : "Confirm and send to the doctor"}</Button>
    </div>
  );
}
