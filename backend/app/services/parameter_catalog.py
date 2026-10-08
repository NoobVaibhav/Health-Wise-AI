"""Catalog of supported laboratory parameters.

To support a new parameter, add one entry to PARAMETERS. Nothing else needs to change.
Each entry holds: canonical name, category, aliases (spellings used by different labs),
the report section it appears in ('blood' or 'urine'), and plain-language educational text.

NOTE: this catalog contains NO reference ranges. Ranges always come from the uploaded report.
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ParameterInfo:
    name: str
    category: str
    aliases: tuple[str, ...]
    meaning: str
    why_it_matters: str
    context: str = "blood"                 # 'blood' or 'urine' (decides where aliases may match)
    favorable_direction: str | None = None  # 'down' / 'up' only where a general rule exists
    extra: dict = field(default_factory=dict)


def _p(name, category, aliases, meaning, why, context="blood", favorable=None) -> ParameterInfo:
    return ParameterInfo(name, category, tuple(aliases), meaning, why, context, favorable)


PARAMETERS: list[ParameterInfo] = [
    # ---- Blood glucose ----
    _p("Fasting Glucose", "glucose",
       ["fasting glucose", "fasting blood sugar", "fasting blood glucose", "glucose fasting", "glucose - fasting",
        "glucose (fasting)", "fasting plasma glucose", "fasting plasma sugar", "plasma glucose fasting", "plasma glucose - fasting", "fbs", "fbg", "fpg", "blood sugar fasting", "blood sugar (fasting)"],
       "Fasting glucose measures the sugar in your blood after not eating for several hours.",
       "It reflects how your body handles sugar between meals.", favorable="down"),
    _p("Random Glucose", "glucose",
       ["random glucose", "random blood sugar", "random blood glucose", "rbs", "glucose random",
        "glucose pp", "post prandial glucose", "postprandial glucose", "ppbs", "blood sugar pp",
        "blood sugar post prandial"],
       "Random glucose measures the sugar in your blood at any time of day, regardless of meals.",
       "It gives a snapshot of blood sugar at the moment the sample was taken."),
    _p("Glucose", "glucose", ["blood glucose", "blood sugar", "glucose", "plasma glucose", "serum glucose"],
       "Glucose is the main sugar in your blood and a primary energy source for the body.",
       "It reflects how your body handles sugar at the time of the test.", favorable="down"),
    _p("HbA1c", "glucose",
       ["hba1c", "hb a1c", "hemoglobin a1c", "haemoglobin a1c", "glycated hemoglobin", "glycated haemoglobin",
        "glycosylated hemoglobin", "glycosylated haemoglobin", "glyco hemoglobin", "glycohemoglobin",
        "a1c", "glycated hb"],
       "HbA1c is a blood test related to your average blood glucose levels over the past two to three months.",
       "It shows longer-term blood sugar patterns rather than a single moment.", favorable="down"),

    # ---- Lipid profile ----
    _p("Total Cholesterol", "lipid",
       ["total cholesterol", "cholesterol total", "cholesterol - total", "serum cholesterol", "cholesterol"],
       "Total cholesterol is the overall amount of cholesterol, a fatty substance, in your blood.",
       "Cholesterol is needed by the body, and doctors look at it together with other lipid values.",
       favorable="down"),
    _p("LDL", "lipid",
       ["ldl", "ldl-c", "ldl cholesterol", "ldl cholesterol direct", "ldl direct", "ldl cholesterol calculated",
        "ldl calculated", "low density lipoprotein", "low density lipoprotein cholesterol"],
       "LDL is often called 'bad' cholesterol because it can build up in blood vessel walls.",
       "It is one of the lipid values commonly reviewed when thinking about heart health.", favorable="down"),
    _p("HDL", "lipid",
       ["hdl", "hdl-c", "hdl cholesterol", "hdl cholesterol direct", "high density lipoprotein",
        "high density lipoprotein cholesterol"],
       "HDL is often called 'good' cholesterol because it helps carry cholesterol away from the blood.",
       "It is reviewed together with LDL and triglycerides.", favorable="up"),
    _p("Triglycerides", "lipid", ["triglycerides", "triglyceride", "tg", "serum triglycerides"],
       "Triglycerides are a type of fat in your blood that comes from food and is made by your body.",
       "They are part of the lipid profile and can be affected by recent meals, activity and alcohol.",
       favorable="down"),
    _p("VLDL", "lipid", ["vldl", "vldl cholesterol", "vldl-c", "very low density lipoprotein"],
       "VLDL carries triglycerides through your blood.",
       "It is usually estimated from triglycerides and reviewed with the other lipid values.", favorable="down"),

    # ---- Liver ----
    _p("ALT", "liver", ["alt", "sgpt", "alt (sgpt)", "alt/sgpt", "alanine aminotransferase", "alanine transaminase"],
       "ALT is an enzyme found mainly in the liver.",
       "It is one of several liver blood tests that doctors review together."),
    _p("AST", "liver", ["ast", "sgot", "ast (sgot)", "ast/sgot", "aspartate aminotransferase",
                        "aspartate transaminase"],
       "AST is an enzyme found in the liver and also in muscles and other organs.",
       "It is reviewed together with ALT and other liver tests."),
    _p("ALP", "liver", ["alp", "alkaline phosphatase", "alk phos", "alkaline phosphatase (alp)"],
       "ALP is an enzyme found in the liver, bile ducts and bones.",
       "It is one of the standard liver and bone related blood tests."),
    _p("Bilirubin", "liver", ["total bilirubin", "bilirubin total", "bilirubin - total", "bilirubin (total)",
                              "bilirubin", "serum bilirubin"],
       "Bilirubin is a yellow substance made when old red blood cells are broken down and processed by the liver.",
       "It is part of standard liver function tests."),
    _p("Direct Bilirubin", "liver", ["direct bilirubin", "bilirubin direct", "bilirubin - direct",
                                     "conjugated bilirubin"],
       "Direct bilirubin is the part of bilirubin that has already been processed by the liver.",
       "It is reviewed together with total bilirubin."),
    _p("Albumin", "liver", ["albumin", "serum albumin"],
       "Albumin is the main protein made by the liver and found in blood.",
       "It helps keep fluid in the blood vessels and carries substances around the body."),
    _p("Total Protein", "liver", ["total protein", "protein total", "protein - total", "serum protein",
                                  "total proteins"],
       "Total protein measures all the proteins in the blood, mainly albumin and globulins.",
       "It gives a general picture of nutrition and liver/kidney function when read with other tests."),

    # ---- Kidney ----
    _p("Creatinine", "kidney", ["creatinine", "serum creatinine", "s. creatinine", "creatinine serum"],
       "Creatinine is a waste product from normal muscle activity that the kidneys filter out.",
       "It is a standard test used to look at how well the kidneys are filtering blood."),
    _p("Urea", "kidney", ["urea", "blood urea", "serum urea", "urea serum"],
       "Urea is a waste product formed when the body breaks down protein.",
       "It is reviewed with creatinine as part of kidney function tests."),
    _p("BUN", "kidney", ["bun", "blood urea nitrogen", "urea nitrogen", "serum urea nitrogen"],
       "BUN measures the nitrogen from urea, a waste product from protein breakdown.",
       "It is reviewed with creatinine as part of kidney function tests."),
    _p("eGFR", "kidney", ["egfr", "e-gfr", "estimated gfr", "estimated glomerular filtration rate",
                          "glomerular filtration rate", "gfr"],
       "eGFR is an estimate of how much blood your kidneys filter each minute, calculated from creatinine, age and sex.",
       "It is commonly used to track kidney function over time.", favorable="up"),
    _p("Uric Acid", "kidney", ["uric acid", "serum uric acid", "uric acid serum"],
       "Uric acid is a waste product formed when the body breaks down substances called purines.",
       "It is affected by diet, hydration and how well the body clears it."),

    # ---- Vitamins ----
    _p("Vitamin D", "vitamin",
       ["vitamin d", "vitamin d3", "25-oh vitamin d", "25 oh vitamin d", "25(oh) vitamin d", "25-hydroxy vitamin d",
        "25 hydroxy vitamin d", "vitamin d total", "vitamin d, 25 hydroxy", "vitamin d 25 hydroxy",
        "25-hydroxyvitamin d", "25 (oh) vitamin d"],
       "Vitamin D supports bone health and many body functions. The body makes it from sunlight and gets it from some foods.",
       "Levels are influenced by sun exposure, diet and season."),
    _p("Vitamin B12", "vitamin", ["vitamin b12", "vitamin b-12", "vit b12", "vit. b12", "b12", "cyanocobalamin",
                                  "cobalamin"],
       "Vitamin B12 helps nerves and blood cells work properly and comes mainly from animal-based foods.",
       "Levels are influenced by diet and by how well the body absorbs the vitamin."),

    # ---- Thyroid ----
    _p("TSH", "thyroid", ["tsh", "thyroid stimulating hormone", "thyrotropin", "tsh ultrasensitive",
                          "tsh (ultrasensitive)", "s. tsh"],
       "TSH is a hormone from the pituitary gland that tells the thyroid gland how much hormone to make.",
       "It is the most common first test used to look at thyroid function."),
    _p("Free T3", "thyroid", ["free t3", "ft3", "free triiodothyronine", "t3 free", "t3, free"],
       "Free T3 is the active, unbound form of a thyroid hormone in the blood.",
       "It is reviewed with TSH and T4 to understand thyroid hormone levels."),
    _p("Free T4", "thyroid", ["free t4", "ft4", "free thyroxine", "t4 free", "t4, free"],
       "Free T4 is the active, unbound form of the main thyroid hormone in the blood.",
       "It is reviewed with TSH to understand thyroid function."),
    _p("T3", "thyroid", ["t3", "total t3", "t3 total", "triiodothyronine", "total triiodothyronine", "t3, total"],
       "T3 (total) measures the thyroid hormone triiodothyronine in the blood, both bound and unbound.",
       "It is reviewed with TSH and T4 to understand thyroid hormone levels."),
    _p("T4", "thyroid", ["t4", "total t4", "t4 total", "thyroxine", "total thyroxine", "t4, total"],
       "T4 (total) measures the thyroid hormone thyroxine in the blood, both bound and unbound.",
       "It is reviewed with TSH to understand thyroid function."),

    # ---- CBC ----
    _p("Hemoglobin", "cbc", ["hemoglobin", "haemoglobin", "hb", "hgb", "hemoglobin (hb)", "haemoglobin (hb)"],
       "Hemoglobin is the protein in red blood cells that carries oxygen around the body.",
       "It is one of the main values in a complete blood count."),
    _p("RBC", "cbc", ["rbc", "rbc count", "total rbc count", "total rbc", "red blood cell count",
                      "red blood cells", "red blood cell", "erythrocyte count", "erythrocytes"],
       "RBC is the number of red blood cells, which carry oxygen.",
       "It is reviewed with hemoglobin and hematocrit."),
    _p("WBC", "cbc", ["wbc", "wbc count", "total wbc count", "total wbc", "white blood cell count",
                      "white blood cells", "total leucocyte count", "total leukocyte count", "tlc",
                      "leucocyte count", "leukocyte count", "leucocytes"],
       "WBC is the number of white blood cells, which are part of your immune system.",
       "It can change with infections, stress, medicines and other factors."),
    _p("Platelets", "cbc", ["platelets", "platelet count", "plt", "platelet", "thrombocytes"],
       "Platelets are small blood cells that help your blood clot.",
       "The count is part of a standard complete blood count."),
    _p("Hematocrit", "cbc", ["hematocrit", "haematocrit", "hct", "pcv", "packed cell volume", "hematocrit (hct)"],
       "Hematocrit is the percentage of your blood made up of red blood cells.",
       "It is reviewed with hemoglobin and RBC count."),
    _p("MCV", "cbc", ["mcv", "mean corpuscular volume", "mean cell volume"],
       "MCV is the average size of your red blood cells.",
       "It helps doctors understand the type of changes in red blood cells."),
    _p("MCH", "cbc", ["mch", "mean corpuscular hemoglobin", "mean corpuscular haemoglobin",
                      "mean cell hemoglobin"],
       "MCH is the average amount of hemoglobin in a red blood cell.",
       "It is reviewed with MCV and MCHC."),
    _p("MCHC", "cbc", ["mchc", "mean corpuscular hemoglobin concentration",
                       "mean corpuscular haemoglobin concentration", "mean cell hemoglobin concentration"],
       "MCHC is the average concentration of hemoglobin in your red blood cells.",
       "It is reviewed with MCV and MCH."),

    # ---- Urine (only matched inside a urine section) ----
    _p("Urine Protein", "urine", ["protein", "urine protein", "albumin urine", "urinary protein"],
       "Urine protein checks for protein in the urine, which is normally present only in very small amounts.",
       "It is part of a routine urine examination.", context="urine"),
    _p("Urine Glucose", "urine", ["glucose", "urine glucose", "urinary glucose", "sugar", "urine sugar"],
       "Urine glucose checks for sugar in the urine, which is normally not present or very low.",
       "It is part of a routine urine examination.", context="urine"),
    _p("Urine RBC", "urine", ["rbc", "rbcs", "red blood cells", "red cells", "red blood cell", "erythrocytes"],
       "Urine RBC counts red blood cells seen in the urine sample.",
       "It is part of a routine urine examination.", context="urine"),
    _p("Urine WBC", "urine", ["wbc", "wbcs", "white blood cells", "pus cells", "leucocytes", "leukocytes",
                              "white blood cell"],
       "Urine WBC (pus cells) counts white blood cells seen in the urine sample.",
       "It is part of a routine urine examination.", context="urine"),
    _p("Specific Gravity", "urine", ["specific gravity", "sp. gravity", "sp gravity", "urine specific gravity", "sg"],
       "Specific gravity shows how concentrated your urine is.",
       "It is affected by how much fluid you have had.", context="urine"),
    _p("Urine pH", "urine", ["ph", "urine ph", "reaction ph"],
       "Urine pH shows how acidic or alkaline your urine is.",
       "It can change with diet and hydration.", context="urine"),
]

# General, non-diagnostic lifestyle wording per category (used by the deterministic explanation).
CATEGORY_LIFESTYLE: dict[str, str] = {
    "glucose": "Regular meals with plenty of vegetables, whole grains and fibre, limiting sugary drinks and sweets, "
               "daily walking and good sleep are general habits that support healthy blood sugar patterns.",
    "lipid": "Eating more fibre, fruits, vegetables, nuts and fish, limiting fried and highly processed foods, "
             "staying physically active and not smoking are general habits that support healthy cholesterol and fat levels.",
    "liver": "Moderating alcohol, keeping a healthy weight, choosing balanced meals and staying active are general "
             "habits that support liver health. Always check with a doctor before using supplements or herbal products.",
    "kidney": "Drinking enough water through the day, limiting excess salt, and keeping blood pressure and blood sugar "
              "in a healthy zone are general habits that support kidney health.",
    "vitamin": "Balanced meals, safe sun exposure and regular outdoor activity are general habits that support "
               "vitamin levels. Please do not start high-dose supplements without a doctor's advice.",
    "thyroid": "Balanced meals, regular sleep and stress management are general wellness habits. Thyroid results "
               "should always be interpreted by a doctor.",
    "cbc": "Balanced meals with a variety of foods, good hydration, regular activity and enough sleep are general "
           "habits that support overall blood health.",
    "urine": "Drinking enough water through the day and keeping a balanced diet are general habits that support "
             "urinary health.",
}

_ALIAS_LOOKUP = {p.name: p for p in PARAMETERS}


def get_parameter_info(normalized_name: str) -> ParameterInfo | None:
    return _ALIAS_LOOKUP.get(normalized_name)
