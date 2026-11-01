// Radiology work list: schedule the scan, do it, attach the image or document (JPG, PNG or PDF), then a radiologist reports and approves.
// A technician cannot write or approve a report. This is not DICOM or PACS.
import { useRef, useState } from "react";
import { CheckCircle2, ScanLine } from "lucide-react";
import useFetch from "../../hooks/useFetch";
import useSave from "../../hooks/useSave";
import { useAuth } from "../../context/AuthContext";
import { addStudyFile, approveStudy, getRadiologyDashboard, getRadiologyOrder, getRadiologyWorklist, openStudyFile, reportStudy, scheduleStudy, startStudy } from "../../services/diagnosticsApi";
import { EmptyState, ErrorBox, Loading, PageTitle } from "../../components/Feedback";
import { Button, Field, Input, Modal, Textarea, fmtUtc } from "../../components/ui";

const TABS = [["OPEN", "To do"], ["ORDERED", "Waiting"], ["SCHEDULED", "Scheduled"], ["IN_PROGRESS", "Scan done"], ["REPORTED", "To approve"], ["APPROVED", "Reported"], ["", "All"]];
const TONE = { ORDERED: "bg-amber-100 text-amber-900", SCHEDULED: "bg-sky-100 text-sky-900", IN_PROGRESS: "bg-violet-100 text-violet-900", REPORTED: "bg-indigo-100 text-indigo-900", APPROVED: "bg-emerald-100 text-emerald-900", CANCELLED: "bg-slate-200 text-slate-700" };
const localInput = (d) => new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);

