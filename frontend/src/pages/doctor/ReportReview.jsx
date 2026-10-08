// The doctor's review page: the report with the AI analysis on one side, patient context and actions on the other.
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Pill, StickyNote, Stethoscope } from "lucide-react";
import useFetch from "../../hooks/useFetch";
import { getReport } from "../../services/reportApi";
import { getPatientHistory } from "../../services/doctorApi";
import ReportView from "../../components/ReportView";
import { Section } from "../../components/HealthCard";
import Timeline from "../../components/Timeline";
import { DoctorNoteCard, RecommendationCard } from "../../components/Cards";
import { ComparisonView, TrendsView } from "../../components/PatientViews";
import { NoteModal, PrescriptionModal, RecommendationModal, ReviewPanel } from "../../components/DoctorForms";
import { Button, Tabs } from "../../components/ui";
import { ErrorBox, Loading } from "../../components/Feedback";

export default function ReportReview() {
  const { id } = useParams();
  const report = useFetch(() => getReport(id), [id]);
  const patientId = report.data?.patient_id;
  const history = useFetch(() => (patientId ? getPatientHistory(patientId) : Promise.resolve(null)), [patientId]);
  const [modal, setModal] = useState(null);
  const [advice, setAdvice] = useState("");     // a drafted tip the doctor chose to turn into official advice

  if (report.loading && !report.data) return <Loading />;
  if (report.error) return <ErrorBox message={report.error} onRetry={report.reload} />;
  const r = report.data;
  const refresh = () => { report.reload(); history.reload(); };
  const close = () => { setModal(null); setAdvice(""); };
  const h = history.data;

  return (
    <div className="space-y-5">
      <ReportView report={r} onChanged={refresh} onUseAsAdvice={(text) => { setAdvice(text); setModal("rec"); }} />

      <Section title="Doctor review">
        {r.doctor_review_status === "REVIEWED"
          ? <p className="text-slate-600">This report has been reviewed. You can still add notes, recommendations or a prescription below.</p>
          : <ReviewPanel report={r} onReviewed={refresh} />}
        <div className="mt-4 flex flex-wrap gap-2 border-t pt-4">
          <Button variant="secondary" onClick={() => setModal("note")}><StickyNote size={15} className="mr-1 inline" /> Add note</Button>
          <Button variant="secondary" onClick={() => setModal("rec")}><Stethoscope size={15} className="mr-1 inline" /> Add recommendation</Button>
          <Button variant="secondary" onClick={() => setModal("rx")}><Pill size={15} className="mr-1 inline" /> Create prescription</Button>
          <Link to={`/doctor/patients/${r.patient_id}`} className="ml-auto self-center text-sm font-medium text-brand-700">Open full patient record →</Link>
        </div>
      </Section>

      <Tabs tabs={[
        ["compare", "Compare with previous reports", <Section><ComparisonView patientId={r.patient_id} /></Section>],
        ["trends", "Trends", <Section><TrendsView patientId={r.patient_id} /></Section>],
        ["history", "Patient history", <Section>{h ? <Timeline events={h.timeline} /> : <Loading />}</Section>],
        ["notes", "Previous notes", (
          <div className="space-y-3">
            {h && h.notes.length === 0 && h.recommendations.length === 0 && <p className="text-slate-500">No previous notes.</p>}
            {h?.notes.map((n) => <DoctorNoteCard key={`n${n.id}`} note={n} />)}
            {h?.recommendations.map((x) => <RecommendationCard key={`r${x.id}`} rec={x} />)}
          </div>)],
      ]} />

      {modal === "note" && <NoteModal patientId={r.patient_id} reportId={r.id} onClose={close} onSaved={refresh} />}
      {modal === "rec" && <RecommendationModal patientId={r.patient_id} reportId={r.id} initialText={advice} onClose={close} onSaved={refresh} />}
      {modal === "rx" && <PrescriptionModal patientId={r.patient_id} reportId={r.id} onClose={close} onSaved={refresh} />}
    </div>
  );
}
