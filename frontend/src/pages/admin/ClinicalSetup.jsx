// Administrator screens for the clinical setup: wards and beds, consultation templates per department, and the alert thresholds. No code change is needed to change any of them.
import { useState } from "react";
import useFetch from "../../hooks/useFetch";
import useSave from "../../hooks/useSave";
import { addBed, addWard, listRules, listTemplates, listWards, saveRule, saveTemplate } from "../../services/careApi";
import { getDepartments } from "../../services/catalogApi";
import { Section } from "../../components/HealthCard";
import { ErrorBox, Loading } from "../../components/Feedback";
import { Button, Field, Input, Select } from "../../components/ui";

const WARD_TYPES = ["GENERAL", "PRIVATE", "SEMI_PRIVATE", "ICU", "NICU", "PICU", "EMERGENCY", "ISOLATION", "RECOVERY"];

export function WardsTab() {
  const { data, loading, error, reload } = useFetch(listWards);
  const { problem, busy, run } = useSave();
  const [ward, setWard] = useState({ name: "", ward_type: "GENERAL" });
  const [codes, setCodes] = useState({});
  return (
    <Section title="Wards and beds">
      {loading && !data ? <Loading /> : error ? <ErrorBox message={error} onRetry={reload} /> : (
        <ul className="mb-4 divide-y">{data.length === 0 && <li className="py-2 text-slate-500">No wards yet.</li>}{data.map((w) => (
          <li key={w.id} className="space-y-2 py-3">
            <p><b>{w.name}</b> <span className="text-sm text-slate-500">{w.ward_type.replace("_", " ").toLowerCase()} · {w.beds.length} beds ({w.counts.AVAILABLE} free, {w.counts.OCCUPIED} occupied)</span></p>
            <p className="text-sm text-slate-600">{w.beds.map((b) => b.code).join(", ") || "No beds yet"}</p>
            <div className="flex gap-2"><Input aria-label={`New bed code for ${w.name}`} placeholder="New bed code, e.g. A4" maxLength={20} value={codes[w.id] || ""} onChange={(e) => setCodes({ ...codes, [w.id]: e.target.value })} />
              <Button type="button" variant="secondary" disabled={busy || !(codes[w.id] || "").trim()} onClick={async () => { if (await run(() => addBed(w.id, codes[w.id].trim()), "Bed added")) { setCodes({ ...codes, [w.id]: "" }); reload(); } }}>Add bed</Button></div>
          </li>))}</ul>)}
      <div className="grid gap-3 sm:grid-cols-[1fr_12rem_auto] sm:items-end"><Field label="New ward"><Input maxLength={100} value={ward.name} onChange={(e) => setWard({ ...ward, name: e.target.value })} /></Field>
        <Field label="Type"><Select value={ward.ward_type} onChange={(e) => setWard({ ...ward, ward_type: e.target.value })}>{WARD_TYPES.map((t) => <option key={t} value={t}>{t.replace("_", " ")}</option>)}</Select></Field>
        <Button type="button" disabled={busy || ward.name.trim().length < 2} onClick={async () => { if (await run(() => addWard(ward), "Ward added")) { setWard({ ...ward, name: "" }); reload(); } }}>Add ward</Button></div>
      {problem && <div className="mt-3"><ErrorBox message={problem} /></div>}
    </Section>
  );
}

const BLANK = { id: null, name: "", department_id: "", fields: [], is_active: true };

export function TemplatesTab() {
  const { data, loading, error, reload } = useFetch(listTemplates);
  const { data: departments } = useFetch(getDepartments, []);
  const { problem, busy, run } = useSave();
  const [t, setT] = useState(null);
  const setField = (i, patch) => setT({ ...t, fields: t.fields.map((f, j) => (j === i ? { ...f, ...patch } : f)) });
  const save = async () => {
    const body = { name: t.name, department_id: t.department_id ? Number(t.department_id) : null, is_active: t.is_active,
      fields: t.fields.map((f) => ({ key: f.key, label: f.label, kind: f.kind, options: f.kind === "choice" ? f.optionsText.split(",").map((o) => o.trim()).filter(Boolean) : [] })) };
    if (await run(() => saveTemplate(t.id, body), "Template saved")) { setT(null); reload(); }
  };
  const edit = (x) => setT({ id: x.id, name: x.name, department_id: x.department_id || "", is_active: x.is_active, fields: x.fields.map((f) => ({ ...f, optionsText: (f.options || []).join(", ") })) });
  return (
    <Section title="Consultation templates" action={<Button type="button" variant="secondary" onClick={() => setT({ ...BLANK })}>New template</Button>}>
      <p className="mb-3 text-sm text-slate-600">Extra fields on the doctor's consultation form. A department with its own template uses it; every other department uses the default.</p>
      {loading && !data ? <Loading /> : error ? <ErrorBox message={error} onRetry={reload} /> : (
        <ul className="divide-y">{data.map((x) => <li key={x.id} className="flex items-center justify-between gap-2 py-2"><span className={x.is_active ? "" : "text-slate-400 line-through"}><b>{x.name}</b> <span className="text-sm text-slate-500">{(departments || []).find((d) => d.id === x.department_id)?.name || "all departments"} · {x.fields.length} fields</span></span><Button type="button" variant="secondary" onClick={() => edit(x)}>Edit</Button></li>)}</ul>)}
      {t && (
        <div className="mt-4 space-y-3 rounded-2xl bg-slate-50 p-4">
          <div className="grid gap-3 sm:grid-cols-2"><Field label="Name"><Input maxLength={120} value={t.name} onChange={(e) => setT({ ...t, name: e.target.value })} /></Field>
            <Field label="Department"><Select value={t.department_id} onChange={(e) => setT({ ...t, department_id: e.target.value })}><option value="">All departments (default)</option>{(departments || []).map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}</Select></Field></div>
          {t.fields.map((f, i) => (
            <div key={i} className="grid gap-2 rounded-xl bg-white p-2 sm:grid-cols-[9rem_1fr_9rem_1fr_auto] sm:items-end">
              <Field label="Key"><Input maxLength={40} value={f.key} onChange={(e) => setField(i, { key: e.target.value })} /></Field><Field label="Label"><Input maxLength={100} value={f.label} onChange={(e) => setField(i, { label: e.target.value })} /></Field>
              <Field label="Kind"><Select value={f.kind} onChange={(e) => setField(i, { kind: e.target.value })}><option value="text">Short text</option><option value="longtext">Long text</option><option value="number">Number</option><option value="choice">Choice</option></Select></Field>
              <Field label="Choices (comma)"><Input disabled={f.kind !== "choice"} value={f.optionsText || ""} onChange={(e) => setField(i, { optionsText: e.target.value })} /></Field>
              <Button type="button" variant="secondary" onClick={() => setT({ ...t, fields: t.fields.filter((_, j) => j !== i) })}>Remove</Button></div>))}
          <div className="flex flex-wrap gap-2"><Button type="button" variant="secondary" onClick={() => setT({ ...t, fields: [...t.fields, { key: "", label: "", kind: "text", options: [], optionsText: "" }] })}>Add a field</Button>
            <label className="flex items-center gap-2 text-sm font-semibold"><input type="checkbox" className="h-5 w-5" checked={t.is_active} onChange={(e) => setT({ ...t, is_active: e.target.checked })} /> In use</label>
            <Button type="button" disabled={busy || t.name.trim().length < 2} onClick={save}>Save template</Button><Button type="button" variant="secondary" onClick={() => setT(null)}>Cancel</Button></div>
          {problem && <ErrorBox message={problem} />}
        </div>)}
    </Section>
  );
}

