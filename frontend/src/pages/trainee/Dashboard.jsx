import { Link } from "react-router-dom";
import { ClipboardList, Send, Users } from "lucide-react";
import useFetch from "../../hooks/useFetch";
import { getTraineeDashboard } from "../../services/traineeApi";
import HealthCard, { Section } from "../../components/HealthCard";
import { Hero, HeroButton } from "../../components/Hero";
import { EmptyState, ErrorBox, Loading } from "../../components/Feedback";
import { Button, fmtUtc, greeting } from "../../components/ui";
import { useAuth } from "../../context/AuthContext";
import { ReferralStatus } from "./MyReferrals";

export default function TraineeDashboard() {
  const { user } = useAuth();
  const { data: d, loading, error, reload } = useFetch(getTraineeDashboard);
  if (loading) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  const t = d.trainee;
  return (
    <div className="space-y-6">
      <Hero title={`${greeting()}, ${user.full_name}`}
        subtitle={`${{ INTERN: "Intern", PG_RESIDENT: "PG Resident", SENIOR_RESIDENT: "Senior Resident" }[t.grade] || "Doctor"}${t.pg_year ? `, year ${t.pg_year}` : ""}${t.year_branch ? `, ${t.year_branch}` : ""}${t.department_name ? ` · ${t.department_name}` : ""}${t.supervisor ? ` · Supervisor: ${t.supervisor}` : ""}`}>
        <HeroButton to="/trainee/take-history" primary>Take a history</HeroButton>
        <HeroButton to="/trainee/referrals">My referrals</HeroButton>
      </Hero>
      <div className="grid gap-4 sm:grid-cols-3">
        <HealthCard title="Waiting for history" icon={Users} tone="amber" value={d.waiting_count} sub="Patients of your department, not yet seen by you today" />
        <HealthCard title="Histories today" icon={ClipboardList} tone="sky" value={d.histories_today} sub="Completed today" />
        <HealthCard title="Referrals sent today" icon={Send} value={d.referrals_today} sub="Patients sent to a doctor" />
      </div>
      <Section title="Waiting for a history">
        {d.waiting_patients.length === 0 ? <EmptyState message="Nobody is waiting" hint="New patients appear here as soon as reception registers them." /> : (
          <ul className="divide-y">{d.waiting_patients.map((p) => (
            <li key={p.id} className="flex items-center justify-between gap-3 py-2.5">
              <span><b>{p.full_name}</b> <span className="text-sm text-slate-500">{p.patient_code} · {p.age ?? "?"} years · {p.gender || ""}</span></span>
              <Link to={`/trainee/take-history/${p.id}`} aria-label={`Take history of ${p.full_name}`}><Button type="button" variant="secondary">Take history</Button></Link>
            </li>))}</ul>)}
      </Section>
      {d.drafts.length > 0 && (
        <Section title="Drafts to continue">
          <ul className="divide-y">{d.drafts.map((h) => (
            <li key={h.id} className="flex items-center justify-between gap-3 py-2.5">
              <span><b>{h.patient_name}</b> <span className="text-sm text-slate-500">{h.data.chief_complaint || "no complaint written yet"} · saved {fmtUtc(h.updated_at)}</span></span>
              <Link to={`/trainee/take-history/${h.patient_id}`}><Button type="button" variant="secondary">Continue</Button></Link>
            </li>))}</ul>
        </Section>)}
      {d.recent_referrals.length > 0 && (
        <Section title="Latest referrals" action={<Link to="/trainee/referrals" className="inline-flex min-h-11 min-w-11 items-center justify-center text-sm font-semibold text-brand-700 underline">See all</Link>}>
          <ul className="divide-y">{d.recent_referrals.map((r) => (
            <li key={r.id} className="flex flex-wrap items-center justify-between gap-2 py-2.5"><span><b>{r.patient_name}</b> to {r.doctor_name}</span><ReferralStatus r={r} /></li>))}</ul>
        </Section>)}
    </div>
  );
}
