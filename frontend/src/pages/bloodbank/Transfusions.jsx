// Transfusions at the bedside, for nurses and ward staff. One person starts (after checking the patient and the unit), a SECOND person does the bedside check,
// and the transfusion is ended with the volume given and any reaction. A reaction stops the transfusion.
import { useState } from "react";
import { Droplets } from "lucide-react";
import useFetch from "../../hooks/useFetch";
import useSave from "../../hooks/useSave";
import { endTransfusion, getActiveTransfusions, getReadyUnits, startTransfusion, verifyTransfusion } from "../../services/operationsApi";
import { Section } from "../../components/HealthCard";
import { EmptyState, ErrorBox, Hint, Loading, PageTitle } from "../../components/Feedback";
import { Button, Field, Input } from "../../components/ui";

export default function Transfusions() {
  const ready = useFetch(getReadyUnits);
  const active = useFetch(getActiveTransfusions);
  const [checks, setChecks] = useState({});
  const [end, setEnd] = useState({});
  const { problem, busy, run } = useSave();
  const reload = () => { ready.reload(); active.reload(); };
  if ((ready.loading && !ready.data) || (active.loading && !active.data)) return <Loading />;
  if (ready.error || active.error) return <ErrorBox message={ready.error || active.error} onRetry={reload} />;
  const set = (id, key, value) => setEnd({ ...end, [id]: { ...end[id], [key]: value } });
  return (
    <div className="space-y-5">
      <PageTitle title="Transfusions" subtitle="Units the blood bank has verified for patients who are in the hospital now." icon={Droplets} />
      <Hint title="Before you start">Check the patient's name band and the unit label against the request. A second person then repeats the check at the bedside. Stop at once if the patient reacts.</Hint>
      {problem && <ErrorBox message={problem} />}

      {active.data.length > 0 && <h2 className="text-lg font-extrabold">Started</h2>}
      {active.data.map((t) => (
        <Section key={t.id}>
          <p className="font-bold">{t.patient_name} <span className="text-sm font-normal text-slate-500">{t.patient_code} - unit {t.unit_number}, {t.blood_group} {t.component.replace("_", " ").toLowerCase()}</span></p>
          {t.status === "AWAITING_CHECK" && (
            <div className="mt-2">
              {t.started_by_me ? <p className="text-sm text-amber-800">Waiting for a second person to do the bedside check. You started it, so you cannot do the check yourself.</p> : (
                <><p className="text-sm text-amber-800">Waiting for the bedside check.</p>
                  <Button disabled={busy} onClick={async () => { if (await run(() => verifyTransfusion(t.id), "Checked: the transfusion is running")) reload(); }}>I am the second person: bedside check done</Button></>)}
            </div>)}
          {t.status === "IN_PROGRESS" && (
            <div className="mt-2 space-y-2"><p className="text-sm font-semibold text-emerald-800">Transfusion running.</p>
              <div className="grid gap-2 sm:grid-cols-2"><Field label="Volume given (ml)"><Input inputMode="numeric" value={end[t.id]?.v || ""} onChange={(e) => set(t.id, "v", e.target.value)} /></Field>
                <Field label="Reaction (describe, if any)"><Input maxLength={500} value={end[t.id]?.n || ""} onChange={(e) => set(t.id, "n", e.target.value)} /></Field></div>
              <div className="flex gap-2"><Button disabled={busy || !end[t.id]?.v || !!end[t.id]?.n} onClick={async () => { if (await run(() => endTransfusion(t.id, { volume_given_ml: Number(end[t.id].v) }), "Transfusion completed")) reload(); }}>Completed</Button>
                <Button variant="secondary" disabled={busy || !end[t.id]?.n || !end[t.id]?.v} onClick={async () => { if (await run(() => endTransfusion(t.id, { volume_given_ml: Number(end[t.id].v), reaction: true, reaction_note: end[t.id].n }), "Stopped: reaction recorded")) reload(); }}>Stop: patient reacted</Button></div></div>)}
        </Section>))}

      {ready.data.length > 0 && <h2 className="text-lg font-extrabold">Ready to start</h2>}
      {ready.data.length === 0 && active.data.length === 0 ? <EmptyState message="No unit is waiting" hint="Verified units appear here." icon={Droplets} /> : ready.data.map((r) => (
        <Section key={r.issue_id}>
          <p className="font-bold">{r.patient_name} <span className="text-sm font-normal text-slate-500">{r.patient_code} - unit {r.unit_number}, {r.blood_group} {r.component.replace("_", " ").toLowerCase()}{r.patient_group ? `, patient group ${r.patient_group}` : ""}</span></p>
          <div className="mt-2 space-y-2"><label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={!!checks[r.issue_id]?.p} onChange={(e) => setChecks({ ...checks, [r.issue_id]: { ...checks[r.issue_id], p: e.target.checked } })} />I checked the patient's identity</label>
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={!!checks[r.issue_id]?.u} onChange={(e) => setChecks({ ...checks, [r.issue_id]: { ...checks[r.issue_id], u: e.target.checked } })} />I checked the unit label against the request</label>
            <Button disabled={busy || !(checks[r.issue_id]?.p && checks[r.issue_id]?.u)} onClick={async () => { if (await run(() => startTransfusion(r.issue_id, { patient_checked: true, unit_checked: true }), "Started: a second person must do the bedside check")) reload(); }}>Start</Button></div>
        </Section>))}
    </div>
  );
}
