#!/usr/bin/env python3
"""Verify Supabase PostgreSQL connectivity from DATABASE_URL.

Usage:
    python scripts/verify_supabase_postgres.py
"""

from __future__ import annotations

import os
import socket
from urllib.parse import urlparse

import psycopg2


def main() -> int:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("[FAIL] DATABASE_URL is not set")
        return 1

    parsed = urlparse(database_url)
    host = parsed.hostname
    if not host:
        print("[FAIL] DATABASE_URL host is missing")
        return 1

    try:
        addr = socket.getaddrinfo(host, None)[0][4][0]
        print(f"[OK] DNS resolved: {host} -> {addr}")
    except Exception as exc:
        print(f"[FAIL] DNS resolution failed for {host}: {exc}")
        return 1

    try:
        with psycopg2.connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT current_database(), current_user")
                db, user = cur.fetchone()
                print(f"[OK] Connected to database '{db}' as '{user}'")
    except Exception as exc:
        print(f"[FAIL] PostgreSQL connection failed: {exc}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
