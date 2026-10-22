"""Fixed wording of the patient assistant in English, Hindi and Marathi.

Only the assistant's own sentences are translated here. The content of the patient's records (doctor's notes, medicine names,
test names, advice) is shown exactly as it was written; the assistant never translates a doctor's words by itself, because a
translation could change their meaning. The Hindi and Marathi text should be reviewed by a native-speaking clinician before use."""
import re
from datetime import date

LANGUAGES = {"en": "English", "hi": "हिन्दी", "mr": "मराठी"}
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

TEXT: dict[str, dict[str, str]] = {
    "help": {
        "en": "I can answer questions about your own records: your last checkup, reports and test results, medicines, appointments, allergies and your doctor's advice. Please choose one of the suggested questions or ask in your own words.",
        "hi": "मैं आपके अपने रिकॉर्ड के बारे में जवाब दे सकता हूँ: पिछला चेकअप, रिपोर्ट और जाँच के नतीजे, दवाइयाँ, अपॉइंटमेंट, एलर्जी और डॉक्टर की सलाह। कृपया सुझाए गए सवालों में से चुनें या अपने शब्दों में पूछें।",
        "mr": "मी तुमच्या स्वतःच्या नोंदींबद्दल उत्तर देऊ शकतो: मागील तपासणी, रिपोर्ट आणि तपासणीचे निकाल, औषधे, अपॉइंटमेंट, ॲलर्जी आणि डॉक्टरांचा सल्ला. कृपया सुचवलेल्या प्रश्नांपैकी निवडा किंवा तुमच्या शब्दांत विचारा.",
    },
    "disclaimer": {
        "en": "This assistant gives information from your own records. It is not a doctor and cannot diagnose or change your treatment. Medical decisions should be made with qualified healthcare professionals.",
        "hi": "यह सहायक आपके अपने रिकॉर्ड से जानकारी देता है। यह डॉक्टर नहीं है और निदान या इलाज में बदलाव नहीं कर सकता। चिकित्सा संबंधी निर्णय योग्य डॉक्टरों के साथ ही लें।",
        "mr": "हा सहाय्यक तुमच्या स्वतःच्या नोंदींमधील माहिती देतो. हा डॉक्टर नाही आणि निदान किंवा उपचारात बदल करू शकत नाही. वैद्यकीय निर्णय पात्र डॉक्टरांसोबतच घ्या.",
    },
    "emergency": {
        "en": "This may be an emergency. Please call {n} or go to the nearest emergency department right now. Do not wait for an online answer. If you can, ask someone to stay with you.",
        "hi": "यह आपातकालीन स्थिति हो सकती है। कृपया अभी {n} पर कॉल करें या नज़दीकी आपातकालीन विभाग में जाएँ। ऑनलाइन जवाब का इंतज़ार न करें। हो सके तो किसी को अपने साथ रखें।",
        "mr": "ही आणीबाणीची स्थिती असू शकते. कृपया आत्ताच {n} वर कॉल करा किंवा जवळच्या आपत्कालीन विभागात जा. ऑनलाइन उत्तराची वाट पाहू नका. शक्य असल्यास कोणालातरी सोबत ठेवा.",
    },
    "reaction": {
        "en": "If you think a medicine may be causing a reaction, please contact your doctor or get medical assessment promptly. If you have trouble breathing or swelling of the face or throat, call {n} now.",
        "hi": "अगर आपको लगता है कि किसी दवा से प्रतिक्रिया हो रही है, तो कृपया तुरंत अपने डॉक्टर से संपर्क करें या चिकित्सकीय जाँच करवाएँ। साँस लेने में तकलीफ या चेहरे/गले में सूजन हो तो अभी {n} पर कॉल करें।",
        "mr": "एखाद्या औषधाची प्रतिक्रिया होत आहे असे वाटत असल्यास कृपया लगेच डॉक्टरांशी संपर्क साधा किंवा वैद्यकीय तपासणी करा. श्वास घेण्यास त्रास किंवा चेहरा/घशाला सूज असल्यास आत्ताच {n} वर कॉल करा.",
    },
    "med_change": {
        "en": "I cannot tell you to stop, start or change a medicine or its dose. Please speak to your doctor or pharmacist before changing anything.",
        "hi": "मैं दवा या उसकी मात्रा को रोकने, शुरू करने या बदलने की सलाह नहीं दे सकता। कुछ भी बदलने से पहले कृपया अपने डॉक्टर या फार्मासिस्ट से बात करें।",
        "mr": "मी औषध किंवा त्याचा डोस थांबवणे, सुरू करणे किंवा बदलणे याबद्दल सांगू शकत नाही. काहीही बदलण्यापूर्वी कृपया तुमच्या डॉक्टरांशी किंवा फार्मासिस्टशी बोला.",
    },
    "diagnosis": {
        "en": "I cannot diagnose or say which condition you have. I can show what your doctor has written and what your test results say.",
        "hi": "मैं निदान नहीं कर सकता और यह नहीं बता सकता कि आपको कौन सी बीमारी है। मैं डॉक्टर ने जो लिखा है और आपकी जाँच के नतीजे दिखा सकता हूँ।",
        "mr": "मी निदान करू शकत नाही आणि तुम्हाला कोणता आजार आहे हे सांगू शकत नाही. डॉक्टरांनी जे लिहिले आहे आणि तुमचे तपासणी निकाल मी दाखवू शकतो.",
    },
    "no_checkup": {
        "en": "I could not find a completed checkup or a doctor's note in your records.",
        "hi": "आपके रिकॉर्ड में मुझे कोई पूरा हुआ चेकअप या डॉक्टर का नोट नहीं मिला।",
        "mr": "तुमच्या नोंदींमध्ये मला पूर्ण झालेली तपासणी किंवा डॉक्टरांची नोंद सापडली नाही.",
    },
    "checkup_head": {
        "en": "Your most recent visit on record was on {date} with {doctor}.",
        "hi": "आपके रिकॉर्ड में सबसे ताज़ा विज़िट {date} को {doctor} के साथ थी।",
        "mr": "तुमच्या नोंदींमधील सर्वात अलीकडील भेट {date} रोजी {doctor} यांच्यासोबत होती.",
    },
    "visit_reason": {"en": "Reason for the visit: {x}", "hi": "विज़िट का कारण: {x}", "mr": "भेटीचे कारण: {x}"},
    "doctor_wrote": {"en": "Doctor's note ({date}): {x}", "hi": "डॉक्टर का नोट ({date}): {x}", "mr": "डॉक्टरांची नोंद ({date}): {x}"},
    "advice": {"en": "Advice recorded ({date}) - {title}: {x}", "hi": "दर्ज सलाह ({date}) - {title}: {x}", "mr": "नोंदवलेला सल्ला ({date}) - {title}: {x}"},
    "follow_by": {"en": "Follow-up date given: {d}", "hi": "बताई गई फॉलो-अप तारीख: {d}", "mr": "सांगितलेली फॉलो-अप तारीख: {d}"},
    "meds_prescribed": {"en": "Medicines prescribed ({date}): {x}", "hi": "लिखी गई दवाइयाँ ({date}): {x}", "mr": "लिहून दिलेली औषधे ({date}): {x}"},
    "tests_advised": {"en": "Tests advised: {x}", "hi": "सुझाई गई जाँचें: {x}", "mr": "सुचवलेल्या तपासण्या: {x}"},
    "next_appt": {"en": "Next appointment on record: {date} with {doctor}.", "hi": "रिकॉर्ड में अगला अपॉइंटमेंट: {date}, {doctor} के साथ।", "mr": "नोंदीतील पुढील अपॉइंटमेंट: {date}, {doctor} यांच्यासोबत."},
    "no_next_appt": {"en": "No upcoming appointment is recorded.", "hi": "कोई आने वाला अपॉइंटमेंट दर्ज नहीं है।", "mr": "पुढील कोणतीही अपॉइंटमेंट नोंदलेली नाही."},
    "documented_only": {
        "en": "This is what your records say. I have not added anything of my own. You can open the original from the links below.",
        "hi": "यह आपके रिकॉर्ड में लिखा है। मैंने अपनी तरफ से कुछ नहीं जोड़ा है। मूल रिकॉर्ड नीचे दिए लिंक से खोल सकते हैं।",
        "mr": "हे तुमच्या नोंदींमध्ये लिहिले आहे. मी स्वतःहून काहीही जोडलेले नाही. मूळ नोंद खालील लिंकवरून उघडू शकता.",
    },
    "discuss": {
        "en": "Please talk to your doctor about what this means for you.",
        "hi": "इसका आपके लिए क्या मतलब है, यह कृपया अपने डॉक्टर से पूछें।",
        "mr": "याचा तुमच्यासाठी काय अर्थ आहे हे कृपया तुमच्या डॉक्टरांना विचारा.",
    },
    "no_reports": {"en": "No report is available in your records yet.", "hi": "आपके रिकॉर्ड में अभी कोई रिपोर्ट उपलब्ध नहीं है।", "mr": "तुमच्या नोंदींमध्ये अद्याप एकही रिपोर्ट उपलब्ध नाही."},
    "waiting": {
        "en": "{n} report(s) are still waiting for your doctor's review, so their results are not shown here yet.",
        "hi": "{n} रिपोर्ट अभी डॉक्टर की समीक्षा का इंतज़ार कर रही हैं, इसलिए उनके नतीजे यहाँ अभी नहीं दिखाए जा रहे।",
        "mr": "{n} रिपोर्ट अजून डॉक्टरांच्या तपासणीची वाट पाहत आहेत, म्हणून त्यांचे निकाल येथे अद्याप दाखवले जात नाहीत.",
    },
    "report_head": {"en": "Your latest reviewed report is from {date} ({name}).", "hi": "आपकी सबसे ताज़ा समीक्षित रिपोर्ट {date} की है ({name}).", "mr": "तुमचा सर्वात अलीकडील तपासलेला रिपोर्ट {date} चा आहे ({name})."},
    "date_unknown": {"en": "date not printed on the report", "hi": "रिपोर्ट पर तारीख नहीं छपी", "mr": "रिपोर्टवर तारीख छापलेली नाही"},
    "value_line": {"en": "{name}: {value} {unit} ({date}). Lab range: {range}. Lab flag: {flag}.", "hi": "{name}: {value} {unit} ({date})। लैब रेंज: {range}। लैब फ्लैग: {flag}।", "mr": "{name}: {value} {unit} ({date}). लॅब श्रेणी: {range}. लॅब फ्लॅग: {flag}."},
    "flag_WITHIN_RANGE": {"en": "inside the printed range", "hi": "छपी रेंज के अंदर", "mr": "छापलेल्या श्रेणीत"},
    "flag_ABOVE_RANGE": {"en": "above the printed range", "hi": "छपी रेंज से ऊपर", "mr": "छापलेल्या श्रेणीपेक्षा जास्त"},
    "flag_BELOW_RANGE": {"en": "below the printed range", "hi": "छपी रेंज से नीचे", "mr": "छापलेल्या श्रेणीपेक्षा कमी"},
    "flag_UNKNOWN": {"en": "no range printed", "hi": "रेंज नहीं छपी", "mr": "श्रेणी छापलेली नाही"},
    "range_none": {"en": "not provided", "hi": "उपलब्ध नहीं", "mr": "उपलब्ध नाही"},
    "caveat": {
        "en": "A value inside or outside the lab's range does not by itself mean illness or good health. Your doctor reads it together with your whole medical picture.",
        "hi": "लैब की रेंज के अंदर या बाहर का मान अपने आप में बीमारी या अच्छी सेहत नहीं बताता। डॉक्टर इसे आपकी पूरी चिकित्सा स्थिति के साथ देखते हैं।",
        "mr": "लॅबच्या श्रेणीत किंवा बाहेरचे मूल्य म्हणजे आपोआप आजार किंवा चांगले आरोग्य असे नाही. डॉक्टर ते तुमच्या संपूर्ण वैद्यकीय स्थितीसह पाहतात.",
    },
    "test_missing": {"en": "I could not find a result for \"{x}\" in your reviewed reports.", "hi": "आपकी समीक्षित रिपोर्टों में \"{x}\" का नतीजा नहीं मिला।", "mr": "तुमच्या तपासलेल्या रिपोर्टमध्ये \"{x}\" चा निकाल सापडला नाही."},
    "prev_value": {"en": "Earlier result ({date}): {value} {unit}.", "hi": "पिछला नतीजा ({date}): {value} {unit}।", "mr": "आधीचा निकाल ({date}): {value} {unit}."},
    "only_one": {"en": "Only one result is on record for {name}, so there is nothing to compare it with.", "hi": "{name} का केवल एक नतीजा दर्ज है, इसलिए तुलना के लिए कुछ नहीं है।", "mr": "{name} चा फक्त एकच निकाल नोंदलेला आहे, त्यामुळे तुलना करण्यासाठी काही नाही."},
    "change_up": {"en": "Change: it went up by {x} {unit}.", "hi": "बदलाव: यह {x} {unit} बढ़ा है।", "mr": "बदल: हे {x} {unit} ने वाढले आहे."},
    "change_down": {"en": "Change: it went down by {x} {unit}.", "hi": "बदलाव: यह {x} {unit} घटा है।", "mr": "बदल: हे {x} {unit} ने कमी झाले आहे."},
    "change_same": {"en": "Change: the value is the same.", "hi": "बदलाव: मान वही है।", "mr": "बदल: मूल्य तेच आहे."},
    "not_comparable": {
        "en": "The earlier and the latest result use different units that cannot be safely converted, so I am not comparing them.",
        "hi": "पिछले और ताज़ा नतीजों की इकाइयाँ अलग हैं और सुरक्षित रूप से बदली नहीं जा सकतीं, इसलिए मैं तुलना नहीं कर रहा।",
        "mr": "आधीच्या आणि ताज्या निकालांची एकके वेगळी आहेत आणि ती सुरक्षितपणे बदलता येत नाहीत, म्हणून मी तुलना करत नाही.",
    },
    "converted": {"en": "The earlier value was converted to the latest unit with a standard factor.", "hi": "पिछला मान मानक गुणांक से ताज़ा इकाई में बदला गया है।", "mr": "आधीचे मूल्य प्रमाण गुणकाने ताज्या एककात बदलले आहे."},
    "range_changed": {"en": "The two reports print different ranges ({a} and {b}); laboratories can differ.", "hi": "दोनों रिपोर्टों में अलग रेंज छपी हैं ({a} और {b}); लैब अलग हो सकती हैं।", "mr": "दोन्ही रिपोर्टमध्ये वेगळ्या श्रेणी छापल्या आहेत ({a} आणि {b}); लॅब वेगवेगळ्या असू शकतात."},
    "conflict": {"en": "Two values were recorded for the same day: {x}. Please check with the laboratory.", "hi": "एक ही दिन के दो मान दर्ज हैं: {x}। कृपया लैब से जाँच करें।", "mr": "एकाच दिवसाचे दोन मूल्य नोंदलेले आहेत: {x}. कृपया लॅबकडे तपासा."},
    "no_date_warn": {"en": "A report has no printed test date, so the order of results may not match the real test dates.", "hi": "एक रिपोर्ट पर जाँच की तारीख नहीं छपी है, इसलिए क्रम असली तारीखों से अलग हो सकता है।", "mr": "एका रिपोर्टवर चाचणीची तारीख छापलेली नाही, त्यामुळे क्रम खऱ्या तारखांशी जुळणार नाही."},
    "abn_head": {"en": "Results outside the printed range in your newest reviewed reports:", "hi": "आपकी नवीनतम समीक्षित रिपोर्टों में छपी रेंज से बाहर के नतीजे:", "mr": "तुमच्या नवीनतम तपासलेल्या रिपोर्टमध्ये छापलेल्या श्रेणीबाहेरचे निकाल:"},
    "abn_none": {
        "en": "No result is marked outside the printed range in your reviewed reports. That does not prove everything is fine, so please still discuss your reports with your doctor.",
        "hi": "आपकी समीक्षित रिपोर्टों में कोई नतीजा छपी रेंज से बाहर चिह्नित नहीं है। इसका मतलब यह नहीं कि सब ठीक है, इसलिए रिपोर्ट के बारे में डॉक्टर से बात करें।",
        "mr": "तुमच्या तपासलेल्या रिपोर्टमध्ये कोणताही निकाल छापलेल्या श्रेणीबाहेर नोंदलेला नाही. याचा अर्थ सर्व काही ठीक आहे असा होत नाही, म्हणून रिपोर्टबद्दल डॉक्टरांशी बोला.",
    },
    "trend_head": {"en": "Results that have more than one value on record:", "hi": "जिन जाँचों के एक से ज़्यादा नतीजे दर्ज हैं:", "mr": "ज्या तपासण्यांचे एकापेक्षा जास्त निकाल नोंदलेले आहेत:"},
    "trend_none": {"en": "No test appears in more than one reviewed report yet, so there is nothing to compare.", "hi": "अभी कोई जाँच एक से ज़्यादा समीक्षित रिपोर्ट में नहीं है, इसलिए तुलना के लिए कुछ नहीं है।", "mr": "अद्याप कोणतीही तपासणी एकापेक्षा जास्त तपासलेल्या रिपोर्टमध्ये नाही, त्यामुळे तुलना करण्यासाठी काही नाही."},
    "meds_head": {"en": "Medicines on your prescriptions:", "hi": "आपके पर्चों पर लिखी दवाइयाँ:", "mr": "तुमच्या प्रिस्क्रिप्शनवरील औषधे:"},
    "med_line": {
        "en": "{name}: {dose}; {freq}; {dur}. Prescribed {date} by {doctor}. Prescription status: {status}. Pharmacy gave {given} of {qty}.",
        "hi": "{name}: {dose}; {freq}; {dur}। {date} को {doctor} ने लिखी। पर्चे की स्थिति: {status}। फार्मेसी ने {qty} में से {given} दी।",
        "mr": "{name}: {dose}; {freq}; {dur}. {date} रोजी {doctor} यांनी लिहिले. प्रिस्क्रिप्शन स्थिती: {status}. फार्मसीने {qty} पैकी {given} दिले.",
    },
    "rx_status_OPEN": {"en": "open", "hi": "चालू", "mr": "चालू"},
    "rx_status_STOPPED": {"en": "cancelled by the doctor", "hi": "डॉक्टर द्वारा रद्द", "mr": "डॉक्टरांनी रद्द केले"},
    "rx_status_OTHER": {"en": "not open (finished or expired)", "hi": "चालू नहीं (पूरी या समाप्त)", "mr": "चालू नाही (पूर्ण किंवा कालबाह्य)"},
    "not_recorded": {"en": "not recorded", "hi": "दर्ज नहीं", "mr": "नोंदलेले नाही"},
    "med_note": {
        "en": "A prescription shows what the doctor wrote. What the pharmacy gave and what you actually take can be different, and a medicine on an old prescription may no longer be meant for you. If anything is unclear, please confirm it with your doctor or pharmacist.",
        "hi": "पर्चा वही दिखाता है जो डॉक्टर ने लिखा। फार्मेसी ने क्या दिया और आप असल में क्या लेते हैं, यह अलग हो सकता है, और पुराने पर्चे की दवा अब आपके लिए न हो सकती है। कुछ भी अस्पष्ट हो तो डॉक्टर या फार्मासिस्ट से पूछ लें।",
        "mr": "प्रिस्क्रिप्शन म्हणजे डॉक्टरांनी जे लिहिले ते. फार्मसीने काय दिले आणि तुम्ही प्रत्यक्षात काय घेता हे वेगळे असू शकते, आणि जुन्या प्रिस्क्रिप्शनमधील औषध आता तुमच्यासाठी नसू शकते. काही अस्पष्ट असल्यास डॉक्टर किंवा फार्मासिस्टकडून खात्री करा.",
    },
    "med_dup": {"en": "{name} is on more than one open prescription. Please confirm with your prescriber which one applies.", "hi": "{name} एक से ज़्यादा चालू पर्चों पर है। कृपया डॉक्टर से पूछें कि कौन सा लागू है।", "mr": "{name} एकापेक्षा जास्त चालू प्रिस्क्रिप्शनवर आहे. कोणते लागू आहे ते डॉक्टरांना विचारा."},
    "no_meds": {"en": "No prescription is recorded for you.", "hi": "आपके लिए कोई पर्चा दर्ज नहीं है।", "mr": "तुमच्यासाठी कोणतेही प्रिस्क्रिप्शन नोंदलेले नाही."},
    "reported_meds": {"en": "Also entered in your health history (not from a prescription here): {x}", "hi": "स्वास्थ्य इतिहास में भी दर्ज (यहाँ के किसी पर्चे से नहीं): {x}", "mr": "आरोग्य इतिहासातही नोंदलेले (येथील प्रिस्क्रिप्शनवरून नाही): {x}"},
    "allergy_head": {"en": "Allergies recorded in your health history: {x}", "hi": "आपके स्वास्थ्य इतिहास में दर्ज एलर्जी: {x}", "mr": "तुमच्या आरोग्य इतिहासात नोंदलेल्या ॲलर्जी: {x}"},
    "allergy_none": {
        "en": "No allergy is recorded. That may mean none was asked about or entered, so please tell your doctor about any reaction you have had.",
        "hi": "कोई एलर्जी दर्ज नहीं है। हो सकता है पूछी या दर्ज न की गई हो, इसलिए पहले हुई किसी भी प्रतिक्रिया के बारे में डॉक्टर को बताएँ।",
        "mr": "कोणतीही ॲलर्जी नोंदलेली नाही. कदाचित विचारली किंवा नोंदवली गेली नसेल, म्हणून पूर्वी झालेल्या कोणत्याही प्रतिक्रियेबद्दल डॉक्टरांना सांगा.",
    },
    "instr_head": {"en": "Advice and instructions your doctor has recorded:", "hi": "डॉक्टर द्वारा दर्ज सलाह और निर्देश:", "mr": "डॉक्टरांनी नोंदवलेला सल्ला आणि सूचना:"},
    "instr_none": {"en": "No advice or instruction from a doctor is recorded.", "hi": "डॉक्टर की कोई सलाह या निर्देश दर्ज नहीं है।", "mr": "डॉक्टरांचा कोणताही सल्ला किंवा सूचना नोंदलेली नाही."},
    "appt_upcoming": {"en": "Upcoming: {date} with {doctor} ({status}).", "hi": "आने वाला: {date}, {doctor} के साथ ({status})।", "mr": "पुढील: {date}, {doctor} यांच्यासोबत ({status})."},
    "appt_past": {"en": "Earlier: {date} with {doctor} ({status}).", "hi": "पिछला: {date}, {doctor} के साथ ({status})।", "mr": "मागील: {date}, {doctor} यांच्यासोबत ({status})."},
    "appt_none": {"en": "No appointment is recorded for you.", "hi": "आपके लिए कोई अपॉइंटमेंट दर्ज नहीं है।", "mr": "तुमच्यासाठी कोणतीही अपॉइंटमेंट नोंदलेली नाही."},
    "prepare": {
        "en": "General suggestions (not from your records): bring your recent reports and prescriptions, write down your questions and any new symptoms, and note when they started.",
        "hi": "सामान्य सुझाव (आपके रिकॉर्ड से नहीं): हाल की रिपोर्टें और पर्चे साथ लाएँ, अपने सवाल और नए लक्षण लिखें और बताएँ कि वे कब शुरू हुए।",
        "mr": "सर्वसाधारण सूचना (तुमच्या नोंदींमधून नाही): अलीकडील रिपोर्ट आणि प्रिस्क्रिप्शन सोबत आणा, तुमचे प्रश्न आणि नवीन लक्षणे लिहून ठेवा आणि ती केव्हा सुरू झाली ते नोंदवा.",
    },
    "prepare_pending": {"en": "From your records, still to do: {x}", "hi": "आपके रिकॉर्ड के अनुसार बाकी: {x}", "mr": "तुमच्या नोंदींनुसार बाकी: {x}"},
    "term_header": {"en": "{term}: {x}", "hi": "{term}: {x}", "mr": "{term}: {x}"},
    "term_general": {"en": "This is general education, not about your own results. Your doctor can explain what it means for you.", "hi": "यह सामान्य जानकारी है, आपके अपने नतीजों के बारे में नहीं। इसका आपके लिए क्या मतलब है, यह डॉक्टर बता सकते हैं।", "mr": "ही सर्वसाधारण माहिती आहे, तुमच्या स्वतःच्या निकालांबद्दल नाही. याचा तुमच्यासाठी काय अर्थ आहे ते डॉक्टर सांगू शकतात."},
    "term_unknown": {"en": "I do not have a plain-language explanation for \"{x}\". Please ask your doctor or pharmacist.", "hi": "\"{x}\" की सरल व्याख्या मेरे पास नहीं है। कृपया डॉक्टर या फार्मासिस्ट से पूछें।", "mr": "\"{x}\" ची सोपी माहिती माझ्याकडे नाही. कृपया डॉक्टर किंवा फार्मासिस्टला विचारा."},
    "english_only": {"en": "", "hi": "(इस स्पष्टीकरण का पाठ अंग्रेज़ी में है।)", "mr": "(या स्पष्टीकरणाचा मजकूर इंग्रजीत आहे.)"},
}

