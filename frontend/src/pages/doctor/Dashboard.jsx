import { CalendarClock, ClipboardList, FileSearch, Pill, Users } from "lucide-react";
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

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <HealthCard title="Today's appointments" icon={CalendarClock} value={d.todays_appointments.length} />
        <HealthCard title="My patients" icon={Users} tone="sky" value={d.my_patients_count} />
        <HealthCard title="Reports to review" icon={FileSearch} tone="amber" value={waiting} sub="Computer-read, waiting for you" />
        <HealthCard title="Follow-ups coming up" icon={ClipboardList} tone="violet" value={d.pending_follow_ups.length} />
      </div>

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
