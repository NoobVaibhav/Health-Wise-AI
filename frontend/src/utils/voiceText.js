// The words of the voice assistant, before they are understood (what was SAID) and before they are spoken (what is READ ALOUD). Fixed rules only: no model,
// no outside service, nothing stored. Three jobs:
//   1. normaliseSpoken: "pandrah", "पंधरा", "fifteen" -> 15; "twelfth of March" -> 12 March; "grams per decilitre" -> g/dL.
//   2. correctMedicalTerms: "met for min", "kreatinin", "h b a 1 c", "क्रिएटिन इन" put back to the name in the records. A number is never changed.
//   3. speechText: an answer made fit for the ear: no marks, units, abbreviations and dates said in words, a short pronunciation list.
import {
  AMBIGUOUS, AND_WORDS, DECIMAL_WORDS, ENGLISH_MONTH_NAMES, HALF_PREFIX, MONTHS, MONTH_EXTRA, NUMBER_WORDS, SCALES, WHOLE_FRACTIONS, ordinalAt,
} from "./voiceNumbers";

const clean = (w) => String(w || "").toLowerCase().replace(/[.,!?;:]+$/g, "");
const tail = (w) => (/[.,!?;:]+$/.exec(String(w || "")) || [""])[0];
const DEVANAGARI = /[ऀ-ॿ]/;

// ------------------------------------------------------------------ numbers
function wordTables(lang) {
  const en = NUMBER_WORDS.en;
  const dev = new Map([...NUMBER_WORDS.mr, ...NUMBER_WORDS.hi]);          // Hindi and Marathi are mixed in speech, and their small words never clash
  if (lang === "en") return { words: en, scales: SCALES.en };
  return { words: new Map([...en, ...dev]), scales: { ...SCALES.en, ...SCALES.hi, ...SCALES.mr } };
}
const smallValue = (words, w) => { const v = words.get(w); return v === undefined || v === 100 ? null : v; };

/** The number said at tokens[i]: { value (as text), used (words) } or null. Handles tens + units in English, hundred/thousand/lakh, "साडेसात", "डेढ़" and "eleven point two". */
export function numberAt(tokens, i, lang = "en") {
  const { words, scales } = wordTables(lang);
  const first = clean(tokens[i]);
  if (!first) return null;
  if (WHOLE_FRACTIONS.has(first)) return { value: String(WHOLE_FRACTIONS.get(first)), used: 1 };
  for (const [prefix, extra] of HALF_PREFIX) {
    if (first.startsWith(prefix)) {
      const rest = first.slice(prefix.length);
      const n = rest ? smallValue(words, rest) : smallValue(words, clean(tokens[i + 1]));
      if (n !== null) return { value: String(n + extra), used: rest ? 1 : 2 };
    }
  }
  let total = 0, current = 0, used = 0, any = false, prevTens = false, j = i;
  while (j < tokens.length) {
    const w = clean(tokens[j]);
    const attached = /^(.+)शे$/.exec(w);                                  // Marathi "पाचशे" = five hundred
    if (any && AND_WORDS.has(w) && smallValue(words, clean(tokens[j + 1])) !== null) { j += 1; used += 1; continue; }
    if (attached && smallValue(words, attached[1]) !== null) { current += smallValue(words, attached[1]) * 100; any = true; prevTens = false; j += 1; used = j - i; continue; }
    if (scales[w] !== undefined) {
      const scale = scales[w];
      if (scale === 100) { if (current >= 100) break; current = (current || 1) * 100; }
      else { total += (current || 1) * scale; current = 0; }
      any = true; prevTens = false; j += 1; used = j - i; continue;
    }
    const v = smallValue(words, w);
    if (v === null) break;
    const fits = !any || current % 100 === 0 || (lang === "en" && prevTens && v >= 1 && v <= 9);
    if (!fits) break;
    current += v;
    prevTens = lang === "en" ? v >= 20 && v % 10 === 0 : false;
    any = true; j += 1; used = j - i;
  }
  if (!any) return null;
  const whole = total + current;
  if (j < tokens.length && DECIMAL_WORDS.has(clean(tokens[j]))) {                  // "eleven point two": the digits after the point are said one by one
    let k = j + 1;
    let digits = "";
    while (k < tokens.length) {
      const d = words.get(clean(tokens[k]));
      if (d === undefined || d > 9) break;
      digits += String(d);
      k += 1;
    }
    if (digits) return { value: `${whole}.${digits}`, used: k - i };
  }
  return { value: String(whole), used };
}

