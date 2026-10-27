// The bill (invoice) a customer receives. The same view is used on screen and for printing.
import { Printer } from "lucide-react";
import Barcode from "./Barcode";
import { printAs } from "../utils/printTitle";
import { Button, fmtDate, fmtUtc } from "./ui";

export const money = (n) => `₹${(Number(n) || 0).toFixed(2)}`;
const METHOD = { CASH: "Cash", UPI: "UPI", CARD: "Card" };

export default function BillView({ bill, onClose, closeLabel = "Close" }) {
  return (
    <div className="space-y-4">
      <div className="print-area rounded-3xl border-2 border-slate-300 bg-white p-6 text-slate-900">
        <div className="text-center">
          <p className="text-2xl font-extrabold">{bill.shop_name}</p>
          <p className="text-sm text-slate-600">Medical bill / Tax invoice</p>
        </div>
        <div className="mt-4 grid gap-1 border-y border-dashed border-slate-400 py-3 text-base sm:grid-cols-2">
          <p><b>Bill no:</b> {bill.bill_number}</p>
          <p className="sm:text-right"><b>Date:</b> {fmtUtc(bill.created_at)}</p>
          <p><b>Customer:</b> {bill.customer_name || "Walk-in customer"}{bill.customer_phone ? ` (${bill.customer_phone})` : ""}</p>
          <p className="sm:text-right"><b>Payment:</b> {METHOD[bill.payment_method] || bill.payment_method}</p>
          {bill.prescription_code && <p><b>Prescription:</b> {bill.prescription_code}</p>}
        </div>

        <div className="overflow-x-auto">
          <table className="mt-3 w-full min-w-[520px] text-left text-sm">
            <thead className="border-b-2 border-slate-400">
              <tr><th className="py-2">Medicine</th><th>Batch</th><th>Expiry</th><th className="text-right">Qty</th><th className="text-right">Rate</th><th className="text-right">GST</th><th className="text-right">Amount</th></tr>
            </thead>
            <tbody>
              {bill.items.map((i, n) => (
                <tr key={n} className="border-b border-slate-200">
                  <td className="py-2 font-semibold">{i.medicine_name}</td>
                  <td>{i.batch_number || "-"}</td>
                  <td>{i.expiry_date ? fmtDate(i.expiry_date) : "-"}</td>
                  <td className="text-right">{i.quantity}</td>
                  <td className="text-right">{money(i.unit_price)}</td>
                  <td className="text-right">{i.gst_percent}%</td>
                  <td className="text-right font-semibold">{money(i.amount)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <dl className="ml-auto mt-4 w-full max-w-xs space-y-1 text-base">
          <Row label="Amount before GST" value={money(bill.subtotal)} />
          <Row label="GST" value={money(bill.tax)} />
          {bill.discount > 0 && <Row label="Discount" value={`- ${money(bill.discount)}`} />}
          <div className="flex justify-between border-t-2 border-slate-900 pt-2 text-xl font-extrabold"><dt>Total to pay</dt><dd>{money(bill.total)}</dd></div>
        </dl>

        <div className="mt-5 flex flex-col items-center gap-1 border-t border-dashed border-slate-400 pt-4 text-center">
          <Barcode value={bill.bill_number} height={40} width={1.6} />
          <p className="text-sm text-slate-600">Served by {bill.staff_name}. Thank you, get well soon!</p>
          <p className="text-xs text-slate-500">Medicines can be returned only with this bill.</p>
        </div>
      </div>

      <div className="no-print flex flex-wrap gap-3">
        <Button onClick={() => printAs(bill.customer_name || "Walk-in customer", bill.bill_number, "Bill")}><Printer size={20} /> Print this bill</Button>
        {onClose && <Button variant="secondary" onClick={onClose}>{closeLabel}</Button>}
      </div>
    </div>
  );
}

const Row = ({ label, value }) => <div className="flex justify-between"><dt className="text-slate-600">{label}</dt><dd className="font-semibold">{value}</dd></div>;
