// Number, month and ordinal words in English, Hindi (Devanagari and as written in Latin letters) and Marathi, for turning what is SAID into digits.
// Index in each list = the number: HI_DEV[15] is "पंद्रह". Spellings a recogniser may give for one word are listed after the main one in EXTRA.

const EN_SMALL = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"];
const EN_TENS = { twenty: 20, thirty: 30, forty: 40, fourty: 40, fifty: 50, sixty: 60, seventy: 70, eighty: 80, ninety: 90 };
const EN_ORDINAL_SMALL = ["", "first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth", "tenth", "eleventh", "twelfth", "thirteenth", "fourteenth", "fifteenth", "sixteenth", "seventeenth", "eighteenth", "nineteenth", "twentieth"];

const HI_DEV = ["शून्य", "एक", "दो", "तीन", "चार", "पाँच", "छह", "सात", "आठ", "नौ", "दस", "ग्यारह", "बारह", "तेरह", "चौदह", "पंद्रह", "सोलह", "सत्रह", "अठारह", "उन्नीस", "बीस",
  "इक्कीस", "बाईस", "तेईस", "चौबीस", "पच्चीस", "छब्बीस", "सत्ताईस", "अट्ठाईस", "उनतीस", "तीस", "इकतीस", "बत्तीस", "तैंतीस", "चौंतीस", "पैंतीस", "छत्तीस", "सैंतीस", "अड़तीस", "उनतालीस", "चालीस",
  "इकतालीस", "बयालीस", "तैंतालीस", "चौवालीस", "पैंतालीस", "छियालीस", "सैंतालीस", "अड़तालीस", "उनचास", "पचास", "इक्यावन", "बावन", "तिरपन", "चौवन", "पचपन", "छप्पन", "सत्तावन", "अट्ठावन", "उनसठ", "साठ",
  "इकसठ", "बासठ", "तिरसठ", "चौंसठ", "पैंसठ", "छियासठ", "सड़सठ", "अड़सठ", "उनहत्तर", "सत्तर", "इकहत्तर", "बहत्तर", "तिहत्तर", "चौहत्तर", "पचहत्तर", "छिहत्तर", "सतहत्तर", "अठहत्तर", "उन्यासी", "अस्सी",
  "इक्यासी", "बयासी", "तिरासी", "चौरासी", "पचासी", "छियासी", "सत्तासी", "अट्ठासी", "नवासी", "नब्बे", "इक्यानवे", "बानवे", "तिरानवे", "चौरानवे", "पंचानवे", "छियानवे", "सत्तानवे", "अट्ठानवे", "निन्यानवे", "सौ"];
const HI_ROMAN = ["shunya", "ek", "do", "teen", "chaar", "paanch", "chhe", "saat", "aath", "nau", "das", "gyarah", "barah", "terah", "chaudah", "pandrah", "solah", "satrah", "atharah", "unnis", "bees",
  "ikkis", "baais", "teis", "chaubis", "pachchis", "chhabbis", "sattais", "atthais", "untis", "tees", "ikatis", "battis", "taintis", "chauntis", "paintis", "chhattis", "saintis", "adtis", "untalis", "chalis",
  "iktalis", "bayalis", "taintalis", "chauwalis", "paintalis", "chhiyalis", "saintalis", "adtalis", "unchas", "pachas", "ikyavan", "bavan", "tirpan", "chauvan", "pachpan", "chhappan", "sattavan", "atthavan", "unsath", "saath",
  "iksath", "basath", "tirsath", "chaunsath", "painsath", "chhiyasath", "sarsath", "adsath", "unhattar", "sattar", "ikhattar", "bahattar", "tihattar", "chauhattar", "pachattar", "chhihattar", "satattar", "athattar", "unyasi", "assi",
  "ikyasi", "bayasi", "tirasi", "chaurasi", "pachasi", "chhiyasi", "sattasi", "atthasi", "navasi", "nabbe", "ikyanve", "banve", "tiranve", "chauranve", "panchanve", "chhiyanve", "sattanve", "atthanve", "ninyanve", "sau"];
