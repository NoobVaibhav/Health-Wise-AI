"""Reports that are not lab tables (2D echo, angiography, stress test, lung function, bone density, X-ray, CT, MRI, ultrasound) are recognised,
their key numbers are read and the most important findings come first. All reports are invented."""
import pytest

from app.services import insight_service as ins
from tests import sample_reports as sr
from tests.conftest import upload


def analyse(name):
    text = sr.ALL[name]
    kind = ins.detect_report_type(text)
    return kind, ins.build_narrative_insights(text, kind)


def metric(out, label_start):
    return next(m for m in out["metrics"] if m["label"].startswith(label_start))


@pytest.mark.parametrize("name,kind", [("ECHO", "ECHO"), ("ANGIO", "ANGIO"), ("CT", "CT"), ("XRAY", "XRAY"), ("MRI", "MRI"), ("USG", "ULTRASOUND"), ("TMT", "TMT"), ("PFT", "PFT"), ("DEXA", "DEXA")])
def test_each_kind_of_report_is_recognised_from_its_title(name, kind):
    assert analyse(name)[0] == kind


def test_a_discharge_summary_that_mentions_an_echo_is_not_taken_for_an_echo():
    text = "DISCHARGE SUMMARY\nPatient Name: A B\nDate of admission: 01/01/2026\nHospital course: 2D echo showed LVEF 55%.\nAdvice on discharge: follow up in one week."
    assert ins.detect_report_type(text) == "DISCHARGE"


def test_echo_reads_the_pumping_strength_the_chambers_the_valves_and_the_wall_motion():
    _, out = analyse("ECHO")
    ef = metric(out, "LVEF")
    assert ef["value"] == 35 and ef["unit"] == "%" and ef["concern"] == "attention" and ef["range"] == "55 - 70"
    assert metric(out, "Left ventricle size, end of filling")["concern"] == "normal"                    # 5.8 cm is inside the usual range
    assert metric(out, "Left atrium")["concern"] == "attention"                                         # 4.2 cm is above it
    assert metric(out, "Mitral regurgitation")["value"] == "Moderate" and metric(out, "Mitral regurgitation")["concern"] == "attention"
    assert metric(out, "Tricuspid regurgitation")["value"] == "Mild" and metric(out, "Tricuspid regurgitation")["concern"] == "neutral"
    assert metric(out, "Aortic stenosis")["value"] == "None"                                            # "no aortic stenosis"
    assert metric(out, "Fluid around the heart")["value"] == "None" and metric(out, "Wall motion")["value"] == "Abnormal"
    assert metric(out, "Heart relaxation")["value"] == "Grade II"
    assert out["metrics"][0]["concern"] == "attention"                                                  # what needs a look comes first


def test_angiography_reads_each_artery_and_marks_the_severe_ones():
    _, out = analyse("ANGIO")
    narrowing = {m["label"]: m for m in out["metrics"] if m["label"].endswith("narrowing")}
    assert narrowing["Proximal LAD narrowing"]["value"] == 90 and narrowing["Proximal LAD narrowing"]["detail"] == "Severe narrowing"
    assert narrowing["Mid RCA narrowing"]["detail"] == "Completely blocked" and narrowing["Ostial LCx narrowing"]["detail"] == "Moderate narrowing"
    assert metric(out, "Left main")["value"] == "Normal" and metric(out, "Blood flow")["concern"] == "attention"
    assert metric(out, "LVEF")["value"] == 40
    assert any("Proximal LAD" in f and "marked finding" in f for f in out["red_flags"])
    assert not any(p["text"].startswith("Other findings") for p in out["summary_points"])                     # the arteries are not listed twice                 # a severe narrowing is raised for the doctor


