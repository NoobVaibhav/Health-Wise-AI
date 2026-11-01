// The technician enters the measured values of one test. The unit, method and limits come from the hospital's list: nothing is guessed.
// "Save draft" keeps it; "Send for approval" passes it to a pathologist (a critical value alerts the doctor at once).
import { useState } from "react";
import useFetch from "../../hooks/useFetch";
import { getErrorMessage } from "../../services/api";
import { getLabTest, saveLabResults } from "../../services/diagnosticsApi";
import { ErrorBox, Loading } from "../../components/Feedback";
import { Button, Field, Input, Modal } from "../../components/ui";
import ResultTable from "../../components/ResultTable";

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
        <div className="grid gap-3 sm:grid-cols-2">{data.analytes.map((a) => (
          <Field key={a.id} label={`${a.name}${a.unit ? ` (${a.unit})` : ""}`} hint={a.ref_low != null || a.ref_high != null ? `Range ${a.ref_low ?? ""} - ${a.ref_high ?? ""}${a.method ? `, ${a.method}` : ""}` : a.method || "No range set by the hospital"}>
            <Input inputMode="decimal" maxLength={20} value={current[a.name] || ""} onChange={(e) => setValues({ ...current, [a.name]: e.target.value })} />
          </Field>))}</div>
        {data.results.length > 0 && !values && <ResultTable results={data.results} />}
        {problem && <ErrorBox message={problem} />}
        <div className="flex flex-wrap justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button variant="secondary" disabled={busy} onClick={() => send(false)}>Save draft</Button>
          <Button disabled={busy} onClick={() => send(true)}>Send for approval</Button>
        </div>
      </div>
    </Modal>
  );
}
