// Shows where a report is on its way: uploaded -> read by computer -> doctor checks -> ready for the patient.
import { Bot, CheckCircle2, Stethoscope, UploadCloud } from "lucide-react";

export default function ReportJourney({ report }) {
  const reviewed = report.doctor_review_status === "REVIEWED";
  const steps = [
    { icon: UploadCloud, title: "Uploaded", text: "The hospital received the report", done: true },
    { icon: Bot, title: "Read by computer", text: report.parameter_count > 0 ? `${report.parameter_count} test results found` : "The report text was read", done: report.processing_status === "ANALYZED" },
    { icon: Stethoscope, title: "Checked by doctor", text: reviewed ? `Reviewed by ${report.reviewed_by_name || "the doctor"}` : "Waiting for the doctor", done: reviewed, current: !reviewed },
    { icon: CheckCircle2, title: "Ready for the patient", text: reviewed ? "The patient can see the result" : "Shown after the doctor check", done: reviewed },
  ];
  return (
    <ol className="grid gap-3 sm:grid-cols-4">
      {steps.map((s, i) => {
        const Icon = s.icon;
        return (
          <li key={s.title} className={`relative rounded-2xl border p-3 ${s.done ? "border-emerald-200 bg-emerald-50" : s.current ? "border-amber-300 bg-amber-50" : "border-slate-200 bg-slate-50"}`}>
            <div className="flex items-center gap-2">
              <span className={`flex h-8 w-8 items-center justify-center rounded-full text-white ${s.done ? "bg-emerald-500" : s.current ? "pulse-ring bg-amber-500" : "bg-slate-300"}`}><Icon size={17} /></span>
              <span className="text-xs font-bold text-slate-400">STEP {i + 1}</span>
            </div>
            <p className="mt-2 font-bold text-slate-900">{s.title}</p>
            <p className="text-sm text-slate-600">{s.text}</p>
          </li>
        );
      })}
    </ol>
  );
}