// ------------------------------------------------------------------ dates
const monthIndexOf = (w) => {
  const word = clean(w);
  const i = MONTHS.findIndex((names) => names.includes(word));
  return i >= 0 ? i : (MONTH_EXTRA[word] ?? -1);
};

/** "twelfth of March", "बारह मार्च", "fifteen June twenty twenty six": { text: "15 June 2026", used }, or null. */
export function dateAt(tokens, i, lang = "en") {
  const low = tokens.map(clean);
  let day = null, used = 0;
  const digits = /^(\d{1,2})(?:st|nd|rd|th)?$/.exec(low[i] || "");
  if (digits) { day = Number(digits[1]); used = 1; }
  else {
    const ord = ordinalAt(low, i);
    if (ord) { day = ord.value; used = ord.used; }
    else {
      const n = numberAt(tokens, i, lang);
      if (n && /^\d+$/.test(n.value)) { day = Number(n.value); used = n.used; }
    }
  }
  if (!day || day < 1 || day > 31) return null;
  let k = i + used;
  if (["of", "का", "के", "ka", "ke"].includes(low[k])) k += 1;
  const month = monthIndexOf(tokens[k]);
  if (month < 0) return null;
  k += 1;
  let year = null;
  if (/^\d{4}$/.test(low[k] || "")) { year = Number(low[k]); k += 1; }
  else {
    const a = numberAt(tokens, k, lang);
    if (a && /^\d+$/.test(a.value)) {
      const av = Number(a.value);
      if (av >= 1900 && av <= 2100) { year = av; k += a.used; }
      else if (av === 19 || av === 20) {                                      // "twenty twenty six"
        const b = numberAt(tokens, k + a.used, lang);
        if (b && /^\d+$/.test(b.value) && Number(b.value) < 100) { year = av * 100 + Number(b.value); k += a.used + b.used; }
      }
    }
  }
  return { text: `${day} ${ENGLISH_MONTH_NAMES[month]}${year ? ` ${year}` : ""}`, used: k - i };
}

// ------------------------------------------------------------------ units
const MASS = [["milligrams?|मिलीग्राम|मिलिग्रॅम|मिलीग्रॅम", "mg"], ["nanograms?|नैनोग्राम|नॅनोग्रॅम", "ng"], ["micrograms?|माइक्रोग्राम|मायक्रोग्रॅम", "µg"], ["grams?|ग्राम|ग्रॅम", "g"]];
const VOLUME = [["decilit(?:re|er)s?|डेसीलीटर|डेसिलिटर|डेसीलिटर", "dL"], ["millilit(?:re|er)s?|मिलीलीटर|मिलिलिटर|मिलीलिटर", "mL"], ["lit(?:re|er)s?|लीटर|लिटर", "L"]];
const EDGE = "(?<![\\p{L}\\p{M}])";
const END = "(?![\\p{L}\\p{M}])";
const UNIT_RULES = [
  ...MASS.flatMap(([m, mu]) => VOLUME.map(([v, vu]) => [new RegExp(`${EDGE}(?:${m})\\s*(?:per|प्रति|/)\\s*(?:${v})${END}`, "giu"), `${mu}/${vu}`])),
  [new RegExp(`${EDGE}(?:millimoles?|मिलीमोल)\\s*(?:per|प्रति)\\s*(?:lit(?:re|er)s?|लीटर)${END}`, "giu"), "mmol/L"],
  [new RegExp(`${EDGE}(?:millimet(?:re|er)s? of mercury|मिलीमीटर पारा)${END}`, "giu"), "mmHg"],
  [new RegExp(`${EDGE}(?:beats per minute|धड़कन प्रति मिनट|ठोके प्रति मिनिट)${END}`, "giu"), "bpm"],
  [new RegExp(`${EDGE}(?:percent|per cent|प्रतिशत|टक्के)${END}`, "giu"), "%"],
];
export const applyUnits = (text) => UNIT_RULES.reduce((t, [re, symbol]) => t.replace(re, symbol), String(text));

const STANDALONE_RISKY = new Set(["one", "do", "a"]);                   // ordinary words too: "the one before that", "do I take it"

