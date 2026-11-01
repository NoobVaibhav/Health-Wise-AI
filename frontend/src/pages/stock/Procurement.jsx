// Inventory and procurement: store items, requisitions, purchase orders, goods received, and stock counts.
// A requisition or an order is approved by someone other than its maker; a count difference needs a reason and a second person.
import { useState } from "react";
import { Warehouse } from "lucide-react";
import useFetch from "../../hooks/useFetch";
import useSave from "../../hooks/useSave";
import { useAuth } from "../../context/AuthContext";
import { addCount, addItem, addOrder, addRequisition, approveOrder, decideCount, decideRequisition, getCounts, getItems, getOrders, getRequisitions, getSuppliers, receiveOrder } from "../../services/operationsApi";
import { Section } from "../../components/HealthCard";
import { EmptyState, ErrorBox, Loading, PageTitle } from "../../components/Feedback";
import { Button, Field, Input, Select, Tabs } from "../../components/ui";

const can = (user, ...p) => (user.permissions || []).some((x) => p.includes(x));
const STATUS = { PENDING: "bg-amber-100 text-amber-900", APPROVED: "bg-emerald-100 text-emerald-900", DRAFT: "bg-amber-100 text-amber-900", PARTIAL: "bg-sky-100 text-sky-900", RECEIVED: "bg-emerald-100 text-emerald-900", REJECTED: "bg-red-100 text-red-900", ORDERED: "bg-slate-200 text-slate-700", CANCELLED: "bg-slate-200 text-slate-700", APPLIED: "bg-emerald-100 text-emerald-900" };
const Chip = ({ s }) => <span className={`rounded-full px-2.5 py-0.5 text-xs font-bold ${STATUS[s] || "bg-slate-100"}`}>{s}</span>;
const lineName = (l, items) => l.medicine_name || items?.find((i) => i.id === l.inventory_item_id)?.name || "item";

function Items({ user }) {
  const { data, loading, error, reload } = useFetch(() => getItems());
  const [form, setForm] = useState({ code: "", name: "", category: "CONSUMABLE", min_level: "0", reorder_quantity: "0" });
  const { problem, busy, run } = useSave();
  if (loading && !data) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  const manage = can(user, "stock.manage", "inventory.manage");
  return (
    <div className="space-y-4">
      {manage && (
        <Section title="Add a store item">
          <div className="grid gap-3 sm:grid-cols-5">
            <Field label="Code *"><Input maxLength={30} value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} /></Field>
            <Field label="Name *"><Input maxLength={200} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field>
            <Field label="Kind"><Select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}><option value="CONSUMABLE">Consumable</option><option value="EQUIPMENT">Equipment</option><option value="SUPPLY">Supply</option></Select></Field>
            <Field label="Minimum level"><Input inputMode="numeric" value={form.min_level} onChange={(e) => setForm({ ...form, min_level: e.target.value })} /></Field>
            <Field label="Reorder quantity"><Input inputMode="numeric" value={form.reorder_quantity} onChange={(e) => setForm({ ...form, reorder_quantity: e.target.value })} /></Field>
          </div>
          {problem && <ErrorBox message={problem} />}
          <Button className="mt-3" disabled={busy || form.code.trim().length < 2 || form.name.trim().length < 2} onClick={async () => { if (await run(() => addItem({ ...form, min_level: Number(form.min_level) || 0, reorder_quantity: Number(form.reorder_quantity) || 0 }), "Item added")) { setForm({ ...form, code: "", name: "" }); reload(); } }}>Add item</Button>
        </Section>)}
      <Section title="Store items">
        {data.length === 0 ? <p className="text-sm text-slate-500">No item yet.</p> : (
          <div className="overflow-x-auto"><table className="w-full min-w-[30rem] text-left text-sm"><thead><tr className="border-b text-xs uppercase text-slate-500"><th className="py-1.5 pr-3">Code</th><th className="pr-3">Name</th><th className="pr-3">Kind</th><th className="pr-3">In stock</th><th>Minimum</th></tr></thead>
            <tbody>{data.map((i) => <tr key={i.id} className="border-b border-slate-100"><td className="py-1.5 pr-3 font-mono">{i.code}</td><td className="pr-3 font-semibold">{i.name}</td><td className="pr-3">{i.category}</td><td className={`pr-3 font-bold ${i.needs_reorder ? "text-red-700" : ""}`}>{i.quantity} {i.unit}{i.needs_reorder ? " - reorder" : ""}</td><td>{i.min_level}</td></tr>)}</tbody></table></div>)}
      </Section>
    </div>
  );
}

