import importlib.util
import pathlib
import sys
import os

# This file is a small loader used by Vercel's Python builder.
# It dynamically loads the FastAPI `app` defined in `fastapi/main.py`
# without requiring the `fastapi` folder to be an importable package.

HERE = pathlib.Path(__file__).parent
MAIN_PY = (HERE / ".." / "fastapi" / "main.py").resolve()

if not MAIN_PY.exists():
    raise RuntimeError(f"Missing expected entrypoint: {MAIN_PY}")

spec = importlib.util.spec_from_file_location("the_listening_tree.fastapi_main", str(MAIN_PY))
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

# Export the FastAPI `app` instance for Vercel to use.
try:
    app = getattr(module, "app")
except Exception as exc:  # pragma: no cover - defensive
    raise RuntimeError("Failed to locate `app` in fastapi/main.py") from exc
