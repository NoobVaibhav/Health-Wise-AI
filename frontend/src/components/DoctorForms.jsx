// Forms only doctors see. Each posts to a doctor-only API; everything saved is labelled "Doctor's ...".
import { useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { addHistoryEntry, addNote, addRecommendation, reviewReport } from "../services/doctorApi";
import { createPrescription } from "../services/prescriptionApi";
import { getErrorMessage } from "../services/api";
import { Button, Field, Input, Modal, Select, Textarea } from "./ui";
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
        <Button disabled={busy}>{busy ? "Saving..." : "Save note"}</Button>
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
        <Button disabled={busy}>{busy ? "Saving..." : "Save recommendation"}</Button>
      </form>
    </Modal>
  );
}

const EMPTY_ITEM = { medicine_name: "", dosage: "", frequency: "", duration: "", quantity: 1, instructions: "" };

export function PrescriptionModal({ patientId, reportId, onClose, onSaved }) {
  const [items, setItems] = useState([{ ...EMPTY_ITEM }]);
  const [indication, setIndication] = useState("");
  const [notes, setNotes] = useState("");
  const setItem = (i, k) => (e) => setItems(items.map((it, n) => (n === i ? { ...it, [k]: e.target.value } : it)));
  const { submit, error, busy } = useSubmit(
    () => createPrescription({
      patient_id: patientId, report_id: reportId || null, clinical_indication: indication || null, notes: notes || null,
      items: items.map((it) => ({ ...it, quantity: Number(it.quantity), instructions: it.instructions || null })),
    }),
    () => { onSaved(); onClose(); }, "Prescription created");
  return (
    <Modal title="Create Prescription" onClose={onClose} wide>
      <p className="mb-3 rounded-lg bg-amber-50 p-2 text-xs text-amber-900">You are entering this prescription yourself. HealthWise AI does not choose or suggest medicines.</p>
      <form onSubmit={submit} className="space-y-4">
        {items.map((it, i) => (
          <div key={i} className="rounded-xl border border-slate-200 p-3">
            <div className="grid gap-3 sm:grid-cols-3">
              <Field label="Medicine"><Input required value={it.medicine_name} onChange={setItem(i, "medicine_name")} /></Field>
              <Field label="Dosage"><Input required placeholder="e.g. 500 mg" value={it.dosage} onChange={setItem(i, "dosage")} /></Field>
              <Field label="Frequency"><Input required placeholder="e.g. Twice daily" value={it.frequency} onChange={setItem(i, "frequency")} /></Field>
              <Field label="Duration"><Input required placeholder="e.g. 5 days" value={it.duration} onChange={setItem(i, "duration")} /></Field>
              <Field label="Quantity"><Input required type="number" min={1} value={it.quantity} onChange={setItem(i, "quantity")} /></Field>
              <Field label="Instructions"><Input value={it.instructions} onChange={setItem(i, "instructions")} /></Field>
            </div>
            {items.length > 1 && <button type="button" onClick={() => setItems(items.filter((_, n) => n !== i))} className="mt-2 flex items-center gap-1 text-xs text-red-600"><Trash2 size={14} /> Remove medicine</button>}
          </div>
        ))}
        <Button type="button" variant="secondary" onClick={() => setItems([...items, { ...EMPTY_ITEM }])}><Plus size={14} className="mr-1 inline" /> Add another medicine</Button>
        <Field label="Clinical indication (optional)"><Input value={indication} onChange={(e) => setIndication(e.target.value)} /></Field>
        <Field label="Notes (optional)"><Textarea value={notes} onChange={(e) => setNotes(e.target.value)} /></Field>
        {error && <ErrorBox message={error} />}
        <Button disabled={busy}>{busy ? "Saving..." : "Create prescription"}</Button>
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
        <Button disabled={busy}>{busy ? "Saving..." : "Save entry"}</Button>
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
      <p className="text-sm text-slate-600">Check the extracted values against the original report, then review the AI analysis.</p>
      <div className="flex flex-wrap gap-2">
        {[["APPROVED", "Approve AI analysis"], ["MODIFIED", "Modify / add comments"], ["CLARIFIED", "Add clarification"]].map(([v, l]) => (
          <button type="button" key={v} onClick={() => setDecision(v)}
            className={`rounded-lg border px-3 py-1.5 text-sm font-medium ${decision === v ? "border-brand-600 bg-brand-50 text-brand-700" : "border-slate-300 text-slate-600"}`}>{l}</button>
        ))}
      </div>
      <Field label={decision === "APPROVED" ? "Comment (optional)" : "Comment (required)"}>
        <Textarea value={comment} onChange={(e) => setComment(e.target.value)} required={decision !== "APPROVED"} />
      </Field>
      {error && <ErrorBox message={error} />}
      <Button disabled={busy}>{busy ? "Saving..." : "Mark as Reviewed by Doctor"}</Button>
    </form>
  );
}