function LineEditor({ lines, setLines, items, withCost }) {
  const set = (idx, patch) => setLines(lines.map((l, i) => (i === idx ? { ...l, ...patch } : l)));
  return (
    <div className="space-y-2">{lines.map((l, idx) => (
      <div key={idx} className="grid gap-2 sm:grid-cols-4">
        <Field label="Store item"><Select value={l.inventory_item_id} onChange={(e) => set(idx, { inventory_item_id: e.target.value, medicine_name: e.target.value ? "" : l.medicine_name })}><option value="">(a medicine instead)</option>{(items || []).map((i) => <option key={i.id} value={i.id}>{i.name}</option>)}</Select></Field>
        <Field label="Medicine name"><Input maxLength={200} disabled={!!l.inventory_item_id} value={l.medicine_name} onChange={(e) => set(idx, { medicine_name: e.target.value })} /></Field>
        <Field label="Quantity *"><Input inputMode="numeric" value={l.quantity} onChange={(e) => set(idx, { quantity: e.target.value })} /></Field>
        {withCost && <Field label="Unit cost"><Input inputMode="decimal" value={l.unit_cost} onChange={(e) => set(idx, { unit_cost: e.target.value })} /></Field>}
      </div>))}
      <Button variant="secondary" onClick={() => setLines([...lines, { inventory_item_id: "", medicine_name: "", quantity: "1", unit_cost: "" }])}>Add a line</Button>
    </div>
  );
}
const cleanLines = (lines) => lines.map((l) => ({ inventory_item_id: l.inventory_item_id ? Number(l.inventory_item_id) : null, medicine_name: l.medicine_name.trim() || null, quantity: Number(l.quantity) || 0, ...(l.unit_cost !== "" && l.unit_cost !== undefined ? { unit_cost: Number(l.unit_cost) } : {}) }));
const EMPTY_LINE = { inventory_item_id: "", medicine_name: "", quantity: "1", unit_cost: "" };

function Requisitions({ user }) {
  const { data, loading, error, reload } = useFetch(getRequisitions);
  const items = useFetch(() => getItems());
  const [lines, setLines] = useState([EMPTY_LINE]);
  const [note, setNote] = useState("");
  const { problem, busy, run } = useSave();
  if (loading && !data) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  const approve = can(user, "procure.approve");
  return (
    <div className="space-y-4">
      <Section title="Ask for items or medicines">
        <LineEditor lines={lines} setLines={setLines} items={items.data} />
        <Field label="Note"><Input maxLength={300} value={note} onChange={(e) => setNote(e.target.value)} /></Field>
        {problem && <ErrorBox message={problem} />}
        <Button className="mt-3" disabled={busy} onClick={async () => { if (await run(() => addRequisition({ note: note || null, items: cleanLines(lines) }), "Requisition sent")) { setLines([EMPTY_LINE]); setNote(""); reload(); } }}>Send the requisition</Button>
      </Section>
      <Section title="Requisitions">
        {data.length === 0 ? <p className="text-sm text-slate-500">None yet.</p> : data.map((r) => (
          <div key={r.id} className="border-b border-slate-100 py-3 last:border-0">
            <p className="flex items-center gap-2 font-bold">{r.number} <Chip s={r.status} /></p>
            <ul className="text-sm text-slate-700">{r.items.map((l) => <li key={l.id}>{lineName(l, items.data)} x {l.quantity}</li>)}</ul>
            {r.decision_note && <p className="text-sm text-slate-500">{r.decision_note}</p>}
            {approve && r.status === "PENDING" && <div className="mt-2 flex gap-2"><Button disabled={busy} onClick={async () => { if (await run(() => decideRequisition(r.id, true), "Approved")) reload(); }}>Approve</Button>
              <Button variant="secondary" disabled={busy} onClick={async () => { const why = window.prompt("Why is it rejected?"); if (why && await run(() => decideRequisition(r.id, false, why), "Rejected")) reload(); }}>Reject</Button></div>}
          </div>))}
      </Section>
    </div>
  );
}

