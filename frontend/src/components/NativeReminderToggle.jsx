// "Reminders on this phone": the switch for the medicine reminders that the Android app shows by itself. Only shown inside the Android app, and only to patients.
import { useEffect, useState } from "react";
import { disableReminders, enableReminders, isNativeApp, permissionState, remindersEnabled } from "../utils/nativeNotifications";

const WORDS = {
  en: { title: "Reminders on this phone", why: "The phone itself reminds you at your medicine times, even when the app is closed or there is no internet. The reminder only says “Time for your medicine”: it never shows a medicine name. It follows the times you confirmed on the Medicines page.",
    on: "Reminders on this phone are on.", blocked: "Notifications are blocked for this app. Open your phone's Settings, then Apps, HealthWise AI, Notifications, allow them, then come back.", off: "Turn on reminders on this phone" },
  hi: { title: "इस फ़ोन पर रिमाइंडर", why: "फ़ोन खुद आपकी दवा के समय पर याद दिलाता है, ऐप बंद हो या इंटरनेट न हो तब भी। रिमाइंडर में सिर्फ़ “आपकी दवा का समय हो गया है” लिखा होता है, दवा का नाम कभी नहीं। यह उन समयों पर चलता है जो आपने दवाइयाँ पेज पर पक्के किए हैं।",
    on: "इस फ़ोन पर रिमाइंडर चालू हैं।", blocked: "इस ऐप के लिए सूचनाएं बंद हैं। फ़ोन की सेटिंग में जाइए, फिर ऐप्स, HealthWise AI, सूचनाएं, उन्हें चालू कीजिए और वापस आइए।", off: "इस फ़ोन पर रिमाइंडर चालू करें" },
  mr: { title: "या फोनवर रिमाइंडर", why: "फोन स्वतः तुमच्या औषधाच्या वेळी आठवण करून देतो, अ‍ॅप बंद असले किंवा इंटरनेट नसले तरी. रिमाइंडरमध्ये फक्त “तुमच्या औषधाची वेळ झाली आहे” असे असते, औषधाचे नाव कधीच नाही. तुम्ही औषधे पानावर निश्चित केलेल्या वेळांप्रमाणे ते चालते.",
    on: "या फोनवर रिमाइंडर चालू आहेत.", blocked: "या अ‍ॅपसाठी सूचना बंद आहेत. फोनच्या सेटिंगमध्ये जा, मग अ‍ॅप्स, HealthWise AI, सूचना, त्या चालू करा आणि परत या.", off: "या फोनवर रिमाइंडर चालू करा" },
};

export default function NativeReminderToggle({ language = "en" }) {
  const w = WORDS[language] || WORDS.en;
  const [on, setOn] = useState(false);
  const [blocked, setBlocked] = useState(false);

  useEffect(() => {
    if (!isNativeApp()) return;
    permissionState().then((p) => { setOn(remindersEnabled() && p === "granted"); setBlocked(p === "denied"); });
  }, []);
  if (!isNativeApp()) return null;

  const change = async (checked) => {
    if (!checked) { await disableReminders(); setOn(false); return; }
    const state = await enableReminders(language);
    setOn(state === "granted");
    setBlocked(state === "denied");
  };

  return (
    <section aria-label={w.title} className="rounded-2xl border border-slate-200 p-4">
      <div className="flex min-h-11 items-start justify-between gap-3">
        <label htmlFor="native-reminders" className="text-sm font-semibold text-slate-800">{w.title}</label>
        <input id="native-reminders" type="checkbox" role="switch" checked={on} onChange={(e) => change(e.target.checked)} className="mt-0.5 h-6 w-11 shrink-0 cursor-pointer accent-brand-600" />
      </div>
      <p className="text-sm text-slate-600">{w.why}</p>
      {on && <p className="mt-2 text-sm font-semibold text-green-800">{w.on}</p>}
      {blocked && <p role="note" className="mt-2 rounded-xl bg-amber-50 p-3 text-sm font-medium text-amber-900">{w.blocked}</p>}
    </section>
  );
}