/** What was said, with numbers, dates and units written as digits and symbols. Words that are also ordinary words ("one", "do") are only taken as numbers in a short
 *  phrase or next to a point, a scale or another number word, so "the one before that" and "do I take metformin" stay as they are. */
export function normaliseSpoken(text, lang = "en") {
  const tokens = applyUnits(text).split(/\s+/).filter(Boolean);
  const out = [];
  let i = 0;
  while (i < tokens.length) {
    const d = dateAt(tokens, i, lang);
    if (d) { out.push(d.text + tail(tokens[i + d.used - 1])); i += d.used; continue; }
    const n = numberAt(tokens, i, lang);
    if (n && !(tokens.length > 1 && n.used === 1 && (STANDALONE_RISKY.has(clean(tokens[i])) || AMBIGUOUS.has(clean(tokens[i]))) && !DECIMAL_WORDS.has(clean(tokens[i + 1])))) {
      out.push(n.value + tail(tokens[i + n.used - 1]));
      i += n.used;
      continue;
    }
    out.push(tokens[i]);
    i += 1;
  }
  return out.join(" ");
}

// ------------------------------------------------------------------ repairing medical words
const DEV = {
  "क": "k", "ख": "k", "ग": "g", "घ": "g", "ङ": "n", "च": "k", "छ": "k", "ज": "j", "झ": "j", "ञ": "n", "ट": "t", "ठ": "t", "ड": "d", "ढ": "d", "ण": "n", "त": "t", "थ": "t", "द": "d", "ध": "d", "न": "n", "प": "p", "फ": "p", "ब": "b", "भ": "b",
  "म": "m", "र": "r", "ल": "l", "व": "v", "श": "s", "ष": "s", "स": "s", "ळ": "l", "ं": "n", "ँ": "", "क़": "k", "ख़": "k", "ग़": "g", "ज़": "j", "ड़": "d", "ढ़": "d", "फ़": "p", "य": "", "ह": "",
};
const LETTER_NAMES = { "ए": "a", "बी": "b", "सी": "c", "डी": "d", "ई": "e", "एफ": "f", "जी": "g", "एच": "h", "आई": "i", "जे": "j", "के": "k", "एल": "l", "एम": "m", "एन": "n", "ओ": "o", "पी": "p", "आर": "r", "एस": "s", "टी": "t", "यू": "u", "वी": "v", "एक्स": "x", "वाई": "y",
  "वन": "1", "टू": "2", "थ्री": "3", "फोर": "4", "फाइव": "5", "सिक्स": "6", "सेवन": "7", "एट": "8", "नाइन": "9" };

/** The consonant sound of a word, the same for a Devanagari and a Latin spelling: "मेटफॉर्मिन" and "metformin" both give "mtprmn". */
export function skeleton(word) {
  let w = String(word).toLowerCase();
  let s;
  if (DEVANAGARI.test(w)) {
    w = w.replace(/क्ष/g, "ks").replace(/ज्ञ/g, "gn");
    s = "";
    for (let i = 0; i < w.length; i += 1) {
      const ch = w[i];
      if (w[i + 1] === "़") { s += DEV[ch] || ""; i += 1; continue; }
      s += DEV[ch] ?? (ch === "k" || ch === "s" || ch === "g" || ch === "n" ? ch : "");
    }
  } else {
    s = w.replace(/[^a-z]/g, "").replace(/c(?=[eiy])/g, "s");
    for (const [a, b] of [["ph", "p"], ["ck", "k"], ["ch", "k"], ["sh", "s"], ["th", "t"], ["kh", "k"], ["gh", "g"], ["dh", "d"], ["bh", "b"]]) s = s.split(a).join(b);
    s = s.replace(/c/g, "k").replace(/q/g, "k").replace(/f/g, "p").replace(/w/g, "v").replace(/x/g, "ks").replace(/[aeiouyh]/g, "");
  }
  return s.replace(/(.)\1+/g, "$1");
}

