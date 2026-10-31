// Small helpers for the printed prescription. Nothing here invents a value: when the meaning is not clear, it returns "" and the sheet shows the plain text only.

/** Morning-noon-night shorthand ("1-0-1") for the usual ways of writing a frequency, or "" when it is not clear.
 *  "Once a day" is NOT converted: it could be 1-0-0 (morning) or 0-0-1 (night), and guessing would change the instruction. */
export function frequencyShorthand(frequency) {
  const f = String(frequency ?? "").toLowerCase().replace(/[.,]/g, " ").replace(/\s+/g, " ").trim();
  if (!f) return "";
  const written = f.match(/^(\d(?:\.5)?|½)\s*[-–]\s*(\d(?:\.5)?|½)\s*[-–]\s*(\d(?:\.5)?|½)(?:\s*[-–]\s*(\d(?:\.5)?|½))?\b/);
  if (written) return written.slice(1).filter(Boolean).join("-").replace(/½/g, "0.5");          // already written that way
  if (/\b(tds|tid|thrice|three times|3 times)\b/.test(f)) return "1-1-1";
  if (/\b(qid|qds|four times|4 times)\b/.test(f)) return "1-1-1-1";
  if (/\b(bd|bid|twice|two times|2 times)\b/.test(f)) return "1-0-1";
  if (/\b(hs|at bedtime|at night|bedtime|nightly|every night)\b/.test(f) && !/\b(morning|noon|afternoon)\b/.test(f)) return "0-0-1";
  if (/\b(in the morning|every morning|morning only|early morning)\b/.test(f) && !/\b(night|evening|noon)\b/.test(f)) return "1-0-0";
  return "";
}

/** "Dr. Anjali Sharma" stays as it is; "Anjali Sharma" becomes "Dr. Anjali Sharma". */
export const doctorLabel = (name) => {
  const n = String(name ?? "").trim();
  return !n ? "" : /^dr\.?\s/i.test(n) ? n : `Dr. ${n}`;
};

export const has = (value) => value !== null && value !== undefined && String(value).trim() !== "";

/** "34 y / Male", "34 y", "Male" or "" depending on what is known. */
export function ageSex(info) {
  const parts = [];
  if (info?.age !== null && info?.age !== undefined) parts.push(`${info.age} y`);
  if (has(info?.gender)) parts.push(String(info.gender).charAt(0).toUpperCase() + String(info.gender).slice(1));
  return parts.join(" / ");
}

/** The notice shown above the prescription when it cannot be given out any more, or "" when it can. */
export function statusBanner(status) {
  switch (status) {
    case "EXPIRED": return { title: "EXPIRED", text: "This prescription is past its valid-until date. Medicine cannot be given on it." };
    case "DISPENSED": return { title: "FULLY DISPENSED", text: "All the medicine on this prescription has been given." };
    case "CANCELLED": return { title: "CANCELLED", text: "The doctor cancelled this prescription. Medicine cannot be given on it." };
    default: return null;
  }
}

/** What the patient sees next to each medicine: Collected, Partly collected, Not in stock or Pending. */
export function collectionState(item) {
  if (item.dispense_status === "DISPENSED") return { label: "Collected", tone: "done" };
  if (item.dispense_status === "PARTIALLY_DISPENSED") return { label: `Partly collected (${item.dispensed_quantity} of ${item.quantity})`, tone: "part" };
  if (item.dispense_status === "UNAVAILABLE") return { label: "Not in stock", tone: "stop" };
  return { label: "Pending", tone: "wait" };
}