const MR_DEV = ["शून्य", "एक", "दोन", "तीन", "चार", "पाच", "सहा", "सात", "आठ", "नऊ", "दहा", "अकरा", "बारा", "तेरा", "चौदा", "पंधरा", "सोळा", "सतरा", "अठरा", "एकोणीस", "वीस",
  "एकवीस", "बावीस", "तेवीस", "चोवीस", "पंचवीस", "सव्वीस", "सत्तावीस", "अठ्ठावीस", "एकोणतीस", "तीस", "एकतीस", "बत्तीस", "तेहतीस", "चौतीस", "पस्तीस", "छत्तीस", "सदतीस", "अडतीस", "एकोणचाळीस", "चाळीस",
  "एक्केचाळीस", "बेचाळीस", "त्रेचाळीस", "चव्वेचाळीस", "पंचेचाळीस", "सेहेचाळीस", "सत्तेचाळीस", "अठ्ठेचाळीस", "एकोणपन्नास", "पन्नास", "एक्कावन्न", "बावन्न", "त्रेपन्न", "चोपन्न", "पंचावन्न", "छप्पन्न", "सत्तावन्न", "अठ्ठावन्न", "एकोणसाठ", "साठ",
  "एकसष्ठ", "बासष्ठ", "त्रेसष्ठ", "चौसष्ठ", "पासष्ठ", "सहासष्ठ", "सदुसष्ठ", "अडुसष्ठ", "एकोणसत्तर", "सत्तर", "एक्काहत्तर", "बाहत्तर", "त्र्याहत्तर", "चौर्‍याहत्तर", "पंच्याहत्तर", "शहात्तर", "सत्याहत्तर", "अठ्याहत्तर", "एकोणऐंशी", "ऐंशी",
  "एक्क्याऐंशी", "ब्याऐंशी", "त्र्याऐंशी", "चौऱ्याऐंशी", "पंच्याऐंशी", "शहाऐंशी", "सत्त्याऐंशी", "अठ्ठ्याऐंशी", "एकोणनव्वद", "नव्वद", "एक्क्याण्णव", "ब्याण्णव", "त्र्याण्णव", "चौऱ्याण्णव", "पंच्याण्णव", "शहाण्णव", "सत्त्याण्णव", "अठ्ठ्याण्णव", "नव्व्याण्णव", "शंभर"];

// other spellings of the same words (a recogniser does not spell consistently)
const EXTRA = {
  hi: { "पांच": 5, "छः": 6, "छे": 6, "छ": 6, "पन्द्रह": 15, "पंदरह": 15, "अठाईस": 28, "अट्ठाइस": 28, "चौंतीस": 34, "चौतीस": 34, "चौबिस": 24, "चौवन": 54, "पचीस": 25, "छब्बिस": 26, "सताईस": 27, "इकत्तीस": 31 },
  roman: { "panch": 5, "pach": 5, "chah": 6, "chhah": 6, "che": 6, "chhey": 6, "pandra": 15, "gyaarah": 11, "gyara": 11, "baarah": 12, "bara": 12, "tera": 13, "chaudaha": 14, "solaha": 16, "satra": 17, "athara": 18, "unees": 19, "bis": 20, "tis": 30, "chalees": 40, "pachaas": 50, "saath": 60, "sattar": 70, "assi": 80, "nabbey": 90 },
  mr: { "नव": 9, "पाचं": 5, "तिन": 3, "चौदा": 14, "पंधरा": 15, "पंधरा": 15, "एकोनीस": 19, "अठ्ठावीस": 28, "सत्तावीस": 27, "चौतीस": 34, "छत्तीस": 36 },
};
const toMap = (list, extra = {}) => { const m = new Map(list.map((w, i) => [w, i])); Object.entries(extra).forEach(([w, v]) => m.set(w, v)); return m; };

