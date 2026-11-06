import { useId } from "react";
import { MARK, WORDMARK } from "./brandPaths";

// The HealthWise AI logo as inline SVG: it stays crisp at any size, takes no request, and follows the page. The drawing is the one in frontend/public/brand
// (path data generated into brandPaths.js; the wordmark is Manrope converted to outlines, so no font loads).
//   variant "color"  gradient mark, dark wordmark, teal AI    (on white)
//   variant "onDark" white mark, white wordmark, cyan AI      (on the brand teal or dark)
//   variant "white"  all white                                (one colour, on any dark or coloured surface)
//   variant "dark"   all dark ink                             (one colour, print and black and white)
const INK = "#0F172A";
const TONES = {
  color: { mark: "gradient", text: INK, ai: "#0A7C99" },
  onDark: { mark: "#fff", text: "#fff", ai: "#22D3EE" },
  white: { mark: "#fff", text: "#fff", ai: "#fff" },
  dark: { mark: INK, text: INK, ai: INK },
};

function MarkShape({ id, tone }) {
  const paint = tone.mark === "gradient" ? `url(#${id}-g)` : tone.mark;
  return (
    <>
      <defs>
        {tone.mark === "gradient" && (
          <linearGradient id={`${id}-g`} gradientUnits="userSpaceOnUse" x1="6" y1="8" x2="58" y2="57">
            <stop offset="0" stopColor="#164E63" /><stop offset="0.55" stopColor="#0A7C99" /><stop offset="1" stopColor="#22D3EE" />
          </linearGradient>)}
        <mask id={`${id}-m`} maskUnits="userSpaceOnUse" x="0" y="0" width="64" height="64">
          <rect width="64" height="64" fill="#fff" />
          <path d={MARK.PULSE} fill="none" stroke="#000" strokeWidth="3.6" strokeLinecap="round" strokeLinejoin="round" />
          <circle cx="14.5" cy="32" r="3.1" fill="#000" />
          <circle cx="49.5" cy="32" r="3.1" fill="none" stroke="#000" strokeWidth="2.3" />
        </mask>
      </defs>
      <path d={MARK.HEART} fill={paint} mask={`url(#${id}-m)`} />
    </>
  );
}

/** The heart mark alone. `decorative` hides it from screen readers (when the name is written next to it). */
export function BrandMark({ size = 32, variant = "color", decorative = false, className = "", title = "HealthWise AI" }) {
  const id = useId().replace(/:/g, "");
  return (
    <svg viewBox="0 0 64 64" width={size} height={size} className={className} {...(decorative ? { "aria-hidden": "true" } : { role: "img", "aria-label": title })}>
      <MarkShape id={id} tone={TONES[variant]} />
    </svg>
  );
}

/** Mark and name side by side. `height` is the height of the whole logo in px. */
export default function BrandLogo({ height = 40, variant = "color", className = "", decorative = false }) {
  const id = useId().replace(/:/g, "");
  const tone = TONES[variant];
  return (
    <svg viewBox={`0 0 ${WORDMARK.width} 64`} height={height} width={(WORDMARK.width / 64) * height} className={className} {...(decorative ? { "aria-hidden": "true" } : { role: "img", "aria-label": "HealthWise AI" })}>
      <MarkShape id={id} tone={tone} />
      <path d={WORDMARK.health} fill={tone.text} />
      <path d={WORDMARK.ai} fill={tone.ai} />
    </svg>
  );
}
