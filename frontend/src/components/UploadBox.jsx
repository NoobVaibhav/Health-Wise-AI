import { useRef, useState } from "react";
import { UploadCloud } from "lucide-react";

const ALLOWED = ["pdf", "jpg", "jpeg", "png", "webp", "txt", "csv"];
const MAX_MB = 10;

// Drag & drop / click to choose. Validates type and size before anything is sent.
export default function UploadBox({ onFile, disabled }) {
  const inputRef = useRef(null);
  const [dragging, setDragging] = useState(false);
  const [problem, setProblem] = useState("");

  const handle = (file) => {
    if (!file) return;
    const ext = file.name.split(".").pop().toLowerCase();
    if (!ALLOWED.includes(ext)) return setProblem("Wrong file uploaded. Please upload a medical report as a PDF, JPG, JPEG, PNG or WEBP file.");
    if (file.size > MAX_MB * 1024 * 1024) return setProblem(`The file is too large. Maximum size is ${MAX_MB} MB.`);
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
        <p className="text-sm text-slate-500">or click to choose a file. PDF, JPG, PNG or WEBP, up to {MAX_MB} MB</p>
        <input ref={inputRef} type="file" hidden accept=".pdf,.jpg,.jpeg,.png,.webp,.txt,.csv"
          onChange={(e) => { handle(e.target.files[0]); e.target.value = ""; }} />
      </div>
      {problem && <p className="mt-2 text-sm text-red-600">{problem}</p>}
    </div>
  );
}