const PARAMS = ["pulse", "bp_systolic", "bp_diastolic", "temperature_f", "resp_rate", "spo2", "gcs"];

export function ThresholdsTab() {
  const { data, loading, error, reload } = useFetch(listRules);
  const { problem, busy, run } = useSave();
  const [edit, setEdit] = useState({});
  const [fresh, setFresh] = useState({ parameter: "pulse", comparison: "GT", threshold: "", level: "WARNING", message: "" });
  if (loading && !data) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  return (
    <Section title="Alert thresholds">
      <p className="mb-3 text-sm text-slate-600">Plain numbers the hospital decides, checked every time vital signs are saved. No AI is involved. Please have them reviewed by your clinical team.</p>
      <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr className="border-b text-xs uppercase text-slate-500"><th className="py-1">Measurement</th><th>When</th><th>Level</th><th>Message</th><th /></tr></thead>
        <tbody>{data.map((r) => (
          <tr key={r.id} className={`border-b ${r.is_active ? "" : "text-slate-400 line-through"}`}><td className="py-1.5">{r.parameter}</td><td>{r.comparison === "GT" ? "above" : "below"} <input aria-label={`Threshold of ${r.message}`} className="w-20 rounded-lg border border-slate-300 px-2 py-1" type="number" step="any" value={edit[r.id] ?? r.threshold} onChange={(e) => setEdit({ ...edit, [r.id]: e.target.value })} /></td>
            <td>{r.level}</td><td>{r.message}</td><td className="whitespace-nowrap text-right">
              {edit[r.id] !== undefined && Number(edit[r.id]) !== r.threshold && <Button type="button" variant="secondary" disabled={busy} onClick={async () => { if (await run(() => saveRule(r.id, { ...r, threshold: Number(edit[r.id]) }), "Threshold saved")) { setEdit({ ...edit, [r.id]: undefined }); reload(); } }}>Save</Button>}
              <Button type="button" variant="secondary" disabled={busy} onClick={async () => { await run(() => saveRule(r.id, { ...r, is_active: !r.is_active })); reload(); }}>{r.is_active ? "Switch off" : "Switch on"}</Button></td></tr>))}</tbody></table></div>
      <div className="mt-4 grid gap-2 sm:grid-cols-[9rem_6rem_7rem_8rem_1fr_auto] sm:items-end">
        <Field label="Measurement"><Select value={fresh.parameter} onChange={(e) => setFresh({ ...fresh, parameter: e.target.value })}>{PARAMS.map((p) => <option key={p}>{p}</option>)}</Select></Field>
        <Field label="When"><Select value={fresh.comparison} onChange={(e) => setFresh({ ...fresh, comparison: e.target.value })}><option value="GT">above</option><option value="LT">below</option></Select></Field>
        <Field label="Value"><Input type="number" step="any" value={fresh.threshold} onChange={(e) => setFresh({ ...fresh, threshold: e.target.value })} /></Field>
        <Field label="Level"><Select value={fresh.level} onChange={(e) => setFresh({ ...fresh, level: e.target.value })}><option>WARNING</option><option>CRITICAL</option></Select></Field>
        <Field label="Message"><Input maxLength={200} value={fresh.message} onChange={(e) => setFresh({ ...fresh, message: e.target.value })} /></Field>
        <Button type="button" disabled={busy || fresh.threshold === "" || fresh.message.trim().length < 3} onClick={async () => { if (await run(() => saveRule(null, { ...fresh, threshold: Number(fresh.threshold) }), "Rule added")) { setFresh({ ...fresh, threshold: "", message: "" }); reload(); } }}>Add</Button></div>
      {problem && <div className="mt-3"><ErrorBox message={problem} /></div>}
    </Section>
  );
}
