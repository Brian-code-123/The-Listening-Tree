import { afterEach, describe, expect, it, vi } from "vitest";
import { streamChatMessage } from "../app/lib/chat";

function sseResponse(chunks: string[]): Response {
  const enc = new TextEncoder();
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      chunks.forEach((c) => controller.enqueue(enc.encode(c)));
      controller.close();
    },
  });
  return new Response(body, { status: 200, headers: { "content-type": "text/event-stream" } });
}

afterEach(() => vi.unstubAllGlobals());

describe("streamChatMessage", () => {
  it("shows the reply as it grows and returns the whole of it", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(sseResponse([
      'data: {"delta":"Good "}\n\n',
      'data: {"delta":"morning"}\n\ndata: {"done":true,"response":"Good morning"}\n\n',
    ])));
    const seen: string[] = [];
    const reply = await streamChatMessage("hi", null, (s) => seen.push(s));
    expect(seen[0]).toBe("Good ");
    expect(seen).toContain("Good morning");
    expect(reply).toBe("Good morning");
  });

  it("copes with an event split across two reads", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(sseResponse(['data: {"delta":"He', 'llo"}\n\n'])));
    const reply = await streamChatMessage("hi", 3, () => {});
    expect(reply).toBe("Hello");
  });

  it("accepts a plain JSON reply (commands, safety replies)", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ response: "Call 999" }), { headers: { "content-type": "application/json" } })));
    const seen: string[] = [];
    expect(await streamChatMessage("help", null, (s) => seen.push(s))).toBe("Call 999");
    expect(seen).toEqual(["Call 999"]);
  });

  it("throws on an error status so the page can show its error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("{}", { status: 429 })));
    await expect(streamChatMessage("hi", null, () => {})).rejects.toThrow("429");
  });
});
