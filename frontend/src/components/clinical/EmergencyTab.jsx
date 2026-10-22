// Emergency history and event review. The doctor records what the hospital's records say; the review shows only that.
// It keeps a documented cause, documented contributing factors, possible associations and an unknown cause apart.
import { useState } from "react";
import { AlertTriangle, Plus } from "lucide-react";
import useFetch from "../../hooks/useFetch";
import { getEmergencyEvent, getEmergencyHistory, recordEmergency } from "../../services/clinicalApi";
import { getErrorMessage } from "../../services/api";
import { Section } from "../HealthCard";
import { Button, Input, Modal, Select, Textarea, fmtDate, inputClass } from "../ui";
import { Chips, Fold } from "../historyKit";
import { ErrorBox, Loading } from "../Feedback";
import { useToast } from "../Toast";
import Statement, { LabelChip, SourceChip } from "./Statement";

const SYMPTOMS = ["Giddiness", "Fainting", "Chest pain", "Breathlessness", "Palpitations", "Sweating", "Fever", "Vomiting", "Headache", "Weakness", "Seizure", "Bleeding"];
const KINDS = [["ARRIVAL", "Arrival"], ["VITALS", "Vitals taken"], ["INVESTIGATION", "Tests ordered"], ["RESULT", "Results"], ["ASSESSMENT", "Assessment"], ["TREATMENT", "Treatment given"], ["REASSESSMENT", "Reassessment"], ["DISPOSITION", "Admission or discharge"], ["OTHER", "Other"]];
const when = (iso) => (iso ? new Date(iso).toLocaleString(undefined, { day: "numeric", month: "short", year: "numeric", hour: "numeric", minute: "2-digit" }) : "Date not recorded");
const num = (v) => (v === "" || v === undefined ? null : Number(v));
const t = (v) => (v && v.trim() ? v.trim() : null);

