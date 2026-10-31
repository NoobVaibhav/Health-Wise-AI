// Registration details of one patient: UHID, ABHA number (only with consent), consents, insurance, and (administrator only) merging a duplicate record into this one.
import { useState } from "react";
import { BadgeCheck, ShieldCheck } from "lucide-react";
import useFetch from "../hooks/useFetch";
import { addConsent, addInsurance, deactivateInsurance, getRegistry, mergePatients, saveAbha, withdrawConsent } from "../services/hospitalApi";
import { listPatients } from "../services/patientApi";
import { getErrorMessage } from "../services/api";
import { useAuth } from "../context/AuthContext";
import { ErrorBox, Loading } from "./Feedback";
import { Button, Field, Input, Modal, Select, fmtUtc } from "./ui";
import { useToast } from "./Toast";

const KINDS = [["TREATMENT", "Treatment"], ["DATA_SHARING", "Sharing records with other doctors"], ["ABHA", "ABHA (health ID) link"], ["PHOTO", "Photo"], ["RESEARCH", "Research use"]];

function Block({ title, children }) { return <section className="rounded-2xl border border-slate-200 p-4"><h3 className="mb-2 font-bold text-slate-900">{title}</h3>{children}</section>; }

export default function PatientRegistryPanel({ patient, onClose, onChanged }) {
  const { user } = useAuth();
  const toast = useToast();
  const { data, loading, error, reload } = useFetch(() => getRegistry(patient.id), [patient.id]);
  const [problem, setProblem] = useState("");
  const [abha, setAbha] = useState("");
  const [kind, setKind] = useState("TREATMENT");
  const [givenBy, setGivenBy] = useState("");
  const [policy, setPolicy] = useState({ insurer_name: "", policy_number: "", valid_to: "" });
  const [merge, setMerge] = useState(null);
  const done = async (fn, message) => {
    setProblem("");
    try { await fn(); if (message) toast(message); reload(); onChanged?.(); } catch (e) { setProblem(getErrorMessage(e)); }
  };
  const abhaConsent = data?.consents.find((c) => c.kind === "ABHA" && c.active);

  return (
    <Modal title={`Registration: ${patient.full_name}`} onClose={onClose} wide>
      {loading && !data ? <Loading /> : error ? <ErrorBox message={error} onRetry={reload} /> : (
        <div className="space-y-4">
          <p className="text-sm text-slate-600">UHID <b className="text-slate-900">{data.uhid || "not issued"}</b> · patient ID {data.patient_code}</p>
          {problem && <ErrorBox message={problem} />}

          <Block title="Consents">
            <ul className="mb-3 divide-y">
              {data.consents.length === 0 && <li className="py-1.5 text-sm text-slate-500">No consent recorded yet.</li>}
              {data.consents.map((c) => (
                <li key={c.id} className="flex flex-wrap items-center justify-between gap-2 py-1.5 text-sm">
                  <span><ShieldCheck size={14} className="mr-1 inline text-emerald-600" /><b>{KINDS.find((k) => k[0] === c.kind)?.[1] || c.kind}</b> · given by {c.given_by} · {fmtUtc(c.granted_at)}{!c.active && <span className="ml-2 font-semibold text-red-700">withdrawn {fmtUtc(c.withdrawn_at)}</span>}</span>
                  {c.active && <Button type="button" variant="secondary" onClick={() => done(() => withdrawConsent(patient.id, c.id), "Consent withdrawn")}>Withdraw</Button>}
                </li>))}
            </ul>
            <div className="flex flex-wrap items-end gap-2">
              <Field label="Consent for"><Select value={kind} onChange={(e) => setKind(e.target.value)}>{KINDS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</Select></Field>
              <Field label="Given by (if not the patient)"><Input maxLength={150} value={givenBy} onChange={(e) => setGivenBy(e.target.value)} /></Field>
              <Button type="button" onClick={() => done(() => addConsent(patient.id, { kind, given_by: givenBy || null }).then(() => setGivenBy("")), "Consent recorded")}>Record consent</Button>
            </div>
          </Block>

          <Block title="ABHA number">
            {data.abha_id ? <p className="mb-2 text-sm"><BadgeCheck size={14} className="mr-1 inline text-emerald-600" />Saved: <b>{data.abha_id}</b></p> : <p className="mb-2 text-sm text-slate-500">{abhaConsent ? "No number saved yet." : "Record the patient's ABHA consent first, then save the number."}</p>}
            <div className="flex flex-wrap items-end gap-2">
              <Field label="14-digit ABHA number"><Input inputMode="numeric" maxLength={20} disabled={!abhaConsent} placeholder="12-3456-7890-1234" value={abha} onChange={(e) => setAbha(e.target.value)} /></Field>
              <Button type="button" disabled={!abhaConsent || !abha} onClick={() => done(() => saveAbha(patient.id, abha).then(() => setAbha("")), "ABHA number saved")}>Save</Button>
              {data.abha_id && <Button type="button" variant="secondary" onClick={() => done(() => saveAbha(patient.id, null), "ABHA number removed")}>Remove</Button>}
            </div>
            <p className="mt-2 text-xs text-slate-500">This only stores the number. Nothing is sent to any ABDM service.</p>
          </Block>

          <Block title="Insurance">
            <ul className="mb-3 divide-y">
              {data.insurance.length === 0 && <li className="py-1.5 text-sm text-slate-500">No insurance recorded.</li>}
              {data.insurance.map((i) => (
                <li key={i.id} className="flex flex-wrap items-center justify-between gap-2 py-1.5 text-sm">
                  <span className={i.is_active ? "" : "text-slate-400 line-through"}><b>{i.insurer_name}</b> · policy {i.policy_number}{i.valid_to ? ` · valid to ${i.valid_to}` : ""}{i.expired && <span className="ml-2 font-semibold text-red-700">expired</span>}</span>
                  {i.is_active && <Button type="button" variant="secondary" onClick={() => done(() => deactivateInsurance(patient.id, i.id), "Insurance switched off")}>Switch off</Button>}
                </li>))}
            </ul>
            <div className="grid gap-2 sm:grid-cols-4 sm:items-end">
              <Field label="Insurer"><Input maxLength={150} value={policy.insurer_name} onChange={(e) => setPolicy({ ...policy, insurer_name: e.target.value })} /></Field>
              <Field label="Policy number"><Input maxLength={60} value={policy.policy_number} onChange={(e) => setPolicy({ ...policy, policy_number: e.target.value })} /></Field>
              <Field label="Valid until"><Input type="date" value={policy.valid_to} onChange={(e) => setPolicy({ ...policy, valid_to: e.target.value })} /></Field>
              <Button type="button" disabled={!policy.insurer_name.trim() || !policy.policy_number.trim()} onClick={() => done(() => addInsurance(patient.id, { insurer_name: policy.insurer_name, policy_number: policy.policy_number, valid_to: policy.valid_to || null }).then(() => setPolicy({ insurer_name: "", policy_number: "", valid_to: "" })), "Insurance added")}>Add</Button>
            </div>
          </Block>

          {user.role === "ADMIN" && (
            <Block title="Merge a duplicate record into this one">
              <p className="mb-2 text-sm text-slate-600">If the same person was registered twice, search the second record and merge it into this one. All its records move here and the old record is kept, archived. This is written to the audit log and cannot be undone from the screen.</p>
              <MergeFinder keepId={patient.id} onPick={setMerge} />
            </Block>)}
        </div>)}
      {merge && <ConfirmMerge keep={patient} old={merge} onClose={() => setMerge(null)} onDone={() => { setMerge(null); toast("The records were merged"); onChanged?.(); onClose(); }} />}
    </Modal>
  );
}

function MergeFinder({ keepId, onPick }) {
  const [q, setQ] = useState("");
  const [rows, setRows] = useState(null);
  const [problem, setProblem] = useState("");
  const search = async () => { setProblem(""); try { setRows((await listPatients(q)).filter((p) => p.id !== keepId)); } catch (e) { setProblem(getErrorMessage(e)); } };
  return (
    <div className="space-y-2">
      <div className="flex gap-2"><Input aria-label="Find the duplicate record" placeholder="Name, UHID or phone of the second record" value={q} onChange={(e) => setQ(e.target.value)} /><Button type="button" disabled={q.trim().length < 3} onClick={search}>Search</Button></div>
      {problem && <p className="text-sm text-red-600">{problem}</p>}
      {rows && rows.length === 0 && <p className="text-sm text-slate-500">Nobody found.</p>}
      {rows && rows.slice(0, 8).map((p) => (
        <div key={p.id} className="flex items-center justify-between gap-2 rounded-xl bg-slate-50 p-2 text-sm"><span><b>{p.full_name}</b> · {p.uhid || p.patient_code} · {p.date_of_birth || "date of birth not set"}</span><Button type="button" variant="secondary" onClick={() => onPick(p)}>Merge this one</Button></div>))}
    </div>
  );
}

function ConfirmMerge({ keep, old, onClose, onDone }) {
  const [reason, setReason] = useState("");
  const [problem, setProblem] = useState("");
  const [busy, setBusy] = useState(false);
  const go = async () => {
    setBusy(true); setProblem("");
    try { await mergePatients({ keep_id: keep.id, merge_id: old.id, reason: reason.trim() }); onDone(); } catch (e) { setProblem(getErrorMessage(e)); } finally { setBusy(false); }
  };
  return (
    <Modal title="Merge these two records?" onClose={onClose}>
      <div className="space-y-3">
        <p className="text-slate-700">Everything of <b>{old.full_name}</b> ({old.uhid || old.patient_code}) moves to <b>{keep.full_name}</b> ({keep.uhid || keep.patient_code}). The old login is switched off.</p>
        <Field label="Why are these the same person? (written in the audit log) *"><Input maxLength={500} value={reason} onChange={(e) => setReason(e.target.value)} /></Field>
        {problem && <ErrorBox message={problem} />}
        <div className="flex justify-end gap-2"><Button type="button" variant="secondary" onClick={onClose}>Cancel</Button><Button type="button" variant="danger" disabled={busy || reason.trim().length < 10} onClick={go}>{busy ? "Merging..." : "Yes, merge"}</Button></div>
      </div>
    </Modal>
  );
}
