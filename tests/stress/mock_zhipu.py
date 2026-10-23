"""A stand-in for the Zhipu chat API that is slow the way the real one is.

Used by run-multiuser.sh so the app can be load-tested with realistic model
latency without spending quota or touching the real account: half a second to
the first words, then a reply written out over about three seconds.
"""
import asyncio
import json
import time

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

app = FastAPI()
WORDS = ("Good morning to you. I hope you slept well last night. "
         "Remember to drink some water and take a gentle walk today. " * 2).split()


def _chunk(text: str) -> str:
    return "data: " + json.dumps({"choices": [{"delta": {"content": text}}]}) + "\n\n"


@app.post("/chat/completions")
async def completions(request: Request):
    body = await request.json()
    await asyncio.sleep(0.5)
    if body.get("stream"):
        async def gen():
            for word in WORDS[:20]:
                await asyncio.sleep(0.15)
                yield _chunk(word + " ")
            yield "data: [DONE]\n\n"

        return StreamingResponse(gen(), media_type="text/event-stream")
    await asyncio.sleep(2.5)
    return JSONResponse({"choices": [{"message": {"content": " ".join(WORDS[:20])}}], "usage": {"completion_tokens": 20}})


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=5200, log_level="warning")
