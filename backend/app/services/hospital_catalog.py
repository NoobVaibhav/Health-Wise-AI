"""Lists the doctor can pick from when writing a prescription: medicines and tests used in the hospital.

Medicines = what the hospital pharmacy has in stock + medicines already prescribed here + a built-in list of common
medicines (so the list is useful even when the stock register is still empty).
Tests = the lab tests this system can read from reports + common lab and scan tests.
The doctor can still type anything that is not in the list: this is only a shortcut, never a restriction."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import MedicineInventory, PrescriptionItem
from app.services.parameter_catalog import PARAMETERS

COMMON_MEDICINES = [
    "Paracetamol 500 mg tablet", "Paracetamol 650 mg tablet", "Ibuprofen 400 mg tablet", "Diclofenac 50 mg tablet",
    "Aspirin 75 mg tablet", "Aspirin 150 mg tablet", "Amoxicillin 500 mg capsule", "Amoxicillin + Clavulanic acid 625 mg tablet",
    "Azithromycin 500 mg tablet", "Ciprofloxacin 500 mg tablet", "Cefixime 200 mg tablet", "Doxycycline 100 mg capsule",
    "Metronidazole 400 mg tablet", "Nitrofurantoin 100 mg capsule", "Cetirizine 10 mg tablet", "Levocetirizine 5 mg tablet",
    "Montelukast 10 mg tablet", "Salbutamol inhaler", "Budesonide inhaler", "Pantoprazole 40 mg tablet",
    "Omeprazole 20 mg capsule", "Rabeprazole 20 mg tablet", "Ranitidine 150 mg tablet", "Domperidone 10 mg tablet",
    "Ondansetron 4 mg tablet", "ORS powder", "Loperamide 2 mg capsule", "Metformin 500 mg tablet",
    "Metformin 1000 mg tablet", "Glimepiride 1 mg tablet", "Glimepiride 2 mg tablet", "Gliclazide 80 mg tablet",
    "Sitagliptin 50 mg tablet", "Insulin glargine injection", "Insulin regular injection", "Amlodipine 5 mg tablet",
    "Amlodipine 10 mg tablet", "Telmisartan 40 mg tablet", "Losartan 50 mg tablet", "Ramipril 5 mg capsule",
    "Atenolol 50 mg tablet", "Metoprolol 50 mg tablet", "Bisoprolol 5 mg tablet", "Hydrochlorothiazide 12.5 mg tablet",
    "Furosemide 40 mg tablet", "Spironolactone 25 mg tablet", "Atorvastatin 10 mg tablet", "Atorvastatin 20 mg tablet",
    "Atorvastatin 40 mg tablet", "Rosuvastatin 10 mg tablet", "Rosuvastatin 20 mg tablet", "Fenofibrate 145 mg tablet",
    "Clopidogrel 75 mg tablet", "Warfarin 5 mg tablet", "Levothyroxine 50 mcg tablet", "Levothyroxine 100 mcg tablet",
    "Vitamin D3 60000 IU capsule", "Vitamin D3 1000 IU tablet", "Calcium + Vitamin D3 tablet", "Vitamin B12 (Methylcobalamin) 1500 mcg tablet",
    "Vitamin B12 injection", "Folic acid 5 mg tablet", "Iron + Folic acid tablet", "Multivitamin tablet", "Omega-3 capsule",
    "Prednisolone 10 mg tablet", "Prednisolone 20 mg tablet", "Dexamethasone 4 mg tablet", "Allopurinol 100 mg tablet",
    "Febuxostat 40 mg tablet", "Colchicine 0.5 mg tablet", "Tramadol 50 mg capsule", "Pregabalin 75 mg capsule",
    "Gabapentin 300 mg capsule", "Alprazolam 0.25 mg tablet", "Escitalopram 10 mg tablet", "Sertraline 50 mg tablet",
    "Amitriptyline 10 mg tablet", "Levetiracetam 500 mg tablet", "Tamsulosin 0.4 mg capsule", "Finasteride 5 mg tablet",
    "Sildenafil 50 mg tablet", "Fluconazole 150 mg tablet", "Clotrimazole cream", "Povidone iodine ointment",
    "Mupirocin ointment", "Diclofenac gel", "Eye drops (lubricant)", "Ciprofloxacin eye drops", "Normal saline nasal drops",
    "Cough syrup (dextromethorphan)", "Ambroxol syrup", "Antacid gel", "Lactulose syrup", "Isabgol (psyllium husk)",
]

COMMON_TESTS = [
    ("Complete Blood Count (CBC)", "Blood"), ("Haemoglobin", "Blood"), ("ESR", "Blood"), ("Peripheral blood smear", "Blood"),
    ("Blood group and Rh factor", "Blood"), ("Fasting blood sugar", "Diabetes"), ("Post-prandial blood sugar", "Diabetes"),
    ("Random blood sugar", "Diabetes"), ("HbA1c (glycated haemoglobin)", "Diabetes"), ("Lipid profile", "Heart"),
    ("Liver function test (LFT)", "Liver"), ("Kidney function test (KFT)", "Kidney"), ("Serum electrolytes (Na, K, Cl)", "Kidney"),
    ("Serum creatinine", "Kidney"), ("Blood urea", "Kidney"), ("Uric acid", "Kidney"), ("Thyroid profile (T3, T4, TSH)", "Thyroid"),
    ("TSH", "Thyroid"), ("Vitamin D (25-OH)", "Vitamins"), ("Vitamin B12", "Vitamins"), ("Serum iron and ferritin", "Vitamins"),
    ("Serum calcium", "Bones"), ("Serum phosphorus", "Bones"), ("CRP (C-reactive protein)", "Infection"),
    ("Widal test", "Infection"), ("Dengue NS1 / IgM", "Infection"), ("Malaria parasite test", "Infection"),
    ("Hepatitis B surface antigen (HBsAg)", "Infection"), ("HIV test", "Infection"), ("COVID-19 RT-PCR", "Infection"),
    ("Urine routine and microscopy", "Urine"), ("Urine culture and sensitivity", "Urine"), ("Urine albumin / creatinine ratio", "Urine"),
    ("Stool routine", "Stool"), ("Stool occult blood", "Stool"), ("Blood culture", "Infection"), ("PSA (prostate specific antigen)", "Other"),
    ("Troponin", "Heart"), ("D-dimer", "Heart"), ("PT / INR", "Blood"), ("ECG", "Heart"), ("2D Echo", "Heart"),
    ("Treadmill test (TMT)", "Heart"), ("Holter monitoring", "Heart"), ("Chest X-ray", "Scan"), ("X-ray (joint / bone)", "Scan"),
    ("Ultrasound abdomen and pelvis", "Scan"), ("Ultrasound KUB", "Scan"), ("CT scan head", "Scan"), ("CT scan chest", "Scan"),
    ("MRI brain", "Scan"), ("MRI spine", "Scan"), ("Doppler study", "Scan"), ("Pulmonary function test (PFT)", "Other"),
    ("Bone density scan (DEXA)", "Scan"), ("Eye check-up", "Other"), ("Audiometry", "Other"), ("Biopsy", "Other"),
]


def medicine_options(db: Session) -> list[dict]:
    """Hospital stock first (marked in_stock), then medicines already prescribed here, then the common list."""
    seen: dict[str, dict] = {}

    def add(name: str | None, in_stock: bool) -> None:
        name = (name or "").strip()
        if len(name) < 2:
            return
        key = name.lower()
        if key in seen:
            seen[key]["in_stock"] = seen[key]["in_stock"] or in_stock
        else:
            seen[key] = {"name": name, "in_stock": in_stock}

    for (name,) in db.execute(select(MedicineInventory.medicine_name).where(MedicineInventory.quantity > 0).distinct()):
        add(name, True)
    for (name,) in db.execute(select(MedicineInventory.medicine_name).distinct()):
        add(name, False)
    for (name,) in db.execute(select(PrescriptionItem.medicine_name).distinct()):
        add(name, False)
    for name in COMMON_MEDICINES:
        add(name, False)
    return sorted(seen.values(), key=lambda m: (not m["in_stock"], m["name"].lower()))


def test_options() -> list[dict]:
    """Common lab / scan tests plus every test this system can read from a report."""
    seen: dict[str, dict] = {}
    for name, group in COMMON_TESTS:
        seen[name.lower()] = {"name": name, "group": group}
    for p in PARAMETERS:
        if not any(p.name.lower() in key for key in seen):
            seen[p.name.lower()] = {"name": p.name, "group": (p.category or "Other").title()}
    return sorted(seen.values(), key=lambda t: t["name"].lower())
