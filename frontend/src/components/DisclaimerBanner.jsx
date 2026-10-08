import { ShieldCheck } from "lucide-react";

export const DISCLAIMER =
  "HealthWise AI provides AI-assisted educational analysis of uploaded health reports. It is not a diagnostic system. AI analysis must be reviewed by a qualified healthcare professional. Prescriptions are created only by authorized doctors.";

// Always visible, but calm: it should inform, not scare.
export default function DisclaimerBanner() {
  return (
    <div className="mb-5 flex items-start gap-2.5 rounded-2xl border border-amber-200/80 bg-amber-50/80 px-4 py-2.5 text-xs leading-relaxed text-amber-900">
      <ShieldCheck className="mt-0.5 shrink-0 text-amber-600" size={16} />
      <p>{DISCLAIMER}</p>
    </div>
  );
}