function Orders({ user }) {
  const { data, loading, error, reload } = useFetch(getOrders);
  const items = useFetch(() => getItems());
  const suppliers = useFetch(getSuppliers);
  const reqs = useFetch(getRequisitions);
  const [form, setForm] = useState({ supplier_id: "", requisition_id: "" });
  const [lines, setLines] = useState([EMPTY_LINE]);
  const [receiving, setReceiving] = useState(null);
  const [recv, setRecv] = useState({});
  const { problem, busy, run } = useSave();
  if (loading && !data) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  const approve = can(user, "procure.approve");
  const approved = (reqs.data || []).filter((r) => r.status === "APPROVED");
  const useRequisition = (id) => {
    const r = approved.find((x) => String(x.id) === id);
    setForm({ ...form, requisition_id: id });
    if (r) setLines(r.items.map((l) => ({ inventory_item_id: l.inventory_item_id || "", medicine_name: l.medicine_name || "", quantity: String(l.quantity), unit_cost: "" })));
  };
  const sendReceive = async (o) => {
    const rows = o.items.filter((i) => recv[i.id]?.quantity).map((i) => ({ order_item_id: i.id, quantity: Number(recv[i.id].quantity), batch_number: recv[i.id].batch || null, expiry_date: recv[i.id].expiry || null, selling_price: recv[i.id].price ? Number(recv[i.id].price) : null, gst_percent: recv[i.id].gst ? Number(recv[i.id].gst) : null }));
    if (await run(() => receiveOrder(o.id, { items: rows }), "Goods received: stock updated")) { setReceiving(null); setRecv({}); reload(); }
  };
  return (
    <div className="space-y-4">
      <Section title="New purchase order">
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Supplier *"><Select value={form.supplier_id} onChange={(e) => setForm({ ...form, supplier_id: e.target.value })}><option value="">Choose</option>{(suppliers.data || []).map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</Select></Field>
          <Field label="From an approved requisition"><Select value={form.requisition_id} onChange={(e) => useRequisition(e.target.value)}><option value="">None</option>{approved.map((r) => <option key={r.id} value={r.id}>{r.number}</option>)}</Select></Field>
        </div>
        <LineEditor lines={lines} setLines={setLines} items={items.data} withCost />
        {problem && <ErrorBox message={problem} />}
        <Button className="mt-3" disabled={busy || !form.supplier_id} onClick={async () => { if (await run(() => addOrder({ supplier_id: Number(form.supplier_id), requisition_id: form.requisition_id ? Number(form.requisition_id) : null, items: cleanLines(lines) }), "Order made: another person approves it")) { setLines([EMPTY_LINE]); setForm({ supplier_id: "", requisition_id: "" }); reload(); reqs.reload(); } }}>Make the order</Button>
      </Section>
      <Section title="Purchase orders">
        {data.length === 0 ? <EmptyState message="No order yet" icon={Warehouse} /> : data.map((o) => (
          <div key={o.id} className="border-b border-slate-100 py-3 last:border-0">
            <p className="flex items-center gap-2 font-bold">{o.number} <Chip s={o.status} /> <span className="text-sm font-normal text-slate-500">{o.supplier}</span></p>
            <ul className="text-sm text-slate-700">{o.items.map((l) => <li key={l.id}>{lineName(l, items.data)}: {l.received_quantity} of {l.ordered_quantity} received</li>)}</ul>
            <div className="mt-2 flex flex-wrap gap-2">
              {approve && o.status === "DRAFT" && <Button disabled={busy} onClick={async () => { if (await run(() => approveOrder(o.id), "Order approved")) reload(); }}>Approve</Button>}
              {["APPROVED", "PARTIAL"].includes(o.status) && <Button variant="secondary" onClick={() => setReceiving(receiving === o.id ? null : o.id)}>Receive goods</Button>}
            </div>
            {receiving === o.id && (
              <div className="mt-2 space-y-2 rounded-xl bg-slate-50 p-3">{o.items.filter((i) => i.received_quantity < i.ordered_quantity).map((i) => (
                <div key={i.id} className="grid gap-2 sm:grid-cols-5"><p className="self-end font-semibold">{lineName(i, items.data)}</p>
                  <Field label="Received now"><Input inputMode="numeric" value={recv[i.id]?.quantity || ""} onChange={(e) => setRecv({ ...recv, [i.id]: { ...recv[i.id], quantity: e.target.value } })} /></Field>
                  {i.medicine_name && <><Field label="Batch *"><Input maxLength={50} value={recv[i.id]?.batch || ""} onChange={(e) => setRecv({ ...recv, [i.id]: { ...recv[i.id], batch: e.target.value } })} /></Field>
                    <Field label="Expiry *"><Input type="date" value={recv[i.id]?.expiry || ""} onChange={(e) => setRecv({ ...recv, [i.id]: { ...recv[i.id], expiry: e.target.value } })} /></Field>
                    <Field label="Selling price"><Input inputMode="decimal" value={recv[i.id]?.price || ""} onChange={(e) => setRecv({ ...recv, [i.id]: { ...recv[i.id], price: e.target.value } })} /></Field></>}
                </div>))}
                <Button disabled={busy} onClick={() => sendReceive(o)}>Save the receipt</Button></div>)}
          </div>))}
      </Section>
    </div>
  );
}

