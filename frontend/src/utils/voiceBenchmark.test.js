// The voice quality benchmark, browser side. It SCORES the voice layer (it asserts only that the sets loaded) and prints tables; the same file is run
// before and after the voice work so the numbers can be compared.
//   npx vitest run src/utils/voiceBenchmark.test.js
//   VOICE_BENCH_LABEL=baseline npx vitest run src/utils/voiceBenchmark.test.js     also writes backend/tests/voice_benchmark/results/frontend-baseline.json
// Fixtures and the written answers come from backend/tests/voice_benchmark (synthetic data only). The "heard" text of the mishearing set is hand-written,
// not recorded from a real recogniser, so what is measured is the repair layer after the recogniser, never the accuracy of a speech engine.
import { describe, expect, it } from "vitest";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import * as voice from "./voice";

const here = path.dirname(fileURLToPath(import.meta.url));
const bench = path.resolve(here, "../../../backend/tests/voice_benchmark");
const load = (name, fallback = []) => { try { return JSON.parse(fs.readFileSync(path.join(bench, name), "utf8")); } catch { return fallback; } };
const label = process.env.VOICE_BENCH_LABEL || "";
const out = {};
const pct = (n, total) => (total ? Math.round((1000 * n) / total) / 10 : 0);
const show = (title, rows) => console.log(`\n== ${title}\n${rows.map((r) => "  " + r.join("  ")).join("\n")}`);

const wer = (reference, heard) => {
  const r = reference.toLowerCase().split(/\s+/).filter(Boolean);
  const h = heard.toLowerCase().split(/\s+/).filter(Boolean);
  let d = Array.from({ length: h.length + 1 }, (_, j) => j);
  for (let i = 1; i <= r.length; i += 1) {
    const next = [i];
    for (let j = 1; j <= h.length; j += 1) next[j] = Math.min(d[j] + 1, next[j - 1] + 1, d[j - 1] + (r[i - 1] === h[j - 1] ? 0 : 1));
    d = next;
  }
  return d[h.length] / Math.max(1, r.length);
};
// a function the voice work will add: named here so the same benchmark measures it afterwards (absent = scored 0, not skipped)
const optional = (name) => (typeof voice[name] === "function" ? voice[name] : null);

