// A list of prescriptions as cards. Each card has two big buttons in its top-right corner: Open (shows the full prescription sheet under the card) and
// Print (opens it and prints it). Only one sheet is open at a time, because only one thing can be on the paper.
import { useEffect, useState } from "react";
import { FileText, Printer, X } from "lucide-react";
import { PrescriptionCard } from "./Cards";
import PrescriptionSheet from "./PrescriptionSheet";
import { Button } from "./ui";
import { printAs } from "../utils/printTitle";

export default function PrescriptionList({ items, variant = "patient", showPatient = false, renderBelow }) {
  const [openId, setOpenId] = useState(null);
  const [printId, setPrintId] = useState(null);

  // Print waits until the sheet is on the page (a moment after it was opened), then prints it once.
  useEffect(() => {
    if (printId === null || openId !== printId) return undefined;
    const rx = items.find((r) => r.id === printId);
    const timer = setTimeout(() => { if (rx) printAs(rx.patient_name, rx.code, "Prescription"); setPrintId(null); }, 300);
    return () => clearTimeout(timer);
  }, [printId, openId, items]);

  return (
    <div className="space-y-4">
      {items.map((rx) => {
        const open = openId === rx.id;
        const actions = (
          <>
            <Button type="button" variant="secondary" aria-expanded={open} aria-label={`${open ? "Close" : "Open"} prescription ${rx.code}`} className="min-h-12 px-5 text-base"
              onClick={() => { setPrintId(null); setOpenId(open ? null : rx.id); }}>
              {open ? <><X size={20} className="mr-1.5 inline" /> Close</> : <><FileText size={20} className="mr-1.5 inline" /> Open</>}
            </Button>
            <Button type="button" aria-label={`Print prescription ${rx.code}`} className="min-h-12 px-5 text-base" onClick={() => { setOpenId(rx.id); setPrintId(rx.id); }}>
              <Printer size={20} className="mr-1.5 inline" /> Print
            </Button>
          </>
        );
        return (
          <div key={rx.id}>
            <PrescriptionCard rx={rx} showPatient={showPatient} actions={actions} />
            {renderBelow?.(rx)}
            {open && <div className="mt-3"><PrescriptionSheet rx={rx} variant={variant} onPrint={() => printAs(rx.patient_name, rx.code, "Prescription")} /></div>}
          </div>
        );
      })}
    </div>
  );
}
