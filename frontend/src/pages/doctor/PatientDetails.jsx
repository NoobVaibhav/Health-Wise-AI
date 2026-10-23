// Everything a doctor needs about one patient: profile, history timeline, reports, notes, prescriptions, comparison.
import { useState } from "react";
import { useParams } from "react-router-dom";
import { Pill, Plus, StickyNote, Stethoscope } from "lucide-react";
import useFetch from "../../hooks/useFetch";
import { getPatientHistory } from "../../services/doctorApi";
import { Section } from "../../components/HealthCard";
import Timeline from "../../components/Timeline";
import DoctorHistoryView from "../../components/DoctorHistoryView";
import ClinicalIntel from "../../components/clinical/ClinicalIntel";
import { DoctorNoteCard, PrescriptionCard, RecommendationCard, ReportsTable } from "../../components/Cards";
import { ComparisonView, TrendsView } from "../../components/PatientViews";
import { HistoryEntryModal, NoteModal, PrescriptionModal, RecommendationModal } from "../../components/DoctorForms";
import LabTestProgress from "../../components/LabTestProgress";
import { Button, Tabs, fmtDate, inputClass } from "../../components/ui";
import { ErrorBox, Loading, PageTitle } from "../../components/Feedback";

export default function PatientDetails() {
  const { id } = useParams();
  const [q, setQ] = useState("");
  const { data, loading, error, reload } = useFetch(() => getPatientHistory(id, q), [id, q]);
  const [modal, setModal] = useState(null);
  const [mainTab, setMainTab] = useState("medical");
  if (loading && !data) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  const p = data.patient;
  const close = () => setModal(null);

  const profileRow = (label, value) => (value ? <p><span className="text-slate-500">{label}:</span> {value}</p> : null);

  return (
    <div className="space-y-5">
      <PageTitle title={p.full_name} subtitle={`${p.patient_code} - ${p.age ?? "?"} years - ${p.gender || "gender not set"}`} />
      <Section title="Patient information">
        <div className="grid gap-x-8 gap-y-1 text-sm sm:grid-cols-2">
          {profileRow("Phone", p.phone)}{profileRow("Email", p.email)}{profileRow("Address", p.address)}
          {profileRow("Emergency contact", p.emergency_contact)}{profileRow("Blood group", p.blood_group)}
          {profileRow("Allergies", p.allergies)}{profileRow("Current medications", p.current_medications)}
          {profileRow("Medical history (patient-provided)", p.medical_history_text)}
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          <Button onClick={() => setModal("note")}><StickyNote size={15} className="mr-1 inline" /> Add note</Button>
          <Button variant="secondary" onClick={() => setModal("rec")}><Stethoscope size={15} className="mr-1 inline" /> Add recommendation</Button>
          <Button variant="secondary" onClick={() => setModal("rx")}><Pill size={15} className="mr-1 inline" /> Create prescription</Button>
          <Button variant="secondary" onClick={() => setModal("history")}><Plus size={15} className="mr-1 inline" /> Add history entry</Button>
        </div>
      </Section>

      <Tabs value={mainTab} onChange={setMainTab} tabs={[
        ["medical", "Medical history", <DoctorHistoryView patient={p} />],
        ["clinical", "Clinical summary", <ClinicalIntel patient={p} reports={data.reports} onJump={setMainTab} />],
        ["timeline", "Timeline", (
          <Section>
            <input className={`${inputClass} mb-4`} placeholder="Search the history (e.g. report, prescription, HbA1c)" value={q} onChange={(e) => setQ(e.target.value)} />
            <Timeline events={data.timeline} />
          </Section>)],
        ["reports", `Reports (${data.reports.length})`, <div className="space-y-4"><LabTestProgress patientId={p.id} base="/doctor/reports" /><Section><ReportsTable reports={data.reports} base="/doctor/reports" showPatient={false} /></Section></div>],
        ["notes", "Notes and recommendations", (
          <div className="space-y-3">
            {data.notes.length === 0 && data.recommendations.length === 0 && <p className="text-slate-500">No notes or recommendations yet.</p>}
            {data.notes.map((n) => <DoctorNoteCard key={`n${n.id}`} note={n} />)}
            {data.recommendations.map((r) => <RecommendationCard key={`r${r.id}`} rec={r} />)}
          </div>)],
        ["rx", `Prescriptions (${data.prescriptions.length})`, (
          <div className="space-y-3">{data.prescriptions.length === 0 ? <p className="text-slate-500">No prescriptions yet.</p> : data.prescriptions.map((x) => <PrescriptionCard key={x.id} rx={x} />)}</div>)],
        ["compare", "Compare reports", <Section><ComparisonView patientId={p.id} /></Section>],
        ["trends", "Trends", <Section><TrendsView patientId={p.id} /></Section>],
        ["background", "Medical background", (
          <Section>{data.history_entries.length === 0 ? <p className="text-slate-500">No background entries yet.</p> : (
            <ul className="divide-y">{data.history_entries.map((e) => (
              <li key={e.id} className="py-2"><b>{e.entry_type}</b> ({fmtDate(e.entry_date)}) - {e.description}<span className="block text-xs text-slate-400">added by {e.doctor_name}</span></li>))}</ul>)}
          </Section>)],
      ]} />

      {modal === "note" && <NoteModal patientId={p.id} onClose={close} onSaved={reload} />}
      {modal === "rec" && <RecommendationModal patientId={p.id} onClose={close} onSaved={reload} />}
      {modal === "rx" && <PrescriptionModal patientId={p.id} onClose={close} onSaved={reload} />}
      {modal === "history" && <HistoryEntryModal patientId={p.id} onClose={close} onSaved={reload} />}
    </div>
  );
}
