"""Small, real-model load check: 10 different users each send 3 chat messages
about ten seconds apart to the live Zhipu model (the free glm-4-flash), through a
local backend and the local e2e database. About 30 model calls in total.

Run by `npm run test:stress:realai`. The key is read from .env.local and handed
to the backend process only; it is never printed. Reports the time to the first
words, the time for the whole reply, and how many answers were Zhipu's own
rate-limit or error fallbacks.
"""
import asyncio
import json
import os
import statistics
import subprocess
import sys
import time
import uuid

import httpx
from dotenv import dotenv_values

USERS = int(os.environ.get("REAL_AI_USERS", "10"))
MESSAGES = int(os.environ.get("REAL_AI_MESSAGES", "3"))
GAP = float(os.environ.get("REAL_AI_GAP", "10"))
PORT = os.environ.get("REAL_AI_PORT", "5103")
BASE = f"http://127.0.0.1:{PORT}"
TEXTS = ["I did not sleep well last night.", "My knee hurts a little today.", "What should I have for lunch?",
         "今日天氣好好。", "我琴晚瞓得唔好。", "我好掛住個孫。"]


def main() -> None:
    key = dotenv_values(".env.local").get("ZHIPU_API_KEY", "")
    if not key:
        sys.exit("no ZHIPU_API_KEY in .env.local")
    env = dict(os.environ, SKIP_ENV_LOCAL="1", ZHIPU_API_KEY=key, LOG_LEVEL="WARNING", SECRET_KEY="realai-secret", PORT=PORT,
               TRUSTED_PROXY="1", NEWS_API_KEY="", HF_API_KEY="", AZURE_COMMUNICATION_CONNECTION_STRING="",
               GOOGLE_CLIENT_ID="", GOOGLE_CLIENT_SECRET="")
    server = subprocess.Popen([sys.executable, "run.py"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    emails: list[str] = []
    try:
        for _ in range(60):
            try:
                if httpx.get(BASE + "/health", timeout=1).status_code == 200:
                    break
            except Exception:
                time.sleep(1)
        from app.services import ai
        from tests.integration.helpers import PASSWORD, create_user_direct

        fallbacks = set(ai.WARM_FALLBACK_EN) | set(ai.WARM_FALLBACK_ZH)
        run = uuid.uuid4().hex[:6]
        emails = [f"realai{run}_{i}@example.com" for i in range(USERS)]
        for e in emails:
            create_user_direct(e)

        async def user(i: int, email: str):
            rows = []
            async with httpx.AsyncClient(base_url=BASE, timeout=90) as c:
                h = {"X-Forwarded-For": f"198.51.100.{i + 1}"}
                r = await c.post("/auth/login", data={"email": email, "password": PASSWORD}, headers={**h, "accept": "application/json"})
                assert r.json()["success"], r.text
                await asyncio.sleep(i * GAP / USERS)  # spread the users out
                for m in range(MESSAGES):
                    start = time.perf_counter()
                    first = None
                    reply = ""
                    status = 0
                    async with c.stream("POST", "/get_response", data={"msg": TEXTS[(i + m) % len(TEXTS)]}, headers={**h, "accept": "text/event-stream"}) as resp:
                        status = resp.status_code
                        async for line in resp.aiter_lines():
                            if line.startswith("data:"):
                                ev = json.loads(line[5:])
                                if ev.get("delta") and first is None:
                                    first = time.perf_counter() - start
                                if ev.get("done"):
                                    reply = ev["response"]
                    rows.append({"status": status, "first": first, "total": time.perf_counter() - start, "fallback": reply in fallbacks or not reply})
                    await asyncio.sleep(GAP)
            return rows

        async def run_all():
            return await asyncio.gather(*(user(i, e) for i, e in enumerate(emails)))

        started = time.perf_counter()
        results = [r for rows in asyncio.run(run_all()) for r in rows]
        wall = time.perf_counter() - started

        def stats(xs):
            xs = sorted(xs)
            return f"min={xs[0]:.2f}s median={statistics.median(xs):.2f}s p90={xs[max(int(len(xs) * 0.9) - 1, 0)]:.2f}s max={xs[-1]:.2f}s"

        ok = [r for r in results if r["status"] == 200 and not r["fallback"]]
        print(f"requests={len(results)} real replies={len(ok)} fallback (model error/limit)={sum(r['fallback'] for r in results)} "
              f"non-200={sum(r['status'] != 200 for r in results)} wall={wall:.0f}s")
        if ok:
            print("first words :", stats([r["first"] for r in ok if r["first"] is not None]))
            print("whole reply :", stats([r["total"] for r in ok]))
    finally:
        server.terminate()
        from tests.integration.helpers import delete_user_direct

        for e in emails:
            delete_user_direct(e)


if __name__ == "__main__":
    main()