# Plain-language explanations of common terms, for the "what does X mean" question. General education only.
GLOSSARY: dict[str, dict[str, str]] = {
    "hemoglobin": {"words": ["hemoglobin", "haemoglobin", "हीमोग्लोबिन", "हिमोग्लोबिन"],
                   "en": "Haemoglobin is the protein in red blood cells that carries oxygen around the body.",
                   "hi": "हीमोग्लोबिन लाल रक्त कोशिकाओं में मौजूद प्रोटीन है जो शरीर में ऑक्सीजन पहुँचाता है।",
                   "mr": "हिमोग्लोबिन हे लाल रक्तपेशींमधील प्रथिन आहे जे शरीरात ऑक्सिजन वाहून नेते."},
    "hba1c": {"words": ["hba1c", "glycosylated", "glycated"],
              "en": "HbA1c reflects the average blood sugar over roughly the past two to three months.",
              "hi": "HbA1c पिछले लगभग दो-तीन महीनों के औसत ब्लड शुगर को दर्शाता है।",
              "mr": "HbA1c हे गेल्या सुमारे दोन-तीन महिन्यांतील सरासरी रक्तशर्करा दर्शवते."},
    "cholesterol": {"words": ["cholesterol", "कोलेस्ट्रॉल", "कोलेस्टेरॉल"],
                    "en": "Cholesterol is a fat-like substance in the blood. A lipid profile measures its different types, such as LDL and HDL.",
                    "hi": "कोलेस्ट्रॉल रक्त में मौजूद वसा जैसा पदार्थ है। लिपिड प्रोफ़ाइल इसके अलग-अलग प्रकार, जैसे LDL और HDL, मापती है।",
                    "mr": "कोलेस्टेरॉल हा रक्तातील चरबीसारखा पदार्थ आहे. लिपिड प्रोफाइल त्याचे वेगवेगळे प्रकार, जसे LDL आणि HDL, मोजते."},
    "creatinine": {"words": ["creatinine", "क्रिएटिनिन"],
                   "en": "Creatinine is a waste product from muscles that the kidneys filter out. It is used to check how well the kidneys are working.",
                   "hi": "क्रिएटिनिन मांसपेशियों से बनने वाला अपशिष्ट है जिसे किडनी छानती है। इससे किडनी के काम की जाँच होती है।",
                   "mr": "क्रिएटिनिन हा स्नायूंमधून तयार होणारा टाकाऊ पदार्थ आहे जो मूत्रपिंड गाळते. यावरून मूत्रपिंडाच्या कामाची तपासणी होते."},
    "vitamin d": {"words": ["vitamin d", "विटामिन डी", "व्हिटॅमिन डी", "व्हिटामिन डी"],
                  "en": "Vitamin D helps the body use calcium and keeps bones healthy.",
                  "hi": "विटामिन डी शरीर को कैल्शियम इस्तेमाल करने में मदद करता है और हड्डियों को स्वस्थ रखता है।",
                  "mr": "व्हिटॅमिन डी शरीराला कॅल्शियम वापरण्यास मदत करते आणि हाडे निरोगी ठेवते."},
    "tsh": {"words": ["tsh", "thyroid"],
            "en": "TSH is a hormone from the brain that tells the thyroid gland how much hormone to make. It is used to check thyroid function.",
            "hi": "TSH मस्तिष्क से निकलने वाला हार्मोन है जो थायरॉइड ग्रंथि को बताता है कि कितना हार्मोन बनाना है। इससे थायरॉइड के काम की जाँच होती है।",
            "mr": "TSH हे मेंदूतील संप्रेरक आहे जे थायरॉईड ग्रंथीला किती संप्रेरक तयार करायचे ते सांगते. यावरून थायरॉईडच्या कामाची तपासणी होते."},
    "ecg": {"words": ["ecg", "ekg", "electrocardiogram"],
            "en": "An ECG records the electrical activity of the heart through small stickers on the chest. It is painless.",
            "hi": "ECG छाती पर लगे छोटे स्टिकरों से दिल की बिजली की गतिविधि रिकॉर्ड करता है। इसमें दर्द नहीं होता।",
            "mr": "ECG छातीवरील लहान स्टिकर्सद्वारे हृदयाची विद्युत क्रिया नोंदवते. यात वेदना होत नाहीत."},
    "hypertension": {"words": ["hypertension", "high blood pressure", "उच्च रक्तचाप", "उच्च रक्तदाब"],
                     "en": "Hypertension is the medical word for blood pressure that stays higher than the recommended level over time.",
                     "hi": "हाइपरटेंशन उस स्थिति का चिकित्सीय नाम है जिसमें रक्तचाप लंबे समय तक सुझाए गए स्तर से ऊँचा रहता है।",
                     "mr": "हायपरटेन्शन म्हणजे रक्तदाब दीर्घकाळ शिफारस केलेल्या पातळीपेक्षा जास्त राहणे यासाठीचा वैद्यकीय शब्द."},
    "anemia": {"words": ["anemia", "anaemia", "एनीमिया", "अॅनिमिया", "रक्ताल्पता"],
               "en": "Anaemia means the blood carries less haemoglobin or fewer red blood cells than expected. Doctors look for the reason before suggesting treatment.",
               "hi": "एनीमिया का मतलब है कि खून में हीमोग्लोबिन या लाल कोशिकाएँ अपेक्षा से कम हैं। इलाज से पहले डॉक्टर कारण ढूँढते हैं।",
               "mr": "अॅनिमिया म्हणजे रक्तात अपेक्षेपेक्षा कमी हिमोग्लोबिन किंवा लाल रक्तपेशी असणे. उपचार सुचवण्यापूर्वी डॉक्टर कारण शोधतात."},
    "bp": {"words": ["blood pressure", "बीपी", "रक्तचाप", "रक्तदाब"],
           "en": "Blood pressure is the force of blood against the walls of the arteries. It is written as two numbers, for example 120/80.",
           "hi": "ब्लड प्रेशर वह दबाव है जो खून धमनियों की दीवारों पर डालता है। इसे दो संख्याओं में लिखा जाता है, जैसे 120/80।",
           "mr": "रक्तदाब म्हणजे रक्त धमन्यांच्या भिंतींवर टाकणारा दाब. तो दोन संख्यांमध्ये लिहिला जातो, उदा. 120/80."},
}


def t(key: str, lang: str, **kw) -> str:
    entry = TEXT[key]
    text = entry.get(lang) or entry["en"]
    return text.format(**kw) if kw else text


def fdate(value: str | date | None, lang: str) -> str:
    if not value:
        return t("not_recorded", lang)
    d = value if isinstance(value, date) else date.fromisoformat(str(value)[:10])
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}" if lang == "en" else f"{d.day:02d}/{d.month:02d}/{d.year}"


def normalise_lang(lang: str | None) -> str:
    return lang if lang in LANGUAGES else "en"


def has_devanagari(text: str) -> bool:
    return bool(re.search(r"[ऀ-ॿ]", text))
