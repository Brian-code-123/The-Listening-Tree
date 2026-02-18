# Vercel entry point — imports the FastAPI app from run.py
# Vercel's @vercel/python runtime looks for `app` in this file.
from run import app  # noqa: F401  (re-exported for Vercel)
