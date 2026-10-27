// The printable emergency card (no menus, so it prints on one clean page).
import { Link } from "react-router-dom";
import { Printer } from "lucide-react";
import useFetch from "../../hooks/useFetch";
import { getMyHistory } from "../../services/historyApi";
import EmergencyCard from "../../components/EmergencyCard";
import { printAs } from "../../utils/printTitle";
import { ErrorBox, Loading } from "../../components/Feedback";

export default function EmergencyCardPage() {
  const { data, loading, error, reload } = useFetch(getMyHistory, []);
  if (loading) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  return (
    <div className="mx-auto max-w-3xl p-4 print:p-0">
      <div className="mb-4 flex items-center justify-between print:hidden">
        <Link to="/patient/health-history" className="text-sm font-semibold text-brand-700 hover:underline">Back to my health history</Link>
        <button onClick={() => printAs(data.card.name, "Emergency card")} className="inline-flex items-center gap-2 rounded-xl bg-brand-700 px-4 py-2.5 font-bold text-white"><Printer size={16} /> Print this card</button>
      </div>
      <div className="print-area print-compact">
        <p className="mb-2 text-center text-sm font-extrabold uppercase tracking-widest text-slate-500">Medical emergency card</p>
        <EmergencyCard card={data.card} />
      </div>
    </div>
  );
}
