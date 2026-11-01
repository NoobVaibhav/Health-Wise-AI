// The laboratory work list: every advised test, followed from order to result.
// Waiting for the sample -> sample taken (a label code is made) -> being tested -> result uploaded. A bad sample is rejected with a reason.
import { useState } from "react";
import { AlertTriangle, CheckCircle2, FlaskConical, Play, RotateCcw, Search, TestTube2, Upload, XCircle } from "lucide-react";
import useFetch from "../../hooks/useFetch";
import { getErrorMessage } from "../../services/api";
import { getLabDashboard, getWorklist, setTestStatus, setTestUrgent, uploadTestResult } from "../../services/labApi";
import { EmptyState, ErrorBox, Hint, Loading, PageTitle } from "../../components/Feedback";
import { Button, Field, Modal, Select, Textarea, fmtUtc, inputClass } from "../../components/ui";
import { useToast } from "../../components/Toast";
import ResultEntry from "./ResultEntry";

const TABS = [["OPEN", "To do"], ["ORDERED", "Waiting for sample"], ["SAMPLE_COLLECTED", "Sample taken"], ["IN_PROGRESS", "Being tested"], ["COMPLETED", "Done"], ["REJECTED", "Rejected"], ["", "All"]];
const TONE = { ORDERED: "bg-amber-100 text-amber-900", SAMPLE_COLLECTED: "bg-sky-100 text-sky-900", IN_PROGRESS: "bg-violet-100 text-violet-900", COMPLETED: "bg-emerald-100 text-emerald-900", REJECTED: "bg-red-100 text-red-900", CANCELLED: "bg-slate-200 text-slate-700" };
const waiting = (h) => (h == null ? "" : h < 1 ? "less than an hour" : h < 48 ? `${Math.round(h)} h` : `${Math.round(h / 24)} days`);

