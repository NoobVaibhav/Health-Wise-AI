import { useEffect, useState } from "react";
import { Package, Pill, Plus, Printer, ScanBarcode, Search } from "lucide-react";
import useFetch from "../../hooks/useFetch";
import { listInventory, lookupBarcode, receiveStock, updateInventory } from "../../services/pharmacyApi";
import { getErrorMessage } from "../../services/api";
import Barcode from "../../components/Barcode";
import { money } from "../../components/BillView";
import { StockMeter } from "../../components/DataViews";
import { Button, Field, Input, Modal, Select, fmtDate, inputClass } from "../../components/ui";
import Autocomplete from "../../components/Autocomplete";
import { getMedicineOptions } from "../../services/catalogApi";
import { EmptyState, ErrorBox, Loading, PageTitle } from "../../components/Feedback";
import { printAs } from "../../utils/printTitle";
import { useToast } from "../../components/Toast";

// Medicine stock as cards: the bar shows how much is left, and the expiry line is in plain words.
export default function Inventory() {
  const [q, setQ] = useState("");
  const { data, loading, error, reload } = useFetch(() => listInventory(q), [q]);
  const [adding, setAdding] = useState(false);
  const [label, setLabel] = useState(null);       // the stock item whose barcode label is shown
  const toast = useToast();

  const restock = async (item) => {
    const value = window.prompt(`How many ${item.medicine_name} are on the shelf now? (batch ${item.batch_number || "-"})`, item.quantity);
    if (value === null) return;
    try { await updateInventory(item.id, { quantity: Number(value) }); toast("Stock updated"); reload(); } catch (e) { toast(getErrorMessage(e), "error"); }
  };

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <PageTitle title="Medicine stock" subtitle="What you have on the shelf. Stock goes down automatically when you sell or give medicine." icon={Package} />
        <Button onClick={() => setAdding(true)}><Plus size={20} /> Add new stock</Button>
      </div>
      <div className="relative">
        <Search className="pointer-events-none absolute left-3.5 top-3 text-slate-400" size={18} />
        <input className={`${inputClass} pl-10`} placeholder="Type a medicine name or scan a barcode to search" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      {loading && !data ? <Loading /> : error ? <ErrorBox message={error} onRetry={reload} /> : data.length === 0 ? (
        <EmptyState message={q ? "No medicine matches your search" : "No stock recorded yet"} hint={q ? undefined : 'Press "Add new stock" to record the medicines you have.'} icon={Package} />
      ) : (
        <div className="space-y-3">
          {data.map((i) => {
            const days = i.expiry_date ? Math.round((new Date(i.expiry_date) - Date.now()) / 86400000) : null;
            const expired = days !== null && days < 0;
            const soon = days !== null && days >= 0 && days <= 30;
            return (
              <div key={i.id} className="flex flex-wrap items-center justify-between gap-4 rounded-3xl border border-slate-200/70 bg-white p-4 shadow-sm">
                <div className="flex min-w-0 items-center gap-4">
                  <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-amber-400 to-orange-500 text-white"><Pill size={24} /></span>
                  <div className="min-w-0">
                    <p className="text-lg font-extrabold text-slate-900">{i.medicine_name}</p>
                    <p className="text-base text-slate-600">
                      {i.batch_number ? `Batch ${i.batch_number}` : "No batch number"}{i.manufacturer && ` - ${i.manufacturer}`}{i.unit_price != null && ` - price ${money(i.unit_price)} each`}{i.gst_percent != null && ` + ${i.gst_percent}% GST`}
                    </p>
                    <p className="text-sm text-slate-500">Barcode: <b className="font-mono text-slate-700">{i.barcode || "none yet"}</b></p>
                    <p className={`text-base font-semibold ${expired ? "text-red-600" : soon ? "text-amber-600" : "text-slate-500"}`}>
                      {i.expiry_date ? (expired ? `Expired on ${fmtDate(i.expiry_date)} - do not give` : soon ? `Expires soon: ${fmtDate(i.expiry_date)}` : `Expires ${fmtDate(i.expiry_date)}`) : "No expiry date"}
                    </p>
                  </div>
                </div>
                <div className="flex flex-wrap items-center gap-3">
                  <StockMeter quantity={i.quantity} />
                  <Button variant="secondary" onClick={() => restock(i)}>Change count</Button>
                  {i.barcode && <Button variant="soft" onClick={() => setLabel(i)}><ScanBarcode size={18} /> Barcode label</Button>}
                </div>
              </div>
            );
          })}
        </div>
      )}
      {adding && <AddStock onClose={() => setAdding(false)} onSaved={(item) => { toast(`Stock added. Barcode: ${item.barcode}`); reload(); setLabel(item); }} />}
      {label && <LabelModal item={label} onClose={() => setLabel(null)} />}
    </div>
  );
}

