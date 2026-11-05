import { useRef, useState } from "react";
import { Camera, UploadCloud } from "lucide-react";

import { REPORT_FILE, file as checkFile } from "../utils/validators";

// Drag & drop / click to choose. Validates type and size before anything is sent.
export default function UploadBox({ onFile, disabled }) {
  const inputRef = useRef(null);
  const cameraRef = useRef(null);
  const [dragging, setDragging] = useState(false);
  const [problem, setProblem] = useState("");

  const handle = (file) => {
    if (!file) return;
    const message = checkFile(file, REPORT_FILE);        // type, size and empty file: the server checks the real content again
    if (message) return setProblem(message);
    setProblem("");
    onFile(file);
  };

  return (
    <div>
      <div
        role="button" tabIndex={disabled ? -1 : 0} aria-label="Choose a report file"
        onKeyDown={(e) => { if ((e.key === "Enter" || e.key === " ") && !disabled) { e.preventDefault(); inputRef.current.click(); } }}
        onClick={() => !disabled && inputRef.current.click()}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => { e.preventDefault(); setDragging(false); if (!disabled) handle(e.dataTransfer.files[0]); }}
        className={`cursor-pointer rounded-2xl border-2 border-dashed p-6 text-center sm:p-10 transition ${dragging ? "border-brand-500 bg-brand-50" : "border-slate-300 bg-white"} ${disabled ? "opacity-50" : "hover:border-brand-500"}`}
      >
        <UploadCloud className="mx-auto text-brand-600" size={44} />
        <p className="mt-3 font-semibold text-slate-800">Drag and drop your report here</p>
        <p className="text-sm text-slate-500">or tap to choose a file. {REPORT_FILE.hint}</p>
        <input ref={inputRef} type="file" hidden accept=".pdf,.jpg,.jpeg,.png,.txt,.csv"
          onChange={(e) => { handle(e.target.files[0]); e.target.value = ""; }} />
      </div>
      <button type="button" disabled={disabled} onClick={() => cameraRef.current.click()} className="mt-3 inline-flex min-h-12 items-center gap-2 rounded-xl border-2 border-brand-700 bg-white px-4 font-bold text-brand-800 disabled:opacity-50"><Camera size={18} aria-hidden="true" /> Take a photo of the report</button>
      <input ref={cameraRef} type="file" hidden accept="image/*" capture="environment" aria-label="Take a photo"
        onChange={(e) => { handle(e.target.files[0]); e.target.value = ""; }} />
      {problem && <p role="alert" className="mt-2 text-sm font-medium text-red-600">{problem}</p>}
    </div>
  );
}