function lcsRatio(a, b) {
  if (!a.length || !b.length) return 0;
  let prev = new Array(b.length + 1).fill(0);
  for (let i = 1; i <= a.length; i += 1) {
    const row = new Array(b.length + 1).fill(0);
    for (let j = 1; j <= b.length; j += 1) row[j] = a[i - 1] === b[j - 1] ? prev[j - 1] + 1 : Math.max(prev[j], row[j - 1]);
    prev = row;
  }
  return (2 * prev[b.length]) / (a.length + b.length);
}
function closeness(candidate, name) {
  const plain = /^[\x00-\x7F]+$/.test(candidate) ? lcsRatio(candidate, name) : 0;
  const a = skeleton(candidate), b = skeleton(name);
  const sound = a.length >= 4 && b.length >= 4 ? lcsRatio(a, b) * 0.99 : 0;
  return Math.max(plain >= 0.88 ? plain : 0, sound >= 0.89 ? sound : 0);
}

export const GENERAL_TERMS = [
  "metformin", "atorvastatin", "paracetamol", "amlodipine", "telmisartan", "losartan", "aspirin", "clopidogrel", "pantoprazole", "omeprazole", "levothyroxine", "glimepiride", "rosuvastatin",
  "azithromycin", "amoxicillin", "cetirizine", "ibuprofen", "diclofenac", "montelukast", "insulin", "ramipril", "metoprolol", "furosemide", "ondansetron",
  "hemoglobin", "haemoglobin", "creatinine", "cholesterol", "triglycerides", "bilirubin", "platelet", "platelets", "glucose", "thyroid", "HbA1c", "calcium", "potassium", "sodium",
  "appointment", "appointments", "abnormal", "latest", "checkup", "prescription", "prescriptions", "medicine", "medicines", "medication", "allergies", "allergy", "instructions", "consultation",
];
export const MEDICINE_WORDS = new Set(GENERAL_TERMS.slice(0, 24));
// how the same words are written in Devanagari in each language, so a split-up Hindi or Marathi word is put back in that script
const DEVANAGARI_NAMES = {
  hi: { creatinine: "क्रिएटिनिन", hemoglobin: "हीमोग्लोबिन", haemoglobin: "हीमोग्लोबिन", metformin: "मेटफॉर्मिन", atorvastatin: "अटोरवास्टेटिन", paracetamol: "पैरासिटामोल", appointment: "अपॉइंटमेंट", cholesterol: "कोलेस्ट्रॉल", amlodipine: "एम्लोडिपिन" },
  mr: { creatinine: "क्रिएटिनिन", hemoglobin: "हिमोग्लोबिन", haemoglobin: "हिमोग्लोबिन", metformin: "मेटफॉर्मिन", atorvastatin: "अटोरवास्टेटिन", paracetamol: "पॅरासिटामॉल", appointment: "अपॉइंटमेंट", cholesterol: "कोलेस्ट्रॉल", amlodipine: "ॲम्लोडिपिन" },
};
const TOKEN = /[A-Za-z0-9]+|[ऀ-ॿ]+/g;
const ACCENTS = [[/\bvitamin\s+(?:dee|di|the|d3)\b/gi, "vitamin D"], [/\bcheck\s+up\b/gi, "checkup"]];
const HBA1C = /\bh\s*b\s*a\s*(?:1|one|won)\s*c\b|\ba\s*(?:1|one|won)\s*c\b/gi;

/** "h b a 1 c" -> "hba1c", "l d l" -> "ldl", "एल डी एल" -> "ldl": a run of three or more spelled letters is joined; a number between words is left alone. */
function joinSpelledLetters(text) {
  const t = text.replace(HBA1C, (m) => (/^h/i.test(m) ? "HbA1c" : "a1c"));
  const tokens = [...t.matchAll(TOKEN)];
  let out = "", last = 0, i = 0;
  while (i < tokens.length) {
    let j = i;
    const letters = [];
    while (j < tokens.length) {
      const w = tokens[j][0].toLowerCase();
      const letter = LETTER_NAMES[w] || (w.length === 1 && /[a-z0-9]/.test(w) ? w : null);
      if (!letter) break;
      letters.push(letter);
      j += 1;
    }
    if (letters.length >= 3 && letters.some((c) => /[a-z]/.test(c))) {
      const joined = letters.join("").toUpperCase();
      out += t.slice(last, tokens[i].index) + (joined === "HBA1C" ? "HbA1c" : joined);
      last = tokens[j - 1].index + tokens[j - 1][0].length;
      i = j;
    } else i += 1;
  }
  return out + t.slice(last);
}

/** The text with medical words put back together and spelled as in the records. `vocabulary` is the patient's own medicine and test names. A number in the text is never
 *  changed, added or dropped (only "h b a 1 c" style spelling is joined). A split Latin word is replaced by the name; a split Devanagari word by the name in that script. */
