"""run.py — local dev-server entry point for The Listening Tree.

The actual FastAPI application lives in `app/` (see `app/main.py`); this
file is a thin shim kept so `python run.py` / `npm run dev` keep working
unchanged. Vercel's serverless entrypoint (`api/index.py`) imports
`app.main:app` directly and never touches this file.
"""
import logging
import os

from app.main import app

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 5000))
    url = f"http://localhost:{port}"
    logger.info(f"Server running: {url}")

    # Run Uvicorn with quieter logging. Access logs and INFO-level logs are
    # disabled to keep console output minimal.
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning", access_log=False)
