// "My health history": the patient fills in the medicines, allergies, illnesses and habits once, and keeps it up to date.
// A doctor at any hospital can then see it quickly (here, or on the printed emergency card).
import { Link } from "react-router-dom";
import { useState } from "react";
import { CheckCircle2, Printer } from "lucide-react";
import useFetch from "../../hooks/useFetch";
import { getMyHistory, saveMyHistory } from "../../services/historyApi";
import { getErrorMessage } from "../../services/api";
import { Hero } from "../../components/Hero";
import { Hint, ErrorBox, Loading } from "../../components/Feedback";
import HistoryForm from "../../components/HistoryForm";
import { useToast } from "../../components/Toast";

export default function MyHealthHistory() {
  const toast = useToast();
  const { data, loading, error, reload, setData } = useFetch(getMyHistory, []);
  const [saving, setSaving] = useState(false);
  if (loading && !data) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;

  const save = async (payload) => {
    setSaving(true);
    try { const fresh = await saveMyHistory(payload); setData(fresh); toast("Your health history was saved"); window.scrollTo({ top: 0, behavior: "smooth" }); }
    catch (e) { throw new Error(getErrorMessage(e)); } finally { setSaving(false); }
  };

  return (
    <div className="mx-auto max-w-4xl space-y-5">
      <Hero title="My health history" subtitle="Fill this in once and keep it up to date. If you ever need a doctor in a new hospital, they can see your medicines, allergies and illnesses at once.">
        <Link to="/emergency-card" target="_blank" className="inline-flex min-h-12 items-center gap-2 rounded-xl border-2 border-white bg-white px-5 py-2.5 text-base font-bold text-brand-800 shadow-md"><Printer size={18} /> Print my emergency card</Link>
      </Hero>

      <div className="rounded-3xl border border-slate-200/70 bg-white p-5 shadow-sm">
        <div className="mb-2 flex items-center justify-between"><p className="font-extrabold text-slate-900">{data.completeness.percent}% complete</p>
          <p className="text-sm text-slate-500">{data.history.saved_before ? "Saved" : "Not saved yet"}</p></div>
        <div className="h-3 overflow-hidden rounded-full bg-slate-200"><div className="h-full rounded-full bg-emerald-500 transition-all" style={{ width: `${data.completeness.percent}%` }} /></div>
        <div className="mt-3 flex flex-wrap gap-2">{data.completeness.parts.map((p) => (
          <span key={p.name} className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-bold ${p.done ? "bg-emerald-100 text-emerald-800" : "bg-slate-100 text-slate-500"}`}>{p.done && <CheckCircle2 size={12} />}{p.name}</span>
        ))}</div>
      </div>

      <Hint title="Your answers are private">Only you and the doctors who treat you can see this. Every time a doctor opens it, it is written in the activity log. If you do not know an answer, leave it empty. You can come back and change it at any time.</Hint>

      <HistoryForm initial={data.history} onSave={save} saving={saving} saveLabel="Save my health history" />
    </div>
  );
}
