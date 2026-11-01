// Six boxes for a one-time code: type or paste digits, the cursor moves by itself, Backspace goes back, and the whole code can be pasted into any box.
import { useEffect, useRef } from "react";

export default function OtpInput({ value, onChange, onComplete, disabled = false, invalid = false, length = 6 }) {
  const refs = useRef([]);
  const digits = Array.from({ length }, (_, i) => value[i] || "");
  useEffect(() => { refs.current[0]?.focus(); }, []);

  const put = (text, from) => {
    const clean = text.replace(/\D/g, "").slice(0, length - from);
    if (!clean) return;
    const next = (value.slice(0, from) + clean + value.slice(from + clean.length)).slice(0, length);
    onChange(next);
    const target = Math.min(from + clean.length, length - 1);
    refs.current[target]?.focus();
    if (next.length === length && !next.includes(" ")) onComplete?.(next);
  };

  return (
    <div className="flex justify-between gap-2" role="group" aria-label="One-time code">
      {digits.map((d, i) => (
        <input key={i} ref={(el) => (refs.current[i] = el)} value={d} disabled={disabled} inputMode="numeric" autoComplete={i === 0 ? "one-time-code" : "off"} maxLength={length} aria-label={`Digit ${i + 1}`}
          aria-invalid={invalid ? "true" : undefined} data-filled={d ? "true" : "false"} className="hw-otp"
          onChange={(e) => put(e.target.value, i)}
          onPaste={(e) => { e.preventDefault(); put(e.clipboardData.getData("text"), 0); }}
          onFocus={(e) => e.target.select()}
          onKeyDown={(e) => {
            if (e.key === "Backspace") {
              e.preventDefault();
              if (d) onChange(value.slice(0, i) + value.slice(i + 1));
              else if (i > 0) { onChange(value.slice(0, i - 1) + value.slice(i)); refs.current[i - 1]?.focus(); }
            } else if (e.key === "ArrowLeft" && i > 0) refs.current[i - 1]?.focus();
            else if (e.key === "ArrowRight" && i < length - 1) refs.current[i + 1]?.focus();
          }} />))}
    </div>
  );
}
