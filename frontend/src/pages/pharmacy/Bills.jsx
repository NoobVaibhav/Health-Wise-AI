// All bills made by the shop: today's sales at the top, then every bill (open one to see it or print it again).
import { useState } from "react";
import { Link } from "react-router-dom";
import { ReceiptText, Search } from "lucide-react";
import useFetch from "../../hooks/useFetch";
import { getSale, getSalesSummary, listSales } from "../../services/pharmacyApi";
import { getErrorMessage } from "../../services/api";
import HealthCard, { Section } from "../../components/HealthCard";
import BillView, { money } from "../../components/BillView";
import { EmptyState, ErrorBox, Loading, PageTitle } from "../../components/Feedback";
import { Button, Modal, fmtUtc, inputClass } from "../../components/ui";
import { useToast } from "../../components/Toast";

const METHOD = { CASH: "Cash", UPI: "UPI", CARD: "Card" };

export default function Bills() {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(null);
  const toast = useToast();
  const summary = useFetch(getSalesSummary, []);
  const { data, loading, error, reload } = useFetch(() => listSales(q), [q]);

  const show = async (id) => {
    try { setOpen(await getSale(id)); } catch (e) { toast(getErrorMessage(e), "error"); }
  };

  const s = summary.data;
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <PageTitle title="Bills and sales" subtitle="Every bill you have made, newest first." icon={ReceiptText} />
        <Link to="/pharmacy/billing" className="inline-flex min-h-11 items-center gap-2 rounded-xl border-2 border-emerald-800 bg-emerald-600 px-5 py-2.5 text-base font-bold text-white shadow-md hover:bg-emerald-700">Sell medicine and make a bill</Link>
      </div>

      {s && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <HealthCard title="Bills today" icon={ReceiptText} value={s.bills_today} />
          <HealthCard title="Sales today" icon={ReceiptText} tone="emerald" value={money(s.sales_today)} />
          <HealthCard title="Cash / UPI / Card" icon={ReceiptText} tone="sky" value={`${money(s.by_method.CASH)} / ${money(s.by_method.UPI)} / ${money(s.by_method.CARD)}`} />
          <HealthCard title="Sold the most today" icon={ReceiptText} tone="amber" value={s.top_medicines[0]?.medicine_name || "-"} sub={s.top_medicines[0] ? `${s.top_medicines[0].quantity} sold` : "No sales yet"} />
        </div>
      )}

      <div className="relative w-full max-w-md">
        <Search className="pointer-events-none absolute left-3.5 top-3.5 text-slate-500" size={20} />
        <input className={`${inputClass} pl-11`} placeholder="Type bill number, customer name or phone" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>

      {loading && !data ? <Loading /> : error ? <ErrorBox message={error} onRetry={reload} /> : data.length === 0 ? (
        <EmptyState message={q ? "No bill matches your search" : "No bills yet"} hint={q ? undefined : 'Press "Sell medicine and make a bill" to make the first one.'} icon={ReceiptText} />
      ) : (
        <Section>
          <ul className="divide-y">
            {data.map((b) => (
              <li key={b.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
                <div>
                  <p className="text-lg font-extrabold text-slate-900">{b.bill_number}</p>
                  <p className="text-base text-slate-600">{b.prescription_code ? `Prescription ${b.prescription_code} - ` : "Without prescription - "}{b.customer_name || "Walk-in customer"} - {b.item_count} item{b.item_count === 1 ? "" : "s"} - {METHOD[b.payment_method] || b.payment_method} - {fmtUtc(b.created_at)}</p>
                </div>
                <div className="flex items-center gap-3">
                  <p className="text-xl font-extrabold text-slate-900">{money(b.total)}</p>
                  <Button variant="secondary" onClick={() => show(b.id)}>View / Print</Button>
                </div>
              </li>
            ))}
          </ul>
        </Section>
      )}

      {open && <Modal title={`Bill ${open.bill_number}`} onClose={() => setOpen(null)} wide><BillView bill={open} onClose={() => setOpen(null)} /></Modal>}
    </div>
  );
}
