// Sell medicine WITHOUT a prescription (walk-in customer) and make the bill.
// (Medicine given on a doctor's prescription is billed from the "Prescriptions" page, after it is given.)
// The server decides the real price, takes the stock out (earliest expiry first) and numbers the bill.
import { useEffect, useMemo, useRef, useState } from "react";
import { Minus, Plus, ReceiptText, ScanBarcode, Trash2 } from "lucide-react";
import { Link } from "react-router-dom";
import useFetch from "../../hooks/useFetch";
import { createSale, listInventory, lookupBarcode } from "../../services/pharmacyApi";
import { getErrorMessage } from "../../services/api";
import Autocomplete from "../../components/Autocomplete";
import BillView, { money } from "../../components/BillView";
import { ErrorBox, PageTitle } from "../../components/Feedback";
import { Button, Field, Input, inputClass } from "../../components/ui";
import { useToast } from "../../components/Toast";
import ActionBar from "../../components/ActionBar";
import BarcodeScan from "../../components/BarcodeScan";
import useLayoutMode from "../../hooks/useLayoutMode";

const METHODS = [["CASH", "Cash"], ["UPI", "UPI"], ["CARD", "Card"]];

const Step = ({ n, title, children }) => (
  <section className="rounded-3xl border-2 border-slate-200 bg-white p-5 shadow-sm">
    <h2 className="mb-3 flex items-center gap-3 text-xl font-extrabold text-slate-900">
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-brand-700 text-lg font-extrabold text-white">{n}</span>
      {title}
    </h2>
    {children}
  </section>
);