function EventForm({ patientId, reports, onClose, onSaved }) {
  const toast = useToast();
  const [f, setF] = useState({ symptoms: [], vitals: {}, timeline: [], reports: [], contributing: "" });
  const [busy, setBusy] = useState(false);
  const set = (k, v) => setF((o) => ({ ...o, [k]: v }));
  const area = (label, key, rows = 2, ph = "") => <label className="block text-xs font-bold text-slate-500">{label}<Textarea rows={rows} placeholder={ph} value={f[key] ?? ""} onChange={(e) => set(key, e.target.value)} /></label>;

  const save = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const v = f.vitals;
      const review = await recordEmergency(patientId, {
        event_at: f.event_at || null, arrival_method: t(f.arrival), chief_complaint: t(f.complaint), symptoms: f.symptoms, onset_text: t(f.onset), duration_text: t(f.duration),
        vitals: { pulse: num(v.pulse), bp_systolic: num(v.sys), bp_diastolic: num(v.dia), spo2: num(v.spo2), temperature_f: num(v.temp), resp_rate: num(v.rr) },
        recent_medication_changes: t(f.medchanges), exam_findings: t(f.exam), investigations_ordered: t(f.ordered), investigation_results: t(f.results),
        clinician_assessment: t(f.assessment), documented_cause: t(f.cause), contributing_factors: (f.contributing || "").split(/[;\n]/).map((x) => x.trim()).filter(Boolean),
        treatment_given: t(f.treatment), response_to_treatment: t(f.response), disposition: f.disposition || null, discharge_instructions: t(f.discharge), follow_up_recommendations: t(f.followup),
        treating_clinician: t(f.clinician), source_report_ids: f.reports,
        timeline: f.timeline.filter((x) => x.at && x.text?.trim()).map((x) => ({ occurred_at: x.at, kind: x.kind || "OTHER", text: x.text.trim() })),
      });
      toast("Emergency visit recorded");
      onSaved(review);
    } catch (err) { toast(getErrorMessage(err), "error"); } finally { setBusy(false); }
  };

  return (
    <Modal title="Record an emergency visit" onClose={onClose} wide>
      <form onSubmit={save} className="space-y-3">
        <p className="rounded-xl bg-sky-50 p-3 text-sm text-sky-900">Write only what the hospital's records say. Leave a field empty if it was not recorded: the review will say that it is missing. Write a cause only if the treating clinician documented one.</p>
        <div className="grid gap-3 sm:grid-cols-3">
          <label className="text-xs font-bold text-slate-500">Date and time<input type="datetime-local" className={inputClass} value={f.event_at ?? ""} onChange={(e) => set("event_at", e.target.value)} /></label>
          <label className="text-xs font-bold text-slate-500">How the patient arrived<Select value={f.arrival ?? ""} onChange={(e) => set("arrival", e.target.value)}><option value="">Not recorded</option><option>Ambulance</option><option>Walk-in</option><option>Referred</option><option>Other</option></Select></label>
          <label className="text-xs font-bold text-slate-500">Treating clinician<Input value={f.clinician ?? ""} onChange={(e) => set("clinician", e.target.value)} /></label>
        </div>
        {area("Chief complaint", "complaint", 2, "In the words of the record")}
        <div><p className="mb-1.5 text-xs font-bold text-slate-500">Symptoms recorded at presentation</p><Chips items={SYMPTOMS} selected={f.symptoms} onToggle={(s) => set("symptoms", f.symptoms.includes(s) ? f.symptoms.filter((x) => x !== s) : [...f.symptoms, s])} /></div>
        <div className="grid gap-3 sm:grid-cols-2"><label className="text-xs font-bold text-slate-500">When did it start?<Input value={f.onset ?? ""} placeholder="e.g. 10 pm the night before" onChange={(e) => set("onset", e.target.value)} /></label>
          <label className="text-xs font-bold text-slate-500">How long did it last?<Input value={f.duration ?? ""} placeholder="e.g. 30 seconds" onChange={(e) => set("duration", e.target.value)} /></label></div>
        <Fold title="Vital signs and examination">
          <div className="grid grid-cols-3 gap-3 sm:grid-cols-6">{[["pulse", "Pulse"], ["sys", "BP top"], ["dia", "BP bottom"], ["spo2", "SpO2 %"], ["temp", "Temp F"], ["rr", "Breaths"]].map(([k, l]) => <label key={k} className="text-xs font-bold text-slate-500">{l}<Input type="number" value={f.vitals[k] ?? ""} onChange={(e) => set("vitals", { ...f.vitals, [k]: e.target.value })} /></label>)}</div>
          <div className="mt-3">{area("Examination findings", "exam")}</div>
        </Fold>
        <Fold title="Tests and results">{area("Investigations ordered", "ordered")}<div className="mt-3">{area("Investigation results", "results")}</div></Fold>
        <Fold title="Assessment, cause and treatment" defaultOpen>
          {area("Clinician-documented assessment", "assessment", 2, "As written by the treating clinician")}
          <div className="mt-3">{area("Documented cause (only if the clinician wrote one)", "cause", 2, "Leave empty if no cause was documented")}</div>
          <div className="mt-3">{area("Contributing factors the clinician recorded (separate with ;)", "contributing", 2)}</div>
          <div className="mt-3">{area("Recent medication changes (as recorded)", "medchanges")}</div>
          <div className="mt-3">{area("Treatment given", "treatment")}</div>
          <div className="mt-3">{area("Response to treatment (as recorded)", "response")}</div>
          <div className="mt-3 grid gap-3 sm:grid-cols-2"><label className="text-xs font-bold text-slate-500">Outcome of the visit<Select value={f.disposition ?? ""} onChange={(e) => set("disposition", e.target.value)}><option value="">Not recorded</option><option value="ADMITTED">Admitted</option><option value="DISCHARGED">Discharged</option><option value="TRANSFERRED">Transferred</option><option value="OTHER">Other</option></Select></label></div>
          <div className="mt-3">{area("Discharge instructions", "discharge")}</div><div className="mt-3">{area("Follow-up recommended", "followup")}</div>
        </Fold>
        <Fold title="Timeline: what was recorded, and when" badge={f.timeline.length || ""}>
          <div className="space-y-2">{f.timeline.map((x, i) => (
            <div key={i} className="grid gap-2 rounded-2xl bg-slate-50 p-2.5 sm:grid-cols-[11rem_10rem_1fr_auto]">
              <input type="datetime-local" className={inputClass} value={x.at ?? ""} onChange={(e) => set("timeline", f.timeline.map((y, k) => (k === i ? { ...y, at: e.target.value } : y)))} />
              <Select value={x.kind ?? "OTHER"} onChange={(e) => set("timeline", f.timeline.map((y, k) => (k === i ? { ...y, kind: e.target.value } : y)))}>{KINDS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</Select>
              <Input placeholder="What was recorded" value={x.text ?? ""} onChange={(e) => set("timeline", f.timeline.map((y, k) => (k === i ? { ...y, text: e.target.value } : y)))} />
              <button type="button" className="px-2 text-sm font-bold text-slate-400 hover:text-red-600" onClick={() => set("timeline", f.timeline.filter((_, k) => k !== i))}>Remove</button></div>))}</div>
          <Button type="button" variant="soft" className="mt-2" onClick={() => set("timeline", [...f.timeline, { kind: "OTHER" }])}>+ Add a timestamped step</Button>
          <p className="mt-2 text-xs text-slate-500">Only add steps that were recorded. Gaps stay gaps.</p>
        </Fold>
        {reports.length > 0 && <Fold title="Link reports that belong to this visit" badge={f.reports.length || ""}>
          <ul className="space-y-1">{reports.map((r) => <li key={r.id}><label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={f.reports.includes(r.id)} onChange={() => set("reports", f.reports.includes(r.id) ? f.reports.filter((x) => x !== r.id) : [...f.reports, r.id])} />{r.filename}</label></li>)}</ul>
        </Fold>}
        <div className="flex justify-end gap-3"><Button type="button" variant="secondary" onClick={onClose}>Cancel</Button><Button disabled={busy}>{busy ? "Saving..." : "Save the emergency visit"}</Button></div>
      </form>
    </Modal>
  );
}

