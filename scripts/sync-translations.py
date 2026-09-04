#!/usr/bin/env python3
"""Sync translations.py's TRANSLATIONS dict into web-next/app/lib/translations-data.json.

Run after editing translations.py so the Next.js frontend's local copy
(used to avoid a network round trip to the backend on every page load)
stays in sync:

    npm run sync:translations
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import translations  # noqa: E402

OUT_PATH = ROOT / "web-next" / "app" / "lib" / "translations-data.json"

OUT_PATH.write_text(
    json.dumps(translations.TRANSLATIONS, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)

print(f"Wrote {OUT_PATH.relative_to(ROOT)}")
