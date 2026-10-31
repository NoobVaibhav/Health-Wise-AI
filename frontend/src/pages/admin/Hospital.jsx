// Hospital setup for the administrator: profile, branches, settings, price list, roles and the review of emergency (break-glass) access.
import { useEffect, useState } from "react";
import useFetch from "../../hooks/useFetch";
import {
  addBranch, addService, getHospitalProfile, listBranches, listBreakGlass, listPermissions, listRoles, listServices, listSettings, reviewBreakGlass, saveHospitalProfile,
  saveRolePermissions, saveSetting, updateBranch, updateService,
} from "../../services/hospitalApi";
import { listDepartments } from "../../services/adminApi";
import { getErrorMessage } from "../../services/api";
import { Section } from "../../components/HealthCard";
import { Button, Field, Input, Select, Tabs, fmtUtc } from "../../components/ui";
import { ErrorBox, Loading, PageTitle } from "../../components/Feedback";
import { useToast } from "../../components/Toast";
import { TemplatesTab, ThresholdsTab, WardsTab } from "./ClinicalSetup";

const CATEGORIES = ["CONSULTATION", "PROCEDURE", "LAB", "RADIOLOGY", "BED", "NURSING", "OT", "PHARMACY", "OTHER"];

function useSave() {
  const toast = useToast();
  const [problem, setProblem] = useState("");
  const run = async (fn, message) => {
    setProblem("");
    try { const r = await fn(); if (message) toast(message); return r; } catch (e) { setProblem(getErrorMessage(e)); return null; }
  };
  return { problem, run };
}

function Profile() {
  const { data, loading, error, reload } = useFetch(getHospitalProfile);
  const [form, setForm] = useState(null);
  const { problem, run } = useSave();
  useEffect(() => { if (data) setForm(Object.fromEntries(Object.entries(data).map(([k, v]) => [k, v || ""]))); }, [data]);
  if (loading || !form) return error ? <ErrorBox message={error} onRetry={reload} /> : <Loading />;
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  const fields = [["name", "Hospital name"], ["address", "Address"], ["phone", "Phone"], ["email", "E-mail"], ["registration_number", "Registration number"], ["gst_number", "GST number"]];
  return (
    <Section title="Hospital profile" >
      <p className="mb-3 text-sm text-slate-600">Printed on prescriptions and bills.</p>
      <div className="grid gap-4 sm:grid-cols-2">{fields.map(([k, label]) => <Field key={k} label={label}><Input maxLength={k === "address" ? 300 : 200} value={form[k]} onChange={set(k)} /></Field>)}</div>
      {problem && <div className="mt-3"><ErrorBox message={problem} /></div>}
      <div className="mt-4"><Button type="button" onClick={async () => { if (await run(() => saveHospitalProfile(Object.fromEntries(Object.entries(form).map(([k, v]) => [k, v.trim() || null]))), "Hospital profile saved")) reload(); }}>Save</Button></div>
    </Section>
  );
}

function Branches() {
  const { data, loading, error, reload } = useFetch(listBranches);
  const [form, setForm] = useState({ code: "", name: "", address: "" });
  const { problem, run } = useSave();
  return (
    <Section title="Branches">
      {loading && !data ? <Loading /> : error ? <ErrorBox message={error} onRetry={reload} /> : (
        <ul className="mb-4 divide-y">{data.map((b) => (
          <li key={b.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
            <span className={b.is_active ? "" : "text-slate-400 line-through"}><b>{b.code}</b> · {b.name}{b.address ? ` · ${b.address}` : ""}</span>
            <Button type="button" variant="secondary" onClick={async () => { await run(() => updateBranch(b.id, { is_active: !b.is_active }), b.is_active ? "Branch switched off" : "Branch switched on"); reload(); }}>{b.is_active ? "Switch off" : "Switch on"}</Button>
          </li>))}</ul>)}
      <div className="grid gap-3 sm:grid-cols-4 sm:items-end">
        <Field label="Code (letters, for the UHID)"><Input maxLength={8} placeholder="PUN" value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} /></Field>
        <Field label="Name"><Input maxLength={150} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field>
        <Field label="Address"><Input maxLength={300} value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} /></Field>
        <Button type="button" disabled={form.code.trim().length < 2 || form.name.trim().length < 2}
          onClick={async () => { if (await run(() => addBranch({ code: form.code, name: form.name, address: form.address || null }), "Branch added")) { setForm({ code: "", name: "", address: "" }); reload(); } }}>Add branch</Button>
      </div>
      {problem && <div className="mt-3"><ErrorBox message={problem} /></div>}
      <p className="mt-3 text-xs text-slate-500">The code is part of every UHID of the branch, so it cannot be changed later. A branch can be switched off.</p>
    </Section>
  );
}

