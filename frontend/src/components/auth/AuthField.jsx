// A sign-in field with a floating label, an icon, a glow ring that opens smoothly, an animated show/hide button for passwords and a tick that pops in when the value is good.
// The label stays tied to the input, the error is linked with aria-describedby, and the input keeps its type, autocomplete and maxLength.
// `flash` is a counter: every change plays a quick highlight (used when the demo picker fills the field).
import { useState } from "react";
import { Check, Eye, EyeOff } from "lucide-react";

export default function AuthField({ id, label, icon: Icon, type = "text", error, password = false, valid = false, flash = 0, ...input }) {
  const [shown, setShown] = useState(false);
  return (
    <div>
      <div className="hw-field" data-invalid={error ? "true" : undefined}>
        <Icon className="hw-icon" size={20} aria-hidden="true" />
        <input id={id} name={id} className="hw-input" placeholder=" " type={password ? (shown ? "text" : "password") : type}
          aria-invalid={error ? "true" : undefined} aria-describedby={error ? `${id}-error` : undefined} {...input} />
        <label htmlFor={id} className="hw-label">{label}</label>
        {flash > 0 && <span key={flash} className="hw-flash" aria-hidden="true" />}
        {valid && !error && !password && <span className="hw-valid" aria-hidden="true"><Check size={14} strokeWidth={3} /></span>}
        {password && (
          <button type="button" className="hw-eye" aria-pressed={shown} aria-label={shown ? "Hide password" : "Show password"} onClick={() => setShown(!shown)}>
            <Eye className="eye-open" size={20} aria-hidden="true" />
            <EyeOff className="eye-off" size={20} aria-hidden="true" />
          </button>)}
      </div>
      <p id={`${id}-error`} aria-live="polite" className={error ? "mt-1.5 text-sm font-semibold text-red-700" : "sr-only"}>{error || ""}</p>
    </div>
  );
}