function Review({ r, labels, onOpen }) {
  const c = r.cause;
  return (
    <div className="space-y-4">
      <Section title={`Emergency visit: ${when(r.event_at)}`}>
        <p className="text-sm text-slate-600">{r.arrival_method ? `Arrived: ${r.arrival_method}. ` : ""}Recorded by {r.recorded_by}.</p>
        {r.source_reports.length > 0 && <div className="mt-2 flex flex-wrap gap-1.5">{r.source_reports.map((s) => <SourceChip key={s.id} source={s} onOpen={onOpen} />)}</div>}
      </Section>
      <Section title="Timeline of recorded events">
        {r.timeline.length === 0 ? <p className="rounded-xl bg-amber-50 p-3 text-sm font-semibold text-amber-900">{r.timeline_note}</p> : (
          <ol className="space-y-1.5">{r.timeline.map((e) => <li key={e.id} className="flex gap-3 text-sm"><b className="w-44 shrink-0 text-slate-800">{when(e.time)}</b><span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-bold text-slate-600">{KINDS.find(([k]) => k === e.kind)?.[1] || e.kind}</span><span className="text-slate-800">{e.text}</span></li>)}</ol>
        )}
        {r.timeline.length > 0 && !r.timeline_complete && <p className="mt-2 text-sm font-semibold text-amber-800">The timeline is incomplete: some expected steps were not recorded.</p>}
      </Section>
      <Section title="What happened"><ul className="space-y-2">{r.what_happened.map((s) => <Statement key={s.key} st={{ ...s, sources: [s.source], reviews: [] }} labels={labels} onOpen={onOpen} />)}</ul></Section>
      <Section title="Cause and contributing factors">
        <div className="space-y-3">
          <div className={`rounded-2xl border p-3 ${c.documented_cause ? "border-emerald-300 bg-emerald-50" : "border-slate-300 bg-slate-50"}`}><p className="text-xs font-extrabold uppercase text-slate-500">Documented cause</p><p className="font-bold text-slate-900">{c.text}</p></div>
          <div className="rounded-2xl border border-slate-200 p-3"><p className="text-xs font-extrabold uppercase text-slate-500">Documented contributing factors</p>{c.documented_contributing.length ? <ul className="list-disc pl-5 text-slate-800">{c.documented_contributing.map((x) => <li key={x}>{x}</li>)}</ul> : <p className="text-slate-600">None were documented.</p>}</div>
          <div className="rounded-2xl border border-amber-200 bg-amber-50/50 p-3"><p className="text-xs font-extrabold uppercase text-amber-800">Possible associations: for clinician review, not established as a cause</p>
            {c.possible_associations.length ? <ul className="mt-1 space-y-1.5">{c.possible_associations.map((p) => <li key={p.title} className="text-sm"><b>{p.title}.</b> {p.text} <LabelChip label={p.label} labels={labels} /></li>)}</ul> : <p className="text-slate-600">No associations were found by the checks.</p>}
            <p className="mt-2 text-xs text-slate-500">{c.note}</p></div>
        </div>
      </Section>
      {r.missing.length > 0 && <Section title="Missing or incomplete information"><ul className="space-y-1.5">{r.missing.map((m) => <li key={m} className="flex gap-2 text-sm text-amber-900"><AlertTriangle size={15} className="mt-0.5 shrink-0" />{m}</li>)}</ul></Section>}
    </div>
  );
}

export default function EmergencyTab({ patientId, reports, labels, onOpen, openId, onClearOpen }) {
  const { data, loading, error, reload } = useFetch(() => getEmergencyHistory(patientId), [patientId]);
  const [creating, setCreating] = useState(false);
  const [selected, setSelected] = useState(openId || null);
  const detail = useFetch(() => (selected ? getEmergencyEvent(selected) : Promise.resolve(null)), [selected]);
  if (loading && !data) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;

  return (
    <div className="space-y-4">
      <Section title="Emergency history" action={<Button onClick={() => setCreating(true)}><Plus size={15} className="mr-1 inline" />Record an emergency visit</Button>}>
        {data.events.length === 0 ? <p className="text-slate-600">{data.message}</p> : (
          <ul className="space-y-2">{data.events.map((e) => (
            <li key={e.id}><button type="button" onClick={() => { setSelected(e.id); onClearOpen?.(); }} className={`w-full rounded-2xl border p-3 text-left hover:bg-slate-50 ${selected === e.id ? "border-brand-500 bg-brand-50/40" : "border-slate-200 bg-white"}`}>
              <div className="flex flex-wrap items-center justify-between gap-2"><b className="text-slate-900">{e.event_at ? when(e.event_at) : e.date_note}</b>
                <span className="flex flex-wrap gap-1.5 text-xs font-bold">{e.disposition && <span className="rounded-full bg-slate-100 px-2 py-0.5 text-slate-700">{e.disposition.toLowerCase()}</span>}{!e.has_assessment && <span className="rounded-full bg-amber-100 px-2 py-0.5 text-amber-900">No assessment documented</span>}{!e.has_response && <span className="rounded-full bg-amber-100 px-2 py-0.5 text-amber-900">No documented response</span>}</span></div>
              <p className="text-sm text-slate-700">{e.chief_complaint || "The reason for presentation was not recorded."}</p></button></li>))}</ul>
        )}
      </Section>
      {selected && (detail.loading && !detail.data ? <Loading /> : detail.error ? <ErrorBox message={detail.error} /> : detail.data && <Review r={detail.data} labels={labels} onOpen={onOpen} />)}
      {creating && <EventForm patientId={patientId} reports={reports || []} onClose={() => setCreating(false)} onSaved={(review) => { setCreating(false); reload(); setSelected(review.id); }} />}
    </div>
  );
}