export default function Billing() {
  const toast = useToast();
  const { split } = useLayoutMode();
  const scanBox = useRef(null);
  const [code, setCode] = useState("");
  const [lines, setLines] = useState([]);                 // { barcode, name, price, gst, available, qty }
  const [customer, setCustomer] = useState({ name: "", phone: "" });
  const [method, setMethod] = useState("CASH");
  const [discount, setDiscount] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [bill, setBill] = useState(null);
  const [search, setSearch] = useState("");
  const stock = useFetch(() => listInventory(""), []);

  const focusScan = () => setTimeout(() => scanBox.current?.focus(), 50);
  useEffect(() => { focusScan(); }, [bill]);

  const nameOptions = useMemo(() => {
    const seen = new Map();
    for (const i of stock.data || []) if (i.barcode && i.quantity > 0 && !seen.has(i.barcode)) seen.set(i.barcode, { name: i.medicine_name, hint: `${i.quantity} in stock`, barcode: i.barcode });
    return [...seen.values()];
  }, [stock.data]);

  const addProduct = (found) => {
    setError("");
    setMessage("");
    if (found.available <= 0) { setError(`${found.medicine_name} is not in stock (or is expired).`); return false; }
    if (found.unit_price == null) { setError(`No price is set for ${found.medicine_name}. Set the price in Medicine stock first.`); return false; }
    setLines((all) => {
      const at = all.findIndex((l) => l.barcode === found.barcode);
      if (at >= 0) {
        const next = [...all];
        if (next[at].qty + 1 > found.available) setError(`Only ${found.available} of ${found.medicine_name} in stock.`);
        next[at] = { ...next[at], qty: Math.min(next[at].qty + 1, found.available), available: found.available };
        return next;
      }
      return [...all, { barcode: found.barcode, name: found.medicine_name, price: found.unit_price, gst: found.gst_percent || 0, available: found.available, qty: 1 }];
    });
    return true;
  };

  const scan = async (value) => {
    const wanted = (value ?? code).trim();
    if (!wanted) return;
    setCode("");
    try {
      const found = await lookupBarcode(wanted);
      if (addProduct(found)) setMessage(`Added: ${found.medicine_name}`);
    } catch (e) {
      setError(e?.response?.status === 404 ? `Barcode ${wanted} is not in your stock. Add it first in "Medicine stock".` : getErrorMessage(e));
    }
    focusScan();
  };

  const setQty = (barcode, qty) => setLines((all) => all.map((l) => {
    if (l.barcode !== barcode) return l;
    if (Number(qty) > l.available) setError(`Only ${l.available} of ${l.name} in stock.`);
    return { ...l, qty: Math.max(1, Math.min(Number(qty) || 1, l.available)) };
  }));
  const remove = (barcode) => setLines((all) => all.filter((l) => l.barcode !== barcode));

  // totals are a preview: the server calculates the real bill
  const subtotal = lines.reduce((s, l) => s + l.qty * l.price, 0);
  const tax = lines.reduce((s, l) => s + (l.qty * l.price * l.gst) / 100, 0);
  const off = Math.min(Number(discount) || 0, subtotal + tax);
  const total = subtotal + tax - off;

  const generate = async () => {
    setBusy(true);
    setError("");
    try {
      const made = await createSale({
        customer_name: customer.name || null, customer_phone: customer.phone || null, payment_method: method,
        discount: Number(discount) || 0, items: lines.map((l) => ({ barcode: l.barcode, quantity: l.qty })),
      });
      setBill(made);
      toast(`Bill ${made.bill_number} is ready`);
      stock.reload();
    } catch (e) { setError(getErrorMessage(e)); } finally { setBusy(false); }
  };

  const newSale = () => { setBill(null); setLines([]); setCustomer({ name: "", phone: "" }); setDiscount(""); setMethod("CASH"); setMessage(""); setError(""); };

  if (bill) {
    return (
      <div className="mx-auto max-w-3xl space-y-4">
        <PageTitle title="Bill is ready" subtitle="The stock was reduced automatically. Print the bill and hand it to the customer." icon={ReceiptText} />
        <BillView bill={bill} onClose={newSale} closeLabel="Start a new sale" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl space-y-5">
      <PageTitle title="Sell medicine (without prescription)" subtitle="For customers who just walk in. Follow the 3 steps, then print the bill." icon={ReceiptText} />
      <p className="rounded-2xl border-2 border-violet-200 bg-violet-50 p-3 text-base text-violet-900">
        Medicine from a <b>doctor's prescription</b>? Open it in <Link to="/pharmacy/prescriptions" className="font-bold underline">Prescriptions</Link>, give the medicine there, and then make its bill on the same page.
      </p>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_24rem] lg:items-start">
        <div className="min-w-0 space-y-5">
      <Step n={1} title="Scan the medicine">
        <label htmlFor="scan" className="flex items-center gap-2 text-base font-semibold text-slate-700"><ScanBarcode size={22} className="text-brand-700" /> Click the box and scan the barcode on the pack</label>
        <div className="mt-2 flex flex-wrap gap-2">
          <input id="scan" ref={scanBox} autoFocus autoComplete="off" enterKeyHint="search" value={code} onChange={(e) => setCode(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); scan(); } }}
            placeholder="Scan here (or type the code and press Enter)"
            className={`${inputClass} min-w-0 flex-1 border-2 border-brand-600 !py-3.5 text-lg`} />
          <Button onClick={() => scan()} disabled={!code.trim()} className="min-w-24">Add</Button>
          <BarcodeScan onDetect={(c) => scan(c)} />
        </div>
        <div className="mt-4">
          <Field label="No barcode on the pack? Search by name">
            <Autocomplete options={nameOptions} value={search} onChange={setSearch} placeholder="Type a few letters of the medicine name"
              onPick={(name) => { const hit = nameOptions.find((o) => o.name === name); setSearch(""); if (hit) scan(hit.barcode); }} />
          </Field>
        </div>
        {message && <p className="mt-3 rounded-xl bg-emerald-50 p-3 text-base font-semibold text-emerald-800">{"✓ "}{message}</p>}
        {error && <div className="mt-3"><ErrorBox message={error} /></div>}
      </Step>

      <Step n={2} title={`Check the list (${lines.length})`}>
        {lines.length === 0 ? (
          <p className="rounded-2xl bg-slate-50 py-8 text-center text-lg text-slate-500">Nothing added yet. Scan the first medicine above.</p>
        ) : (
          <ul className="space-y-3">
            {lines.map((l) => (
              <li key={l.barcode} className="grid items-center gap-3 rounded-2xl border-2 border-slate-200 p-3 sm:grid-cols-[1fr_auto_auto_auto]">
                <div className="min-w-0">
                  <p className="text-lg font-extrabold text-slate-900">{l.name}</p>
                  <p className="text-base text-slate-600">{money(l.price)} each{l.gst ? ` + ${l.gst}% GST` : ""} - {l.available} in stock</p>
                </div>
                <div className="flex items-center gap-1" role="group" aria-label={`Quantity of ${l.name}`}>
                  <button type="button" aria-label={`One less ${l.name}`} onClick={() => setQty(l.barcode, l.qty - 1)} className="flex h-11 w-11 items-center justify-center rounded-xl border-2 border-brand-700 bg-white text-brand-800 hover:bg-brand-50"><Minus size={20} /></button>
                  <input aria-label={`Number of ${l.name}`} type="number" min={1} max={l.available} value={l.qty} onChange={(e) => setQty(l.barcode, e.target.value)} className="h-11 w-16 rounded-xl border-2 border-slate-400 text-center text-lg font-bold" />
                  <button type="button" aria-label={`One more ${l.name}`} onClick={() => setQty(l.barcode, l.qty + 1)} className="flex h-11 w-11 items-center justify-center rounded-xl border-2 border-brand-700 bg-white text-brand-800 hover:bg-brand-50"><Plus size={20} /></button>
                </div>
                <p className="min-w-24 text-right text-xl font-extrabold text-slate-900">{money(l.qty * l.price * (1 + l.gst / 100))}</p>
                <button type="button" aria-label={`Remove ${l.name}`} onClick={() => remove(l.barcode)} className="inline-flex h-11 items-center justify-center gap-1 rounded-xl border-2 border-red-600 bg-white px-3 text-base font-bold text-red-700 hover:bg-red-50"><Trash2 size={18} /> Remove</button>
              </li>
            ))}
          </ul>
        )}
      </Step>

        </div>
        <div className="lg:sticky lg:top-[calc(var(--height-appbar)+var(--safe-top)+0.75rem)]">
      <Step n={3} title="Take payment and make the bill">
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-1">
          <div className="space-y-3">
            <Field label="Customer name (optional)"><Input value={customer.name} onChange={(e) => setCustomer({ ...customer, name: e.target.value })} /></Field>
            <Field label="Customer phone (optional)"><Input type="tel" inputMode="tel" autoComplete="off" enterKeyHint="next" value={customer.phone} onChange={(e) => setCustomer({ ...customer, phone: e.target.value })} /></Field>
            <div>
              <p className="mb-1.5 text-sm font-semibold text-slate-700">How is the customer paying?</p>
              <div className="flex gap-2" role="group" aria-label="Payment method">
                {METHODS.map(([v, label]) => (
                  <button key={v} type="button" aria-pressed={method === v} onClick={() => setMethod(v)}
                    className={`min-h-12 flex-1 rounded-xl border-2 text-lg font-bold ${method === v ? "border-brand-800 bg-brand-700 text-white shadow" : "border-slate-400 bg-white text-slate-800 hover:bg-slate-50"}`}>{method === v ? "✓ " : ""}{label}</button>
                ))}
              </div>
            </div>
            <Field label="Discount in rupees (if any)"><Input type="number" inputMode="decimal" enterKeyHint="done" min={0} step="0.01" value={discount} onChange={(e) => setDiscount(e.target.value)} /></Field>
          </div>

          <div className="flex flex-col justify-between rounded-2xl bg-slate-50 p-5">
            <dl className="space-y-2 text-lg">
              <div className="flex justify-between"><dt className="text-slate-600">Amount before GST</dt><dd className="font-semibold">{money(subtotal)}</dd></div>
              <div className="flex justify-between"><dt className="text-slate-600">GST</dt><dd className="font-semibold">{money(tax)}</dd></div>
              {off > 0 && <div className="flex justify-between"><dt className="text-slate-600">Discount</dt><dd className="font-semibold">- {money(off)}</dd></div>}
              <div className="flex justify-between border-t-2 border-slate-900 pt-3 text-3xl font-extrabold"><dt>Total</dt><dd>{money(total)}</dd></div>
            </dl>
            <div className="mt-5 space-y-2">
              <Button onClick={generate} disabled={busy || lines.length === 0} className="w-full !border-emerald-800 !bg-emerald-600 !py-4 !text-xl hover:!bg-emerald-700">
                {busy ? "Making the bill..." : "✓ Generate bill"}
              </Button>
              {lines.length === 0 && <p className="text-center text-sm text-slate-500">Add at least one medicine to make a bill.</p>}
              {lines.length > 0 && <Button variant="secondary" onClick={newSale} className="w-full">Clear everything and start again</Button>}
            </div>
          </div>
        </div>
      </Step>
        </div>
      </div>
      {lines.length > 0 && !split && (
        <ActionBar status={<span className="num text-xl font-extrabold text-slate-900">Total {money(total)}</span>}>
          <Button onClick={generate} disabled={busy} className="!border-emerald-800 !bg-emerald-600 hover:!bg-emerald-700">{busy ? "Making the bill..." : "✓ Generate bill"}</Button>
        </ActionBar>
      )}
    </div>
  );
}
