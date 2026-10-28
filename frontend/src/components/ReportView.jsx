// Shows one report of ANY kind (lab table, scan, ECG, summary ...). Used by every role; the BACKEND decides what is
// included (patients get no analysis until a doctor has reviewed it, employees never get clinical content).
import { useNavigate } from "react-router-dom";
import { useState } from "react";
import { Bot, FileDown, Hourglass } from "lucide-react";
import ReportPrintSheet from "./ReportPrintSheet";
import SummaryPoints from "./SummaryPoints";
import { AtAGlance, CopySummary, DownloadMenu } from "./ReportActions";
import { Section } from "./HealthCard";
import ParameterTable from "./ParameterTable";
import ReportJourney from "./ReportJourney";
import KeyNumbers from "./KpiPanel";
import DeleteReportButton from "./DeleteReport";
import { DoctorInsights, KeyFindings, PatientTips } from "./InsightsPanel";
import { StatusPill } from "./StatusBadge";
import { Hint } from "./Feedback";
import { Button, fmtDate, fmtUtc, fmtUtcDate } from "./ui";
import { openReportFile } from "../services/reportApi";
import { getErrorMessage } from "../services/api";
import { useToast } from "./Toast";
import { useAuth } from "../context/AuthContext";

export default function ReportView({ report, canOpenFile = true, onUseAsAdvice, onChanged }) {
  const toast = useToast();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [sheetMode, setSheetMode] = useState("full");
  const open = () => openReportFile(report.id).catch((e) => toast(getErrorMessage(e), "error"));
  const c = report.counts;
  const outside = c.ABOVE_RANGE + c.BELOW_RANGE;
  const isDoctor = user.role === "DOCTOR";
  const isPatient = user.role === "PATIENT";
  return (
    <div className="space-y-5">
      <ReportPrintSheet report={report} role={user.role} short={sheetMode === "short"} />
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-slate-900 md:text-3xl">{report.filename}</h1>
          <p className="text-base text-slate-600">
            Patient: <b className="text-slate-700">{report.patient_name}</b> ({report.patient_code}) - Test date: {report.report_date ? fmtDate(report.report_date) : "not printed on the report"} -
            Added on {fmtUtcDate(report.uploaded_at)} by {report.uploaded_by_name}
          </p>
          <p className="mt-1"><span className="rounded-full bg-brand-100 px-3 py-1 text-xs font-bold text-brand-800">{report.report_type_label}</span></p>
        </div>
        <div className="flex flex-wrap gap-2">
          {(isDoctor || isPatient) && report.analysis_visible && <><CopySummary text={report.ai_summary} /><DownloadMenu report={report} setMode={setSheetMode} /></>}
          {canOpenFile && <Button variant="secondary" onClick={open}><FileDown size={18} /> View the original report</Button>}
          <DeleteReportButton report={report} onDeleted={() => navigate(-1)} />
        </div>
      </div>

      {(isDoctor || isPatient) && <AtAGlance report={report} />}

      <ReportJourney report={report} />

      {report.warnings?.map((w) => (
        <div key={w} className="rounded-2xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900"><b>Please check:</b> {w}</div>
      ))}

      {report.doctor_review_status === "REVIEWED" && (
        <Section title="What the doctor said about this report">
          <div className="rounded-2xl border border-emerald-200 bg-emerald-50/60 p-4">
            <div className="mb-1 flex flex-wrap items-center gap-2">
              <span className="rounded-full bg-emerald-600 px-3 py-1 text-xs font-bold text-white">Checked by Doctor</span>
              <StatusPill value={report.review_decision} />
              <span className="text-xs text-slate-500">{report.reviewed_by_name} - {fmtUtc(report.reviewed_at)}</span>
            </div>
            <p className="text-slate-700">{report.review_comment || "The doctor looked at the computer analysis and agreed with it."}</p>
          </div>
        </Section>
      )}

      {report.analysis_visible ? (
        <>
          <Section title="In short">
            <p className="mb-2 inline-flex items-center gap-1 rounded-full bg-violet-100 px-3 py-1 text-xs font-bold text-violet-800"><Bot size={13} /> Written by the computer, not by a doctor. A doctor will check it.</p>
            <SummaryPoints report={report} />
            {!report.is_narrative && (
              <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
                <Count n={c.WITHIN_RANGE} label="Normal" color="text-emerald-600" />
                <Count n={c.ABOVE_RANGE} label="Too high" color="text-amber-600" />
                <Count n={c.BELOW_RANGE} label="Too low" color="text-sky-600" />
                <Count n={c.UNKNOWN} label="No normal range" color="text-slate-500" />
              </div>
            )}
            {outside > 0 && isPatient && <div className="mt-4"><Hint title="Is a result outside the range a problem?">A result outside the normal range is not a diagnosis. Many things can change a result. Please talk to your doctor about it.</Hint></div>}
          </Section>

          <div id="report-results" className="scroll-mt-4" />
          {(isDoctor || isPatient) && <KeyNumbers report={report} />}

          {isDoctor && <DoctorInsights report={report} onUseAsAdvice={onUseAsAdvice} onChanged={onChanged} />}

          {report.is_narrative
            ? <KeyFindings findings={report.insights?.key_findings} />
            : <Section title="All test results"><ParameterTable parameters={report.parameters} /></Section>}

          {isPatient && <PatientTips insights={report.insights} />}
        </>
      ) : (
        <Section>
          <div className="flex items-center gap-4 py-4">
            <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-amber-100 text-amber-600"><Hourglass size={28} /></span>
            <div>
              <p className="text-lg font-bold text-slate-900">
                {report.display_status === "WAITING_FOR_DOCTOR" ? "Waiting for the doctor to check this report" : "Medical content is not shown for your role"}
              </p>
              <p className="text-slate-500">
                {report.display_status === "WAITING_FOR_DOCTOR" ? "The results and tips will appear here as soon as the doctor has looked at them. This keeps you safe from confusing numbers." : "Only the doctor and the patient can see the medical content of a report."}
              </p>
            </div>
          </div>
        </Section>
      )}
    </div>
  );
}

const Count = ({ n, label, color }) => (
  <div className="rounded-2xl bg-slate-50 p-3 text-center">
    <p className={`text-3xl font-extrabold ${color}`}>{n}</p>
    <p className="text-sm font-semibold text-slate-600">{label}</p>
  </div>
);
