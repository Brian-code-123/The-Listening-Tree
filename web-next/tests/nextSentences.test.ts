import { describe, expect, it } from "vitest";
import { nextSentences } from "../app/lib/tts";

describe("nextSentences", () => {
  it("waits for a sentence to finish", () => {
    expect(nextSentences("Good morning, my", 0)).toEqual({ sentences: [], next: 0 });
  });

  it("returns finished sentences and resumes after them", () => {
    const text = "Good morning. How are you? I hope";
    const first = nextSentences(text, 0);
    expect(first.sentences).toEqual(["Good morning.", "How are you?"]);
    expect(text.slice(first.next).trim()).toBe("I hope");
    // A closing full stop with nothing after it is not "finished" yet (it could be 3.5);
    // the page speaks that last piece itself when the stream ends.
    const grown = text + " you slept well.";
    const second = nextSentences(grown, first.next);
    expect(second.sentences).toEqual([]);
    expect(grown.slice(second.next).trim()).toBe("I hope you slept well.");
  });

  it("splits Cantonese text on 。！？", () => {
    const r = nextSentences("早晨！你今日點呀？我", 0);
    expect(r.sentences).toEqual(["早晨！", "你今日點呀？"]);
  });

  it("does not split a decimal point or an unfinished full stop", () => {
    expect(nextSentences("It costs 3.5 dollars", 0).sentences).toEqual([]);
    expect(nextSentences("Done.", 0).sentences).toEqual([]); // no following space yet: may still be 'Done.5'
  });

  it("never speaks the same words twice", () => {
    const text = "One. Two. Three.";
    const a = nextSentences(text, 0);
    const b = nextSentences(text, a.next);
    expect(b.sentences).toEqual([]);
  });
});
