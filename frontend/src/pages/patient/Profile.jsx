import { Link } from "react-router-dom";
import useFetch from "../../hooks/useFetch";
import { getMyProfile } from "../../services/patientApi";
import { Section } from "../../components/HealthCard";
import { fmtDate } from "../../components/ui";
import { ErrorBox, Loading, PageTitle } from "../../components/Feedback";

export default function PatientProfile() {
  const { data: p, loading, error, reload } = useFetch(getMyProfile);
  if (loading) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  const row = (label, value) => <p className="text-sm"><span className="text-slate-500">{label}:</span> {value || <span className="text-slate-400">Not provided</span>}</p>;
  return (
    <div className="mx-auto max-w-2xl space-y-5">
      <PageTitle title="My Profile" subtitle="To change these details please ask hospital reception" />
      <Section title={p.full_name}>
        <div className="grid gap-2 sm:grid-cols-2">
          {row("Patient ID", p.patient_code)}{row("Email", p.email)}{row("Date of birth", p.date_of_birth && fmtDate(p.date_of_birth))}
          {row("Age", p.age)}{row("Gender", p.gender)}{row("Phone", p.phone)}{row("Address", p.address)}
          {row("Emergency contact", p.emergency_contact)}{row("Blood group", p.blood_group)}{row("Allergies", p.allergies)}
          {row("Current medications", p.current_medications)}{row("Assigned doctor", p.assigned_doctor_name)}
        </div>
      </Section>
      <Link to="/change-password" className="text-sm font-medium text-brand-700">Change my password →</Link>
    </div>
  );
}
