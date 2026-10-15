import { useState } from "react";
import { Package, Pill, Plus, Search } from "lucide-react";
import useFetch from "../../hooks/useFetch";
import { addInventory, listInventory, updateInventory } from "../../services/pharmacyApi";
import { getErrorMessage } from "../../services/api";
import { StockMeter } from "../../components/DataViews";
import { Button, Field, Input, Modal, fmtDate, inputClass } from "../../components/ui";
import { EmptyState, ErrorBox, Loading, PageTitle } from "../../components/Feedback";
import { useToast } from "../../components/Toast";

// Medicine stock as cards: the bar shows how much is left, and the expiry line is in plain words.
export default function Inventory() {
  const [q, setQ] = useState("");
  const { data, loading, error, reload } = useFetch(() => listInventory(q), [q]);
  const [adding, setAdding] = useState(false);
  const toast = useToast();

  const restock = async (item) => {
    const value = window.prompt(`How many ${item.medicine_name} are on the shelf now? (batch ${item.batch_number || "-"})`, item.quantity);
    if (value === null) return;
    try { await updateInventory(item.id, { quantity: Number(value) }); toast("Stock updated"); reload(); } catch (e) { toast(getErrorMessage(e), "error"); }
  };

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <PageTitle title="Medicine stock" subtitle="What you have on the shelf. Stock goes down automatically when you give medicine." icon={Package} />
        <Button onClick={() => setAdding(true)}><Plus size={20} /> Add new stock</Button>
      </div>
      <div className="relative">
        <Search className="pointer-events-none absolute left-3.5 top-3 text-slate-400" size={18} />
        <input className={`${inputClass} pl-10`} placeholder="Type a medicine name to search" value={q} onChange={(e) => setQ(e.target.value)} />
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
                <div className="flex items-center gap-4">
                  <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-amber-400 to-orange-500 text-white"><Pill size={24} /></span>
                  <div>
                    <p className="text-lg font-extrabold text-slate-900">{i.medicine_name}</p>
                    <p className="text-base text-slate-600">
                      {i.batch_number ? `Batch ${i.batch_number}` : "No batch number"}{i.manufacturer && ` - ${i.manufacturer}`}{i.unit_price != null && ` - price ${i.unit_price} each`}
                    </p>
                    <p className={`text-base font-semibold ${expired ? "text-red-600" : soon ? "text-amber-600" : "text-slate-500"}`}>
                      {i.expiry_date ? (expired ? `Expired on ${fmtDate(i.expiry_date)} - do not give` : soon ? `Expires soon: ${fmtDate(i.expiry_date)}` : `Expires ${fmtDate(i.expiry_date)}`) : "No expiry date"}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-5">
                  <StockMeter quantity={i.quantity} />
                  <Button variant="secondary" onClick={() => restock(i)}>Change count</Button>
                </div>
              </div>
            );
          })}
        </div>
      )}
      {adding && <AddStock onClose={() => setAdding(false)} onSaved={() => { toast("Stock added"); reload(); }} />}
    </div>
  );
}

function AddStock({ onClose, onSaved }) {
  const [form, setForm] = useState({ medicine_name: "", batch_number: "", quantity: 0, expiry_date: "", manufacturer: "", unit_price: "" });
  const [error, setError] = useState("");
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  const submit = async (e) => {
    e.preventDefault();
    try {
      await addInventory({ ...form, quantity: Number(form.quantity), expiry_date: form.expiry_date || null, unit_price: form.unit_price === "" ? null : Number(form.unit_price), batch_number: form.batch_number || null, manufacturer: form.manufacturer || null });
      onSaved();
      onClose();
    } catch (err) { setError(getErrorMessage(err)); }
  };
  return (
    <Modal title="Add medicine stock" onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        <Field label="Medicine name"><Input required value={form.medicine_name} onChange={set("medicine_name")} /></Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Batch number"><Input value={form.batch_number} onChange={set("batch_number")} /></Field>
          <Field label="How many?"><Input type="number" min={0} required value={form.quantity} onChange={set("quantity")} /></Field>
          <Field label="Expiry date"><Input type="date" value={form.expiry_date} onChange={set("expiry_date")} /></Field>
          <Field label="Price of one"><Input type="number" min={0} step="0.01" value={form.unit_price} onChange={set("unit_price")} /></Field>
        </div>
        <Field label="Manufacturer"><Input value={form.manufacturer} onChange={set("manufacturer")} /></Field>
        {error && <ErrorBox message={error} />}
        <Button className="w-full">✓ Save this stock</Button>
      </form>
    </Modal>
  );
}