function Counts({ user }) {
  const { data, loading, error, reload } = useFetch(getCounts);
  const items = useFetch(() => getItems());
  const [form, setForm] = useState({ inventory_item_id: "", counted_quantity: "", reason: "" });
  const { problem, busy, run } = useSave();
  if (loading && !data) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  if (!can(user, "stock.manage", "inventory.manage")) return <p className="text-sm text-slate-500">Stock counts are done by the store and pharmacy managers.</p>;
  return (
    <div className="space-y-4">
      <Section title="Count a store item">
        <div className="grid gap-3 sm:grid-cols-3">
          <Field label="Item *"><Select value={form.inventory_item_id} onChange={(e) => setForm({ ...form, inventory_item_id: e.target.value })}><option value="">Choose</option>{(items.data || []).map((i) => <option key={i.id} value={i.id}>{i.name} ({i.quantity} in the system)</option>)}</Select></Field>
          <Field label="Counted *"><Input inputMode="numeric" value={form.counted_quantity} onChange={(e) => setForm({ ...form, counted_quantity: e.target.value })} /></Field>
          <Field label="Reason for a difference"><Input maxLength={300} value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} /></Field>
        </div>
        {problem && <ErrorBox message={problem} />}
        <Button className="mt-3" disabled={busy || !form.inventory_item_id || form.counted_quantity === ""} onClick={async () => { if (await run(() => addCount({ inventory_item_id: Number(form.inventory_item_id), counted_quantity: Number(form.counted_quantity), reason: form.reason || null }), "Count saved")) { setForm({ inventory_item_id: "", counted_quantity: "", reason: "" }); reload(); } }}>Save the count</Button>
      </Section>
      <Section title="Counts">
        {data.length === 0 ? <p className="text-sm text-slate-500">None yet.</p> : data.map((c) => (
          <div key={c.id} className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 py-2 last:border-0">
            <span>{c.inventory_item_id ? items.data?.find((i) => i.id === c.inventory_item_id)?.name : `Medicine batch ${c.medicine_inventory_id}`}: system {c.system_quantity}, counted <b>{c.counted_quantity}</b> {c.reason ? `(${c.reason})` : ""}</span>
            <span className="flex items-center gap-2"><Chip s={c.status} />{c.status === "PENDING" && <><Button disabled={busy} onClick={async () => { if (await run(() => decideCount(c.id, true), "Stock corrected")) reload(); }}>Approve</Button><Button variant="secondary" disabled={busy} onClick={async () => { if (await run(() => decideCount(c.id, false), "Rejected")) reload(); }}>Reject</Button></>}</span>
          </div>))}
      </Section>
    </div>
  );
}

export default function Procurement() {
  const { user } = useAuth();
  return (
    <div className="space-y-5">
      <PageTitle title="Procurement and store" subtitle="Ask, approve, order, receive and count. Approvals are always by a second person." icon={Warehouse} />
      <Tabs tabs={[["items", "Store items", <Items user={user} />], ["req", "Requisitions", <Requisitions user={user} />], ["orders", "Purchase orders", <Orders user={user} />], ["counts", "Stock counts", <Counts user={user} />]]} />
    </div>
  );
}
