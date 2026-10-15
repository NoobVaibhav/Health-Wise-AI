// Delete a report that was uploaded by mistake (wrong file or wrong patient). A doctor can delete any report of their
// patients. An employee can delete only a report they uploaded themselves, until the doctor has reviewed it.
// Nothing happens until the person confirms in a window that names the report.
import { useState } from "react";
import { createPortal } from "react-dom";
import { Trash2 } from "lucide-react";
import { Button, Modal } from "./ui";
import { deleteReport } from "../services/reportApi";
import { getErrorMessage } from "../services/api";
import { useToast } from "./Toast";
import { useAuth } from "../context/AuthContext";

export const canDeleteReport = (user, report) =>
  user.role === "DOCTOR" || (user.role === "EMPLOYEE" && report.uploaded_by_id === user.id && report.doctor_review_status === "PENDING");

export default function DeleteReportButton({ report, onDeleted, compact = false }) {
  const { user } = useAuth();
  const toast = useToast();
  const [asking, setAsking] = useState(false);
  const [busy, setBusy] = useState(false);
  if (!canDeleteReport(user, report)) return null;

  const confirm = async () => {
    setBusy(true);
    try {
      await deleteReport(report.id);
      toast(`"${report.filename}" was deleted`);
      setAsking(false);
      onDeleted?.();
    } catch (e) {
      toast(getErrorMessage(e), "error");
    } finally {
      setBusy(false);
    }
  };

  // the button sits inside a clickable row on the list page: do not open the report when it is pressed
  const open = (e) => { e.preventDefault(); e.stopPropagation(); setAsking(true); };

  return (
    <>
      {compact
        ? <button onClick={open} title="Delete this report" aria-label={`Delete ${report.filename}`} className="rounded-xl p-2 text-slate-400 hover:bg-red-50 hover:text-red-600"><Trash2 size={18} /></button>
        : <Button variant="secondary" onClick={open} className="!border-red-600 !text-red-700 hover:!bg-red-50"><Trash2 size={18} />Delete this report</Button>}
      {asking && createPortal(
        // drawn on the page itself, not inside the clickable row, and clicks do not reach the row behind it
        <div onClick={(e) => { e.preventDefault(); e.stopPropagation(); }}>
          <Modal title="Delete this report?" onClose={() => !busy && setAsking(false)}>
            <p className="text-slate-700">You are about to delete <b>{report.filename}</b> of <b>{report.patient_name}</b> ({report.patient_code}).</p>
            <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-slate-600">
              <li>The report, its test results and the uploaded file are removed for good.</li>
              <li>Notes, advice and prescriptions already written stay in the patient's history.</li>
              <li>The deletion is written to the activity log.</li>
            </ul>
            <div className="mt-5 flex justify-end gap-3">
              <Button variant="secondary" disabled={busy} onClick={() => setAsking(false)}>No, keep it</Button>
              <Button variant="danger" disabled={busy} onClick={confirm}>{busy ? "Deleting..." : "Yes, delete it"}</Button>
            </div>
          </Modal>
        </div>,
        document.body,
      )}
    </>
  );
}