// Add stock: scan the barcode on the pack first. A medicine you already know is filled in for you.
function AddStock({ onClose, onSaved }) {
  const [form, setForm] = useState({ barcode: "", medicine_name: "", batch_number: "", quantity: 1, expiry_date: "", manufacturer: "", unit_price: "", gst_percent: "" });
  const [known, setKnown] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  const setName = (value) => setForm((f) => ({ ...f, medicine_name: value }));

  // pick-list: medicines in your stock first, then medicines used in the hospital and common medicines
  const [names, setNames] = useState([]);
  const [shelf, setShelf] = useState([]);
  useEffect(() => {
    getMedicineOptions().then((list) => setNames(list.map((m) => ({ name: m.name, hint: m.in_stock ? "In stock" : undefined })))).catch(() => {});
    listInventory("").then(setShelf).catch(() => {});
  }, []);
  // choosing a medicine you already stock fills its barcode, price, GST and manufacturer
  const pickName = (name) => {
    const known = shelf.find((i) => i.medicine_name.toLowerCase() === name.toLowerCase());
    setForm((f) => ({
      ...f, medicine_name: name,
      barcode: f.barcode || known?.barcode || "",
      unit_price: f.unit_price === "" ? (known?.unit_price ?? "") : f.unit_price,
      gst_percent: f.gst_percent === "" ? (known?.gst_percent ?? "") : f.gst_percent,
      manufacturer: f.manufacturer || known?.manufacturer || "",
    }));
    if (known) setKnown(`Known medicine: ${known.medicine_name}. Its barcode and price were filled in. Type the details of the new delivery.`);
  };
  const gstSlabs = ["0", "5", "12", "18", "28"];
  const gstChoices = form.gst_percent !== "" && !gstSlabs.includes(String(form.gst_percent)) ? [String(form.gst_percent), ...gstSlabs] : gstSlabs;

  const scan = async () => {
    const code = form.barcode.trim();
    if (!code) return;
    try {
      const found = await lookupBarcode(code);
      setForm((f) => ({ ...f, medicine_name: found.medicine_name, unit_price: found.unit_price ?? "", gst_percent: found.gst_percent ?? "" }));
      setKnown(`Known medicine: ${found.medicine_name} (${found.available} in stock now). Type the details of the new delivery.`);
    } catch {
      setKnown("This barcode is new. Type the medicine name and details.");
    }
  };

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const saved = await receiveStock({
        barcode: form.barcode.trim() || null, medicine_name: form.medicine_name, batch_number: form.batch_number || null,
        quantity: Number(form.quantity), expiry_date: form.expiry_date || null, manufacturer: form.manufacturer || null,
        unit_price: form.unit_price === "" ? null : Number(form.unit_price), gst_percent: form.gst_percent === "" ? null : Number(form.gst_percent),
      });
      onSaved(saved);
      onClose();
    } catch (err) { setError(getErrorMessage(err)); } finally { setBusy(false); }
  };

  return (
    <Modal title="Add medicine stock" onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        <Field label="Scan the barcode on the pack (or leave empty to make one)" hint="Click the box, then scan. Press Enter if you typed the code.">
          <input autoFocus className={`${inputClass} border-2 border-brand-600`} value={form.barcode} onChange={set("barcode")}
            onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); scan(); } }} onBlur={scan} placeholder="Scan here" />
        </Field>
        {known && <p className="rounded-xl bg-brand-50 p-3 text-base font-semibold text-brand-900">{known}</p>}
        <Field label="Medicine name (type a few letters, then pick from the list)">
          <Autocomplete required options={names} value={form.medicine_name} onChange={setName} onPick={pickName} placeholder="e.g. para" />
        </Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Batch number"><Input value={form.batch_number} onChange={set("batch_number")} /></Field>
          <Field label="How many are you adding?"><Input type="number" min={1} required value={form.quantity} onChange={set("quantity")} /></Field>
          <Field label="Expiry date"><Input type="date" value={form.expiry_date} onChange={set("expiry_date")} /></Field>
          <Field label="Selling price of one (before GST)"><Input type="number" min={0} step="0.01" value={form.unit_price} onChange={set("unit_price")} /></Field>
          <Field label="GST %">
            <Select value={form.gst_percent === "" ? "" : String(form.gst_percent)} onChange={set("gst_percent")}>
              <option value="">Choose GST</option>{gstChoices.map((g) => <option key={g} value={g}>{g}%</option>)}
            </Select>
          </Field>
          <Field label="Manufacturer"><Input value={form.manufacturer} onChange={set("manufacturer")} /></Field>
        </div>
        <p className="text-sm text-slate-600">If this medicine and batch are already on the shelf, the number is added to the old count.</p>
        {error && <ErrorBox message={error} />}
        <Button disabled={busy} className="w-full">{busy ? "Saving..." : "✓ Save this stock"}</Button>
      </form>
    </Modal>
  );
}

// A sticker to print and paste on the shelf or the pack, so every sale can be scanned.
function LabelModal({ item, onClose }) {
  const [copies, setCopies] = useState(8);
  const count = Math.max(1, Math.min(Number(copies) || 1, 48));
  return (
    <Modal title="Barcode label" onClose={onClose} wide>
      <div className="no-print mb-4 flex flex-wrap items-end gap-3">
        <label className="text-base font-semibold text-slate-700">How many stickers?
          <input type="number" min={1} max={48} value={copies} onChange={(e) => setCopies(e.target.value)} className="ml-2 h-11 w-24 rounded-xl border-2 border-slate-400 px-3 text-lg font-bold" />
        </label>
        <Button onClick={() => printAs(item.medicine_name, "Barcode stickers")}><Printer size={20} /> Print stickers</Button>
        <Button variant="secondary" onClick={onClose}>Close</Button>
      </div>
      <div className="print-area grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
        {Array.from({ length: count }, (_, n) => (
          <div key={n} className="flex flex-col items-center rounded-xl border border-slate-400 bg-white p-2 text-center">
            <p className="w-full truncate text-xs font-bold text-slate-900">{item.medicine_name}</p>
            <Barcode value={item.barcode} height={40} width={1.5} />
            {item.unit_price != null && <p className="text-xs font-bold text-slate-800">MRP {money(item.unit_price)}</p>}
          </div>
        ))}
      </div>
    </Modal>
  );
}
