// Patient Clinical Intelligence & History Analyzer: one place where a doctor sees the documented history, the changes in laboratory
// results, the medicines, the emergency visits and the pending follow-ups, with every statement traceable to its source record.
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import useFetch from "../../hooks/useFetch";
import { getClinicalSummary } from "../../services/clinicalApi";
import { Section } from "../HealthCard";
import { ErrorBox, Loading } from "../Feedback";
import SummaryTab from "./SummaryTab";
import TimelineTab from "./TimelineTab";
import TrendsTab from "./TrendsTab";
import EmergencyTab from "./EmergencyTab";
import { FollowUpsTab, MedicationsTab } from "./MedsFollowTabs";
import { SourceChip } from "./Statement";

const TYPE_NAME = { report: "Reports", prescription: "Prescriptions", appointment: "Appointments", note: "Doctor's notes", recommendation: "Recommendations", assessment: "Assessments", emergency: "Emergency visits", history: "Medical history", follow_up: "Follow-ups" };

export default function ClinicalIntel({ patient, reports, onJump }) {
  const navigate = useNavigate();
  const { data, loading, error, reload } = useFetch(() => getClinicalSummary(patient.id), [patient.id]);
  const [tab, setTab] = useState("summary");
  const [openEvent, setOpenEvent] = useState(null);

  // open the original record that a statement or event came from
  const onOpen = (s) => {
    if (s.type === "report") navigate(`/doctor/reports/${s.id}`);
    else if (s.type === "prescription") navigate("/doctor/prescriptions");
    else if (s.type === "appointment") navigate("/doctor/appointments");
    else if (s.type === "note") navigate("/doctor/notes");
    else if (s.type === "recommendation") navigate("/doctor/recommendations");
    else if (s.type === "emergency") { setOpenEvent(s.id); setTab("emergency"); }
    else if (s.type === "follow_up") setTab("followups");
    else onJump?.("medical");                       // history and assessments are on the Medical history tab
  };

  if (loading && !data) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;

  const tabs = [["summary", "Summary"], ["timeline", "Timeline"], ["trends", "Report trends"], ["emergency", `Emergency (${data.counts.emergencies})`], ["meds", "Medications"], ["followups", `Follow-ups${data.overview.pending_follow_ups.count ? ` (${data.overview.pending_follow_ups.count})` : ""}`], ["evidence", "Evidence"]];
  const grouped = data.evidence.reduce((acc, s) => ({ ...acc, [s.type]: [...(acc[s.type] || []), s] }), {});

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-1.5 print:hidden">{tabs.map(([k, label]) => (
        <button key={k} type="button" onClick={() => setTab(k)} className={`rounded-full px-4 py-2 text-sm font-bold ${tab === k ? "bg-brand-700 text-white shadow" : "bg-white text-slate-700 ring-1 ring-slate-200 hover:bg-slate-50"}`}>{label}</button>))}</div>

      {tab === "summary" && <SummaryTab summary={data} patientId={patient.id} onOpen={onOpen} reload={reload} />}
      {tab === "timeline" && <TimelineTab patientId={patient.id} onOpen={onOpen} />}
      {tab === "trends" && <TrendsTab patientId={patient.id} onOpen={onOpen} />}
      {tab === "emergency" && <EmergencyTab patientId={patient.id} reports={reports} labels={data.labels} onOpen={onOpen} openId={openEvent} onClearOpen={() => setOpenEvent(null)} />}
      {tab === "meds" && <MedicationsTab patientId={patient.id} onOpen={onOpen} />}
      {tab === "followups" && <FollowUpsTab patientId={patient.id} onOpen={onOpen} />}
      {tab === "evidence" && (
        <Section title="Evidence panel">
          <p className="-mt-2 mb-3 text-sm text-slate-500">The original records that the summary draws on. Open any of them to read the source.</p>
          {data.evidence.length === 0 ? <p className="text-slate-500">The summary does not yet rest on any record.</p> : Object.entries(grouped).map(([type, list]) => (
            <div key={type} className="mb-3"><p className="mb-1 text-sm font-bold text-slate-700">{TYPE_NAME[type] || type}</p><div className="flex flex-wrap gap-1.5">{list.map((s) => <SourceChip key={`${s.type}${s.id}`} source={s} onOpen={onOpen} />)}</div></div>))}
        </Section>
      )}
    </div>
  );
}