function Settings() {
  const { data, loading, error, reload } = useFetch(listSettings);
  const [edit, setEdit] = useState({});
  const { problem, run } = useSave();
  const LABEL = { break_glass_minutes: "Emergency access lasts (minutes)", appointment_slot_minutes: "Appointment slot (minutes)", working_hours_start: "Working hours start (HH:MM)", working_hours_end: "Working hours end (HH:MM)",
    currency: "Currency", invoice_prefix: "Invoice prefix", duplicate_check: "Warn about a possible second record (on / off)" };
  if (loading && !data) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  return (
    <Section title="Settings">
      <div className="grid gap-4 sm:grid-cols-2">
        {data.map((s) => (
          <Field key={s.key} label={LABEL[s.key] || s.key} hint={`Default: ${s.default}`}>
            <div className="flex gap-2"><Input value={edit[s.key] ?? s.value} onChange={(e) => setEdit({ ...edit, [s.key]: e.target.value })} />
              <Button type="button" variant="secondary" disabled={edit[s.key] === undefined || edit[s.key] === s.value} onClick={async () => { if (await run(() => saveSetting(s.key, edit[s.key]), "Saved")) { setEdit({ ...edit, [s.key]: undefined }); reload(); } }}>Save</Button></div>
          </Field>))}
      </div>
      {problem && <div className="mt-3"><ErrorBox message={problem} /></div>}
    </Section>
  );
}

function Prices() {
  const { data, loading, error, reload } = useFetch(() => listServices(true));
  const { data: departments } = useFetch(listDepartments, []);
  const [form, setForm] = useState({ code: "", name: "", category: "CONSULTATION", department_id: "", price: "", gst_percent: "0" });
  const { problem, run } = useSave();
  return (
    <Section title="Price list">
      {loading && !data ? <Loading /> : error ? <ErrorBox message={error} onRetry={reload} /> : (
        <div className="mb-4 overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr className="border-b text-xs uppercase text-slate-500"><th className="py-1.5">Code</th><th>Service</th><th>Category</th><th className="text-right">Price</th><th className="text-right">GST %</th><th /></tr></thead>
          <tbody>{data.length === 0 && <tr><td colSpan={6} className="py-3 text-slate-500">No services yet.</td></tr>}{data.map((s) => (
            <tr key={s.id} className={`border-b ${s.is_active ? "" : "text-slate-400 line-through"}`}><td className="py-1.5 font-mono">{s.code}</td><td>{s.name}{s.department_name ? ` (${s.department_name})` : ""}</td><td>{s.category}</td>
              <td className="text-right"><PriceCell s={s} run={run} reload={reload} /></td><td className="text-right">{s.gst_percent}</td>
              <td className="text-right"><Button type="button" variant="secondary" onClick={async () => { await run(() => updateService(s.id, { is_active: !s.is_active })); reload(); }}>{s.is_active ? "Switch off" : "Switch on"}</Button></td></tr>))}</tbody></table></div>)}
      <div className="grid gap-3 sm:grid-cols-6 sm:items-end">
        <Field label="Code"><Input maxLength={30} value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} /></Field>
        <Field label="Service"><Input maxLength={200} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field>
        <Field label="Category"><Select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>{CATEGORIES.map((c) => <option key={c}>{c}</option>)}</Select></Field>
        <Field label="Department"><Select value={form.department_id} onChange={(e) => setForm({ ...form, department_id: e.target.value })}><option value="">Any</option>{(departments || []).map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}</Select></Field>
        <Field label="Price (Rs)"><Input type="number" min="0" step="0.01" value={form.price} onChange={(e) => setForm({ ...form, price: e.target.value })} /></Field>
        <Button type="button" disabled={form.code.trim().length < 2 || form.name.trim().length < 2 || form.price === ""}
          onClick={async () => { if (await run(() => addService({ ...form, price: Number(form.price), gst_percent: Number(form.gst_percent), department_id: form.department_id ? Number(form.department_id) : null }), "Service added")) { setForm({ ...form, code: "", name: "", price: "" }); reload(); } }}>Add</Button>
      </div>
      {problem && <div className="mt-3"><ErrorBox message={problem} /></div>}
    </Section>
  );
}

function PriceCell({ s, run, reload }) {
  const [value, setValue] = useState(String(s.price));
  const changed = Number(value) !== s.price;
  return (
    <span className="inline-flex items-center gap-1"><input aria-label={`Price of ${s.name}`} className="w-24 rounded-lg border border-slate-300 px-2 py-1 text-right" type="number" min="0" step="0.01" value={value} onChange={(e) => setValue(e.target.value)} />
      {changed && value !== "" && <Button type="button" variant="secondary" onClick={async () => { await run(() => updateService(s.id, { price: Number(value) }), "Price saved"); reload(); }}>Save</Button>}</span>
  );
}