def test_ct_xray_mri_and_ultrasound_findings_and_sizes():
    _, ct = analyse("CT")
    assert metric(ct, "Nodule size")["value"] == "2.1 x 1.8 cm" and metric(ct, "Lymph node size")["value"] == "1.4 cm"
    assert any("suspicious for malignancy" in f["text"] for f in ct["key_findings"] if f["concern"] == "attention")
    _, xr = analyse("XRAY")
    assert metric(xr, "Heart size")["concern"] == "attention" and any("consolidation" in f["text"] for f in xr["key_findings"][:2])
    _, normal = analyse("XRAY_NORMAL")
    assert metric(normal, "Heart size")["concern"] == "normal" and not any(f["concern"] == "attention" for f in normal["key_findings"])
    assert "Nothing in the findings was marked" in normal["summary_points"][2]["text"]
    _, mri = analyse("MRI")
    assert any("canal stenosis" in f["text"] for f in mri["key_findings"] if f["concern"] == "attention")
    _, usg = analyse("USG")
    assert metric(usg, "Calculus size")["value"] == "9 mm" and metric(usg, "Liver size")["concern"] == "attention" and metric(usg, "Spleen size")["concern"] == "normal"


def test_stress_test_lung_function_and_bone_density_numbers():
    _, tmt = analyse("TMT")
    assert metric(tmt, "ST depression")["concern"] == "attention" and metric(tmt, "Result of the test")["value"] == "Positive"
    assert metric(tmt, "Exercise capacity")["concern"] == "normal"
    _, pft = analyse("PFT")
    assert metric(pft, "FEV1 / FVC")["concern"] == "attention" and metric(pft, "FEV1 (air")["value"] == 48 and metric(pft, "FVC (total")["concern"] == "normal"
    _, dexa = analyse("DEXA")
    assert metric(dexa, "Lumbar spine L1-L4, T-score")["value"] == -2.8 and metric(dexa, "Femoral neck, T-score")["value"] == -2.1


def test_the_summary_leads_with_the_conclusion_and_never_with_the_page_header():
    for name in ("ECHO", "ANGIO", "CT", "MRI", "USG", "TMT", "PFT", "DEXA"):
        _, out = analyse(name)
        points = out["summary_points"]
        assert points[1]["text"] == "What the report concludes:" and points[1]["items"]
        everything = " ".join(p["text"] + " ".join(p.get("items", [])) for p in points)
        assert "Patient Name" not in everything and "Age/Sex" not in everything and "DEPARTMENT" not in everything
        assert points[-1]["text"].startswith("This is not a diagnosis")


def test_reports_of_these_kinds_are_accepted_analysed_and_shown_to_the_doctor_and_after_review_the_patient(client, world):
    created = {}
    for name in ("ECHO", "ANGIO", "CT", "XRAY", "TMT", "PFT"):
        r = upload(client, world.employee, world.patient_id, f"{name.lower()}.txt", sr.ALL[name].encode())
        assert r.status_code == 201, (name, r.text)
        created[name] = r.json()["id"]
    seen = {}
    for name, rid in created.items():
        detail = client.get(f"/api/reports/{rid}", headers=world.doctor).json()
        seen[name] = detail
        assert detail["is_narrative"] is True and detail["insights"]["metrics"] and detail["insights"]["summary_points"]
    assert seen["ECHO"]["report_type_label"] == "2D echo (heart ultrasound) report" and seen["ANGIO"]["report_type_label"] == "Coronary angiography report"
    assert seen["CT"]["report_type_label"] == "CT scan report" and seen["XRAY"]["report_type_label"] == "X-ray report"
    patient_before = client.get(f"/api/reports/{created['ECHO']}", headers=world.patient).json()
    assert not patient_before["analysis_visible"]                                                        # nothing for the patient until the doctor has checked it
    assert client.put(f"/api/doctor/reports/{created['ECHO']}/review", headers=world.doctor, json={"decision": "APPROVED", "comment": "Seen."}).status_code == 200
    patient_after = client.get(f"/api/reports/{created['ECHO']}", headers=world.patient).json()
    assert patient_after["analysis_visible"] and "red_flags" not in patient_after["insights"] and "doctor_suggestions" not in patient_after["insights"]
    assert any(m["label"].startswith("LVEF") for m in patient_after["insights"]["metrics"])
