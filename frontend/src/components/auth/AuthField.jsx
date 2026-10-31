// A sign-in field with a floating label, an icon, a glow ring and (for passwords) an animated show/hide button.
// The label stays tied to the input, the error is linked with aria-describedby, and the input keeps its type, autocomplete and maxLength.
import { useState } from "react";
import { Eye, EyeOff } from "lucide-react";

export default function AuthField({ id, label, icon: Icon, type = "text", error, password = false, ...input }) {
  const [shown, setShown] = useState(false);
  return (
    <div>
      <div className="hw-field" data-invalid={error ? "true" : undefined}>
        <Icon className="hw-icon" size={20} aria-hidden="true" />
        <input id={id} name={id} className="hw-input" placeholder=" " type={password ? (shown ? "text" : "password") : type}
          aria-invalid={error ? "true" : undefined} aria-describedby={error ? `${id}-error` : undefined} {...input} />
        <label htmlFor={id} className="hw-label">{label}</label>
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
