// Open one prescription and dispense it. Pharmacy staff can never edit the prescription itself.
import { useState } from "react";
import { useParams } from "react-router-dom";
import useFetch from "../../hooks/useFetch";
import { getPrescription } from "../../services/prescriptionApi";
import { dispense } from "../../services/pharmacyApi";
import { getErrorMessage } from "../../services/api";
import { Section } from "../../components/HealthCard";
import { StatusPill } from "../../components/StatusBadge";
import { Button, Input, fmtDate } from "../../components/ui";
import Stepper from "../../components/Stepper";
import { ErrorBox, Loading, PageTitle } from "../../components/Feedback";
import { useToast } from "../../components/Toast";
import PrescriptionBill from "../../components/PrescriptionBill";
import PrescriptionSheet from "../../components/PrescriptionSheet";
import { printAs } from "../../utils/printTitle";

export default function Dispensing() {
  const { id } = useParams();
  const { data: rx, loading, error, reload, setData } = useFetch(() => getPrescription(id), [id]);
  if (loading && !rx) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  const open = ["ACTIVE", "PARTIALLY_DISPENSED"].includes(rx.status);
  return (
    <div className="mx-auto max-w-7xl space-y-5">
      <PageTitle title={`Give medicine: ${rx.code}`} subtitle={`Patient: ${rx.patient_name} (${rx.patient_code}). Step 1: give each medicine. Step 2: make the bill.`} />
      {/* from 1024 px: the prescription stays on the left, big and readable, and the counter work is on the right */}
      <div className="grid gap-5 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)] lg:items-start">
        <div className="min-w-0 lg:sticky lg:top-[calc(var(--height-appbar)+var(--safe-top)+0.75rem)] lg:max-h-[calc(100dvh-7rem)] lg:overflow-y-auto lg:overscroll-contain">
          <PrescriptionSheet rx={rx} variant="pharmacy" onPrint={() => printAs(rx.patient_name, rx.code, "Prescription")} />
        </div>
        <div className="min-w-0 space-y-5">
          <h2 className="flex items-center gap-3 text-xl font-extrabold text-slate-900"><span className="flex h-9 w-9 items-center justify-center rounded-full bg-brand-700 text-lg text-white">1</span> Step 1: Give the medicines</h2>
          {rx.items.map((item) => <ItemRow key={item.id} item={item} canDispense={open} onDone={setData} />)}
          <PrescriptionBill rx={rx} />
        </div>
      </div>
    </div>
  );
}

function ItemRow({ item, canDispense, onDone }) {
  const [quantity, setQuantity] = useState(item.remaining_quantity);
  const [notes, setNotes] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const toast = useToast();

  const send = async (extra) => {
    setBusy(true);
    setError("");
    try {
      onDone(await dispense({ prescription_item_id: item.id, quantity: Number(quantity), notes: notes || null, ...extra }));
      toast(extra.mark_unavailable ? "Marked as not in stock" : "Saved: medicine recorded as given");
    } catch (err) { setError(getErrorMessage(err)); } finally { setBusy(false); }
  };

  return (
    <Section>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xl font-extrabold text-slate-900">{item.medicine_name}</p>
          <p className="text-base text-slate-700">{item.dosage} - {item.frequency} - {item.duration}</p>
          {item.instructions && <p className="text-sm text-slate-500">How to take it: {item.instructions}</p>}
        </div>
        <StatusPill value={item.dispense_status} />
      </div>
      <div className="mt-3 grid gap-2 rounded-2xl bg-slate-50 p-3 text-base sm:grid-cols-3">
        <p>Doctor wrote: <b>{item.quantity}</b></p><p>Already given: <b>{item.dispensed_quantity}</b></p><p>Still to give: <b className="text-brand-800">{item.remaining_quantity}</b></p>
      </div>
      {canDispense && item.remaining_quantity > 0 && (
        <div className="mt-4 flex flex-wrap items-end gap-3 border-t pt-4">
          <div className="text-base font-semibold text-slate-700"><span id={`qty-${item.id}`}>How many to give now?</span><div className="mt-1"><Stepper label={`Quantity of ${item.medicine_name} to give now`} min={1} max={item.remaining_quantity} value={String(quantity)} onChange={setQuantity} /></div></div>
          <label className="min-w-[12rem] flex-1 text-base font-semibold text-slate-700">Note (if you want to add one)<Input enterKeyHint="done" value={notes} onChange={(e) => setNotes(e.target.value)} /></label>
          <Button disabled={busy} onClick={() => send({})} className="!border-emerald-800 !bg-emerald-600 hover:!bg-emerald-700">✓ Give medicine</Button>
          <Button variant="secondary" disabled={busy} onClick={() => send({ mark_unavailable: true, quantity: 0 })} className="!border-red-600 !text-red-700 hover:!bg-red-50">✗ Not in stock</Button>
        </div>
      )}
      {error && <div className="mt-3"><ErrorBox message={error} /></div>}
    </Section>
  );
}
