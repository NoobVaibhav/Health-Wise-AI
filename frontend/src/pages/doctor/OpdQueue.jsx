// The doctor's queue of today: who is waiting, how long, and one button to call the next patient (urgent first).
import { useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ListOrdered } from "lucide-react";
import useFetch from "../../hooks/useFetch";
import useSave from "../../hooks/useSave";
import { callNext, callToken, opdQueue } from "../../services/careApi";
import { Section } from "../../components/HealthCard";
import { EmptyState, ErrorBox, Loading, PageTitle } from "../../components/Feedback";
import { Button } from "../../components/ui";

const STATUS = { WAITING: "Waiting", CALLED: "Called", IN_CONSULTATION: "With you", DONE: "Seen", NO_SHOW: "Did not come", CANCELLED: "Cancelled" };

export default function OpdQueue() {
  const navigate = useNavigate();
  const { data, loading, error, reload } = useFetch(() => opdQueue(), []);
  const { problem, busy, run } = useSave();
  useEffect(() => { const t = setInterval(reload, 20000); return () => clearInterval(t); }, [reload]);
  const open = (t) => navigate(`/doctor/consultation/${t.encounter_id}`);
  const waiting = (data || []).filter((t) => t.status === "WAITING");
  const mine = (data || []).filter((t) => ["CALLED", "IN_CONSULTATION"].includes(t.status));
  const done = (data || []).filter((t) => ["DONE", "NO_SHOW", "CANCELLED"].includes(t.status));
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <PageTitle title="Today's queue" subtitle={`${waiting.length} waiting`} icon={ListOrdered} />
        <Button type="button" disabled={busy || waiting.length === 0} onClick={async () => { const t = await run(() => callNext()); if (t && t !== true) open(t); }}>Call the next patient</Button>
      </div>
      {problem && <ErrorBox message={problem} />}
      {loading && !data ? <Loading /> : error ? <ErrorBox message={error} onRetry={reload} /> : data.length === 0 ? <EmptyState message="Nobody in your queue yet" hint="Patients appear here when reception checks them in." icon={ListOrdered} /> : (
        <>
          {mine.length > 0 && <Section title="With you now"><List rows={mine} onOpen={open} action="Continue" /></Section>}
          <Section title="Waiting"><List rows={waiting} onOpen={async (t) => { if (await run(() => callToken(t.id))) open(t); }} action="Call" empty="Nobody is waiting." /></Section>
          {done.length > 0 && <Section title="Finished"><List rows={done} onOpen={open} action="Open" /></Section>}
        </>)}
    </div>
  );
}

function List({ rows, onOpen, action, empty }) {
  if (rows.length === 0) return <p className="text-slate-500">{empty}</p>;
  return (
    <ul className="divide-y">{rows.map((t) => (
      <li key={t.id} className="flex flex-wrap items-center justify-between gap-2 py-2.5">
        <span><b className="mr-2 inline-block min-w-8 rounded-lg bg-slate-900 px-2 py-0.5 text-center text-white">{t.number}</b><b>{t.patient.full_name}</b>
          <span className="ml-2 text-sm text-slate-500">{t.patient.uhid} · {t.patient.age != null ? `${t.patient.age} y` : ""} {t.patient.gender || ""}</span>
          {t.urgent && <span className="ml-2 rounded-full bg-red-100 px-2 py-0.5 text-xs font-bold text-red-700">Urgent</span>}
          {t.source === "TRAINEE_REFERRAL" && <span className="ml-2 rounded-full bg-violet-100 px-2 py-0.5 text-xs font-bold text-violet-800">From a trainee</span>}</span>
        <span className="flex items-center gap-3">{t.waiting_minutes != null && <span className="text-sm text-slate-500">{t.waiting_minutes} min</span>}<span className="text-sm font-semibold text-slate-600">{STATUS[t.status]}</span>
          <Button type="button" variant="secondary" onClick={() => onOpen(t)} aria-label={`${action} ${t.patient.full_name}`}>{action}</Button></span>
      </li>))}</ul>
  );
}
