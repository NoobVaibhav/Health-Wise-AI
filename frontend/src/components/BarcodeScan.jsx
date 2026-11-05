import { useEffect, useRef, useState } from "react";
import { ScanLine } from "lucide-react";
import { Modal } from "./ui";

// Scan a barcode with the camera. It uses the browser's own BarcodeDetector (Android Chrome and the Android app); where that does not exist the button is simply
// not shown and the box that takes a typed or wedge-scanned code keeps working as before.
export const barcodeScanSupported = () =>
  typeof window !== "undefined" && "BarcodeDetector" in window && !!navigator.mediaDevices?.getUserMedia;

const FORMATS = ["ean_13", "ean_8", "code_128", "code_39", "upc_a", "upc_e", "qr_code"];

export default function BarcodeScan({ onDetect, label = "Scan with camera" }) {
  const [open, setOpen] = useState(false);
  if (!barcodeScanSupported()) return null;
  return (
    <>
      <button type="button" onClick={() => setOpen(true)} className="inline-flex min-h-12 items-center gap-2 rounded-xl border-2 border-brand-700 bg-white px-4 font-bold text-brand-800"><ScanLine size={18} aria-hidden="true" /> {label}</button>
      {open && <Scanner onClose={() => setOpen(false)} onDetect={(code) => { setOpen(false); onDetect(code); }} />}
    </>
  );
}

function Scanner({ onClose, onDetect }) {
  const video = useRef(null);
  const found = useRef(onDetect);
  found.current = onDetect;
  const [problem, setProblem] = useState("");
  useEffect(() => {
    let stream, timer, stopped = false;
    (async () => {
      try {
        stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" }, audio: false });
        if (stopped) { stream.getTracks().forEach((t) => t.stop()); return; }
        video.current.srcObject = stream;
        await video.current.play();
        const detector = new window.BarcodeDetector({ formats: FORMATS });
        const tick = async () => {
          if (stopped) return;
          try { const hits = await detector.detect(video.current); if (hits[0]?.rawValue) { found.current(hits[0].rawValue); return; } } catch { /* a frame that cannot be read is skipped */ }
          timer = setTimeout(tick, 250);
        };
        tick();
      } catch { setProblem("The camera could not be opened. Allow the camera in the browser, or type the code instead."); }
    })();
    return () => { stopped = true; clearTimeout(timer); stream?.getTracks().forEach((t) => t.stop()); };
  }, []);
  return (
    <Modal title="Scan the barcode" onClose={onClose}>
      {problem ? <p role="alert" className="rounded-xl bg-amber-50 p-3 text-amber-900">{problem}</p> : (
        <>
          <video ref={video} muted playsInline className="aspect-[4/3] w-full rounded-2xl bg-slate-900 object-cover" aria-label="Camera view" />
          <p className="mt-2 text-sm text-slate-600">Hold the barcode inside the picture. It is read at once; nothing is recorded.</p>
        </>
      )}
    </Modal>
  );
}
