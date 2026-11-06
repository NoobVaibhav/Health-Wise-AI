import { describe, expect, it } from "vitest";
import { CONFIRM_TEXT, correctMedicalTerms, isNo, needsConfirmation, normaliseSpoken, numberAt, sensitiveTerms, skeleton, speechText } from "./voiceText";

describe("spoken numbers", () => {
  it.each([
    ["fifteen", "en", "15"], ["twenty four", "en", "24"], ["eleven point two", "en", "11.2"], ["one hundred and twenty", "en", "120"], ["five hundred", "en", "500"], ["two thousand twenty six", "en", "2026"],
    ["पंद्रह", "hi", "15"], ["पंधरा", "hi", "15"], ["pandrah", "hi", "15"], ["ग्यारह दशमलव दो", "hi", "11.2"], ["gyarah point do", "hi", "11.2"], ["एक सौ बीस", "hi", "120"], ["पाँच सौ", "hi", "500"], ["चौबीस", "hi", "24"],
    ["पंधरा", "mr", "15"], ["अकरा पूर्णांक दोन", "mr", "11.2"], ["एकशे वीस", "mr", "120"], ["पाचशे", "mr", "500"], ["साडेसात", "mr", "7.5"], ["चोवीस", "mr", "24"], ["दोन हजार सव्वीस", "mr", "2026"],
  ])("%s (%s) is %s", (said, lang, digits) => expect(normaliseSpoken(said, lang)).toBe(digits));

  it("keeps ordinary words that are also number words as they are in a sentence", () => {
    expect(normaliseSpoken("do i take it with food", "hi")).toBe("do i take it with food");
    expect(normaliseSpoken("what about the one before that", "en")).toBe("what about the one before that");
    expect(normaliseSpoken("mere saath aao", "hi")).toBe("mere saath aao");
  });
  it("reads a number inside a sentence and keeps the punctuation after it", () => {
    expect(normaliseSpoken("my sugar was one hundred and forty, and yesterday", "en")).toBe("my sugar was 140, and yesterday");
    expect(numberAt(["six", "point", "eight"], 0, "en")).toEqual({ value: "6.8", used: 3 });
  });
});

describe("spoken dates and units", () => {
  it.each([
    ["twelfth of March", "en", "12 March"], ["third of October", "en", "3 October"], ["twenty first of June", "en", "21 June"], ["fifteen June twenty twenty six", "en", "15 June 2026"],
    ["बारह मार्च", "hi", "12 March"], ["पंद्रह जून दो हज़ार छब्बीस", "hi", "15 June 2026"], ["तीन अक्टूबर", "hi", "3 October"], ["बारा मार्च", "mr", "12 March"], ["पंधरा जून दोन हजार सव्वीस", "mr", "15 June 2026"],
  ])("%s (%s) is %s", (said, lang, date) => expect(normaliseSpoken(said, lang)).toBe(date));
  it.each([
    ["grams per decilitre", "g/dL"], ["milligrams per decilitre", "mg/dL"], ["nanograms per millilitre", "ng/mL"], ["ग्राम प्रति डेसीलीटर", "g/dL"], ["मिलीग्राम प्रति डेसीलीटर", "mg/dL"], ["ग्रॅम प्रति डेसिलिटर", "g/dL"],
    ["beats per minute", "bpm"], ["five percent", "5 %"],
  ])("%s is %s", (said, symbol) => expect(normaliseSpoken(said, "en")).toBe(symbol));
  it("a date and a unit together", () => expect(normaliseSpoken("vitamin d twelve nanograms per millilitre on third of october", "en")).toBe("vitamin d 12 ng/mL on 3 October"));
});

describe("putting medical words back", () => {
  const vocabulary = ["metformin", "atorvastatin", "paracetamol", "hemoglobin", "creatinine", "HbA1c", "vitamin D", "cholesterol", "LDL", "TSH"];
  const fix = (text, lang = "en") => correctMedicalTerms(text, { lang, vocabulary });
  it.each([
    ["do i take met for min", "do i take metformin"], ["tell me about a to ra stat in", "tell me about atorvastatin"], ["do i take para set a mol", "do i take paracetamol"],
    ["how is my creatine in", "how is my creatinine"], ["how is my kreatinin", "how is my creatinine"], ["what is my h b a 1 c", "what is my HbA1c"], ["what is my l d l", "what is my LDL"], ["what is my t s h", "what is my TSH"],
    ["is my colesterol high", "is my cholesterol high"], ["what is my vitamin dee level", "what is my vitamin D level"], ["explain my late st report", "explain my latest report"],
    ["which of my results are ab normal", "which of my results are abnormal"], ["when is my next a point meant", "when is my next appointment"],
  ])("%s -> %s", (heard, fixed) => expect(fix(heard)).toBe(fixed));
  it("puts a split Hindi or Marathi word back in its own script", () => {
    expect(fix("मेरा क्रिएटिन इन कैसा है", "hi")).toBe("मेरा क्रिएटिनिन कैसा है");
    expect(fix("माझा हिमो ग्लोबिन किती आहे", "mr")).toBe("माझा हिमोग्लोबिन किती आहे");
    expect(fix("क्या मैं मेट फॉर्मिन लेता हूं", "hi")).toBe("क्या मैं मेटफॉर्मिन लेता हूं");
    expect(fix("मेरा एच बी ए वन सी कितना है", "hi")).toBe("मेरा HbA1c कितना है");
  });
  it("never changes, adds or drops a number, and leaves a sentence with nothing to repair exactly as it was", () => {
    for (const text of ["my hemoglobin is 11.2 and my sugar was 140 on 12 march", "take 2 tablets after 30 minutes", "do i take 500 mg twice daily", "vitamin d 24 ng/ml on 15 june 2026", "what is my hba1c"]) {
      expect(correctMedicalTerms(text, { vocabulary }).match(/\d+(?:\.\d+)?/g)).toEqual(text.match(/\d+(?:\.\d+)?/g));
    }
    expect(fix("what did my doctor say at my last checkup")).toBe("what did my doctor say at my last checkup");
    expect(fix("take 2 tablets after 30 minutes")).toBe("take 2 tablets after 30 minutes");
  });
  it("does not swallow the words next to a medical word", () => {
    expect(fix("what is my hemo globin")).toBe("what is my hemoglobin");
    expect(fix("is my cole ester all high")).toBe("is my cholesterol high");
  });
  it("a Devanagari and a Latin spelling of one word have the same sound skeleton", () => {
    expect(skeleton("मेटफॉर्मिन")).toBe(skeleton("metformin"));
    expect(skeleton("अटोरवास्टेटिन")).toBe(skeleton("atorvastatin"));
    expect(skeleton("क्रिएटिनिन")).toBe(skeleton("creatinine"));
  });
});