export function correctMedicalTerms(text, { lang = "en", vocabulary = [] } = {}) {
  let t = joinSpelledLetters(String(text));
  for (const [re, replacement] of ACCENTS) t = t.replace(re, replacement);
  const names = [...new Set([...GENERAL_TERMS, ...vocabulary])].map((n) => ({ name: n, key: n.toLowerCase().replace(/\s+/g, "") })).filter((n) => n.key.length >= 4);
  const known = new Set(names.map((n) => n.key));
  const tokens = [...t.matchAll(TOKEN)];
  const candidates = [];
  for (let i = 0; i < tokens.length; i += 1) {
    for (let size = 1; size <= Math.min(6, tokens.length - i); size += 1) {
      const words = tokens.slice(i, i + size).map((m) => m[0].toLowerCase());
      if (words.some((w) => /^\d+$/.test(w))) continue;
      const joined = words.join("");
      if (size === 1 && (joined.length < 6 || known.has(joined))) continue;
      if (size > 1 && (words.some((w) => w.length > 8) || joined.length < 6 || joined.length > 18 || words.some((w) => known.has(w)))) continue;
      let best = { score: 0, name: "" };
      for (const n of names) {
        if (Math.abs(n.key.length - joined.length) > 4 && !DEVANAGARI.test(joined)) continue;
        const score = closeness(joined, n.key);
        if (score > best.score) best = { score, name: n.name };
      }
      if (best.score >= 0.88 && (best.name.toLowerCase().replace(/\s+/g, "") !== joined || size > 1)) candidates.push({ score: best.score, letters: joined.length, size, i, name: best.name });
    }
  }
  candidates.sort((a, b) => b.score - a.score || b.letters - a.letters || a.i - b.i);
  const taken = new Set();
  const chosen = [];
  for (const c of candidates) {
    const span = Array.from({ length: c.size }, (_, k) => c.i + k);
    if (span.some((k) => taken.has(k))) continue;
    span.forEach((k) => taken.add(k));
    chosen.push(c);
  }
  chosen.sort((a, b) => a.i - b.i);
  let out = "", last = 0;
  for (const c of chosen) {
    const first = tokens[c.i], final = tokens[c.i + c.size - 1];
    const original = t.slice(first.index, final.index + final[0].length);
    const replacement = DEVANAGARI.test(original) ? (DEVANAGARI_NAMES[lang === "mr" ? "mr" : "hi"][c.name.toLowerCase()] || original) : c.name;
    out += t.slice(last, first.index) + replacement;
    last = final.index + final[0].length;
  }
  return out + t.slice(last);
}

// ------------------------------------------------------------------ "Did I hear you right?"
/** The numbers, dates and medicine names in a sentence: what must not be guessed. */
export function sensitiveTerms(text, vocabulary = []) {
  const found = [];
  const t = String(text);
  for (const m of t.matchAll(/\d+(?:\.\d+)?(?:\s?(?:mg|ml|g|mcg|%|units?))?/gi)) found.push({ kind: "number", text: m[0] });
  const spoken = normaliseSpoken(t, "en");
  if (spoken !== t) for (const m of spoken.matchAll(/\d+(?:\.\d+)?/g)) if (!found.some((f) => f.text.startsWith(m[0]))) found.push({ kind: "number", text: m[0] });
  const lower = t.toLowerCase();
  for (const name of [...MEDICINE_WORDS, ...vocabulary.map((v) => v.toLowerCase())]) if (name.length >= 4 && lower.includes(name)) found.push({ kind: "medicine", text: name });
  return found;
}

/** Should the assistant read back what it heard before acting? Yes when it is not sure (the recogniser's confidence is low) and the sentence holds a number, a date or a
 *  medicine, or when a medicine word had to be repaired (the recogniser got it wrong). Returns what to read back, or null. */
export function needsConfirmation({ heard, corrected, confidence = null, vocabulary = [] }) {
  const items = sensitiveTerms(corrected ?? heard, vocabulary);
  if (!items.length) return null;
  const low = typeof confidence === "number" && confidence < 0.8;
  const repaired = corrected !== undefined && corrected !== heard && sensitiveTerms(corrected, vocabulary).some((x) => x.kind === "medicine") && !sensitiveTerms(heard, vocabulary).some((x) => x.kind === "medicine");
  return low || repaired ? (corrected ?? heard) : null;
}

