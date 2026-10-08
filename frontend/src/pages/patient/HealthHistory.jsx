import { useState } from "react";
import useFetch from "../../hooks/useFetch";
import { getMyHistory, getMyProfile } from "../../services/patientApi";
import { Section } from "../../components/HealthCard";
import Timeline from "../../components/Timeline";
import { ComparisonView, TrendsView } from "../../components/PatientViews";
import { Tabs, fmtDate, inputClass } from "../../components/ui";
import { ErrorBox, Loading, PageTitle } from "../../components/Feedback";

export default function HealthHistory() {
  const [q, setQ] = useState("");
  const profile = useFetch(getMyProfile, []);
  const { data, loading, error, reload } = useFetch(() => getMyHistory(q), [q]);
  if (loading && !data) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  return (
    <div className="space-y-5">
      <PageTitle title="My Timeline" subtitle="Everything that happened with your health at the hospital, newest first" />
      <Tabs tabs={[
        ["timeline", "Timeline", (
          <Section>
            <input className={`${inputClass} mb-4`} placeholder="Search your history" value={q} onChange={(e) => setQ(e.target.value)} />
            <Timeline events={data.timeline} />
          </Section>)],
        ["compare", "Compare reports", <Section>{profile.data ? <ComparisonView patientId={profile.data.id} /> : <Loading />}</Section>],
        ["trends", "Trends", <Section>{profile.data ? <TrendsView patientId={profile.data.id} /> : <Loading />}</Section>],
        ["background", "Medical background", (
          <Section>{data.history_entries.length === 0 ? <p className="text-slate-500">No background entries added by your doctor.</p> : (
            <ul className="divide-y">{data.history_entries.map((e) => <li key={e.id} className="py-2"><b>{e.entry_type}</b> ({fmtDate(e.entry_date)}) - {e.description}<span className="block text-xs text-slate-400">added by {e.doctor_name}</span></li>)}</ul>)}
          </Section>)],
      ]} />
    </div>
  );
}
