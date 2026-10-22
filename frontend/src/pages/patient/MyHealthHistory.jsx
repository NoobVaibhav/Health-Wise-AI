// "My health history": the patient can READ the permanent medical history their doctors keep, and print the emergency card.
// Only doctors can change it. If something is wrong or has changed, the patient tells the doctor.
import { Link } from "react-router-dom";
import { Lock, Printer } from "lucide-react";
import useFetch from "../../hooks/useFetch";
import { getMyHistory } from "../../services/historyApi";
import { Hero } from "../../components/Hero";
import { Section } from "../../components/HealthCard";
import { ErrorBox, Hint, Loading } from "../../components/Feedback";
import EmergencyCard from "../../components/EmergencyCard";
import { fmtUtc } from "../../components/ui";

export default function MyHealthHistory() {
  const { data, loading, error, reload } = useFetch(getMyHistory, []);
  if (loading && !data) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  const h = data.history;
  const empty = !h.saved_before;

  const more = [];
  if (h.family?.length) more.push(["Family history", h.family.map((x) => `${x.condition}${x.relation && x.relation !== "Family member" ? ` (${x.relation.toLowerCase()})` : ""}`).join("; ")]);
  else if (h.no_family_history) more.push(["Family history", "Nothing important"]);
  if (h.socioeconomic) more.push(["Work and home", h.socioeconomic]);
  if (h.immunization) more.push(["Vaccinations", h.immunization]);
  if (h.menstrual_obstetric) more.push(["Periods and pregnancies", h.menstrual_obstetric]);

  return (
    <div className="mx-auto max-w-4xl space-y-5">
      <Hero title="My health history" subtitle="This is the medical history your doctors keep for you: your medicines, allergies and illnesses. Any doctor who treats you can read it.">
        <Link to="/emergency-card" target="_blank" className="inline-flex min-h-12 items-center gap-2 rounded-xl border-2 border-white bg-white px-5 py-2.5 text-base font-bold text-brand-800 shadow-md"><Printer size={18} /> Print my emergency card</Link>
      </Hero>

      <p className="flex items-start gap-3 rounded-2xl border border-slate-200 bg-white p-4 text-slate-700">
        <Lock size={20} className="mt-0.5 shrink-0 text-brand-700" />
        <span><b>You can read this, but only your doctor can change it.</b> If a medicine, allergy or illness is missing or has changed, please tell your doctor at your next visit. You can also write what is happening when you book an appointment.</span>
      </p>

      {empty ? (
        <Section><p className="text-lg font-bold text-slate-900">Your doctor has not filled in your history yet.</p>
          <p className="mt-1 text-slate-600">It is written during your first visit. Bring your medicines (tablet strips or the old prescription) and any old reports. When it is ready, you will see it here.</p></Section>
      ) : (
        <>
          <EmergencyCard card={data.card} />
          {more.length > 0 && <Section title="More in your history"><dl className="space-y-2">{more.map(([k, v]) => <div key={k} className="flex flex-col gap-0.5 sm:flex-row sm:gap-4"><dt className="w-44 shrink-0 text-sm font-bold text-slate-500">{k}</dt><dd className="text-slate-800">{v}</dd></div>)}</dl></Section>}
          <Hint title="Last updated">{h.updated_at ? `${fmtUtc(h.updated_at)} by ${h.updated_by_name || "your doctor"}.` : ""} Your latest blood tests appear here after your doctor has checked your reports.</Hint>
        </>
      )}
    </div>
  );
}
