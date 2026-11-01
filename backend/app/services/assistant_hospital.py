"""What the patient assistant can say about the hospital system: bills, scans, hospital stays and operations.

Same rules as the rest of the assistant: only the patient's OWN records, only what the hospital finished and released (a scan report only after the doctor has seen it,
a discharge summary only after it is approved), every answer names its source, a scan report is quoted in the radiologist's words and never explained by the assistant,
and when nothing is on record the assistant says so instead of guessing."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import Admission, DischargeSummary, Invoice, Patient, RadiologyOrder, Surgery
from app.services.clinical_timeline import source

KEYWORDS = {
    "BILLS": ["bill", "invoice", "payment", "paid", "amount due", "outstanding", "receipt", "how much do i owe", "बिल", "भुगतान", "रसीद", "पैसे", "देयक", "पावती", "रक्कम"],
    "SCANS": ["scan", "x-ray", "xray", "x ray", "ultrasound", "sonography", "mri", "mammogra", "स्कैन", "एक्स-रे", "एक्सरे", "अल्ट्रासाउंड", "सोनोग्राफी", "एमआरआई", "एमआरआय"],
    "STAY": ["discharge", "admitted", "hospital stay", "stay in hospital", "my admission", "my operation", "my surgery", "डिस्चार्ज", "भर्ती", "अॅडमिट", "दाखल", "सुट्टी", "ऑपरेशन किया", "शस्त्रक्रिया झाली"],
}

TEXT = {
    "bill_none": {"en": "No bill has been made for you yet.", "hi": "अभी आपका कोई बिल नहीं बना है।", "mr": "अजून तुमचे कोणतेही बिल तयार झालेले नाही."},
    "bill_line": {"en": "Bill {n} ({d}): total Rs {total}, you paid Rs {paid}. {rest}", "hi": "बिल {n} ({d}): कुल Rs {total}, आपने Rs {paid} दिए। {rest}", "mr": "बिल {n} ({d}): एकूण Rs {total}, तुम्ही Rs {paid} दिले. {rest}"},
    "bill_due": {"en": "Rs {x} is still to pay.", "hi": "Rs {x} देना बाकी है।", "mr": "Rs {x} भरायचे बाकी आहे."},
    "bill_clear": {"en": "Nothing is due.", "hi": "कुछ बाकी नहीं है।", "mr": "काही बाकी नाही."},
    "bill_insurer": {"en": "Your insurer approved Rs {x} of it.", "hi": "आपके बीमा ने इसमें से Rs {x} मंज़ूर किए हैं।", "mr": "तुमच्या विम्याने त्यापैकी Rs {x} मंजूर केले आहेत."},
    "bill_foot": {"en": "For any question about a charge, please ask the billing desk.", "hi": "किसी शुल्क के बारे में पूछने के लिए कृपया बिलिंग डेस्क से संपर्क करें।", "mr": "कोणत्याही शुल्काबद्दल विचारण्यासाठी कृपया बिलिंग डेस्कला विचारा."},
    "scan_none": {"en": "There is no scan report on your record yet.", "hi": "आपके रिकॉर्ड में अभी कोई स्कैन रिपोर्ट नहीं है।", "mr": "तुमच्या नोंदीत अजून स्कॅन रिपोर्ट नाही."},
    "scan_ready": {"en": "{s} ({d}): the radiologist wrote: \"{i}\"", "hi": "{s} ({d}): रेडियोलॉजिस्ट ने लिखा: \"{i}\"", "mr": "{s} ({d}): रेडिओलॉजिस्टने लिहिले: \"{i}\""},
    "scan_wait_doc": {"en": "{s}: the report is ready. Your doctor will go through it with you first.", "hi": "{s}: रिपोर्ट तैयार है। आपके डॉक्टर पहले इसे आपके साथ देखेंगे।", "mr": "{s}: रिपोर्ट तयार आहे. तुमचे डॉक्टर आधी ते तुमच्यासोबत पाहतील."},
    "scan_wait": {"en": "{s}: the scan is not reported yet ({st}).", "hi": "{s}: स्कैन की रिपोर्ट अभी नहीं आई ({st})।", "mr": "{s}: स्कॅनचा रिपोर्ट अजून आलेला नाही ({st})."},
    "scan_foot": {"en": "I cannot explain what a scan means. Please ask your doctor.", "hi": "मैं स्कैन का मतलब नहीं समझा सकता। कृपया अपने डॉक्टर से पूछें।", "mr": "मी स्कॅनचा अर्थ सांगू शकत नाही. कृपया तुमच्या डॉक्टरांना विचारा."},
    "stay_none": {"en": "There is no hospital stay or operation on your record.", "hi": "आपके रिकॉर्ड में अस्पताल में भर्ती या ऑपरेशन की कोई जानकारी नहीं है।", "mr": "तुमच्या नोंदीत रुग्णालयातील दाखल किंवा शस्त्रक्रियेची नोंद नाही."},
    "stay_line": {"en": "Stay {n}: admitted on {a}{d}.", "hi": "भर्ती {n}: {a} को भर्ती हुए{d}।", "mr": "दाखल {n}: {a} रोजी दाखल{d}."},
    "stay_out": {"en": ", discharged on {x}", "hi": ", {x} को छुट्टी मिली", "mr": ", {x} रोजी सुट्टी"},
    "stay_in": {"en": " and you are still in hospital", "hi": " और आप अभी अस्पताल में हैं", "mr": " आणि तुम्ही अजून रुग्णालयात आहात"},
    "stay_summary": {"en": "Discharge summary: final diagnosis {fd}. Follow-up: {fu}. Warning signs: {w}", "hi": "डिस्चार्ज सारांश: अंतिम निदान {fd}। फॉलो-अप: {fu}। चेतावनी के संकेत: {w}", "mr": "डिस्चार्ज सारांश: अंतिम निदान {fd}. पाठपुरावा: {fu}. धोक्याची चिन्हे: {w}"},
    "stay_summary_wait": {"en": "Your discharge summary is not ready yet: your doctor has to approve it first.", "hi": "आपका डिस्चार्ज सारांश अभी तैयार नहीं है: पहले आपके डॉक्टर को इसे मंज़ूर करना होगा।", "mr": "तुमचा डिस्चार्ज सारांश अजून तयार नाही: आधी डॉक्टरांनी तो मंजूर करायचा आहे."},
    "surgery_line": {"en": "Operation: {p} on {d}, surgeon {s}.", "hi": "ऑपरेशन: {p}, {d} को, सर्जन {s}।", "mr": "शस्त्रक्रिया: {p}, {d} रोजी, सर्जन {s}."},
    "none_field": {"en": "not written", "hi": "लिखा नहीं गया", "mr": "लिहिलेले नाही"},
    "discuss": {"en": "Please talk to your doctor about anything you are unsure of.", "hi": "जो बात समझ न आए उसके बारे में अपने डॉक्टर से बात करें।", "mr": "जे समजले नाही त्याबद्दल तुमच्या डॉक्टरांशी बोला."},
}


def tt(key: str, lang: str, **kw) -> str:
    entry = TEXT[key]
    return (entry.get(lang) or entry["en"]).format(**kw)


def _money(x: float) -> str:
    return f"{x:,.2f}"


def answer_bills(db: Session, patient: Patient, lang: str) -> dict:
    from app.services import finance_service as fin
    invoices = db.scalars(select(Invoice).where(Invoice.patient_id == patient.id, Invoice.status == "FINAL").order_by(Invoice.id.desc()).limit(3)).all()
    if not invoices:
        return {"text": tt("bill_none", lang), "sources": [], "topic": {"intent": "BILLS"}}
    lines, sources = [], []
    for inv in invoices:
        own_paid = sum(p.amount for p in inv.payments if p.method != "INSURANCE") - fin.refunded(inv)
        approved = fin.insurer_approved(db, inv)
        due = max(0.0, fin.patient_payable(db, inv) - own_paid) if approved else fin.balance(inv)
        rest = tt("bill_due", lang, x=_money(due)) if due > 0 else tt("bill_clear", lang)
        if approved:
            rest = tt("bill_insurer", lang, x=_money(approved)) + " " + rest
        lines.append(tt("bill_line", lang, n=inv.number, d=inv.finalised_at.date().isoformat(), total=_money(inv.total), paid=_money(fin.paid(inv)), rest=rest))
        sources.append(source("invoice", inv.id, f"Bill {inv.number}", inv.finalised_at.date().isoformat()))
    return {"text": "\n".join(lines + [tt("bill_foot", lang)]), "sources": sources, "topic": {"intent": "BILLS"}}


def answer_scans(db: Session, patient: Patient, lang: str) -> dict:
    orders = db.scalars(select(RadiologyOrder).where(RadiologyOrder.patient_id == patient.id, RadiologyOrder.status != "CANCELLED").order_by(RadiologyOrder.id.desc()).limit(4)).all()
    if not orders:
        return {"text": tt("scan_none", lang), "sources": [], "topic": {"intent": "SCANS"}}
    lines, sources = [], []
    for o in orders:
        if o.status == "APPROVED" and o.doctor_seen_at and o.report:
            when = o.approved_at.date().isoformat()
            lines.append(tt("scan_ready", lang, s=o.study, d=when, i=o.report.impression.strip()))
            sources.append(source("radiology", o.id, f"Scan: {o.study}", when))
        elif o.status == "APPROVED":
            lines.append(tt("scan_wait_doc", lang, s=o.study))
        else:
            lines.append(tt("scan_wait", lang, s=o.study, st=o.status.replace("_", " ").lower()))
    return {"text": "\n".join(lines + [tt("scan_foot", lang)]), "sources": sources, "topic": {"intent": "SCANS"}}


def answer_stay(db: Session, patient: Patient, lang: str) -> dict:
    stays = db.scalars(select(Admission).where(Admission.patient_id == patient.id).order_by(Admission.id.desc()).limit(2)).all()
    surgeries = db.scalars(select(Surgery).where(Surgery.patient_id == patient.id, Surgery.status == "COMPLETED").order_by(Surgery.id.desc()).limit(3)).all()
    if not stays and not surgeries:
        return {"text": tt("stay_none", lang), "sources": [], "topic": {"intent": "STAY"}}
    lines, sources = [], []
    for a in stays:
        out = tt("stay_out", lang, x=a.discharged_at.date().isoformat()) if a.discharged_at else tt("stay_in", lang)
        lines.append(tt("stay_line", lang, n=a.admission_no, a=a.admitted_at.date().isoformat(), d=out))
        sources.append(source("admission", a.id, f"Admission {a.admission_no}", a.admitted_at.date().isoformat()))
        if a.discharged_at:
            summary = db.scalar(select(DischargeSummary).where(DischargeSummary.admission_id == a.id))
            if summary is not None and summary.status == "APPROVED":
                nw = tt("none_field", lang)
                lines.append(tt("stay_summary", lang, fd=summary.final_diagnosis or nw, fu=summary.follow_up or nw, w=summary.warning_signs or nw))
            else:
                lines.append(tt("stay_summary_wait", lang))
    for s in surgeries:
        when = (s.completed_at or s.scheduled_start).date().isoformat()
        lines.append(tt("surgery_line", lang, p=s.procedure, d=when, s=s.surgeon.user.full_name))
        sources.append(source("surgery", s.id, f"Surgery: {s.procedure}", when))
    return {"text": "\n".join(lines + [tt("discuss", lang)]), "sources": sources, "topic": {"intent": "STAY"}}
