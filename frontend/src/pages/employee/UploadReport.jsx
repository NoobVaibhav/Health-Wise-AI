// Employee uploads a report for a patient. The file is sent to the backend and REALLY processed.
// The "complete" state is shown only when the backend returns a result; otherwise the real error is shown.
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { CheckCircle2, Circle, Loader2, XCircle } from "lucide-react";
import useFetch from "../../hooks/useFetch";
import { uploadReport } from "../../services/reportApi";
import { listDoctors } from "../../services/doctorApi";
import { getErrorMessage } from "../../services/api";
import { getHealth } from "../../services/authApi";
import { Hint, PageTitle } from "../../components/Feedback";
import { useToast } from "../../components/Toast";
import UploadBox from "../../components/UploadBox";
import PatientPicker from "../../components/PatientPicker";
import { Section } from "../../components/HealthCard";
import { Field, Select } from "../../components/ui";

const SERVER_STEPS = [
  "Opening the document...",
  "Reading the text (photos and scans use OCR)...",
  "Finding the lab test results...",
  "Comparing each result with its normal range...",
  "Writing simple explanations...",
  "Saving it for the doctor to check...",
];

export default function UploadReport() {
  const { data: doctors } = useFetch(listDoctors, []);
  const { data: health } = useFetch(getHealth, []);
  const toast = useToast();
  const [patient, setPatient] = useState(null);
  const [doctorId, setDoctorId] = useState("");
  const [phase, setPhase] = useState("idle"); // idle | uploading | processing | done | error
  const [uploadPct, setUploadPct] = useState(0);
  const [stepIndex, setStepIndex] = useState(0);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [fileName, setFileName] = useState("");
  const timer = useRef(null);
  useEffect(() => () => clearInterval(timer.current), []);

  const needsDoctor = patient && !patient.assigned_doctor_id;

  const start = async (file) => {
    if (!patient) return setError("Please select the patient first.");
    if (needsDoctor && !doctorId) return setError("This patient has no assigned doctor. Please choose the reviewing doctor.");
    setFileName(file.name);
    setPhase("uploading");
    setUploadPct(0);
    setError("");
    setResult(null);
    setStepIndex(0);
    try {
      const data = await uploadReport(file, patient.id, doctorId || null, (pct) => {
        setUploadPct(pct);
        if (pct >= 100) {
          setPhase("processing");
          clearInterval(timer.current);
          timer.current = setInterval(() => setStepIndex((i) => Math.min(i + 1, SERVER_STEPS.length - 1)), 1200);
        }
      });
      setResult(data);
      setPhase("done");
      toast("Report uploaded and read successfully");
    } catch (err) {
      setError(getErrorMessage(err));
      setPhase("error");
    } finally {
      clearInterval(timer.current);
    }
  };

  const busy = phase === "uploading" || phase === "processing";
  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <PageTitle title="Upload a report" subtitle="Step 1: choose the patient. Step 2: add the report. Lab tests, X-rays, ECGs, discharge summaries and prescriptions are all fine." />
      {health && !health.ocr_available && (
        <Hint title="Photos and scanned papers need the OCR tool">Normal PDF files work fine. For photos or scanned papers, the hospital IT team must install "Tesseract OCR" on the server. Until then, such files will be refused with a clear message.</Hint>
      )}
      <Section title="Step 1: Who is this report for?">
        <PatientPicker value={patient} onChange={(p) => { setPatient(p); setError(""); }} />
        {needsDoctor && (
          <div className="mt-4">
            <Field label="Doctor who should review this report" hint="This patient has no assigned doctor yet">
              <Select value={doctorId} onChange={(e) => setDoctorId(e.target.value)}>
                <option value="">Choose a doctor</option>{(doctors || []).map((d) => <option key={d.id} value={d.id}>{d.full_name}</option>)}</Select>
            </Field>
          </div>
        )}
        {patient && !needsDoctor && <p className="mt-2 text-sm text-slate-500">The report will go to {patient.assigned_doctor_name} for review.</p>}
      </Section>
      <Section title="Step 2: Add the report file">
        <UploadBox onFile={start} disabled={busy || !patient} />
        {!patient && <p className="mt-2 text-sm text-slate-500">Select a patient first.</p>}
        {error && phase === "idle" && <p className="mt-2 text-sm text-red-600">{error}</p>}
      </Section>

      {phase !== "idle" && (
        <Section title={fileName}>
          <ol className="space-y-2 text-sm">
            <Step state={phase === "uploading" ? "active" : "done"} text={`Uploading... ${phase === "uploading" ? uploadPct + "%" : "100%"}`} />
            {SERVER_STEPS.map((text, i) => (
              <Step key={text} text={text}
                state={phase === "uploading" || phase === "error" ? "todo" : phase === "processing" ? (i < stepIndex ? "done" : i === stepIndex ? "active" : "todo") : "done"} />
            ))}
            {phase === "done" && <Step state="done" text="Done. The report is now waiting for the doctor to check it" />}
            {phase === "error" && <Step state="error" text="Analysis failed" />}
          </ol>
          {phase === "error" && (
            <div className="mt-4 rounded-xl border border-red-200 bg-red-50 p-4 text-red-700">
              <p className="font-medium">{error}</p>
              <p className="mt-1 text-sm">This report was not saved.</p>
            </div>
          )}
          {phase === "done" && result && (
            <div className="mt-4 space-y-2 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-emerald-800">
              <p className="font-medium">
                {result.parameter_count > 0
                  ? `${result.parameter_count} test results were found and saved for ${result.patient_name}`
                  : `The ${result.report_type_label.split(" (")[0].toLowerCase()} was read and saved for ${result.patient_name}`}
                {" "}({result.processing_method === "ocr" ? "read with OCR" : "text read directly"}).
              </p>
              {result.warnings.map((w) => <p key={w} className="rounded-lg bg-amber-50 p-2 text-sm text-amber-900"><b>Please check:</b> {w}</p>)}
              <Link to={`/employee/reports/${result.id}`} className="inline-block text-sm font-medium text-brand-700">View upload status →</Link>
            </div>
          )}
        </Section>
      )}
    </div>
  );
}

function Step({ state, text }) {
  const icon = { done: <CheckCircle2 className="text-brand-600" size={18} />, active: <Loader2 className="animate-spin text-brand-600" size={18} />,
    todo: <Circle className="text-slate-300" size={18} />, error: <XCircle className="text-red-600" size={18} /> }[state];
  return <li className={`flex items-center gap-2 ${state === "todo" ? "text-slate-400" : "text-slate-700"}`}>{icon}{text}</li>;
}
