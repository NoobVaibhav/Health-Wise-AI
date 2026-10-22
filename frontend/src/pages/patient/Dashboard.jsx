import { Link } from "react-router-dom";
import { CalendarClock, ClipboardList, FileText, History, Pill } from "lucide-react";
import useFetch from "../../hooks/useFetch";
import { getPatientDashboard } from "../../services/patientApi";
import { getMyHistory } from "../../services/historyApi";
import { Section } from "../../components/HealthCard";
import { Hero, HeroButton, QuickActions } from "../../components/Hero";
import { DoctorNoteCard, PrescriptionCard, RecommendationCard } from "../../components/Cards";
import { StatusPill } from "../../components/StatusBadge";
import Timeline from "../../components/Timeline";
import { fmtDate, fmtDateTime, fmtUtcDate, greeting } from "../../components/ui";
import { EmptyState, ErrorBox, Loading } from "../../components/Feedback";

// A gentle reminder to finish the health history (it is what a doctor in a new hospital reads first).
function HistoryNudge() {
  const { data } = useFetch(getMyHistory, []);
  if (!data || data.completeness.percent >= 100) return null;
  const left = data.completeness.parts.filter((p) => !p.done).map((p) => p.name.toLowerCase());
  return (
    <Link to="/patient/health-history" className="tile flex flex-wrap items-center justify-between gap-3 rounded-3xl border-2 border-amber-300 bg-amber-50 p-5">
      <div>
        <p className="text-lg font-extrabold text-amber-900">Your health history is {data.completeness.percent}% complete</p>
        <p className="text-amber-800">Still to add: {left.join(", ")}. A doctor in any hospital can then see your medicines and allergies at once.</p>
      </div>
      <span className="rounded-xl bg-amber-500 px-4 py-2.5 font-bold text-white">Complete it now</span>
    </Link>
  );
}

export default function PatientDashboard() {
  const { data: d, loading, error, reload } = useFetch(getPatientDashboard);
  if (loading) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  const a = d.next_appointment;
  const r = d.latest_report;
  const firstName = d.patient_name.split(" ")[0];

  const status = !r
    ? "You have no reports yet. When the hospital uploads one, it will appear here."
    : r.display_status === "WAITING_FOR_DOCTOR"
      ? "Your latest report is waiting for your doctor to check. The results will show here after that."
      : "Your doctor has checked your latest report. You can read the results now.";

  return (
    <div className="space-y-6">
      <Hero title={`${greeting()}, ${firstName}`} subtitle={status}>
        {r && <HeroButton to={`/patient/reports/${r.id}`} primary>Open my latest report</HeroButton>}
        <HeroButton to="/patient/appointments">Book an appointment</HeroButton>
      </Hero>

      <HistoryNudge />

      <QuickActions items={[
        { to: "/patient/reports", icon: FileText, label: "My Reports", hint: "Lab results explained" },
        { to: "/patient/prescriptions", icon: Pill, label: "My Medicines", hint: `${d.active_prescriptions.length} active` },
        { to: "/patient/history", icon: History, label: "My Timeline", hint: "Everything in order" },
        { to: "/patient/appointments", icon: CalendarClock, label: "Appointments", hint: a ? `Next: ${fmtDateTime(a.scheduled_at)}` : "None booked" },
      ]} />

      {r && (
        <Section title="Latest report">
          <Link to={`/patient/reports/${r.id}`} className="tile flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 p-4">
            <span className="flex items-center gap-3"><span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-brand-50 text-brand-600"><ClipboardList size={22} /></span>
              <span><span className="block font-bold">{r.filename}</span><span className="text-sm text-slate-500">Uploaded {fmtUtcDate(r.uploaded_at)}</span></span></span>
            <StatusPill value={r.display_status} />
          </Link>
        </Section>
      )}

      {a && (
        <Section title="Your next appointment">
          <p className="text-lg"><b>{fmtDateTime(a.scheduled_at)}</b> with {a.doctor_name}{a.reason && ` - ${a.reason}`}</p>
        </Section>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <Section title="Message from your doctor">
          {d.doctor_notes.length === 0 ? <p className="text-slate-500">Your doctor has not written a note yet.</p> : <div className="space-y-3">{d.doctor_notes.map((n) => <DoctorNoteCard key={n.id} note={n} />)}</div>}
        </Section>
        <Section title="Your doctor's advice">
          {d.recommendations.length === 0 ? <p className="text-slate-500">No advice yet.</p> : <div className="space-y-3">{d.recommendations.map((x) => <RecommendationCard key={x.id} rec={x} />)}</div>}
        </Section>
      </div>

      <Section title="Your medicines">
        {d.active_prescriptions.length === 0 ? <p className="text-slate-500">You have no active prescriptions.</p> : <div className="space-y-3">{d.active_prescriptions.map((p) => <PrescriptionCard key={p.id} rx={p} />)}</div>}
      </Section>

      <Section title="What happened recently" action={<Link to="/patient/history" className="text-sm font-bold text-brand-700">See everything →</Link>}>
        {d.recent_history.length === 0 ? <EmptyState message="Nothing yet" hint="Reports, doctor notes and medicines will show up here." /> : <Timeline events={d.recent_history} />}
      </Section>
    </div>
  );
}
