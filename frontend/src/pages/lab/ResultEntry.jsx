// The technician enters the measured values of one test. The unit, method and limits come from the hospital's list: nothing is guessed.
// "Save draft" keeps it; "Send for approval" passes it to a pathologist (a critical value alerts the doctor at once).
import { useState } from "react";
import useFetch from "../../hooks/useFetch";
import { getErrorMessage } from "../../services/api";
import { getLabTest, saveLabResults } from "../../services/diagnosticsApi";
import { ErrorBox, Loading } from "../../components/Feedback";
import { Button, Input, Modal } from "../../components/ui";
import ResultTable from "../../components/ResultTable";

// What the screen says about a typed value next to the hospital's limits. It only helps the eye: the server checks and flags the real result.
export function flagFor(value, analyte) {
  const n = Number(String(value).trim().replace(",", "."));
  if (String(value).trim() === "" || !Number.isFinite(n)) return null;
  const { ref_low: low, ref_high: high, critical_low: clow, critical_high: chigh } = analyte;
  if ((clow != null && n < clow) || (chigh != null && n > chigh)) return { key: "critical", label: n < (clow ?? -Infinity) ? "Critical low" : "Critical high", tone: "bg-red-600 text-white" };
  if (low != null && n < low) return { key: "low", label: "Low", tone: "bg-sky-100 text-sky-900" };
  if (high != null && n > high) return { key: "high", label: "High", tone: "bg-amber-100 text-amber-900" };
  if (low != null || high != null) return { key: "normal", label: "Normal", tone: "bg-emerald-100 text-emerald-900" };
  return null;
}

function AnalyteField({ analyte: a, value, onChange }) {
  const flag = flagFor(value, a);
  const range = a.ref_low != null || a.ref_high != null ? `Range ${a.ref_low ?? ""} - ${a.ref_high ?? ""}${a.unit ? " " + a.unit : ""}` : "No range set by the hospital";
  return (
    <div className="rounded-2xl border border-slate-200 p-3">
      <label htmlFor={`an-${a.id}`} className="block font-semibold text-slate-800">{a.name}{a.unit ? <span className="font-normal text-slate-600"> ({a.unit})</span> : null}</label>
      <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1.5">
        <Input id={`an-${a.id}`} inputMode="decimal" enterKeyHint="next" autoComplete="off" maxLength={20} value={value} onChange={(e) => onChange(e.target.value)} className="num !w-36 text-lg" />
        <span className="num text-sm text-slate-700">{range}{a.method ? `, ${a.method}` : ""}</span>
        {flag && <span role="status" data-flag={flag.key} className={`rounded-full px-2.5 py-0.5 text-sm font-bold ${flag.tone}`}>{flag.label}</span>}
      </div>
    </div>
  );
}

export default function ResultEntry({ test, onClose, onDone }) {
  const { data, loading, error } = useFetch(() => getLabTest(test.id), [test.id]);
  const [values, setValues] = useState(null);
  const [problem, setProblem] = useState("");
  const [busy, setBusy] = useState(false);
  if (loading) return <Modal title={`Result: ${test.test_name}`} onClose={onClose}><Loading /></Modal>;
  if (error) return <Modal title={`Result: ${test.test_name}`} onClose={onClose}><ErrorBox message={error} /></Modal>;
  if (data.analytes.length === 0) {
    return <Modal title={`Result: ${test.test_name}`} onClose={onClose}><p className="text-slate-700">This test is not in the hospital's test list yet, so there are no values to enter. Ask the administrator to add it (Diagnostics), or upload the result as a file.</p></Modal>;
  }
  const current = values || Object.fromEntries(data.results.map((r) => [r.name, r.value]));
  const send = async (submit) => {
    setProblem("");
    const items = data.analytes.filter((a) => (current[a.name] || "").trim() !== "").map((a) => ({ analyte_id: a.id, value: current[a.name].trim() }));
    setBusy(true);
    try { await saveLabResults(test.id, items, submit); onDone(submit); } catch (e) { setProblem(getErrorMessage(e)); } finally { setBusy(false); }
  };
  return (
    <Modal title={`Enter the result: ${test.test_name}`} onClose={onClose} wide>
      <div className="space-y-4">
        <p className="text-slate-700">Patient: <b>{test.patient_name}</b> ({test.patient_code}). Sample <span className="font-mono">{test.sample_code}</span>.</p>
        {data.approval_note && <p className="rounded-xl bg-amber-50 p-2.5 text-sm text-amber-900"><b>Sent back by the pathologist:</b> {data.approval_note}</p>}
        <div className="grid gap-3 lg:grid-cols-2">{data.analytes.map((a) => <AnalyteField key={a.id} analyte={a} value={current[a.name] || ""} onChange={(v) => setValues({ ...current, [a.name]: v })} />)}</div>
        {data.results.length > 0 && !values && <ResultTable results={data.results} />}
        {problem && <ErrorBox message={problem} />}
        <div className="sticky bottom-0 -mx-5 flex flex-wrap justify-end gap-2 border-t border-slate-200 bg-white px-5 pb-1 pt-3 sm:-mx-6 sm:px-6">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button variant="secondary" disabled={busy} onClick={() => send(false)}>Save draft</Button>
          <Button disabled={busy} onClick={() => send(true)}>Send for approval</Button>
        </div>
      </div>
    </Modal>
  );
}