export const NUMBER_WORDS = {
  en: new Map([...EN_SMALL.map((w, i) => [w, i]), ...Object.entries(EN_TENS), ["a", null]].filter(([, v]) => v !== null)),
  hi: new Map([...toMap(HI_DEV, EXTRA.hi), ...toMap(HI_ROMAN, EXTRA.roman)]),
  mr: toMap(MR_DEV, EXTRA.mr),
};
// words that are also ordinary words and must not become numbers on their own ("do I take it" is not "2 I take it")
export const AMBIGUOUS = new Set(["do", "a", "che", "bis", "tis", "sau", "saath"]);

export const SCALES = {
  en: { hundred: 100, thousand: 1000, lakh: 100000, lac: 100000, million: 1000000 },
  hi: { "सौ": 100, sau: 100, "हज़ार": 1000, "हजार": 1000, hazaar: 1000, hazar: 1000, "लाख": 100000, lakh: 100000 },
  mr: { "शे": 100, "शंभर": 100, "सौ": 100, "हजार": 1000, "हज़ार": 1000, "लाख": 100000 },
};
export const DECIMAL_WORDS = new Set(["point", "dot", "दशमलव", "पूर्णांक", "पॉइंट", "पाईंट", "पॉईंट", "दशांश", "dashmlav", "poorank"]);
export const AND_WORDS = new Set(["and", "aur"]);
export const HALF_PREFIX = [["साढ़े", 0.5], ["साढे", 0.5], ["साडे", 0.5], ["sadhe", 0.5], ["saade", 0.5], ["सवा", 0.25], ["sava", 0.25]];
export const WHOLE_FRACTIONS = new Map([["डेढ़", 1.5], ["डेढ", 1.5], ["दीड", 1.5], ["dedh", 1.5], ["ढाई", 2.5], ["अडीच", 2.5], ["dhai", 2.5], ["adich", 2.5]]);

export const MONTHS = [
  ["january", "जनवरी", "जानेवारी", "jan"], ["february", "फ़रवरी", "फेब्रुवारी", "feb"], ["march", "मार्च", "मार्च", "mar"], ["april", "अप्रैल", "एप्रिल", "apr"], ["may", "मई", "मे", "may"],
  ["june", "जून", "जून", "jun"], ["july", "जुलाई", "जुलै", "jul"], ["august", "अगस्त", "ऑगस्ट", "aug"], ["september", "सितंबर", "सप्टेंबर", "sep"], ["october", "अक्टूबर", "ऑक्टोबर", "oct"],
  ["november", "नवंबर", "नोव्हेंबर", "nov"], ["december", "दिसंबर", "डिसेंबर", "dec"],
];
export const MONTH_EXTRA = { "फरवरी": 1, "सितम्बर": 8, "अक्तूबर": 9, "नवम्बर": 10, "दिसम्बर": 11, "ऑक्टॉबर": 9, "ओक्टोबर": 9, "सेप्टेंबर": 8, "जनेवारी": 0, "septmber": 8 };
export const ENGLISH_MONTH_NAMES = MONTHS.map((m) => m[0][0].toUpperCase() + m[0].slice(1));

/** "twelfth", "third", "twenty first" ... as a number 1 to 31, from the words starting at tokens[i]; { value, used } or null. */
export function ordinalAt(tokens, i) {
  const w = (tokens[i] || "").toLowerCase();
  const small = EN_ORDINAL_SMALL.indexOf(w);
  if (small > 0) return { value: small, used: 1 };
  if (w === "thirtieth") return { value: 30, used: 1 };
  if (w === "twenty" || w === "thirty") {
    const next = EN_ORDINAL_SMALL.indexOf((tokens[i + 1] || "").toLowerCase());
    if (next > 0 && next <= 9) return { value: (w === "twenty" ? 20 : 30) + next, used: 2 };
  }
  return null;
}
