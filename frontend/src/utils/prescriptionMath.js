// Works out how many tablets / capsules to give from dose x times per day x number of days.
// It only answers when it is sure. For syrups, drops, creams or inhalers (counted in bottles or tubes) and for
// "only when needed" it returns null, and the doctor types the quantity.

const FRACTIONS = { "½": 0.5, "¼": 0.25, "¾": 0.75 };

/** "2 tablets" -> 2, "1/2 tablet" -> 0.5, "1 capsule" -> 1. Null when the dose is not a count of tablets/capsules. */
function unitsPerDose(dosage, medicineName) {
  const text = String(dosage || "").toLowerCase().replace(/[½¼¾]/g, (c) => ` ${FRACTIONS[c]} `).trim();
  if (!text) return null;
  if (/\b(ml|drop|drops|puff|puffs|spoon|teaspoon|tsp|tbsp|apply|layer|sachet|patch)\b/.test(text)) return null;

  const count = text.match(/^(\d+(?:\.\d+)?)(?:\s*\/\s*(\d+))?\s*(?:x\s*)?(?:tab|tablet|tablets|cap|capsule|capsules|pill|pills|unit|units)\b/);
  if (count) return count[2] ? Number(count[1]) / Number(count[2]) : Number(count[1]);

  // "500 mg" with a medicine called "... 250 mg tablet"  ->  2 tablets per dose
  const dose = text.match(/^(\d+(?:\.\d+)?)\s*(mg|mcg|g)\b/);
  const strength = String(medicineName || "").toLowerCase().match(/(\d+(?:\.\d+)?)\s*(mg|mcg|g)\b/);
  if (dose && strength && dose[2] === strength[2] && Number(strength[1]) > 0) {
    const n = Number(dose[1]) / Number(strength[1]);
    return Number.isInteger(n * 4) ? n : null;     // only whole, half and quarter tablets make sense
  }
  return null;
}

/** "Twice daily" -> 2, "Every 8 hours" -> 3, "1-0-1" -> 2, "TDS" -> 3. Null for "only when needed" or unknown text. */
function dosesPerDay(frequency) {
  const t = String(frequency || "").toLowerCase().trim();
  if (!t || /only when needed|sos|if needed|as needed|prn/.test(t)) return null;

  const pattern = t.match(/^(\d+(?:\.\d+)?)\s*[-–]\s*(\d+(?:\.\d+)?)\s*[-–]\s*(\d+(?:\.\d+)?)(?:\s*[-–]\s*(\d+(?:\.\d+)?))?$/);
  if (pattern) return pattern.slice(1).filter(Boolean).reduce((sum, n) => sum + Number(n), 0);

  const hours = t.match(/every\s+(\d+)\s*(?:hours?|hrs?|h)\b/);
  if (hours && Number(hours[1]) > 0) return Math.floor(24 / Number(hours[1]));

  const times = t.match(/(\d+)\s*(?:times?|x)\s*(?:a|per)?\s*(?:day|daily)?/);
  if (times) return Number(times[1]);

  if (/\b(once|od|qd|daily|bedtime|hs|breakfast)\b/.test(t) && !/twice|thrice|three|four/.test(t)) return 1;
  if (/\b(twice|bd|bid|two times)\b/.test(t)) return 2;
  if (/\b(thrice|tds|tid|three times)\b/.test(t)) return 3;
  if (/\b(four times|qid|qds)\b/.test(t)) return 4;
  if (/after meals|with meals|before meals/.test(t)) return 3;
  return null;
}

/** "7 days" -> 7, "2 weeks" -> 14, "1 month" -> 30. Null for "until next visit" or unknown text. */
function days(duration) {
  const t = String(duration || "").toLowerCase();
  const m = t.match(/(\d+(?:\.\d+)?)\s*(day|days|d|week|weeks|wk|wks|month|months|mo)\b/);
  if (!m) return null;
  const n = Number(m[1]);
  const unit = m[2];
  return /^(week|weeks|wk|wks)$/.test(unit) ? n * 7 : /^(month|months|mo)$/.test(unit) ? n * 30 : n;
}

/** Returns { quantity, text } or null. `text` explains the sum in plain words. */
export function calculateQuantity({ medicine_name, dosage, frequency, duration }) {
  const perDose = unitsPerDose(dosage, medicine_name);
  const perDay = dosesPerDay(frequency);
  const nDays = days(duration);
  if (perDose === null || perDay === null || nDays === null || perDose <= 0 || perDay <= 0 || nDays <= 0) return null;
  const quantity = Math.ceil(perDose * perDay * nDays);       // never give less than is needed
  if (quantity < 1 || quantity > 10000) return null;
  return { quantity, text: `${perDose} per dose × ${perDay} time${perDay === 1 ? "" : "s"} a day × ${nDays} day${nDays === 1 ? "" : "s"} = ${quantity}` };
}