export default function RadiologyWorklist() {
  const { user } = useAuth();
  const radiologist = user.staff_type === "RADIOLOGIST";
  const [tab, setTab] = useState("OPEN");
  const [dialog, setDialog] = useState(null);
  const { data, loading, error, reload } = useFetch(() => getRadiologyWorklist(tab ? { status_filter: tab } : {}), [tab]);
  const stats = useFetch(getRadiologyDashboard, []);
  const { problem, busy, run } = useSave();
  const refresh = () => { setDialog(null); reload(); stats.reload(); };

  return (
    <div className="space-y-5">
      <PageTitle title="Scan work list" subtitle={radiologist ? "Report the scans and approve the reports. Nothing reaches the doctor before you approve it." : "Schedule and do the scans, attach the images. A radiologist writes and approves the report."} icon={ScanLine} />
      {stats.data && (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          {[["To do", stats.data.open], ["Urgent", stats.data.stat_open], ["To approve", stats.data.waiting_for_report], ["Approved today", stats.data.done_today]].map(([label, value]) => (
            <div key={label} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"><p className="text-sm font-bold text-slate-500">{label}</p><p className="text-2xl font-extrabold text-slate-800">{value}</p></div>))}
        </div>)}
      <div className="flex flex-wrap gap-1.5" role="tablist">{TABS.map(([key, label]) => (
        <button key={key || "all"} type="button" role="tab" aria-selected={tab === key} onClick={() => setTab(key)}
          className={`rounded-full px-4 py-2 text-sm font-bold ${tab === key ? "bg-brand-700 text-white shadow" : "bg-white text-slate-700 ring-1 ring-slate-200 hover:bg-slate-50"}`}>{label}</button>))}</div>
      {problem && <ErrorBox message={problem} />}
      {loading && !data ? <Loading /> : error ? <ErrorBox message={error} onRetry={reload} /> : data.studies.length === 0 ? <EmptyState message="Nothing here" hint="When a doctor orders a scan it appears here." icon={ScanLine} /> : (
        <div className="space-y-3">{data.studies.map((s) => (
          <div key={s.id} className={`rounded-3xl border-2 bg-white p-5 shadow-sm ${["URGENT", "STAT"].includes(s.priority) && !["APPROVED", "CANCELLED"].includes(s.status) ? "border-red-300" : "border-brand-200"}`}>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-lg font-extrabold text-slate-900">{s.study} <span className="text-sm font-semibold text-slate-500">{s.modality}</span>{["URGENT", "STAT"].includes(s.priority) && <span className="ml-2 rounded-full bg-red-600 px-2.5 py-0.5 text-xs font-bold text-white">{s.priority}</span>}</p>
                <p className="text-slate-700">{s.patient_name} <span className="text-slate-500">({s.patient_code})</span></p>
                <p className="text-sm text-slate-500">Ordered by {s.doctor_name} on {s.ordered_on}{s.clinical_info ? ` - ${s.clinical_info}` : ""}{s.scheduled_at ? ` - scheduled ${fmtUtc(s.scheduled_at)}` : ""}</p>
              </div>
              <span className={`rounded-full px-3 py-1 text-sm font-bold ${TONE[s.status]}`}>{s.status_label}</span>
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              {["ORDERED", "SCHEDULED"].includes(s.status) && <Button variant="secondary" onClick={() => setDialog({ kind: "schedule", s })}>Schedule</Button>}
              {["ORDERED", "SCHEDULED"].includes(s.status) && <Button disabled={busy} onClick={async () => { if (await run(() => startStudy(s.id), "Scan started")) refresh(); }}>Start the scan</Button>}
              {["IN_PROGRESS", "REPORTED"].includes(s.status) && <Button variant="secondary" onClick={() => setDialog({ kind: "files", s })}>Images and files</Button>}
              {radiologist && ["IN_PROGRESS", "REPORTED"].includes(s.status) && <Button onClick={() => setDialog({ kind: "report", s })}>{s.status === "REPORTED" ? "Edit the report" : "Write the report"}</Button>}
              {radiologist && s.status === "REPORTED" && <Button disabled={busy} onClick={async () => { if (await run(() => approveStudy(s.id), "Report approved")) refresh(); }}><CheckCircle2 size={16} />Approve the report</Button>}
              {s.status === "APPROVED" && <Button variant="soft" onClick={() => setDialog({ kind: "view", s })}>View the report</Button>}
            </div>
          </div>))}</div>)}
      {dialog?.kind === "schedule" && <ScheduleDialog s={dialog.s} onClose={() => setDialog(null)} onDone={refresh} />}
      {dialog?.kind === "files" && <FilesDialog s={dialog.s} onClose={() => setDialog(null)} />}
      {dialog?.kind === "report" && <ReportDialog s={dialog.s} onClose={() => setDialog(null)} onDone={refresh} />}
      {dialog?.kind === "view" && <ViewDialog s={dialog.s} onClose={() => setDialog(null)} />}
    </div>
  );
}

function ScheduleDialog({ s, onClose, onDone }) {
  const [when, setWhen] = useState(localInput(new Date(Date.now() + 3600000)));
  const { problem, busy, run } = useSave();
  return (
    <Modal title={`Schedule: ${s.study}`} onClose={onClose}>
      <Field label="Date and time"><Input type="datetime-local" value={when} onChange={(e) => setWhen(e.target.value)} /></Field>
      {problem && <ErrorBox message={problem} />}
      <div className="mt-4 flex justify-end gap-2"><Button variant="secondary" onClick={onClose}>Cancel</Button><Button disabled={busy || !when} onClick={async () => { if (await run(() => scheduleStudy(s.id, new Date(when).toISOString().slice(0, 19)), "Scheduled")) onDone(); }}>Schedule</Button></div>
    </Modal>
  );
}

function FilesDialog({ s, onClose }) {
  const input = useRef(null);
  const { data, reload } = useFetch(() => getRadiologyOrder(s.id), [s.id]);
  const { problem, busy, run } = useSave();
  return (
    <Modal title={`Images and files: ${s.study}`} onClose={onClose}>
      <p className="mb-2 text-sm text-slate-600">JPG, PNG or PDF, up to 10 MB each. {s.patient_name} ({s.patient_code}): check the name before you attach.</p>
      <ul className="mb-3 space-y-1">{(data?.files || []).map((f) => <li key={f.id}><button type="button" className="font-semibold text-brand-700 underline" onClick={() => openStudyFile(f.id)}>{f.filename}</button></li>)}</ul>
      <input ref={input} type="file" accept=".jpg,.jpeg,.png,.pdf" aria-label="Choose a file" onChange={async (e) => { const file = e.target.files[0]; if (file && await run(() => addStudyFile(s.id, file), "File attached")) reload(); e.target.value = ""; }} disabled={busy} />
      {problem && <ErrorBox message={problem} />}
    </Modal>
  );
}

function ReportDialog({ s, onClose, onDone }) {
  const { data } = useFetch(() => getRadiologyOrder(s.id), [s.id]);
  const [form, setForm] = useState(null);
  const { problem, busy, run } = useSave();
  const f = form || { technique: data?.report?.technique || "", findings: data?.report?.findings || "", impression: data?.report?.impression || "" };
  const set = (k) => (e) => setForm({ ...f, [k]: e.target.value });
  return (
    <Modal title={`Report: ${s.study}`} onClose={onClose} wide>
      <div className="space-y-3">
        <p className="text-sm text-slate-600">{s.patient_name} ({s.patient_code}). {s.clinical_info || ""}</p>
        {data?.previous_studies?.length > 0 && <div className="rounded-xl bg-sky-50 p-2.5 text-sm text-sky-900"><b>Earlier approved studies of the same kind:</b>{data.previous_studies.map((p) => <p key={p.id}>{p.date}: {p.study} - {p.impression}</p>)}</div>}
        <Field label="Technique (optional)"><Input maxLength={300} value={f.technique} onChange={set("technique")} /></Field>
        <Field label="Findings *"><Textarea rows={6} maxLength={8000} value={f.findings} onChange={set("findings")} /></Field>
        <Field label="Impression *"><Textarea rows={3} maxLength={3000} value={f.impression} onChange={set("impression")} /></Field>
        {problem && <ErrorBox message={problem} />}
        <div className="flex justify-end gap-2"><Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button disabled={busy || f.findings.trim().length < 3 || f.impression.trim().length < 3} onClick={async () => { if (await run(() => reportStudy(s.id, { technique: f.technique.trim() || null, findings: f.findings, impression: f.impression }), "Report saved: now approve it")) onDone(); }}>Save the report</Button></div>
      </div>
    </Modal>
  );
}

function ViewDialog({ s, onClose }) {
  const { data } = useFetch(() => getRadiologyOrder(s.id), [s.id]);
  const r = data?.report;
  return (
    <Modal title={`Report: ${s.study}`} onClose={onClose} wide>
      {!r ? <Loading /> : <div className="space-y-2 text-slate-800"><p><b>Findings</b></p><p className="whitespace-pre-wrap">{r.findings}</p><p><b>Impression</b></p><p className="whitespace-pre-wrap">{r.impression}</p></div>}
    </Modal>
  );
}