export default function Worklist() {
  const toast = useToast();
  const [tab, setTab] = useState("OPEN");
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(null);
  const [dialog, setDialog] = useState(null);       // { kind: "sample" | "reject" | "result", test }
  const { data, loading, error, reload } = useFetch(() => getWorklist({ ...(tab ? { status_filter: tab } : {}), ...(q ? { q } : {}) }), [tab, q]);
  const stats = useFetch(getLabDashboard, []);

  const run = async (test, fn, message) => {
    setBusy(test.id);
    try { await fn(); toast(message); setDialog(null); reload(); stats.reload(); } catch (e) { toast(getErrorMessage(e), "error"); } finally { setBusy(null); }
  };
  const count = (key) => (key === "OPEN" ? stats.data?.open : key === "" ? undefined : stats.data?.counts?.[key]);

  return (
    <div className="space-y-5">
      <PageTitle title="Work list" subtitle="Take the sample, test it, then upload the result. The result goes to the doctor for review." icon={FlaskConical} />

      {stats.data && (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          {[["To do", stats.data.open, "text-brand-800"], ["Urgent", stats.data.urgent_open, stats.data.urgent_open ? "text-red-700" : "text-slate-800"],
            ["Done today", stats.data.done_today, "text-emerald-700"], ["Waiting longest", stats.data.oldest_waiting_hours == null ? "-" : waiting(stats.data.oldest_waiting_hours), "text-slate-800"]].map(([label, value, tone]) => (
            <div key={label} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"><p className="text-sm font-bold text-slate-500">{label}</p><p className={`text-2xl font-extrabold ${tone}`}>{value}</p></div>))}
        </div>
      )}

      <div className="flex flex-wrap gap-1.5" role="tablist">{TABS.map(([key, label]) => (
        <button key={key || "all"} type="button" role="tab" aria-selected={tab === key} onClick={() => setTab(key)}
          className={`rounded-full px-4 py-2 text-sm font-bold ${tab === key ? "bg-brand-700 text-white shadow" : "bg-white text-slate-700 ring-1 ring-slate-200 hover:bg-slate-50"}`}>
          {label}{count(key) !== undefined ? ` (${count(key)})` : ""}</button>))}</div>

      <div className="relative w-full max-w-xl">
        <Search className="pointer-events-none absolute left-3.5 top-3.5 text-slate-500" size={20} />
        <input className={`${inputClass} pl-11`} placeholder="Patient name, patient ID, RX code, test name or sample code" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>

      {loading && !data ? <Loading /> : error ? <ErrorBox message={error} onRetry={reload} /> : data.tests.length === 0 ? (
        <EmptyState message={q ? "No test matches your search" : "Nothing here"} hint={tab === "OPEN" ? "When a doctor advises a test it appears here." : "Try another tab."} icon={FlaskConical} />
      ) : (
        <div className="space-y-3">{data.tests.map((t) => (
          <div key={t.id} className={`rounded-3xl border-2 bg-white p-5 shadow-sm ${t.urgent && ["ORDERED", "SAMPLE_COLLECTED", "IN_PROGRESS"].includes(t.status) ? "border-red-300" : "border-brand-200"}`}>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-lg font-extrabold text-slate-900">{t.test_name}{t.urgent && <span className="ml-2 inline-flex items-center gap-1 rounded-full bg-red-600 px-2.5 py-0.5 text-xs font-bold text-white"><AlertTriangle size={12} />URGENT</span>}</p>
                <p className="text-base text-slate-700">{t.patient_name} <span className="text-slate-500">({t.patient_code})</span></p>
                <p className="text-sm text-slate-500">{t.prescription_code} - advised by {t.doctor_name} on {t.ordered_on}{t.reason ? ` - ${t.reason}` : ""}</p>
              </div>
              <span className={`rounded-full px-3 py-1 text-sm font-bold ${TONE[t.status]}`}>{t.status_label}</span>
            </div>

            {(t.sample_code || t.waiting_hours != null) && (
              <p className="mt-2 text-sm text-slate-600">
                {t.sample_code && <>Sample <b className="font-mono text-slate-900">{t.sample_code}</b> ({t.sample_type}) taken {fmtUtc(t.collected_at)}. </>}
                {t.waiting_hours != null && <>Waiting for {waiting(t.waiting_hours)}.</>}
              </p>
            )}
            {t.result_status === "PENDING_APPROVAL" && <p className="mt-2 rounded-xl bg-indigo-50 p-2.5 text-sm font-semibold text-indigo-900">Result entered{t.has_critical ? " (critical value: the doctor was alerted)" : ""}. Waiting for the pathologist.</p>}
            {t.status === "REJECTED" && <p className="mt-2 rounded-xl bg-red-50 p-2.5 text-sm text-red-800"><b>Rejected:</b> {t.rejection_reason}</p>}
            {t.status === "COMPLETED" && <p className="mt-2 flex items-center gap-1.5 text-sm font-semibold text-emerald-800"><CheckCircle2 size={16} /> Result uploaded {fmtUtc(t.completed_at)} and sent to {t.doctor_name} for review.</p>}

            <div className="mt-3 flex flex-wrap gap-2">
              {t.status === "ORDERED" && <Button disabled={busy === t.id} onClick={() => setDialog({ kind: "sample", test: t })}><TestTube2 size={16} />Collect the sample</Button>}
              {t.status === "SAMPLE_COLLECTED" && <Button disabled={busy === t.id} onClick={() => run(t, () => setTestStatus(t.id, { status: "IN_PROGRESS" }), "Testing started")}><Play size={16} />Start testing</Button>}
              {["SAMPLE_COLLECTED", "IN_PROGRESS"].includes(t.status) && t.result_status !== "PENDING_APPROVAL" && <Button onClick={() => setDialog({ kind: "entry", test: t })}><FlaskConical size={16} />{t.result_status === "DRAFT" ? "Continue the result" : "Enter the result"}</Button>}
              {["SAMPLE_COLLECTED", "IN_PROGRESS"].includes(t.status) && t.result_status !== "PENDING_APPROVAL" && <Button variant="secondary" onClick={() => setDialog({ kind: "result", test: t })}><Upload size={16} />Upload a result file</Button>}
              {["SAMPLE_COLLECTED", "IN_PROGRESS"].includes(t.status) && <Button variant="secondary" onClick={() => setDialog({ kind: "reject", test: t })}><XCircle size={16} />Reject the sample</Button>}
              {t.status === "REJECTED" && <Button variant="secondary" disabled={busy === t.id} onClick={() => run(t, () => setTestStatus(t.id, { status: "ORDERED" }), "Ordered again: the patient gives a new sample")}><RotateCcw size={16} />Order again</Button>}
              {["ORDERED", "SAMPLE_COLLECTED", "IN_PROGRESS"].includes(t.status) && <Button variant="soft" disabled={busy === t.id} onClick={() => run(t, () => setTestUrgent(t.id, !t.urgent), t.urgent ? "Not urgent" : "Marked urgent")}>{t.urgent ? "Not urgent" : "Mark urgent"}</Button>}
            </div>
          </div>))}
        </div>
      )}

      {dialog?.kind === "sample" && <SampleDialog test={dialog.test} types={data?.sample_types || ["Blood", "Urine", "Other"]} onClose={() => setDialog(null)} onSave={(type) => run(dialog.test, () => setTestStatus(dialog.test.id, { status: "SAMPLE_COLLECTED", sample_type: type }), "Sample taken: write the code on the sample")} />}
      {dialog?.kind === "reject" && <RejectDialog test={dialog.test} onClose={() => setDialog(null)} onSave={(note) => run(dialog.test, () => setTestStatus(dialog.test.id, { status: "REJECTED", note }), "Sample rejected")} />}
      {dialog?.kind === "entry" && <ResultEntry test={dialog.test} onClose={() => setDialog(null)} onDone={(sent) => { toast(sent ? "Sent to the pathologist for approval" : "Draft saved"); setDialog(null); reload(); stats.reload(); }} />}
      {dialog?.kind === "result" && <ResultDialog test={dialog.test} onClose={() => setDialog(null)} onDone={() => { toast("Result uploaded and sent to the doctor"); setDialog(null); reload(); stats.reload(); }} />}

      <Hint title="Please note">Check the patient's name and ID on the sample and on the result. A result with a different name is not saved unless you confirm it on purpose.</Hint>
    </div>
  );
}

function SampleDialog({ test, types, onClose, onSave }) {
  const [type, setType] = useState("Blood");
  return (
    <Modal title={`Collect the sample: ${test.test_name}`} onClose={onClose}>
      <p className="mb-3 text-slate-700">Patient: <b>{test.patient_name}</b> ({test.patient_code}). Check the name with the patient before taking the sample.</p>
      <Field label="Sample type"><Select value={type} onChange={(e) => setType(e.target.value)}>{types.map((x) => <option key={x}>{x}</option>)}</Select></Field>
      <p className="mt-2 text-sm text-slate-500">A sample code is made when you save it. Write it on the sample.</p>
      <div className="mt-4 flex justify-end gap-2"><Button variant="secondary" onClick={onClose}>Cancel</Button><Button onClick={() => onSave(type)}>Sample taken</Button></div>
    </Modal>
  );
}

function RejectDialog({ test, onClose, onSave }) {
  const [note, setNote] = useState("");
  return (
    <Modal title={`Reject the sample: ${test.test_name}`} onClose={onClose}>
      <Field label="Why is the sample rejected?" hint="For example: not enough blood, haemolysed, wrong container. The patient is told to give the sample again."><Textarea rows={3} value={note} onChange={(e) => setNote(e.target.value)} /></Field>
      <div className="mt-4 flex justify-end gap-2"><Button variant="secondary" onClick={onClose}>Cancel</Button><Button variant="danger" disabled={note.trim().length < 3} onClick={() => onSave(note.trim())}>Reject the sample</Button></div>
    </Modal>
  );
}

function ResultDialog({ test, onClose, onDone }) {
  const [file, setFile] = useState(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [mismatch, setMismatch] = useState("");
  const send = async (confirm) => {
    setSaving(true); setError("");
    try { await uploadTestResult(test.id, file, confirm); onDone(); } catch (e) {
      const detail = e.response?.data?.detail;
      if (detail?.code === "NAME_MISMATCH") setMismatch(detail.message); else { setMismatch(""); setError(getErrorMessage(e)); }
    } finally { setSaving(false); }
  };
  return (
    <Modal title={`Upload the result: ${test.test_name}`} onClose={onClose}>
      <p className="mb-3 text-slate-700">Patient: <b>{test.patient_name}</b> ({test.patient_code}). The result is read by the system and sent to {test.doctor_name} for review.</p>
      <Field label="Result file (PDF, photo, text or CSV)"><input type="file" accept=".pdf,.png,.jpg,.jpeg,.webp,.txt,.csv" className={inputClass} onChange={(e) => { setFile(e.target.files?.[0] || null); setMismatch(""); setError(""); }} /></Field>
      {error && <p className="mt-3 rounded-xl bg-red-50 p-2.5 text-sm font-semibold text-red-700" role="alert">{error}</p>}
      {mismatch && (
        <div className="mt-3 rounded-xl border-2 border-red-300 bg-red-50 p-3 text-red-900" role="alert">
          <p className="flex items-start gap-2 font-bold"><AlertTriangle size={18} className="mt-0.5 shrink-0" />{mismatch}</p>
          <Button variant="danger" className="mt-2" disabled={saving} onClick={() => send(true)}>I checked: upload it for this patient</Button>
        </div>)}
      <div className="mt-4 flex justify-end gap-2"><Button variant="secondary" onClick={onClose}>Cancel</Button><Button disabled={!file || saving} onClick={() => send(false)}>{saving ? "Uploading..." : "Upload"}</Button></div>
    </Modal>
  );
}
