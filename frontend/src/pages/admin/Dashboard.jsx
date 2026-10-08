import { Activity, CalendarClock, ClipboardList, FileText, Pill, ScrollText, Stethoscope, UserRound, Users } from "lucide-react";
import useFetch from "../../hooks/useFetch";
import { getAdminDashboard } from "../../services/adminApi";
import HealthCard, { Section } from "../../components/HealthCard";
import { Hero, HeroButton, QuickActions } from "../../components/Hero";
import { ErrorBox, Loading } from "../../components/Feedback";
import { greeting } from "../../components/ui";
import { useAuth } from "../../context/AuthContext";

export default function AdminDashboard() {
  const { user } = useAuth();
  const { data: d, loading, error, reload } = useFetch(getAdminDashboard);
  if (loading) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  const methods = d.report_processing.by_method;
  const methodName = { ocr: "Read from scans and photos (OCR)", pdf_text: "Read from PDF text", text: "Read from text files" };
  return (
    <div className="space-y-6">
      <Hero title={`${greeting()}, ${user.full_name}`} subtitle={`${d.total_patients} patient${d.total_patients === 1 ? "" : "s"}, ${d.total_doctors} doctor${d.total_doctors === 1 ? "" : "s"} and ${d.total_reports} report${d.total_reports === 1 ? "" : "s"} in the system.`}>
        <HeroButton to="/admin/doctors" primary>Add a doctor</HeroButton>
        <HeroButton to="/admin/audit-logs">See activity log</HeroButton>
      </Hero>

      <QuickActions items={[
        { to: "/admin/doctors", icon: Stethoscope, label: "Doctors", hint: "Add or view" },
        { to: "/admin/employees", icon: Users, label: "Employees", hint: "Reception and lab" },
        { to: "/admin/pharmacy-staff", icon: Pill, label: "Pharmacy staff", hint: "Medicine counter" },
        { to: "/admin/audit-logs", icon: ScrollText, label: "Activity log", hint: "Who did what" },
      ]} />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <HealthCard title="Patients" icon={UserRound} value={d.total_patients} />
        <HealthCard title="Doctors" icon={Stethoscope} tone="sky" value={d.total_doctors} />
        <HealthCard title="Employees" icon={Users} tone="slate" value={d.total_employees} />
        <HealthCard title="Pharmacy staff" icon={Pill} tone="amber" value={d.total_pharmacy_staff} />
        <HealthCard title="Reports" icon={FileText} tone="violet" value={d.total_reports} />
        <HealthCard title="Waiting for a doctor" icon={ClipboardList} tone="amber" value={d.reports_pending_review} />
        <HealthCard title="Appointments today" icon={CalendarClock} tone="sky" value={d.appointments_today} />
        <HealthCard title="Active prescriptions" icon={Activity} tone="emerald" value={d.active_prescriptions} sub={`${d.medicines_dispensed} medicine units given out`} />
      </div>

      <Section title="How reports are being handled">
        <div className="grid gap-4 text-sm sm:grid-cols-3">
          <div className="rounded-2xl bg-emerald-50 p-4"><p className="text-slate-500">Checked by doctors</p><p className="text-3xl font-extrabold text-emerald-600">{d.report_processing.reviewed}</p></div>
          <div className="rounded-2xl bg-amber-50 p-4"><p className="text-slate-500">Still waiting</p><p className="text-3xl font-extrabold text-amber-600">{d.report_processing.pending}</p></div>
          <div className="rounded-2xl bg-slate-50 p-4">
            <p className="text-slate-500">How they were read</p>
            {Object.keys(methods).length === 0 ? <p className="text-slate-400">No reports yet</p> : <ul>{Object.entries(methods).map(([m, n]) => <li key={m}>{methodName[m] || m}: <b>{n}</b></li>)}</ul>}
          </div>
        </div>
      </Section>
    </div>
  );
}
