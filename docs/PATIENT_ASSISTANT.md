# Patient Assistant (chat and voice)

Where: **Patient > Ask HealthWise** (`/patient/assistant`). A patient types or speaks a question and gets an answer built from **their
own records**, with links to the original report, prescription, note or appointment.

## 1. How an answer is made

```
 question ─► safety rules (emergency / stop-medicine / diagnosis) ─► intent + test name (EN / HI / MR keywords, chat context)
          ─► read only the records that intent needs (what the patient may already see on their own screens)
          ─► answer written by ordinary code from those records  ─► optional AI wording (only if the patient agreed; validated)
          ─► stored with its sources ─► shown, can be read aloud
```

* The patient comes from the login. The request has **no patient id**; a `patient_id` sent anyway is ignored.
* **Laboratory values are used only from reports a doctor has reviewed** (the same rule as the patient's own report page). Reports still
  waiting for review are mentioned ("N reports are waiting for your doctor's review") but their values are not shown.
* The answer text is produced by code, so numbers, dates, units, ranges and names are the record's own. The optional AI model can only
  reword; its text is **rejected** if any number is added, changed or dropped, if it contains a diagnosis, "you have ...", a medicine
  start/stop/change instruction or a link, or if it is not in the selected script. Then the plain answer is shown.
* Record text (doctor's notes, advice, report names) is **data**. It is never put into the model's instructions: the model gets only the
  already-built answer between `<<<DATA ... DATA>>>` markers with a rule to ignore any instruction inside. Report text extracted from PDFs is never sent.
* Not used for patients: the doctor's private assessment sheets and the doctor-only clinical summary (the patient cannot see those screens).

## 2. What it can answer

| Patient asks | What is returned |
|---|---|
| Last checkup / what did the doctor say | Latest completed visit, doctor's notes, advice and follow-up date, medicines and tests written within two days of it, next appointment |
| A test ("vitamin D", "is my cholesterol high?") | Latest value, unit, date, printed range, lab flag, what the test measures; no verdict; "what about my previous test?" continues the same test |
| Compare / changed over time | Previous and latest value, change, unit check (validated conversions only, else "not comparable"), different printed ranges, conflicts, missing dates |
| Abnormal results / latest report | Values marked outside the printed range / the latest reviewed report |
| Medicines | Prescribed (dose, frequency, duration, instructions, doctor, date, status), **dispensed by the pharmacy**, duplicates, allergy-name matches; "taking" is never assumed |
| Allergies, history, doctor's instructions, appointments, how to prepare | From the health history, advice, tests advised and appointments; "prepare" labels general tips as *not from your records* |
| "What does X mean?" | Short plain-language explanation (10 common terms) labelled general education; unknown terms are admitted |

Missing data is always stated ("No prescription is recorded for you.", "I could not find a result for ...").

## 3. Safety layer (runs before any record is read)

* **Emergency** (severe chest pain, cannot breathe, stroke signs, unconscious, seizure, heavy bleeding, throat/face swelling, suicidal thoughts, overdose; English, Hindi, Marathi):
  immediate guidance to call the emergency number (default 112) or go to the nearest emergency department. No record lookup, no AI, no delay; the answer is read aloud automatically.
  A question about *past* chest pain in the records is not treated as an emergency unless it says it is happening now.
* **Stop/start/change a medicine or dose** -> refused; the prescription as written is shown; speak to the doctor or pharmacist.
* **"Do I have ...?" / "what disease do I have?"** -> refused; documented notes and results are shown.
* **Possible medicine reaction** -> prompt professional assessment; call the emergency number for breathing trouble or face/throat swelling.
* Every answer carries the disclaimer; no false reassurance ("inside the range" never means "healthy"); old prescriptions are not presented as current.

## 4. Voice

* **Speech input**: the browser's SpeechRecognition (Chrome / Edge). The recognised text appears in the box and can be edited before sending.
  A one-time notice says that the browser may send the audio to its speech service; HealthWise AI never records or stores audio.
* **Speech output**: the browser's speechSynthesis with Listen / Pause / Resume / Stop, speed (slow, normal, fast), medical abbreviations and units spelled out (English),
  long text shortened for speaking (the full text stays on screen; sources are never read aloud). A voice reading an emergency answer starts automatically.
* **Fallbacks**: no recognition support, blocked microphone, no microphone, no speech heard, offline, unsupported language: a plain message and the cursor returns to the text box.
  A missing Hindi/Marathi voice on the device is announced instead of reading with the wrong accent.
* There is no server-side transcription endpoint; no third-party speech provider is configured.

## 5. Languages

English, Hindi and Marathi: language selector, suggested questions, and the assistant's own sentences are translated; Hindi/Marathi keywords and Devanagari digits are understood.
The doctor's own words, medicine names and test names stay exactly as written (the assistant never translates a clinician's text). The 10 glossary terms ("what does X mean?") exist in all three languages; the
"what this test measures" sentence comes from the app's English catalog, so in Hindi/Marathi it is given in English with a note. Page menus and buttons are in English.
**The Hindi and Marathi wording was written without a native-speaking clinician's review; have it reviewed before real use.**

## 6. API (patient only; every route needs the patient's token)

| Method and path | Purpose |
|---|---|
| `POST /api/patient-assistant/chat` | `{message (1-1000 chars), conversation_id?, language, ai_consent}` -> `{conversation_id, message, reply{text, sources, safety, intent, ai_used}, disclaimer}` |
| `GET /api/patient-assistant/suggestions?lang=` | Questions that the patient's records can actually answer |
| `GET /api/patient-assistant/info?lang=` | Languages, disclaimer, whether AI wording is configured, emergency number, retention days |
| `GET /api/patient-assistant/conversations` | The patient's own chats |
| `GET /api/patient-assistant/conversations/{id}` | One chat with sources (404 for anyone else's) |
| `DELETE /api/patient-assistant/conversations/{id}` | Delete a chat (404 for anyone else's) |

Errors: 401 not logged in, 403 not a patient, 404 unknown or foreign conversation, 422 bad message, 429 more than 20 messages a minute.

## 7. Database (created automatically at start-up)

`patient_assistant_conversations` (patient, title, language, times), `patient_assistant_messages` (role, text, small metadata: intent, topic for follow-ups, safety kind, ai_used),
`patient_assistant_evidence` (source type, id, label, record date: a pointer, not a copy). Only the visible question and answer are stored: no audio, no hidden reasoning.
Chats older than `ASSISTANT_RETENTION_DAYS` are deleted. The audit log records the conversation id, the kind of question and the safety result, **never the question or the answer**.

## 8. Settings (environment variables)

| Variable | Default | Meaning |
|---|---|---|
| `LLM_API_KEY`, `LLM_API_URL`, `LLM_MODEL` | empty | Optional wording help (already used elsewhere in the app). Without a key the assistant works completely, with the plain wording. |
| `EMERGENCY_NUMBER` | `112` | Number shown in emergency guidance |
| `ASSISTANT_RETENTION_DAYS` | `90` | How long chats are kept |
| `ASSISTANT_RATE_PER_MINUTE` | `20` | Messages per patient per minute (kept in memory per server process; use a shared store behind several workers) |

The frontend never sees the AI key. The patient must tick "Let an outside AI service make answers simpler" (shown only when a key is configured) for the model to be called at all.

## 9. Files

Backend: `services/patient_assistant.py` (intents, retrieval, answers, AI wording, chat), `assistant_safety.py`, `assistant_text.py` (EN/HI/MR wording, glossary), `routers/patient_assistant.py`, `schemas/patient_assistant.py`, 3 models in `database/models.py`, 3 settings in `core/config.py`.
Frontend: `components/assistant/AssistantChat.jsx`, `pages/patient/Assistant.jsx`, `utils/voice.js`, `services/assistantApi.js`, route and menu entry.
Tests: `backend/tests/test_patient_assistant.py` (33), `frontend/src/utils/voice.test.js` (9), `frontend/src/components/assistant/AssistantChat.test.jsx` (9; run with `npm test`).

## 10. Known limitations

* Question understanding is keyword based, not a language model: unusual wording can fall to the help message, and a question that mixes several topics gets one topic's answer. The chips cover the main ones.
* The 10-term glossary is small; test descriptions come from the app's catalog and are English only.
* Hindi/Marathi coverage: sentences are translated, records are not; Hindi/Marathi speech quality depends on voices installed on the patient's device and on the browser's recognition.
* Speech recognition is not available in every browser (Firefox has none) and, in Chrome/Edge, needs an internet connection.
* Records are only as complete as what was entered; a report without a printed date is ordered by upload date and flagged.
* Rate limiting is per server process. Doctor-private assessments are intentionally not used.
* The clinical wording and emergency keyword lists should be reviewed by qualified clinicians before real patient use.

## Easier to read, and next questions (Ask HealthWise)
Each answer shows its lines as short paragraphs with the label in bold, the closing reminder in smaller print, repeated sources once (with a count), and Copy and Listen buttons. After an answer the suggestion chips change to up to three next questions that fit it (ollow_ups in the chat reply, chosen by the topic just answered, only questions the patient's own records can answer, none after an emergency answer). A new answer scrolls into view together with the question that led to it.

## Voice assistant (hands-free, free, no outside voice service)
Everything uses the browser's own speech recognition and speech synthesis: no paid service, no API key, nothing recorded or kept by HealthWise.

- **Round button (orb):** one tap starts a hands-free conversation. The assistant listens, sends what was said as soon as the person stops, reads the answer aloud and listens again. The orb shows the state (breathing, red ripple while listening, spinner while thinking, green bars while speaking) and the words being heard appear live. Tapping it while the assistant speaks interrupts it and listens at once. Two rounds of silence end the conversation with a clear message.
- **Spoken commands:** "stop", "repeat" / "say that again", "speak slower", "speak faster", "clear the chat", "switch to Hindi / Marathi / English", "that's all" (English, Hindi and Marathi wording).
- **Hey HealthWise (beta, optional):** switched on in *Voice settings*; listens for the name only on this page, only after the person turned it on and accepted the privacy note.
- **Small microphone:** unchanged; dictates one question into the box to be checked before sending.
- **Reading aloud:** sentence by sentence (long answers are not cut off), the most natural installed voice first (Edge "Natural"/"Online", then Google), a voice chooser, speed, units and abbreviations said in words, a small sound cue (can be switched off), "read every answer aloud" option.
- **More it understands (fixed rules, `assistant_talk.py`):** greetings by name and time of day, thanks, goodbye, "what can you do", the date and time, **"brief me"** (today's update from the patient's own records: next appointment, results outside the printed range, open medicines, follow-up date) and **"open my reports / medicines / appointments / timeline / health history / notes / advice / profile"**, which opens that page. An emergency message is always answered first and never as small talk.
- **Limits:** the browser decides which speech service hears the voice (Chrome: Google, Edge: Microsoft) and whether Hindi/Marathi voices are installed; a browser without speech recognition (for example Firefox) still gets typing and read-aloud. Fully offline voice recognition would need a large model download and is not included.
