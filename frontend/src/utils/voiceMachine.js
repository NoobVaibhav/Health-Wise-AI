// The one place that says what the voice assistant is doing: idle, listening, hearing speech, thinking, speaking, or error. A pure function, so every way into
// and out of each state can be tested without a browser. An event that does not make sense in the current state (a late result after "stop", a second "end") is
// ignored, which is what keeps the screen from ever being stuck on "listening".
//
//   idle ──LISTEN──► listening ──HEARD──► hearing ──SEND──► thinking ──REPLIED──► idle ──SPEAK_START──► speaking ──SPEAK_END──► idle
//   any state ──STOP──► idle (stop, tab in the background, incoming call, leaving the page)      any state ──ERROR──► error ──RESET/LISTEN/SEND──► ...

export const PHASES = ["idle", "listening", "hearing", "thinking", "speaking", "error"];
export const initialVoice = { phase: "idle", error: null };

const to = (next, from) => Object.fromEntries(from.map((p) => [p, next]));
const MOVES = {
  LISTEN: to("listening", ["idle", "error", "speaking", "listening", "hearing"]),            // a tap while the assistant speaks interrupts it and listens
  HEARD: to("hearing", ["listening", "hearing"]),
  SEND: to("thinking", ["idle", "listening", "hearing", "error", "speaking"]),
  REPLIED: to("idle", ["thinking"]),
  SPEAK_START: to("speaking", ["idle", "thinking", "error", "speaking"]),
  SPEAK_END: to("idle", ["speaking"]),
  LISTEN_END: to("idle", ["listening", "hearing"]),                                           // the recogniser ended and nothing was sent
  STOP: to("idle", PHASES),
  RESET: to("idle", ["error"]),
};

/** reducer for useReducer: voiceReducer(state, { type, kind? }) */
export function voiceReducer(state, event) {
  if (event.type === "ERROR") return state.phase === "error" && state.error === event.kind ? state : { phase: "error", error: event.kind || "other" };
  const next = MOVES[event.type]?.[state.phase];
  if (!next || (next === state.phase && state.error === null)) return state;
  return { phase: next, error: null };
}

/** What the screen says for each phase: the label, the hint, and what a screen reader announces. */
export const PHASE_TEXT = {
  idle: { label: "Tap and talk to me", announce: "Ready." },
  listening: { label: "Listening...", announce: "Listening." },
  hearing: { label: "I can hear you...", announce: "Hearing you." },
  thinking: { label: "Looking through your records...", announce: "Thinking." },
  speaking: { label: "Speaking...", announce: "Speaking." },
  error: { label: "Something went wrong", announce: "Something went wrong." },
};