export const CONFIRM_TEXT = {
  en: (x) => `Did I hear: ${x}? Say yes or no.`,
  hi: (x) => `क्या मैंने सुना: ${x}? हाँ या ना कहिए।`,
  mr: (x) => `मी ऐकले: ${x}. बरोबर आहे का? हो किंवा नाही म्हणा.`,
};
export const isNo = (text) => /^(?:no|nope|nah|cancel|wrong|not right|नहीं|नही|ना|नको|नाही|nahi|nahin)[\s.!]*$/i.test(String(text || "").trim());

// ------------------------------------------------------------------ making an answer fit for the ear
const ABBREVIATIONS_EN = [
  [/HbA1c/g, "H b A one C"], [/\bLDL\b/g, "L D L"], [/\bHDL\b/g, "H D L"], [/\bVLDL\b/g, "V L D L"], [/\bTSH\b/g, "T S H"], [/\bECG\b/g, "E C G"], [/\bEEG\b/g, "E E G"],
  [/\bALT\b/g, "A L T"], [/\bAST\b/g, "A S T"], [/\bALP\b/g, "A L P"], [/\bBUN\b/g, "B U N"], [/\beGFR\b/g, "e G F R"], [/\bLVEF\b/g, "L V E F"], [/\bTMT\b/g, "T M T"], [/\bCBC\b/g, "C B C"],
  [/\bCT\b/g, "C T"], [/\bMRI\b/g, "M R I"], [/\bRBC\b/g, "R B C"], [/\bWBC\b/g, "W B C"], [/\bPSA\b/g, "P S A"], [/\bINR\b/g, "I N R"], [/\bBP\b/g, "blood pressure"], [/\bOPD\b/g, "outpatient department"],
  [/\bRs\.?\s?(?=\d)/g, "rupees "], [/\bDr\.\s/g, "Doctor "], [/\bTab\.\s/g, "Tablet "], [/\bCap\.\s/g, "Capsule "], [/\bInj\.\s/g, "Injection "], [/\bSyp\.\s/g, "Syrup "],
];
const UNITS = {
  en: [[/mg\/dL/gi, "milligrams per decilitre"], [/ng\/mL/gi, "nanograms per millilitre"], [/µg\/dL|mcg\/dL/gi, "micrograms per decilitre"], [/g\/dL/gi, "grams per decilitre"], [/mmol\/L/gi, "millimoles per litre"],
    [/mEq\/L/gi, "milliequivalents per litre"], [/IU\/L/gi, "international units per litre"], [/U\/L/gi, "units per litre"], [/µg|μg|mcg/gi, "micrograms"], [/\bmg\b/gi, "milligrams"], [/\bml\b/gi, "millilitres"],
    [/\bbpm\b/gi, "beats per minute"], [/\bmmHg\b/g, "millimetres of mercury"], [/(\d)\s*%/g, "$1 percent"]],
  hi: [[/mg\/dL/gi, "मिलीग्राम प्रति डेसीलीटर"], [/ng\/mL/gi, "नैनोग्राम प्रति मिलीलीटर"], [/g\/dL/gi, "ग्राम प्रति डेसीलीटर"], [/mmol\/L/gi, "मिलीमोल प्रति लीटर"], [/µg|μg|mcg/gi, "माइक्रोग्राम"],
    [/\bmg\b/gi, "मिलीग्राम"], [/\bml\b/gi, "मिलीलीटर"], [/\bbpm\b/gi, "धड़कन प्रति मिनट"], [/\bmmHg\b/g, "मिलीमीटर पारा"], [/(\d)\s*%/g, "$1 प्रतिशत"]],
  mr: [[/mg\/dL/gi, "मिलीग्रॅम प्रति डेसिलिटर"], [/ng\/mL/gi, "नॅनोग्रॅम प्रति मिलिलिटर"], [/g\/dL/gi, "ग्रॅम प्रति डेसिलिटर"], [/mmol\/L/gi, "मिलीमोल प्रति लिटर"], [/µg|μg|mcg/gi, "मायक्रोग्रॅम"],
    [/\bmg\b/gi, "मिलीग्रॅम"], [/\bml\b/gi, "मिलिलिटर"], [/\bbpm\b/gi, "ठोके प्रति मिनिट"], [/\bmmHg\b/g, "मिलिमीटर पारा"], [/(\d)\s*%/g, "$1 टक्के"]],
};
const SPELLED_DEV = { HbA1c: "एच बी ए वन सी", LDL: "एल डी एल", HDL: "एच डी एल", TSH: "टी एस एच", ECG: "ई सी जी", ALT: "ए एल टी", AST: "ए एस टी", BP: "ब्लड प्रेशर", MRI: "एम आर आय", CT: "सी टी" };
const RANGE = { en: "to", hi: "से", mr: "ते" };
const LESS = { en: "less than", hi: "से कम", mr: "पेक्षा कमी" };
const MORE = { en: "more than", hi: "से ज़्यादा", mr: "पेक्षा जास्त" };
const MONTH_FULL = { en: ENGLISH_MONTH_NAMES, hi: MONTHS.map((m) => m[1]), mr: MONTHS.map((m) => m[2]) };
const SHORT_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
// a few words an engine commonly says badly: written the way they should sound (checked by ear on real devices; keep the list short)
const PRONUNCIATION = [[/\bhaemoglobin\b/gi, "heemoglobin"], [/\bhemoglobin\b/gi, "heemoglobin"], [/\bcreatinine\b/gi, "kree-attinin"], [/\bparacetamol\b/gi, "para-seetamol"], [/\bamlodipine\b/gi, "am-lodipeen"],
  [/\bmetformin\b/gi, "met-formin"], [/\batorvastatin\b/gi, "ator-vastatin"], [/\bglimepiride\b/gi, "glime-piryd"]];