describe("Did I hear you right?", () => {
  it("finds the numbers and medicines in a sentence", () => {
    expect(sensitiveTerms("do i take metformin 500 mg").map((x) => x.kind).sort()).toEqual(["medicine", "number"]);
    expect(sensitiveTerms("what did the doctor say")).toEqual([]);
  });
  it("asks when the recogniser was not sure and the sentence holds a number or a medicine", () => {
    expect(needsConfirmation({ heard: "take 2 tablets", confidence: 0.4 })).toBe("take 2 tablets");
    expect(needsConfirmation({ heard: "take 2 tablets", confidence: 0.95 })).toBeNull();
    expect(needsConfirmation({ heard: "what did the doctor say", confidence: 0.2 })).toBeNull();                 // nothing sensitive: no need to ask
    expect(needsConfirmation({ heard: "take 2 tablets", confidence: null })).toBeNull();                          // a recogniser that gives no confidence is not second-guessed on numbers
  });
  it("asks when a medicine name had to be repaired, whatever the confidence", () => {
    expect(needsConfirmation({ heard: "do i take met for min", corrected: "do i take metformin", confidence: 0.99 })).toBe("do i take metformin");
    expect(needsConfirmation({ heard: "do i take metformin", corrected: "do i take metformin", confidence: 0.99 })).toBeNull();
  });
  it("speaks the question in the three languages and understands no", () => {
    expect(CONFIRM_TEXT.en("take 2 tablets")).toBe("Did I hear: take 2 tablets? Say yes or no.");
    expect(CONFIRM_TEXT.hi("x")).toMatch(/हाँ या ना/);
    expect(CONFIRM_TEXT.mr("x")).toMatch(/हो किंवा नाही/);
    for (const no of ["no", "No.", "नहीं", "नाही", "nahi"]) expect(isNo(no)).toBe(true);
    expect(isNo("no problem tell me my sugar")).toBe(false);
  });
});

describe("making an answer fit for the ear", () => {
  it("says units, ranges, comparisons, abbreviations and dates in words", () => {
    const said = speechText("HbA1c: 6.1 % on 12 Sep 2026, printed range 4.0 - 5.6 %. LDL < 100 mg/dL. BP 120/80 mmHg. Dr. Rao, Tab. Metformin 500 mg.", "en");
    expect(said).toMatch(/H b A one C: 6\.1 percent on 12 September 2026, printed range 4\.0 to 5\.6 percent\./);
    expect(said).toMatch(/L D L less than 100 milligrams per decilitre/);
    expect(said).toMatch(/blood pressure 120\/80 millimetres of mercury/);
    expect(said).toMatch(/Doctor Rao, Tablet met-formin 500 milligrams/);
    expect(said).not.toMatch(/[<%]|\bmg\b|Sep\b/);
  });
  it("says them in Hindi and Marathi, in that language's words", () => {
    expect(speechText("Hemoglobin: 12.1 g/dL on 12/09/2026, range 13.0 - 17.0 g/dL", "hi")).toBe("Hemoglobin: 12.1 ग्राम प्रति डेसीलीटर on 12 सितंबर 2026, range 13.0 से 17.0 ग्राम प्रति डेसीलीटर");
    expect(speechText("Vitamin D 18 ng/mL, 30 - 100", "mr")).toBe("Vitamin D 18 नॅनोग्रॅम प्रति मिलिलिटर, 30 ते 100");
    expect(speechText("HbA1c 6.1 %", "hi")).toBe("एच बी ए वन सी 6.1 प्रतिशत");
  });
  it("leaves no list marks or table bars, and cuts a very long text at a sentence", () => {
    expect(speechText("- one\n- two | three\n* four", "en")).toBe("one. two three. four");
    const long = speechText("This is a sentence. ".repeat(100), "en", 300);
    expect(long.endsWith("The rest is in the written answer.")).toBe(true);
    expect(long.length).toBeLessThan(380);
  });
});
