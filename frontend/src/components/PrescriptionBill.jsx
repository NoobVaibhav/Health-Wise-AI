// "Step 2: make the bill" on the Give-medicine page. It bills the medicine that was already given for this prescription
// (the stock was reduced when the medicine was given, so making the bill does not touch the stock again).
import { useState } from "react";
import { ReceiptText } from "lucide-react";
import useFetch from "../hooks/useFetch";
import { createPrescriptionBill, getBillPreview, getSale } from "../services/pharmacyApi";
import { getErrorMessage } from "../services/api";
import BillView, { money } from "./BillView";
import { ErrorBox } from "./Feedback";
import { Button, Field, Input, Modal } from "./ui";
import { useToast } from "./Toast";

const METHODS = [["CASH", "Cash"], ["UPI", "UPI"], ["CARD", "Card"]];

export default function PrescriptionBill({ rx }) {
  const toast = useToast();
  const given = rx.items.reduce((s, i) => s + i.dispensed_quantity, 0);
  const { data: preview, loading, error, reload } = useFetch(() => getBillPreview(rx.id), [rx.id, given]);
  const [method, setMethod] = useState("CASH");
  const [discount, setDiscount] = useState("");
  const [phone, setPhone] = useState("");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState("");
  const [bill, setBill] = useState(null);

  const make = async () => {
    setBusy(true);
    setProblem("");
    try {
      const made = await createPrescriptionBill(rx.id, { payment_method: method, discount: Number(discount) || 0, customer_phone: phone || null });
      setBill(made);
      setDiscount("");
      toast(`Bill ${made.bill_number} is ready`);
      reload();
    } catch (e) { setProblem(getErrorMessage(e)); } finally { setBusy(false); }
  };
  const openOld = async (id) => { try { setBill(await getSale(id)); } catch (e) { toast(getErrorMessage(e), "error"); } };

  const lines = preview?.lines || [];
  const off = Math.min(Number(discount) || 0, preview?.total || 0);

  return (
    <section className="rounded-3xl border-2 border-emerald-300 bg-white p-5 shadow-sm">
      <h2 className="mb-3 flex items-center gap-3 text-xl font-extrabold text-slate-900">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-emerald-600 text-white"><ReceiptText size={20} /></span>
        Step 2: Make the bill
      </h2>

      {loading && !preview ? <p className="text-base text-slate-500">Checking what can be billed...</p> : error ? <ErrorBox message={error} onRetry={reload} /> : (
        <>
          {preview.problems.map((p) => <div key={p} className="mb-3"><ErrorBox message={p} /></div>)}

          {lines.length === 0 && preview.problems.length === 0 && (
            <p className="rounded-2xl bg-slate-50 p-4 text-base text-slate-700">
              {given === 0 ? "Give the medicine above first (Step 1). Then you can make its bill here." : "All the medicine that was given has been billed."}
            </p>
          )}

          {lines.length > 0 && (
            <div className="space-y-4">
              <div className="overflow-x-auto rounded-2xl border-2 border-slate-200">
                <table className="w-full min-w-[480px] text-left text-base">
                  <thead className="bg-slate-50 text-sm text-slate-600"><tr><th className="p-3">Medicine given</th><th>How many</th><th>Price</th><th className="pr-3 text-right">Amount</th></tr></thead>
                  <tbody>
                    {lines.map((l, n) => (
                      <tr key={n} className="border-t">
                        <td className="p-3 font-bold text-slate-900">{l.medicine_name}</td>
                        <td>{l.quantity}</td>
                        <td>{money(l.unit_price)}{l.gst_percent ? ` + ${l.gst_percent}% GST` : ""}</td>
                        <td className="pr-3 text-right font-extrabold">{money(l.amount)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-3">
                  <div>
                    <p className="mb-1.5 text-sm font-semibold text-slate-700">How is the patient paying?</p>
                    <div className="flex gap-2" role="group" aria-label="Payment method">
                      {METHODS.map(([v, label]) => (
                        <button key={v} type="button" aria-pressed={method === v} onClick={() => setMethod(v)}
                          className={`min-h-12 flex-1 rounded-xl border-2 text-lg font-bold ${method === v ? "border-brand-800 bg-brand-700 text-white shadow" : "border-slate-400 bg-white text-slate-800 hover:bg-slate-50"}`}>{method === v ? "✓ " : ""}{label}</button>
                      ))}
                    </div>
                  </div>
                  <Field label="Patient phone (optional)"><Input value={phone} onChange={(e) => setPhone(e.target.value)} /></Field>
                  <Field label="Discount in rupees (if any)"><Input type="number" min={0} step="0.01" value={discount} onChange={(e) => setDiscount(e.target.value)} /></Field>
                </div>
                <div className="flex flex-col justify-between rounded-2xl bg-emerald-50 p-5">
                  <dl className="space-y-2 text-lg">
                    <div className="flex justify-between"><dt className="text-slate-700">Amount before GST</dt><dd className="font-semibold">{money(preview.subtotal)}</dd></div>
                    <div className="flex justify-between"><dt className="text-slate-700">GST</dt><dd className="font-semibold">{money(preview.tax)}</dd></div>
                    {off > 0 && <div className="flex justify-between"><dt className="text-slate-700">Discount</dt><dd className="font-semibold">- {money(off)}</dd></div>}
                    <div className="flex justify-between border-t-2 border-slate-900 pt-3 text-3xl font-extrabold"><dt>Total</dt><dd>{money(preview.total - off)}</dd></div>
                  </dl>
                  <Button onClick={make} disabled={busy} className="mt-5 w-full !border-emerald-800 !bg-emerald-600 !py-4 !text-xl hover:!bg-emerald-700">
                    {busy ? "Making the bill..." : "✓ Make the bill"}
                  </Button>
                </div>
              </div>
              {problem && <ErrorBox message={problem} />}
            </div>
          )}

          {preview.bills.length > 0 && (
            <div className="mt-4 border-t pt-3">
              <p className="mb-2 text-sm font-bold text-slate-600">Bills already made for this prescription</p>
              <div className="flex flex-wrap gap-2">
                {preview.bills.map((b) => <Button key={b.id} variant="secondary" onClick={() => openOld(b.id)}>{b.bill_number} - View / Print</Button>)}
              </div>
            </div>
          )}
        </>
      )}

      {bill && <Modal title={`Bill ${bill.bill_number}`} onClose={() => setBill(null)} wide><BillView bill={bill} onClose={() => setBill(null)} /></Modal>}
    </section>
  );
}