/** The text for the voice: no list marks or symbols, dates, ranges, comparisons, units and abbreviations said in words, in the language of the answer. */
export function speechText(text, lang = "en", limit = 900) {
  let t = String(text || "").replace(/(^|\n)\s*[-–—]\s+/g, "$1").replace(/[••*_#>|`]/g, " ").replace(/:\s*\n+\s*/g, ": ").replace(/\s*\n+\s*/g, ". ").replace(/\.\s*\./g, ".").replace(/\s+/g, " ").trim();
  const language = lang === "hi" || lang === "mr" ? lang : "en";
  // dates: "12 Sep 2026" and "12/09/2026" -> the month in words
  t = t.replace(new RegExp(`\\b(\\d{1,2}) (${SHORT_MONTHS.join("|")}) (\\d{4})\\b`, "g"), (_, d, mon, y) => `${d} ${MONTH_FULL[language][SHORT_MONTHS.indexOf(mon)]} ${y}`);
  t = t.replace(/\b(\d{1,2})\/(\d{1,2})\/(\d{4})\b/g, (m, d, mo, y) => (Number(mo) >= 1 && Number(mo) <= 12 ? `${Number(d)} ${MONTH_FULL[language][Number(mo) - 1]} ${y}` : m));
  // ranges and comparisons next to numbers: "30 - 100", "< 200", "> 5"
  t = t.replace(/(\d(?:\.\d+)?)\s*[-–—]\s*(\d)/g, `$1 ${RANGE[language]} $2`).replace(/(?:<|&lt;)\s*(\d)/g, `${LESS[language]} $1`).replace(/(?:>|&gt;)\s*(\d)/g, `${MORE[language]} $1`);
  t = t.replace(/\s=\s/g, " ").replace(/\s&\s/g, " and ");
  if (language === "en") for (const [pattern, spoken] of ABBREVIATIONS_EN) t = t.replace(pattern, spoken);
  else for (const [word, spoken] of Object.entries(SPELLED_DEV)) t = t.replace(new RegExp(`(?<![A-Za-z0-9])${word}(?![A-Za-z0-9])`, "g"), spoken);
  for (const [pattern, spoken] of UNITS[language]) t = t.replace(pattern, spoken);
  if (language === "en") for (const [pattern, spoken] of PRONUNCIATION) t = t.replace(pattern, spoken);
  t = t.replace(/\s+([.,;:!?।])/g, "$1").replace(/\s+/g, " ").trim();
  if (t.length > limit) {
    const cut = t.slice(0, limit);
    t = cut.slice(0, Math.max(cut.lastIndexOf(". "), 200)) + ". The rest is in the written answer.";
  }
  return t;
}

