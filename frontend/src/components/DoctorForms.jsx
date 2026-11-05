// Forms only doctors see. Each posts to a doctor-only API; everything saved is labelled "Doctor's ...".
import { useEffect, useState } from "react";
import { Plus, Trash2, X } from "lucide-react";
import Autocomplete from "./Autocomplete";
import { calculateQuantity } from "../utils/prescriptionMath";
import { getMedicineOptions, getTestOptions } from "../services/catalogApi";
import { addHistoryEntry, addNote, addRecommendation, reviewReport } from "../services/doctorApi";
import { createPrescription } from "../services/prescriptionApi";
import { getErrorMessage } from "../services/api";
import { Button, Field, Input, Modal, Select, Textarea, ModalActions } from "./ui";
import { ErrorBox } from "./Feedback";
import { useToast } from "./Toast";

const PRIORITIES = [["NORMAL", "Normal"], ["IMPORTANT", "Important"], ["FOLLOW_UP_REQUIRED", "Follow-up required"]];

// Shared helper: submit, show the error, close on success.
function useSubmit(action, onDone, message = "Saved") {
  const toast = useToast();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await action();
      toast(message);
      onDone();
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  };
  return { submit, error, busy };
}

export function NoteModal({ patientId, reportId, onClose, onSaved }) {
  const [note, setNote] = useState("");
  const [priority, setPriority] = useState("NORMAL");
  const { submit, error, busy } = useSubmit(
    () => addNote({ patient_id: patientId, report_id: reportId || null, note, priority }),
    () => { onSaved(); onClose(); }, "Doctor's note saved");
  return (
    <Modal title="Add Doctor's Note" onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        <Field label="Note"><Textarea required minLength={2} rows={5} value={note} onChange={(e) => setNote(e.target.value)} /></Field>
        <Field label="Priority"><Select value={priority} onChange={(e) => setPriority(e.target.value)}>{PRIORITIES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</Select></Field>
        {error && <ErrorBox message={error} />}
        <ModalActions><Button disabled={busy}>{busy ? "Saving..." : "Save note"}</Button></ModalActions>
      </form>
    </Modal>
  );
}

export function RecommendationModal({ patientId, reportId, onClose, onSaved, initialText = "" }) {
  // initialText: a draft tip chosen from the suggestions panel; the doctor can edit it before saving
  const [form, setForm] = useState({ title: initialText ? "Advice after reviewing your report" : "", recommendation: initialText, follow_up_date: "", priority: "NORMAL" });
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  const { submit, error, busy } = useSubmit(
    () => addRecommendation({ ...form, patient_id: patientId, report_id: reportId || null, follow_up_date: form.follow_up_date || null }),
    () => { onSaved(); onClose(); }, "Recommendation saved");
  return (
    <Modal title="Add Doctor's Recommendation" onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        <Field label="Title"><Input required value={form.title} onChange={set("title")} /></Field>
        <Field label="Description"><Textarea required rows={4} value={form.recommendation} onChange={set("recommendation")} /></Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Follow-up date (optional)"><Input type="date" value={form.follow_up_date} onChange={set("follow_up_date")} /></Field>
          <Field label="Priority"><Select value={form.priority} onChange={set("priority")}>{PRIORITIES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</Select></Field>
        </div>
        {error && <ErrorBox message={error} />}
        <ModalActions><Button disabled={busy}>{busy ? "Saving..." : "Save recommendation"}</Button></ModalActions>
      </form>
    </Modal>
  );
}

// quick picks for the dosage / frequency / duration boxes (the doctor can still type anything)
const DOSAGES = ["1 tablet", "2 tablets", "1 capsule", "5 ml", "10 ml", "1 puff", "1 drop in each eye", "Apply thin layer", "250 mg", "500 mg", "1000 mg"];
const FREQUENCIES = ["Once daily", "Twice daily", "Three times daily", "Four times daily", "Every 8 hours", "Every 12 hours",
  "At bedtime", "Before breakfast", "After meals", "Only when needed"];
const DURATIONS = ["3 days", "5 days", "7 days", "10 days", "14 days", "1 month", "3 months", "Continue until next visit"];

// Under the quantity box: how the number was worked out, or why the doctor must type it.
function QuantityHint({ item, onUse }) {
  const calc = calculateQuantity(item);
  if (!calc) {
    const filled = item.dosage && item.frequency && item.duration;
    return <p className="mt-1 text-sm text-slate-500">{filled ? "Cannot be counted automatically (syrup, drops, \"only when needed\" ...). Please type the quantity." : "Fill dosage, frequency and duration and the quantity is worked out for you."}</p>;
  }
  const same = Number(item.quantity) === calc.quantity;
  return (
    <p className="mt-1 text-sm font-semibold text-emerald-700">
      {calc.text}
      {!same && <button type="button" onClick={onUse} className="ml-2 rounded-lg border-2 border-brand-700 bg-white px-2 py-0.5 text-sm font-bold text-brand-800 hover:bg-brand-50">Use {calc.quantity}</button>}
    </p>
  );
}

const EMPTY_ITEM ={ medicine_name: "", dosage: "", frequency: "", duration: "", quantity: 1, instructions: "" };

export function PrescriptionModal({ patientId, reportId, encounterId, onClose, onSaved }) {
  const [items, setItems] = useState([{ ...EMPTY_ITEM }]);
  const [indication, setIndication] = useState("");
  const [notes, setNotes] = useState("");
  const [tests, setTests] = useState([]);          // tests the doctor wants done, picked from the hospital list
  const [testText, setTestText] = useState("");
  const [medicineList, setMedicineList] = useState([]);
  const [testList, setTestList] = useState([]);
  // the pick-lists are only a shortcut: if they cannot be loaded the doctor can still type everything
  useEffect(() => {
    getMedicineOptions().then((list) => setMedicineList(list.map((m) => ({ name: m.name, hint: m.in_stock ? "In stock" : undefined })))).catch(() => {});
    getTestOptions().then((list) => setTestList(list.map((t) => ({ name: t.name, hint: t.group })))).catch(() => {});
  }, []);
  // dose x times per day x days = total quantity. It refills by itself until the doctor types a quantity by hand.
  const setItemValue = (i, k) => (value) => setItems((all) => all.map((it, n) => {
    if (n !== i) return it;
    const next = { ...it, [k]: value };
    if (k === "quantity") next.qtyManual = true;
    else if (!next.qtyManual) { const calc = calculateQuantity(next); if (calc) next.quantity = calc.quantity; }
    return next;
  }));
  const setItem = (i, k) => (e) => setItemValue(i, k)(e.target.value);
  const useCalculated = (i) => setItems((all) => all.map((it, n) => {
    const calc = n === i && calculateQuantity(it);
    return calc ? { ...it, quantity: calc.quantity, qtyManual: false } : it;
  }));
  const addTest = (name) => {
    const clean = (name || "").trim();
    if (clean && !tests.some((t) => t.toLowerCase() === clean.toLowerCase())) setTests([...tests, clean]);
    setTestText("");
  };
  const { submit, error, busy } = useSubmit(
    () => createPrescription({
      patient_id: patientId, report_id: reportId || null, encounter_id: encounterId || null, clinical_indication: indication || null, notes: notes || null, tests,
      items: items.map(({ qtyManual, ...it }) => ({ ...it, quantity: Number(it.quantity), instructions: it.instructions || null })),
    }),
    () => { onSaved(); onClose(); }, "Prescription created");
  return (
    <Modal title="Create Prescription" onClose={onClose} wide>
      <p className="mb-3 rounded-lg bg-amber-50 p-2 text-xs text-amber-900">You are entering this prescription yourself. HealthWise AI does not choose or suggest medicines.</p>
      <form onSubmit={submit} className="space-y-4">
        {items.map((it, i) => (
          <div key={i} className="rounded-xl border border-slate-200 p-3">
            <div className="grid gap-3 sm:grid-cols-3">
              <Field label="Medicine (type a few letters)"><Autocomplete required options={medicineList} placeholder="e.g. para" value={it.medicine_name} onChange={setItemValue(i, "medicine_name")} /></Field>
              <Field label="Dosage"><Autocomplete required options={DOSAGES} placeholder="e.g. 1 tablet" value={it.dosage} onChange={setItemValue(i, "dosage")} /></Field>
              <Field label="Frequency"><Autocomplete required options={FREQUENCIES} placeholder="e.g. Twice daily" value={it.frequency} onChange={setItemValue(i, "frequency")} /></Field>
              <Field label="Duration"><Autocomplete required options={DURATIONS} placeholder="e.g. 5 days" value={it.duration} onChange={setItemValue(i, "duration")} /></Field>
              <div>
                <Field label="Quantity (total)"><Input required type="number" min={1} value={it.quantity} onChange={setItem(i, "quantity")} /></Field>
                <QuantityHint item={it} onUse={() => useCalculated(i)} />
              </div>
              <Field label="Instructions"><Input value={it.instructions} onChange={setItem(i, "instructions")} /></Field>
            </div>
            {items.length > 1 && <button type="button" onClick={() => setItems(items.filter((_, n) => n !== i))} className="mt-2 flex items-center gap-1 text-xs text-red-600"><Trash2 size={14} /> Remove medicine</button>}
          </div>
        ))}
        <Button type="button" variant="secondary" onClick={() => setItems([...items, { ...EMPTY_ITEM }])}><Plus size={14} className="mr-1 inline" /> Add another medicine</Button>
        <div className="rounded-xl border border-slate-200 p-3">
          <Field label="Tests to get done (type a few letters, then pick). Shown to the lab and the reception, not to the pharmacy.">
            <Autocomplete options={testList} placeholder="e.g. lipid, HbA1c, ECG" value={testText} onChange={setTestText} onPick={addTest} onEnter={() => addTest(testText)} />
          </Field>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <Button type="button" variant="soft" disabled={!testText.trim()} onClick={() => addTest(testText)}><Plus size={16} /> Add this test</Button>
            {tests.map((t) => (
              <span key={t} className="inline-flex items-center gap-1 rounded-full border-2 border-brand-300 bg-brand-100 py-1 pl-3 pr-1.5 text-sm font-bold text-brand-900">
                {t}
                <button type="button" onClick={() => setTests(tests.filter((x) => x !== t))} aria-label={`Remove ${t}`} className="rounded-full p-0.5 hover:bg-brand-200"><X size={14} /></button>
              </span>
            ))}
          </div>
        </div>
        <Field label="Clinical indication (optional)"><Input value={indication} onChange={(e) => setIndication(e.target.value)} /></Field>
        <Field label="Notes (optional)"><Textarea value={notes} onChange={(e) => setNotes(e.target.value)} /></Field>
        {error && <ErrorBox message={error} />}
        <ModalActions><Button disabled={busy}>{busy ? "Saving..." : "Create prescription"}</Button></ModalActions>
      </form>
    </Modal>
  );
}

export function HistoryEntryModal({ patientId, onClose, onSaved }) {
  const [form, setForm] = useState({ entry_date: new Date().toISOString().slice(0, 10), entry_type: "Past illness", description: "" });
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  const { submit, error, busy } = useSubmit(() => addHistoryEntry({ ...form, patient_id: patientId }), () => { onSaved(); onClose(); }, "History entry saved");
  return (
    <Modal title="Add medical history entry" onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Date"><Input type="date" required value={form.entry_date} onChange={set("entry_date")} /></Field>
          <Field label="Type"><Select value={form.entry_type} onChange={set("entry_type")}>
            {["Past illness", "Surgery", "Allergy", "Family history", "Other"].map((t) => <option key={t}>{t}</option>)}</Select></Field>
        </div>
        <Field label="Description"><Textarea required rows={4} value={form.description} onChange={set("description")} /></Field>
        {error && <ErrorBox message={error} />}
        <ModalActions><Button disabled={busy}>{busy ? "Saving..." : "Save entry"}</Button></ModalActions>
      </form>
    </Modal>
  );
}

// Approve / modify / clarify the AI analysis and mark the report as reviewed.
export function ReviewPanel({ report, onReviewed }) {
  const [decision, setDecision] = useState("APPROVED");
  const [comment, setComment] = useState("");
  const { submit, error, busy } = useSubmit(() => reviewReport(report.id, { decision, comment: comment || null }), onReviewed, "Report marked as checked by doctor");
  if (report.doctor_review_status === "REVIEWED") return null;
  return (
    <form onSubmit={submit} className="space-y-3">
      <p className="text-base text-slate-700"><b>Step 1.</b> Compare the numbers above with the original report. <b>Step 2.</b> Choose what you want to do. <b>Step 3.</b> Press the big button at the bottom.</p>
      <div className="flex flex-wrap gap-2">
        {[["APPROVED", "The computer is right (approve)"], ["MODIFIED", "I want to change something"], ["CLARIFIED", "I want to explain something"]].map(([v, l]) => (
          <button type="button" key={v} onClick={() => setDecision(v)}
            aria-pressed={decision === v}
            className={`min-h-11 rounded-xl border-2 px-4 py-2 text-base font-bold ${decision === v ? "border-brand-800 bg-brand-700 text-white shadow" : "border-slate-400 bg-white text-slate-800 hover:bg-slate-50"}`}>{decision === v ? "✓ " : ""}{l}</button>
        ))}
      </div>
      <Field label={decision === "APPROVED" ? "Your comment (you may leave this empty)" : "Your comment (you must write something)"}>
        <Textarea value={comment} onChange={(e) => setComment(e.target.value)} required={decision !== "APPROVED"} />
      </Field>
      {error && <ErrorBox message={error} />}
      <Button disabled={busy} className="w-full sm:w-auto sm:min-w-72 !py-3.5 !text-lg">{busy ? "Saving..." : "✓ Save: I have checked this report"}</Button>
    </form>
  );
}
