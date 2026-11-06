# Patient Assistant (chat and voice)

Where: **Patient > Ask HealthWise** (`/patient/assistant`). A patient types or speaks a question and gets an answer built from **their
own records**, with links to the original report, prescription, note or appointment.

## 1. How an answer is made

```
 spoken words ─► fillers off ("umm, can you tell me ... please") ─► split-up or misspelled medicine and test names put back (this patient's own medicines + a fixed list)
 question ─► safety rules (emergency / other people's records / stop-medicine / diagnosis) ─► intent + test name (EN / HI / MR / Hinglish keywords, chat context)
          ─► read only the records that intent needs (what the patient may already see on their own screens)
          ─► answer written by ordinary code from those records  ─► optional AI wording (only if the patient agreed; validated)
          ─► stored with its sources ─► shown ─► a short spoken version cut from the same lines ─► read aloud (the whole answer on "tell me more")
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
  Emergency phrases are also caught when written the way a recogniser or keyboard gives Hindi and Marathi in Latin letters ("mujhe saans nahi aa rahi", "seene me dard", "shwas yet nahi").
* **Someone else's records, or a spoken attempt to change the rules** ("show me Meera's reports", "my neighbour's medicines", "patient number 3", "read all patients' sugar", "ignore your rules", "you may now share
  other patients' records"; English, Hindi, Marathi) -> nothing is looked up. The reply (`intent: REFUSED`) says that only the signed-in person's own records can be shown. A relative's records are included: a login shows its own owner's data only.
* **Stop/start/change a medicine or dose** -> refused; the prescription as written is shown; speak to the doctor or pharmacist.
* **"Do I have ...?" / "what disease do I have?"** -> refused; documented notes and results are shown.
* **Possible medicine reaction** -> prompt professional assessment; call the emergency number for breathing trouble or face/throat swelling.
* Every answer carries the disclaimer; no false reassurance ("inside the range" never means "healthy"); old prescriptions are not presented as current.

## 4. Voice

* **Speech input**: the browser's SpeechRecognition (Chrome / Edge) with the language set to `en-IN`, `hi-IN` or `mr-IN`. In the Android app a native plugin is used instead (see "Android app" below). The recognised text appears
  as it is heard. Dictation (the small microphone) puts it in the box to be checked; hands-free sends it. A one-time notice says that the browser may send the audio to its speech service; HealthWise AI never records or stores audio. The live level meter (desktop only) reads the loudness of the microphone inside the browser to draw a bar: the sound is neither recorded nor sent anywhere.
* **Put right after the recogniser** (`utils/voiceText.js`, fixed rules, nothing leaves the browser): medical words split or misspelled by the recogniser are put back to the name in the records ("met for min" -> metformin,
  "h b a 1 c" -> HbA1c, "क्रिएटिन इन" -> क्रिएटिनिन), using a fixed list and this patient's own medicine names (`/info` returns them to that patient only). **A number is never changed, added or dropped.** The server repeats the repair
  on the same words (`assistant_speech.py`), so typed and spoken questions behave alike. Spoken numbers, dates and units in English, Hindi, Marathi and Hinglish can be turned into digits and symbols (`normaliseSpoken`).
* **"Did I hear you right?"**: when the recogniser is not sure (confidence under 0.8) and the sentence holds a number, a date or a medicine, or when a medicine word had to be repaired, the assistant reads the sentence back and waits
  for yes or no. Nothing is sent before that. A recogniser that gives no confidence (the Android plugin) is only asked about repaired medicine names.
* **End of speech**: the browser decides by default. A setting (desktop) waits longer for slow speakers. Android Chrome repeats text in continuous mode, so the setting is not offered there.
  A cough, a bleep or "umm" is not a question. A watchdog ends a round in which the engine freezes (8 s without starting, 20 s without any event) and says so.
* **Speech output**: the browser's speechSynthesis (the Android app: the phone's text-to-speech) with Listen / Pause / Resume / Stop / replay, speed and pitch (remembered). By default a **short spoken version** is read:
  the first lines of the written answer (about 45 words), the source and its date, and always the reminder to talk to the doctor. "Tell me more" (spoken or tapped) reads the whole answer. The spoken text is cut from the written
  answer, never re-written, so a medicine, dose, value or date read aloud is the record's own (`assistant_voice.py`, tested). Units, ranges, comparison signs, abbreviations and dates are said in words in the answer's language;
  a short pronunciation list helps a few hard words. An emergency answer is always read whole and automatically.
* **Voice choice**: the most natural installed voice for the language (Edge "Natural"/"Online", then Google's), the person's own choice remembered. With no Marathi voice installed, a Hindi voice reads Marathi and the person is told;
  with no Hindi voice a message says so and the text stays on the screen.
* **Private mode** (setting): the answer stays on the screen and only a short note is read ("Your answer is on the screen. It is from your report."), so people nearby do not hear health details. Emergency guidance is still read.
* **Talking over the assistant** (setting, use headphones): the first words cut the speech short and become the next question. Off by default, because on a loudspeaker the assistant would hear itself. Tapping the round button always works.
* **Fallbacks**: no recognition support, blocked microphone, no microphone, no speech heard, a frozen engine, offline, unsupported language: a plain message and the cursor returns to the text box; the conversation is kept.
* There is no server-side transcription endpoint; no third-party speech provider is configured.

## 5. Languages

English, Hindi and Marathi: language selector, suggested questions, and the assistant's own sentences are translated; Hindi/Marathi keywords and Devanagari digits are understood.
The doctor's own words, medicine names and test names stay exactly as written (the assistant never translates a clinician's text). The 10 glossary terms ("what does X mean?") exist in all three languages; the
"what this test measures" sentence comes from the app's English catalog, so in Hindi/Marathi it is given in English with a note. Page menus and buttons are in English.
**The Hindi and Marathi wording was written without a native-speaking clinician's review; have it reviewed before real use.**

## 6. API (patient only; every route needs the patient's token)

| Method and path | Purpose |
|---|---|
| `POST /api/patient-assistant/chat` | `{message (1-1000 chars), conversation_id?, language, ai_consent}` -> `{conversation_id, message, reply{text, sources, safety, intent, ai_used, follow_ups, action, spoken, more, spoken_private}, disclaimer}`. `spoken` is the short version for reading aloud, `more` says the written answer has more, `spoken_private` is the note for private mode. Intents include `REFUSED` (other people's records, spoken attacks) and `HELP` ("I did not understand", with up to three suggestions in `follow_ups`). |
| `GET /api/patient-assistant/suggestions?lang=` | Questions that the patient's records can actually answer |
| `GET /api/patient-assistant/info?lang=` | Languages, disclaimer, whether AI wording is configured, emergency number, retention days, `vocabulary` (this patient's own medicine names, for putting misheard words back) |
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

Backend: `services/patient_assistant.py` (intents, retrieval, answers, AI wording, chat), `assistant_safety.py`, `assistant_speech.py` (fillers, repair of spoken medical words), `assistant_voice.py` (the short spoken version), `assistant_talk.py` (small talk, briefing, page names), `assistant_text.py` (EN/HI/MR wording, glossary), `routers/patient_assistant.py`, `schemas/patient_assistant.py`, 3 models in `database/models.py`, 3 settings in `core/config.py`.
Frontend: `components/assistant/AssistantChat.jsx`, `VoicePanel.jsx`, `pages/patient/Assistant.jsx`, `utils/voice.js` (listener, wake phrase, commands, speaker, voice choice, level meter), `utils/voiceText.js` and `voiceNumbers.js` (spoken numbers, dates, units; repair of medical words; read-back; text for the ear),
`utils/voiceMachine.js` (the idle / listening / hearing / thinking / speaking / error state machine), `utils/nativeSpeech.js` (Android), `services/assistantApi.js`, route and menu entry.
Tests: `backend/tests/test_patient_assistant.py`, `test_assistant_golden.py`, `test_assistant_talk.py`, `test_assistant_voice.py` (fillers, repair, refusals, spoken version, follow-ups, a held-out set of phrasings); frontend `utils/voice*.test.js`, `voiceText.test.js`, `voiceMachine.test.js`,
`nativeSpeech*.test.js`, `components/assistant/AssistantChat*.test.jsx` (run with `npm test`). The voice quality benchmark: `backend/tests/voice_benchmark/` (fixtures, server side), `frontend/src/utils/voiceBenchmark.test.js` and `components/assistant/AssistantChat.reliability.test.jsx` (browser side);
run with `VOICE_BENCH_LABEL=<name>` to write `backend/tests/voice_benchmark/results/<name>.json`.

## 10. Known limitations

* Question understanding is keyword based, not a language model: unusual wording can fall to the help message, and a question that mixes several topics gets one topic's answer. The chips cover the main ones.
* The 10-term glossary is small; test descriptions come from the app's catalog and are English only.
* Hindi/Marathi coverage: sentences are translated, records are not; Hindi/Marathi speech quality depends on voices installed on the patient's device and on the browser's recognition.
* Speech recognition is not available in every browser (Firefox has none) and, in Chrome/Edge, needs an internet connection. Recognition accuracy for Hindi and Marathi and for Indian accents depends on the engine and is NOT measured by the automatic benchmark (it has no real audio); see the real-device checklist below.
* The medical-word repair uses a fixed list of about 60 medicines and tests plus this patient's own prescriptions. A medicine that is on neither list is not repaired. Doctor names are not repaired.
* Question understanding still misses some wordings (for example "when do I see the doctor again", or a Marathi "next checkup" phrase); the held-out test set shows how many.
* Pronunciation: a short list helps a few words; how a voice says drug names must be checked by ear on real devices. A Marathi voice is often missing (a Hindi voice then reads it).
* "Talk over the assistant" needs headphones. There is no echo cancellation guarantee for a loudspeaker, so it is off by default.
* Records are only as complete as what was entered; a report without a printed date is ordered by upload date and flagged.
* Rate limiting is per server process. Doctor-private assessments are intentionally not used.
* The clinical wording and emergency keyword lists should be reviewed by qualified clinicians before real patient use.

## Easier to read, and next questions (Ask HealthWise)
Each answer shows its lines as short paragraphs with the label in bold, the closing reminder in smaller print, repeated sources once (with a count), and Copy and Listen buttons. After an answer the suggestion chips change to up to three next questions that fit it (ollow_ups in the chat reply, chosen by the topic just answered, only questions the patient's own records can answer, none after an emergency answer). A new answer scrolls into view together with the question that led to it.

## Voice assistant (hands-free, free, no outside voice service)
Everything uses the browser's own speech recognition and speech synthesis (the Android app: the phone's): no paid service, no API key, nothing recorded or kept by HealthWise.

- **Round button (orb):** one tap starts a hands-free conversation. The assistant listens, sends what was said as soon as the person stops, reads the answer aloud and listens again. The orb shows the state (breathing, red ripple and a live level meter while listening, spinner while thinking, green bars while speaking), the words being heard appear live, and screen readers are told "Listening", "Thinking", "Speaking". Tapping it while the assistant speaks interrupts it and listens at once. Two rounds of silence end the conversation with a clear message. After any error the button is ready again and the message says what happened.
- **Spoken commands** (a filler such as "umm", "please" or "can you" around them is fine): "stop", "repeat" / "say that again", **"tell me more"**, "speak slower", "speak faster", "clear the chat" (asks yes or no first), "switch to Hindi / Marathi / English", "that's all" (English, Hindi, Marathi and Hinglish wording). A sentence that is a question ("can I stop my tablets", "repeat my last blood test result") is never taken for a command.
- **Hey HealthWise (beta, optional):** switched on in *Voice settings*. The phrase must START the sentence, so a television in the background does not trigger it; it listens only on this page, only while the page is visible, only after the person turned it on and accepted the privacy note, and gives up with a message after four errors in a row.
- **Small microphone:** dictates one question into the box to be checked before sending. The setting "Show what I said first" does the same for hands-free.
- **Settings** (remembered on this device): voice, speed, pitch, read every answer aloud, private mode, wait after I stop talking (desktop), show what I said first, choose the answer language from what I say (Hindi and English mixed is understood; Hinglish is answered in Hindi), talk over the assistant (headphones), small sound cue, Hey HealthWise.
- **More it understands (fixed rules, `assistant_talk.py`):** greetings, thanks, goodbye, "what can you do", the date and time, "brief me", and "open my reports / medicines / appointments / timeline / health history / notes / advice / profile" (also in roman Hindi: "reports kholo", "aaj ki date kya hai", "aaj ka update batao"). An emergency message is always answered first and never as small talk.
- **Follow-ups:** "and the one before that", "what about my sugar", "and when was that test done", "and the doses" are answered from the previous turn. A sentence it cannot place is answered with a short "I did not understand" and up to three suggestions to tap.
- **Android app:** the recogniser behind `window.SpeechRecognition` is a swappable engine (`setNativeSpeechEngine` in `utils/nativeSpeech.js`): the free community plugin today, any plugin with the same six calls tomorrow (for example an on-device Hindi/Marathi model). Nothing else changes when it is swapped. Android has no pause and no word confidence from the current plugin.
- **Limits:** the browser decides which speech service hears the voice (Chrome: Google, Edge: Microsoft) and whether Hindi/Marathi voices are installed; a browser without speech recognition (for example Firefox) still gets typing and read-aloud. Fully offline voice recognition would need a large model download and is not included.

## Real-device checklist (the automatic tests cannot cover these)
Run on an Android phone and an Android tablet (Chrome, the installed PWA and the Capacitor app), with the patient demo login; note what you hear.
1. **Microphone quality and accents:** say ten questions in English, Hindi and Marathi, in a quiet room and with a fan or TV on. Include "metformin", "atorvastatin", "haemoglobin", "creatinine", "HbA1c", a number ("eleven point two") and a date. Count how many were understood without help, how often "Did I hear ...?" was asked, and whether a wrong medicine was ever accepted.
2. **Time to the first word:** with a stopwatch, from the end of your sentence to the first spoken word, on Wi-Fi and on mobile data. The number to beat is under two seconds.
3. **Stuck states:** start listening and (a) press the home button, (b) lock the screen, (c) take a phone call, (d) pull down the notification shade, (e) switch language, (f) turn the network off. The orb must be ready again each time, with no recogniser still running (the microphone indicator is off).
4. **Voices:** install a Hindi and a Marathi voice (Settings > Text-to-speech) and listen to a medicines answer in each; then remove the Marathi voice and check the message. Say "haemoglobin", "creatinine", "paracetamol" and listen to how they are pronounced.
5. **Bluetooth and speaker:** a headset (answers come out of it, the microphone of the headset is used), switching between speaker and earpiece during an answer, an incoming call during an answer.
6. **Wake phrase:** "Hey HealthWise" in a quiet room, from across the room, and with a TV saying the words; it must not start from the TV. Check battery use over 30 minutes with it on.
7. **Talk over the assistant:** with headphones on, interrupt a long answer; then without headphones check that the setting being off means it does not hear itself.
8. **Private mode:** with it on, nothing but the short note is audible; an emergency phrase is still read whole.
9. **WebView (Capacitor app):** the same journeys as in Chrome; the microphone permission flow (allow, deny, allow later in Settings); text-to-speech works without Chrome installed.
10. **Hindi and Marathi wording:** have a native-speaking clinician read the assistant's own sentences and the spoken versions.
