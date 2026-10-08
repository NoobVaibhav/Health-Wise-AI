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
import { ErrorBox, Loading, PageTitle } from "../../components/Feedback";
import { useToast } from "../../components/Toast";

export default function Dispensing() {
  const { id } = useParams();
  const { data: rx, loading, error, reload, setData } = useFetch(() => getPrescription(id), [id]);
  if (loading && !rx) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  const open = ["ACTIVE", "PARTIALLY_DISPENSED"].includes(rx.status);
  return (
    <div className="mx-auto max-w-4xl space-y-5">
      <PageTitle title={`Dispensing ${rx.code}`} subtitle={`Patient: ${rx.patient_name} (${rx.patient_code})`} />
      <Section>
        <div className="grid gap-2 text-sm sm:grid-cols-2">
          <p><span className="text-slate-500">Prescribed by:</span> {rx.doctor_name}</p>
          <p><span className="text-slate-500">Prescription date:</span> {fmtDate(rx.prescription_date)} (valid until {fmtDate(rx.valid_until)})</p>
          <p><span className="text-slate-500">Status:</span> <StatusPill value={rx.status} /></p>
          {rx.clinical_indication && <p><span className="text-slate-500">Indication:</span> {rx.clinical_indication}</p>}
          {rx.notes && <p className="sm:col-span-2"><span className="text-slate-500">Doctor's notes:</span> {rx.notes}</p>}
        </div>
        {!open && <p className="mt-3 rounded-lg bg-slate-100 p-2 text-sm text-slate-600">This prescription is {rx.status.toLowerCase().replace("_", " ")} and cannot be dispensed.</p>}
      </Section>
      {rx.items.map((item) => <ItemRow key={item.id} item={item} canDispense={open} onDone={setData} />)}
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
      toast(extra.mark_unavailable ? "Marked as not in stock" : "Medicine recorded as given");
    } catch (err) { setError(getErrorMessage(err)); } finally { setBusy(false); }
  };

  return (
    <Section>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-lg font-semibold">{item.medicine_name}</p>
          <p className="text-sm text-slate-600">{item.dosage} - {item.frequency} - {item.duration}</p>
          {item.instructions && <p className="text-sm text-slate-500">Instructions: {item.instructions}</p>}
        </div>
        <StatusPill value={item.dispense_status} />
      </div>
      <div className="mt-3 grid gap-2 text-sm sm:grid-cols-3">
        <p>Prescribed: <b>{item.quantity}</b></p><p>Dispensed: <b>{item.dispensed_quantity}</b></p><p>Remaining: <b>{item.remaining_quantity}</b></p>
      </div>
      {canDispense && item.remaining_quantity > 0 && (
        <div className="mt-4 flex flex-wrap items-end gap-3 border-t pt-4">
          <label className="text-sm">Quantity to dispense<Input type="number" min={1} max={item.remaining_quantity} value={quantity} onChange={(e) => setQuantity(e.target.value)} className="mt-1 w-32 rounded-lg border border-slate-300 px-3 py-2" /></label>
          <label className="flex-1 text-sm">Notes<Input value={notes} onChange={(e) => setNotes(e.target.value)} /></label>
          <Button disabled={busy} onClick={() => send({})}>Dispense</Button>
          <Button variant="secondary" disabled={busy} onClick={() => send({ mark_unavailable: true, quantity: 0 })}>Mark unavailable</Button>
        </div>
      )}
      {error && <div className="mt-3"><ErrorBox message={error} /></div>}
    </Section>
  );
}
