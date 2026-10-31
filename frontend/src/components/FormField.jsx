import { cloneElement } from "react";
import { Eye, EyeOff } from "lucide-react";
import { useState } from "react";
import { inputClass } from "./ui";
import { passwordStrength } from "../utils/validators";

/** A labelled field with its error (red, under the field), an optional note and an optional character counter. The input inside gets the id, `aria-invalid`
 *  and `aria-describedby` that connect it to the messages, so a screen reader reads the error with the field. */
export function FormField({ label, name, error, hint, count, max, warning, children }) {
  const describedBy = [error && `${name}-error`, warning && `${name}-warning`, hint && `${name}-hint`].filter(Boolean).join(" ") || undefined;
  const extra = { id: name, name, "aria-invalid": error ? "true" : undefined, "aria-describedby": describedBy };
  if (children.props.maxLength === undefined && max) extra.maxLength = max;
  const input = cloneElement(children, extra);
  return (
    <div>
      <div className="flex items-baseline justify-between gap-2">
        <label htmlFor={name} className="block text-sm font-semibold text-slate-700">{label}</label>
        {max && count !== undefined && <span className={`text-xs ${count > max * 0.9 ? "text-amber-700" : "text-slate-400"}`} aria-hidden="true">{count}/{max}</span>}
      </div>
      <div className="mt-1.5">{input}</div>
      {error && <p id={`${name}-error`} className="mt-1 text-sm font-medium text-red-600">{error}</p>}
      {!error && warning && <p id={`${name}-warning`} className="mt-1 text-sm font-medium text-amber-700">{warning}</p>}
      {hint && <p id={`${name}-hint`} className="mt-1 text-xs text-slate-500">{hint}</p>}
    </div>
  );
}

const STRENGTH = { weak: ["bg-red-500", "w-1/3", "text-red-700"], okay: ["bg-amber-500", "w-2/3", "text-amber-700"], strong: ["bg-emerald-500", "w-full", "text-emerald-700"] };

/** A password box with a show/hide button and, when `meter` is set, a live strength hint (weak / okay / strong). */
export function PasswordInput({ value, onChange, onBlur, meter = false, autoComplete = "new-password", id, placeholder, ...rest }) {
  const [show, setShow] = useState(false);
  const strength = passwordStrength(value);
  const bar = STRENGTH[strength.level];
  return (
    <div>
      <div className="relative">
        <input id={id} type={show ? "text" : "password"} value={value} onChange={onChange} onBlur={onBlur} autoComplete={autoComplete} placeholder={placeholder} maxLength={128}
          className={`${inputClass} pr-12`} {...rest} />
        <button type="button" onClick={() => setShow(!show)} aria-label={show ? "Hide password" : "Show password"} className="absolute right-3 top-3 text-slate-500 hover:text-slate-800">
          {show ? <EyeOff size={20} /> : <Eye size={20} />}
        </button>
      </div>
      {meter && strength.level && (
        <div className="mt-1.5" aria-live="polite">
          <div className="h-1.5 w-full rounded-full bg-slate-200"><div className={`h-1.5 rounded-full transition-all ${bar[0]} ${bar[1]}`} /></div>
          <p className={`mt-1 text-xs font-semibold ${bar[2]}`}>Password strength: {strength.label}</p>
        </div>
      )}
    </div>
  );
}
