#!/usr/bin/env python3
"""One-time migration utility: SQLite -> PostgreSQL.

Usage:
    export SQLITE_PATH=reminders.db
    export DATABASE_URL=postgresql://user:pass@host:5432/dbname
    python scripts/migrate_sqlite_to_postgres.py
"""

import os
import sqlite3
from typing import Any, Dict, List

import psycopg2
from psycopg2.extras import RealDictCursor, execute_values


SQLITE_PATH = os.environ.get("SQLITE_PATH", "reminders.db")
POSTGRES_URL = os.environ.get("DATABASE_URL", "").strip()


def require_env() -> None:
    if not POSTGRES_URL.startswith("postgres://") and not POSTGRES_URL.startswith("postgresql://"):
        raise RuntimeError("DATABASE_URL must be a PostgreSQL URL for migration")


def ensure_schema(pg_conn) -> None:
    with pg_conn.cursor() as c:
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id BIGSERIAL PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                username TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE
            )
            """
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS reminders (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                label TEXT NOT NULL,
                reminder_time TEXT NOT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                repeat_type TEXT DEFAULT 'once',
                priority TEXT DEFAULT 'normal',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_history (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                lang TEXT DEFAULT 'en',
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_bot BOOLEAN NOT NULL,
                message TEXT NOT NULL,
                is_deleted BOOLEAN DEFAULT FALSE,
                token_count INTEGER
            )
            """
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS preferences (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                pref_key TEXT NOT NULL,
                pref_value TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, pref_key)
            )
            """
        )
    pg_conn.commit()


def fetch_sqlite_rows(sqlite_conn, query: str) -> List[Dict[str, Any]]:
    sqlite_conn.row_factory = sqlite3.Row
    cur = sqlite_conn.cursor()
    cur.execute(query)
    return [dict(r) for r in cur.fetchall()]


def upsert_rows(pg_conn, table: str, columns: List[str], rows: List[Dict[str, Any]]) -> int:
    if not rows:
        return 0

    values = [[row.get(c) for c in columns] for row in rows]
    cols = ", ".join(columns)
    conflict_updates = ", ".join([f"{c}=EXCLUDED.{c}" for c in columns if c != "id"])

    query = f"""
        INSERT INTO {table} ({cols}) VALUES %s
        ON CONFLICT (id) DO UPDATE SET {conflict_updates}
    """

    with pg_conn.cursor() as c:
        execute_values(c, query, values)
    pg_conn.commit()
    return len(rows)


def reset_sequences(pg_conn) -> None:
    with pg_conn.cursor() as c:
        for table in ["users", "reminders", "chat_history", "preferences"]:
            c.execute(
                f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), COALESCE(MAX(id), 1), true) FROM {table}"
            )
    pg_conn.commit()


def main() -> None:
    require_env()
    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    pg_conn = psycopg2.connect(POSTGRES_URL, cursor_factory=RealDictCursor)

    try:
        ensure_schema(pg_conn)

        users = fetch_sqlite_rows(sqlite_conn, "SELECT id, email, password, username, created_at, last_login, is_active FROM users")
        reminders = fetch_sqlite_rows(sqlite_conn, "SELECT id, user_id, label, reminder_time, is_active, repeat_type, priority, created_at, updated_at FROM reminders")
        chat_history = fetch_sqlite_rows(sqlite_conn, "SELECT id, user_id, lang, timestamp, is_bot, message, is_deleted, token_count FROM chat_history")
        preferences = fetch_sqlite_rows(sqlite_conn, "SELECT id, user_id, pref_key, pref_value, created_at, updated_at FROM preferences")

        users_count = upsert_rows(pg_conn, "users", ["id", "email", "password", "username", "created_at", "last_login", "is_active"], users)
        reminders_count = upsert_rows(pg_conn, "reminders", ["id", "user_id", "label", "reminder_time", "is_active", "repeat_type", "priority", "created_at", "updated_at"], reminders)
        chat_count = upsert_rows(pg_conn, "chat_history", ["id", "user_id", "lang", "timestamp", "is_bot", "message", "is_deleted", "token_count"], chat_history)
        prefs_count = upsert_rows(pg_conn, "preferences", ["id", "user_id", "pref_key", "pref_value", "created_at", "updated_at"], preferences)

        reset_sequences(pg_conn)

        print("Migration completed successfully")
        print(f"users: {users_count}")
        print(f"reminders: {reminders_count}")
        print(f"chat_history: {chat_count}")
        print(f"preferences: {prefs_count}")

    finally:
        sqlite_conn.close()
        pg_conn.close()


if __name__ == "__main__":
    main()
