import { useState } from "react";
import { ShieldCheck } from "lucide-react";

export const DISCLAIMER =
  "HealthWise AI provides AI-assisted educational analysis of uploaded health reports. It is not a diagnostic system. AI analysis must be reviewed by a qualified healthcare professional. Prescriptions are created only by authorized doctors.";

// Always visible, but calm: it should inform, not scare. On a phone it shows one line with a "More" button; the full text is always in the page.
export default function DisclaimerBanner() {
  const [more, setMore] = useState(false);
  return (
    <div className="mb-3 flex items-start gap-2.5 rounded-2xl border border-amber-200/80 bg-amber-50/80 px-3 py-2 text-xs leading-relaxed text-amber-900 md:mb-5 md:px-4 md:py-2.5">
      <ShieldCheck className="mt-0.5 shrink-0 text-amber-600" size={16} aria-hidden="true" />
      <p className={`min-w-0 flex-1 ${more ? "" : "max-sm:line-clamp-1"}`}>{DISCLAIMER}</p>
      <button type="button" onClick={() => setMore((m) => !m)} aria-expanded={more} className="-my-2 min-h-11 min-w-11 shrink-0 px-1 font-bold underline sm:hidden">{more ? "Less" : "More"}</button>
    </div>
  );
}
