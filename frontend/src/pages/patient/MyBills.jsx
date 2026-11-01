// A patient's own bills and receipts (final invoices only).
import { ReceiptText } from "lucide-react";
import useFetch from "../../hooks/useFetch";
import { getHospitalProfile } from "../../services/hospitalApi";
import { getMyInvoices, getReceipt } from "../../services/financeApi";
import { printInvoice, printReceipt } from "../../utils/printDocument";
import { Section } from "../../components/HealthCard";
import { EmptyState, ErrorBox, Loading, PageTitle } from "../../components/Feedback";
import { Button, fmtUtc } from "../../components/ui";

const rupee = (n) => `Rs ${Number(n || 0).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

export default function MyBills() {
  const { data, loading, error, reload } = useFetch(getMyInvoices);
  if (loading && !data) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  return (
    <div className="space-y-5">
      <PageTitle title="My bills" subtitle="Your invoices and the receipts of what you paid." icon={ReceiptText} />
      {data.length === 0 ? <EmptyState message="No bill yet" hint="Your bills appear here after the hospital makes them." icon={ReceiptText} /> : data.map((i) => (
        <Section key={i.id}>
          <div className="flex flex-wrap items-center justify-between gap-2"><p className="font-bold">{i.number} <span className="text-sm font-normal text-slate-500">{fmtUtc(i.finalised_at)}</span></p><span className={`font-bold ${i.balance > 0 ? "text-red-700" : "text-emerald-700"}`}>{i.balance > 0 ? `To pay ${rupee(i.patient_payable - (i.paid - i.refunded) > 0 ? Math.min(i.balance, i.patient_payable - (i.paid - i.refunded)) : 0)}` : "Paid"}</span></div>
          <ul className="my-2 text-sm text-slate-700">{i.lines.map((l) => <li key={l.id} className="flex justify-between"><span>{l.description} x {l.quantity}</span><span>{rupee(l.amount + l.tax)}</span></li>)}</ul>
          <p className="text-sm text-slate-600">Total {rupee(i.total)}{i.discount ? ` after a discount of ${rupee(i.discount)}` : ""}. Paid {rupee(i.paid)}.{i.insurer_approved ? ` Your insurer approved ${rupee(i.insurer_approved)}.` : ""}</p>
          <div className="mt-2 flex flex-wrap gap-2"><Button variant="secondary" onClick={async () => printInvoice(i, await getHospitalProfile().catch(() => ({})))}>Print the bill</Button>
            {i.payments.map((p) => <Button key={p.id} variant="soft" onClick={async () => printReceipt(await getReceipt(p.id))}>Receipt {p.receipt_number}</Button>)}</div>
        </Section>))}
    </div>
  );
}
