import { AlertTriangle } from "lucide-react";

// The patient the screen is about: it stays under the top bar while the page scrolls, so the doctor always sees who this is and the allergies (in red).
export default function PatientBanner({ name, age, gender, uhid, allergies, children }) {
  const facts = [uhid, age != null && age !== "" ? `${age} y` : null, gender].filter(Boolean).join(" · ");
  return (
    <header data-patient-banner className="sticky top-[calc(var(--height-appbar)+var(--safe-top))] z-10 -mx-3 border-b border-slate-200 bg-white/95 px-3 py-2 shadow-card backdrop-blur-sm sm:-mx-4 sm:px-4 lg:-mx-6 lg:px-6 xl:-mx-8 xl:px-8 [@media(max-height:32rem)]:static">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
        <h1 className="min-w-0 truncate text-lg font-extrabold text-slate-900 sm:text-xl">{name}</h1>
        <p className="num text-sm text-slate-700">{facts}</p>
        {allergies ? (
          <p role="alert" className="inline-flex max-w-full items-center gap-1.5 rounded-full bg-red-100 px-3 py-1 text-sm font-bold text-red-800"><AlertTriangle size={15} className="shrink-0" aria-hidden="true" /><span className="min-w-0 break-words">Allergies: {allergies}</span></p>
        ) : <p className="text-sm text-slate-600">No allergies recorded</p>}
        {children && <div className="ml-auto flex flex-wrap gap-2">{children}</div>}
      </div>
    </header>
  );
}