describe("voice benchmark (browser side)", () => {
  it("voice commands: understood when said with filler words, Hinglish and the other languages; questions never taken for a command", () => {
    const sets = load("fixtures/commands.json");
    expect(sets.length).toBeGreaterThan(40);
    const by = {};
    const wrong = [];
    let ok = 0;
    for (const { text, type } of sets) {
      const got = voice.matchVoiceCommand(text)?.type ?? null;
      const good = got === type;
      ok += good;
      const key = type ?? "question (must not match)";
      by[key] = by[key] || [0, 0];
      by[key][0] += good;
      by[key][1] += 1;
      if (!good) wrong.push({ text, expected: type, got });
    }
    const falsePositives = wrong.filter((w) => w.expected === null).length;
    show(`Voice commands (${sets.length})`, [["all", `${pct(ok, sets.length)}%`, `${ok}/${sets.length}`], ...Object.entries(by).map(([k, v]) => [k, `${pct(v[0], v[1])}%`, `${v[0]}/${v[1]}`]), ["questions taken for a command", falsePositives]]);
    out.commands = { n: sets.length, match_pct: pct(ok, sets.length), by_type: Object.fromEntries(Object.entries(by).map(([k, v]) => [k, pct(v[0], v[1])])), false_positives: falsePositives, wrong };
  });

  it("spoken numbers, dates and units are turned into digits and symbols in three languages (a function the voice work adds)", () => {
    const fn = optional("normaliseSpoken");
    const groups = { numbers: load("fixtures/numbers.json"), dates: load("fixtures/dates.json"), units: load("fixtures/units.json") };
    const result = {};
    const rows = [];
    for (const [name, items] of Object.entries(groups)) {
      let ok = 0;
      const wrong = [];
      for (const it2 of items) {
        let got = null;
        try { got = fn ? String(fn(it2.spoken, it2.lang)).trim() : null; } catch { got = null; }
        const good = got !== null && got.replace(/\s+/g, " ").toLowerCase() === it2.value.toLowerCase();
        ok += good;
        if (!good) wrong.push({ spoken: it2.spoken, lang: it2.lang, expected: it2.value, got });
      }
      result[name] = { n: items.length, ok_pct: pct(ok, items.length), implemented: Boolean(fn), wrong };
      rows.push([name, fn ? `${pct(ok, items.length)}%` : "not implemented (0%)", `${ok}/${items.length}`]);
    }
    show("Spoken numbers, dates and units", rows);
    out.normalisation = result;
  });

  it("medical-term repair after the recogniser lowers the word error rate and never changes a number (a function the voice work adds)", () => {
    const degraded = load("fixtures/degraded.json");
    expect(degraded.length).toBeGreaterThan(30);
    const fix = optional("correctMedicalTerms");
    const vocabulary = ["metformin", "atorvastatin", "paracetamol", "hemoglobin", "creatinine", "HbA1c", "vitamin D", "cholesterol", "LDL", "TSH"];
    const before = [];
    const after = [];
    let numberChanged = 0;
    for (const item of degraded) {
      before.push(wer(item.reference, item.heard));
      let repaired = item.heard;
      try { repaired = fix ? fix(item.heard, { lang: item.lang, vocabulary }) : item.heard; } catch { repaired = item.heard; }
      after.push(wer(item.reference, repaired));
      if ((item.heard.match(/\d+(?:\.\d+)?/g) || []).join(",") !== (String(repaired).match(/\d+(?:\.\d+)?/g) || []).join(",")) numberChanged += 1;
    }
    const mean = (a) => a.reduce((x, y) => x + y, 0) / Math.max(1, a.length);
    show(`Medical-term repair (${degraded.length} hand-written mishearings)`, [["word error rate before", `${Math.round(1000 * mean(before)) / 10}%`], ["word error rate after", fix ? `${Math.round(1000 * mean(after)) / 10}%` : "not implemented (unchanged)"], ["phrases where a number was changed", numberChanged]]);
    out.repair = { n: degraded.length, implemented: Boolean(fix), wer_before_pct: Math.round(1000 * mean(before)) / 10, wer_after_pct: Math.round(1000 * mean(after)) / 10, numbers_changed: numberChanged };
  });

  it("how the written answers sound when read aloud: symbols, length, abbreviations, dates and a source", () => {
    const answers = load("results/answers.json");
    if (!answers.length) { out.spoken = { skipped: "run the server benchmark with VOICE_BENCH_LABEL set first (it writes results/answers.json)" }; return; }
    const symbol = /[|•*_#>\[\]{}\\<=]|\s\/\s|\d\/[A-Za-z]/;
    const abbreviation = /\b(?:mg|ml|dL|g\/dL|mg\/dL|ng\/mL|HbA1c|LDL|HDL|TSH|ALT|AST|BP|mmHg|bpm)\b/;
    const monthAbbr = /\b(?:Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b/;
    const words = [];
    const long = [];
    let symbols = 0, abbreviations = 0, months = 0, hasDate = 0, hasSource = 0, cut = 0;
    const perLang = {};
    for (const a of answers) {
      const spoken = voice.speakableText(a.text, a.lang);
      const n = spoken.split(/\s+/).filter(Boolean).length;
      words.push(n);
      if (n > 60) long.push(a.question);
      if (symbol.test(spoken)) symbols += 1;
      if (abbreviation.test(spoken)) { abbreviations += 1; perLang[a.lang] = (perLang[a.lang] || 0) + 1; }
      if (monthAbbr.test(spoken)) months += 1;
      if (/\d{1,2} [A-Z][a-z]{2} \d{4}|\d{4}-\d\d-\d\d|\bon \d/.test(spoken)) hasDate += 1;
      if ((a.sources || []).length) hasSource += 1;
      if (/The rest is in the written answer/.test(spoken)) cut += 1;
    }
    const mean = Math.round(words.reduce((x, y) => x + y, 0) / words.length);
    show(`Answers read aloud (${answers.length})`, [["average spoken words", mean], ["answers over 60 spoken words", `${long.length}/${answers.length}`], ["answers still holding symbols or table marks", `${symbols}/${answers.length}`],
      ["answers with an unspoken-out abbreviation or unit (mg, g/dL, HbA1c, ...)", `${abbreviations}/${answers.length}`], ["answers with an abbreviated month (Oct, Mar, ...)", `${months}/${answers.length}`],
      ["answers cut off by the length limit", `${cut}/${answers.length}`], ["answers that carry a source", `${hasSource}/${answers.length}`], ["... of which a date is spoken", hasDate]]);
    out.spoken = { n: answers.length, mean_words: mean, over_60_words: long.length, with_symbols: symbols, with_abbreviation: abbreviations, abbreviation_by_lang: perLang, with_month_abbreviation: months, cut_off: cut, with_source: hasSource, dates_spoken: hasDate, long };
  });

  it("what the voice layer controls in the time from end of speech to the first spoken word (static: from the code, not a stopwatch)", () => {
    const native = fs.readFileSync(path.resolve(here, "nativeSpeech.js"), "utf8");
    const get = (name) => Number((new RegExp(`const ${name} = (\\d+)`).exec(native) || [])[1]) || null;
    const chat = fs.readFileSync(path.resolve(here, "../components/assistant/AssistantChat.jsx"), "utf8");
    const delays = [...chat.matchAll(/later\(.*?,\s*(\d+)\)/g)].map((m) => Number(m[1]));
    out.latency_static = {
      browser_final_result_to_send_ms: 0,
      native_wait_for_final_text_after_speech_ends_ms: get("FINAL_WAIT_MS"),
      native_no_speech_timeout_ms: get("NO_SPEECH_MS"),
      native_listening_poll_ms: 800,
      hands_free_restart_delays_ms: [...new Set(delays)].sort((a, b) => a - b),
      reply_is_spoken_only_after_the_whole_answer_arrives: !/stream|ReadableStream|EventSource/.test(chat),
      first_spoken_unit: "a sentence-sized chunk (max 180 characters) of the whole answer",
    };
    show("Time from end of speech to first word: what the code adds", Object.entries(out.latency_static).map(([k, v]) => [k, JSON.stringify(v)]));
  });

  it("writes the browser-side results when a label is given", () => {
    if (label) {
      fs.mkdirSync(path.join(bench, "results"), { recursive: true });
      fs.writeFileSync(path.join(bench, "results", `frontend-${label}.json`), JSON.stringify(out, null, 1), "utf8");
    }
    expect(Object.keys(out).length).toBeGreaterThan(0);
  });
});
