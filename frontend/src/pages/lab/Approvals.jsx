// The pathologist checks the values a technician entered and approves them, or sends them back with a comment.
// A technician can open this page to see what is waiting, but only a pathologist can approve.
import { useState } from "react";
import { BadgeCheck } from "lucide-react";
import useFetch from "../../hooks/useFetch";
import useSave from "../../hooks/useSave";
import { useAuth } from "../../context/AuthContext";
import { approveLabResult, listPendingApproval, returnLabResult } from "../../services/diagnosticsApi";
import { Section } from "../../components/HealthCard";
import { EmptyState, ErrorBox, Loading, PageTitle } from "../../components/Feedback";
import { Button, Field, Input } from "../../components/ui";
import ResultTable from "../../components/ResultTable";

export default function Approvals() {
  const { user } = useAuth();
  const pathologist = user.staff_type === "PATHOLOGIST";
  const { data, loading, error, reload } = useFetch(listPendingApproval);
  const { problem, busy, run } = useSave();
  const [returning, setReturning] = useState(null);
  const [comment, setComment] = useState("");
  if (loading && !data) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  const done = () => { setReturning(null); setComment(""); reload(); };
  return (
    <div className="space-y-5">
      <PageTitle title="Results waiting for approval" subtitle={pathologist ? "Check the values, then approve. The doctor sees a result only after you approve it." : "A pathologist approves these. You can see what is waiting."} icon={BadgeCheck} />
      {problem && <ErrorBox message={problem} />}
      {data.length === 0 ? <EmptyState message="Nothing is waiting" hint="Results the technicians send on appear here." icon={BadgeCheck} /> : data.map((t) => (
        <Section key={t.id}>
          <div className="flex flex-wrap items-start justify-between gap-2">
            <p className="text-lg font-extrabold text-slate-900">{t.test_name} <span className="text-base font-normal text-slate-600">{t.patient_name} ({t.patient_code})</span></p>
            {t.has_critical && <span className="rounded-full bg-red-600 px-3 py-1 text-xs font-bold text-white">CRITICAL VALUE - the doctor has been alerted</span>}
          </div>
          <p className="mb-3 text-sm text-slate-500">Entered by {t.entered_by}. Advised by {t.doctor_name}.</p>
          <ResultTable results={t.results} />
          {pathologist && (
            <div className="mt-3 space-y-2">
              <div className="flex flex-wrap gap-2">
                <Button disabled={busy} onClick={async () => { if (await run(() => approveLabResult(t.id), "Approved")) done(); }}>Approve</Button>
                <Button variant="secondary" onClick={() => setReturning(t.id)}>Send back with a comment</Button>
              </div>
              {returning === t.id && (
                <div className="flex flex-wrap items-end gap-2 rounded-xl bg-slate-50 p-2">
                  <Field label="What should be checked? *"><Input maxLength={500} value={comment} onChange={(e) => setComment(e.target.value)} /></Field>
                  <Button disabled={busy || comment.trim().length < 3} onClick={async () => { if (await run(() => returnLabResult(t.id, comment.trim()), "Sent back")) done(); }}>Send back</Button>
                </div>)}
            </div>)}
        </Section>))}
    </div>
  );
}
