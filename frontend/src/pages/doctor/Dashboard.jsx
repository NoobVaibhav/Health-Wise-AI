import { Link } from "react-router-dom";
import { AlertTriangle, CalendarClock, ClipboardList, FileSearch, Pill, Users } from "lucide-react";
import useFetch from "../../hooks/useFetch";
import { getDoctorDashboard } from "../../services/doctorApi";
import HealthCard, { Section } from "../../components/HealthCard";
import { Hero, HeroButton, QuickActions } from "../../components/Hero";
import { DoctorNoteCard, PrescriptionCard, RecommendationCard, ReportsTable } from "../../components/Cards";
import { AppointmentCard } from "../../components/DataViews";
import { greeting } from "../../components/ui";
import { ErrorBox, Loading } from "../../components/Feedback";
import { useAuth } from "../../context/AuthContext";

export default function DoctorDashboard() {
  const { user } = useAuth();
  const { data: d, loading, error, reload } = useFetch(getDoctorDashboard);
  if (loading) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  const waiting = d.reports_waiting_count;
  return (
    <div className="space-y-6">
      <Hero title={`${greeting()}, ${user.full_name}`}
        subtitle={waiting > 0 ? `${waiting} report${waiting === 1 ? " is" : "s are"} waiting for your review. ${d.todays_appointments.length} appointment${d.todays_appointments.length === 1 ? "" : "s"} today.` : `Nothing is waiting for review. ${d.todays_appointments.length} appointment${d.todays_appointments.length === 1 ? "" : "s"} today.`}>
        {waiting > 0 && <HeroButton to="/doctor/reports" primary>Review reports now</HeroButton>}
        <HeroButton to="/doctor/patients">My patients</HeroButton>
      </Hero>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-6">
        <HealthCard title="Urgent wording" icon={AlertTriangle} tone="rose" value={d.waiting_urgent_count} sub="Reports waiting with urgent wording" />
        <HealthCard title="Values to look at" icon={FileSearch} tone="amber" value={d.waiting_outside_values} sub="Outside range, in waiting reports" />
        <HealthCard title="Today's appointments" icon={CalendarClock} value={d.todays_appointments.length} sub="Booked for today" />
        <HealthCard title="My patients" icon={Users} tone="sky" value={d.my_patients_count} sub="Assigned to you" />
        <HealthCard title="Reports to review" icon={FileSearch} tone="amber" value={waiting} sub="Computer-read, waiting for you" />
        <HealthCard title="Follow-ups coming up" icon={ClipboardList} tone="violet" value={d.pending_follow_ups.length} sub="Tasks still open" />
      </div>

      <AttentionQueue items={d.attention_queue} />

      <QuickActions items={[
        { to: "/doctor/reports", icon: FileSearch, label: "Reports to review", hint: `${waiting} waiting` },
        { to: "/doctor/patients", icon: Users, label: "My patients", hint: "History and comparison" },
        { to: "/doctor/appointments", icon: CalendarClock, label: "Appointments", hint: "Today and upcoming" },
        { to: "/doctor/prescriptions", icon: Pill, label: "Prescriptions", hint: "What you prescribed" },
      ]} />

      <Section title="Reports waiting for your review">
        {waiting === 0 ? <p className="text-slate-500">All caught up. New reports will appear here.</p> : <ReportsTable reports={d.reports_waiting} base="/doctor/reports" />}
      </Section>

      <Section title="Today's appointments">
        {d.todays_appointments.length === 0 ? <p className="text-slate-500">No appointments today.</p> : <div className="space-y-3">{d.todays_appointments.map((a) => <AppointmentCard key={a.id} a={a} />)}</div>}
      </Section>

      <div className="grid gap-4 lg:grid-cols-2">
        <Section title="Follow-ups coming up">
          {d.pending_follow_ups.length === 0 ? <p className="text-slate-500">No follow-ups scheduled.</p> : <div className="space-y-3">{d.pending_follow_ups.map((r) => <RecommendationCard key={r.id} rec={r} showPatient />)}</div>}
        </Section>
        <Section title="Your recent notes">
          {d.recent_notes.length === 0 ? <p className="text-slate-500">No notes yet.</p> : <div className="space-y-3">{d.recent_notes.map((n) => <DoctorNoteCard key={n.id} note={n} showPatient />)}</div>}
        </Section>
      </div>
      <Section title="Recent prescriptions">
        {d.recent_prescriptions.length === 0 ? <p className="text-slate-500">No prescriptions yet.</p> : <div className="space-y-3">{d.recent_prescriptions.map((p) => <PrescriptionCard key={p.id} rx={p} showPatient />)}</div>}
      </Section>
    </div>
  );
}

// The reports that most need a doctor's eyes first, with the important values already pulled out.
function AttentionQueue({ items }) {
  if (!items?.length) return null;
  return (
    <Section title="Look at these first">
      <p className="-mt-2 mb-4 text-sm text-slate-500">Reports waiting for you, with urgent wording or the most values outside the normal range at the top.</p>
      <div className="space-y-3">
        {items.map((i) => (
          <Link key={i.report_id} to={`/doctor/reports/${i.report_id}`} className="tile block rounded-2xl border border-slate-200 bg-white p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className="font-bold text-slate-900">{i.patient_name} <span className="text-sm font-normal text-slate-400">{i.patient_code}</span></p>
                <p className="text-sm text-slate-500">{i.report_type_label} - {i.filename}</p>
              </div>
              <div className="flex flex-wrap gap-2">
                {i.red_flags > 0 && <span className="rounded-full bg-rose-100 px-2.5 py-1 text-xs font-bold text-rose-800">Urgent wording</span>}
                {i.outside_count > 0 && <span className="rounded-full bg-amber-100 px-2.5 py-1 text-xs font-bold text-amber-800">{i.outside_count} to look at</span>}
                {i.red_flags === 0 && i.outside_count === 0 && <span className="rounded-full bg-emerald-100 px-2.5 py-1 text-xs font-bold text-emerald-800">Nothing flagged</span>}
              </div>
            </div>
            {i.highlights.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-2">
                {i.highlights.map((h) => <span key={h} className="rounded-lg bg-slate-100 px-2.5 py-1 text-sm font-semibold text-slate-700">{h}</span>)}
              </div>
            )}
          </Link>
        ))}
      </div>
    </Section>
  );
}