function Roles() {
  const { data: roles, loading, error, reload } = useFetch(listRoles);
  const { data: permissions } = useFetch(listPermissions, []);
  const [open, setOpen] = useState(null);
  const [draft, setDraft] = useState([]);
  const { problem, run } = useSave();
  if (loading && !roles) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  const pick = (r) => { setOpen(open === r.id ? null : r.id); setDraft(r.permissions); };
  return (
    <Section title="Roles and what they may do">
      <p className="mb-3 text-sm text-slate-600">Each person logs in with one role (doctor, receptionist ...). These hospital roles decide what they may do in the newer screens. Give a person extra roles from their account.</p>
      <ul className="divide-y">{roles.map((r) => (
        <li key={r.id} className="py-2">
          <button type="button" aria-expanded={open === r.id} onClick={() => pick(r)} className="flex w-full items-center justify-between text-left"><span><b>{r.name}</b> <span className="text-sm text-slate-500">{r.description}</span></span><span className="text-sm text-slate-500">{r.permissions.length} permissions</span></button>
          {open === r.id && (
            <div className="mt-2 space-y-2 rounded-xl bg-slate-50 p-3">
              <div className="grid gap-1 sm:grid-cols-2">{(permissions || []).map((p) => (
                <label key={p.code} className="flex items-start gap-2 text-sm"><input type="checkbox" className="mt-1" checked={draft.includes(p.code)} onChange={(e) => setDraft(e.target.checked ? [...draft, p.code] : draft.filter((c) => c !== p.code))} /><span><b>{p.code}</b><br /><span className="text-slate-500">{p.description}</span></span></label>))}</div>
              <Button type="button" onClick={async () => { if (await run(() => saveRolePermissions(r.id, draft), "Role saved")) reload(); }}>Save this role</Button>
            </div>)}
        </li>))}</ul>
      {problem && <div className="mt-3"><ErrorBox message={problem} /></div>}
    </Section>
  );
}

function EmergencyAccess() {
  const { data, loading, error, reload } = useFetch(() => listBreakGlass(false));
  const { problem, run } = useSave();
  const [notes, setNotes] = useState({});
  if (loading && !data) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  return (
    <Section title="Emergency (break-glass) access">
      <p className="mb-3 text-sm text-slate-600">A clinician opened a patient without being assigned, with a written reason. Each one must be reviewed.</p>
      {data.length === 0 ? <p className="text-slate-500">Nobody has used emergency access.</p> : (
        <ul className="divide-y">{data.map((g) => (
          <li key={g.id} className="space-y-1 py-2 text-sm">
            <p><b>{g.user}</b> opened <b>{g.patient_name}</b> ({g.uhid}) · {fmtUtc(g.granted_at)}{g.active && <span className="ml-2 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-bold text-amber-800">open now</span>}</p>
            <p className="text-slate-700">Reason: {g.reason}</p>
            {g.reviewed_at ? <p className="text-emerald-700">Reviewed {fmtUtc(g.reviewed_at)}{g.review_note ? `: ${g.review_note}` : ""}</p> : (
              <div className="flex gap-2"><Input aria-label="Review note" maxLength={500} placeholder="Review note (optional)" value={notes[g.id] || ""} onChange={(e) => setNotes({ ...notes, [g.id]: e.target.value })} />
                <Button type="button" onClick={async () => { await run(() => reviewBreakGlass(g.id, notes[g.id]), "Marked as reviewed"); reload(); }}>Mark reviewed</Button></div>)}
          </li>))}</ul>)}
      {problem && <div className="mt-3"><ErrorBox message={problem} /></div>}
    </Section>
  );
}

export default function Hospital() {
  return (
    <div className="mx-auto max-w-5xl space-y-5">
      <PageTitle title="Hospital" subtitle="Profile, branches, settings, price list, roles and emergency access" />
      <Tabs tabs={[["profile", "Profile", <Profile />], ["branches", "Branches", <Branches />], ["settings", "Settings", <Settings />], ["prices", "Price list", <Prices />], ["roles", "Roles", <Roles />], ["wards", "Wards and beds", <WardsTab />], ["templates", "Consultation forms", <TemplatesTab />], ["thresholds", "Alert thresholds", <ThresholdsTab />], ["glass", "Emergency access", <EmergencyAccess />]]} />
    </div>
  );
}
