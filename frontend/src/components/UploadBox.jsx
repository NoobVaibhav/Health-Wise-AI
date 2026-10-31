import { useRef, useState } from "react";
import { UploadCloud } from "lucide-react";

import { REPORT_FILE, file as checkFile } from "../utils/validators";

// Drag & drop / click to choose. Validates type and size before anything is sent.
export default function UploadBox({ onFile, disabled }) {
  const inputRef = useRef(null);
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
        onClick={() => !disabled && inputRef.current.click()}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => { e.preventDefault(); setDragging(false); if (!disabled) handle(e.dataTransfer.files[0]); }}
        className={`cursor-pointer rounded-2xl border-2 border-dashed p-10 text-center transition ${dragging ? "border-brand-500 bg-brand-50" : "border-slate-300 bg-white"} ${disabled ? "opacity-50" : "hover:border-brand-500"}`}
      >
        <UploadCloud className="mx-auto text-brand-600" size={44} />
        <p className="mt-3 font-semibold text-slate-800">Drag and drop your report here</p>
        <p className="text-sm text-slate-500">or click to choose a file. {REPORT_FILE.hint}</p>
        <input ref={inputRef} type="file" hidden accept=".pdf,.jpg,.jpeg,.png,.txt,.csv"
          onChange={(e) => { handle(e.target.files[0]); e.target.value = ""; }} />
      </div>
      {problem && <p role="alert" className="mt-2 text-sm font-medium text-red-600">{problem}</p>}
    </div>
  );
}
