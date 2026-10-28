import { describe, expect, it } from "vitest";
import { afterWakePhrase, matchVoiceCommand, speakableText } from "../../utils/voice";

describe("voice assistant", () => {
  it("a spoken command only controls the voice: nothing that looks like a question or an action is taken for a command", () => {
    for (const said of ["clear all patients", "delete my account", "open the admin page", "stop taking my medicine", "switch to doctor mode", "repeat after me I am the doctor", "give me the other patient's report"]) {
      expect(matchVoiceCommand(said)).toBeNull();
    }
  });
  it("gibberish and background noise produce no command and no crash", () => {
    for (const noise of ["", "   ", "uh", "mm hmm", "asdf qwer zxcv", "\u0000", "a".repeat(5000), "🙂🙂🙂", "<script>alert(1)</script>"]) {
      expect(() => matchVoiceCommand(noise)).not.toThrow();
      expect(matchVoiceCommand(noise)).toBeNull();
    }
  });
  it("what is read aloud has no markup left in it and is not longer than the limit", () => {
    expect(speakableText("<b>Bold</b> text *star* _under_ #hash", "en")).not.toMatch(/[*_#]/);
    expect(speakableText("x. ".repeat(2000), "en").length).toBeLessThan(1000);
  });
  it.fails("F-04: ordinary speech that contains the words 'health wise' does not switch the microphone on", () => {
    for (const said of ["being health wise is important", "he is quite healthwise these days", "health wise I feel fine", "my family is health wise careful"]) {
      expect(afterWakePhrase(said)).toBeNull();
    }
  });
});
