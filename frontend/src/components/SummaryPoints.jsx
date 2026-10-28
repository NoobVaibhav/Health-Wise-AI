import { summaryPoints } from "../utils/summaryPoints";

/** The "In short" text as a short list. `print` uses the smaller sheet style. */
export default function SummaryPoints({ report, print = false }) {
  const points = summaryPoints(report);
  if (!points.length) return null;
  return (
    <ul className={print ? "list-disc space-y-0.5 pl-4 text-[12px]" : "list-disc space-y-2 pl-5 text-lg leading-relaxed text-slate-800 marker:text-brand-600"}>
      {points.map((p, i) => (
        <li key={i} style={print ? { breakInside: "avoid" } : undefined}>
          {p.text}
          {p.items?.length > 0 && (
            <ul className={print ? "mt-0.5 list-[circle] space-y-0.5 pl-4" : "mt-1 list-[circle] space-y-1 pl-5 text-base"}>
              {p.items.map((t, j) => <li key={j} className={print ? "" : "font-semibold text-slate-900"}>{t}</li>)}
            </ul>
          )}
        </li>
      ))}
    </ul>
  );
}
