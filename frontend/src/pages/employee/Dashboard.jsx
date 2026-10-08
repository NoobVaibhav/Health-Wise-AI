import { CalendarClock, Clock, FileUp, UserPlus, Users } from "lucide-react";
import useFetch from "../../hooks/useFetch";
import { getEmployeeDashboard } from "../../services/adminApi";
import HealthCard, { Section } from "../../components/HealthCard";
import { Hero, HeroButton, QuickActions } from "../../components/Hero";
import { ReportsTable } from "../../components/Cards";
import { AppointmentCard } from "../../components/DataViews";
import { greeting } from "../../components/ui";
import { ErrorBox, Hint, Loading } from "../../components/Feedback";
import { useAuth } from "../../context/AuthContext";

export default function EmployeeDashboard() {
  const { user } = useAuth();
  const { data: d, loading, error, reload } = useFetch(getEmployeeDashboard);
  if (loading) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  return (
    <div className="space-y-6">
      <Hero title={`${greeting()}, ${user.full_name}`} subtitle={`${d.appointments_today_count} appointment${d.appointments_today_count === 1 ? "" : "s"} today and ${d.awaiting_review_count} report${d.awaiting_review_count === 1 ? "" : "s"} waiting for a doctor.`}>
        <HeroButton to="/employee/upload" primary>Upload a report</HeroButton>
        <HeroButton to="/employee/register">Register a patient</HeroButton>
      </Hero>

      <QuickActions items={[
        { to: "/employee/register", icon: UserPlus, label: "Register patient", hint: "New patient + login" },
        { to: "/employee/upload", icon: FileUp, label: "Upload report", hint: "PDF or photo" },
        { to: "/employee/appointments", icon: CalendarClock, label: "Appointments", hint: "Book or change" },
        { to: "/employee/patients", icon: Users, label: "Find a patient", hint: `${d.patients_count} registered` },
      ]} />

      <Hint title="How uploading works">Choose the patient, then add the report: a lab test, X-ray, ECG, discharge summary or prescription all work. The computer reads it and writes suggestions for the doctor. The doctor checks everything before the patient can see anything. You do not need to type any values.</Hint>

      <div className="grid gap-4 sm:grid-cols-3">
        <HealthCard title="Appointments today" icon={CalendarClock} tone="sky" value={d.appointments_today_count} />
        <HealthCard title="Reports I uploaded" icon={FileUp} tone="slate" value={d.my_recent_uploads.length} sub="Most recent 10" />
        <HealthCard title="Waiting for a doctor" icon={Clock} tone="amber" value={d.awaiting_review_count} />
      </div>

      <Section title="Today's appointments">
        {d.appointments_today.length === 0 ? <p className="text-slate-500">No appointments today.</p> : <div className="space-y-3">{d.appointments_today.map((a) => <AppointmentCard key={a.id} a={a} />)}</div>}
      </Section>
      <Section title="Reports I uploaded recently"><ReportsTable reports={d.my_recent_uploads} base="/employee/reports" /></Section>
      <Section title="Reports waiting for a doctor"><ReportsTable reports={d.awaiting_review} base="/employee/reports" /></Section>
    </div>
  );
}
