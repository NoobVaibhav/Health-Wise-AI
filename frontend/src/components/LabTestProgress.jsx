// The progress of a patient's laboratory tests: for the patient (plain words) and for the doctor (with the result link).
import { Link } from "react-router-dom";
import { FlaskConical } from "lucide-react";
import useFetch from "../hooks/useFetch";
import { getMyTests, getPatientTests } from "../services/labApi";
import { markLabSeen } from "../services/diagnosticsApi";
import useSave from "../hooks/useSave";
import ResultTable from "./ResultTable";
import { Button } from "./ui";
import { Section } from "./HealthCard";
import { fmtUtc } from "./ui";

const TONE = { ORDERED: "bg-amber-100 text-amber-900", SAMPLE_COLLECTED: "bg-sky-100 text-sky-900", IN_PROGRESS: "bg-violet-100 text-violet-900", COMPLETED: "bg-emerald-100 text-emerald-900", REJECTED: "bg-red-100 text-red-900", CANCELLED: "bg-slate-200 text-slate-700" };

export default function LabTestProgress({ patientId, base }) {
  const doctor = patientId != null;
  const { data, reload } = useFetch(() => (doctor ? getPatientTests(patientId) : getMyTests()), [patientId]);
  const { busy, run } = useSave();
  if (!data || data.length === 0) return null;
  return (
    <Section title="Laboratory tests">
      <p className="-mt-2 mb-3 text-sm text-slate-500">{doctor ? "Tests advised for this patient and where each one is now." : "The tests your doctor asked for, and where each one is now."}</p>
      <ul className="divide-y divide-slate-100">
        {data.map((t) => (
          <li key={t.id} className="flex flex-wrap items-center justify-between gap-2 py-2.5">
            <div className="min-w-0">
              <p className="flex items-center gap-2 font-bold text-slate-900"><FlaskConical size={16} className="text-brand-600" />{t.test_name}{t.urgent && <span className="rounded-full bg-red-600 px-2 py-0.5 text-xs font-bold text-white">URGENT</span>}</p>
              <p className="text-sm text-slate-600">{doctor ? t.status_label : t.patient_message}{t.status === "REJECTED" && t.rejection_reason ? ` (${t.rejection_reason})` : ""}</p>
              <p className="text-xs text-slate-400">Advised on {t.ordered_on} by {t.doctor_name}{t.completed_at ? ` - result ${fmtUtc(t.completed_at)}` : ""}</p>
            </div>
            <div className="flex items-center gap-2">
              <span className={`rounded-full px-3 py-1 text-sm font-bold ${TONE[t.status]}`}>{doctor ? t.status_label : t.status === "COMPLETED" && t.result_reviewed ? "Result ready" : t.status_label}</span>
              {t.has_critical && doctor && t.result_status === "APPROVED" && <span className="rounded-full bg-red-600 px-2.5 py-0.5 text-xs font-bold text-white">Critical value</span>}
              {t.report_id && <Link to={`${base}/${t.report_id}`} className="text-sm font-bold text-brand-700 hover:underline">Open the result</Link>}
            </div>
            {t.results?.length > 0 && <div className="w-full pt-2"><ResultTable results={t.results} />
              {doctor && !t.doctor_seen_at && <Button className="mt-2" variant="secondary" disabled={busy} onClick={async () => { if (await run(() => markLabSeen(t.id), "Marked as seen: the patient can now see it")) reload(); }}>I have seen this result</Button>}</div>}
          </li>))}
      </ul>
    </Section>
  );
}
