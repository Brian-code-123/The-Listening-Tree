import os

import pytest

from app.core import config
from app.db import pool as db_pool
from app.db import queries as db
from app.db import schema

# Safety guard: RUN_LIVE_DB=1 tests are meant to run against a disposable
# LOCAL Postgres. .env.local is loaded with override=True (see
# app/core/config.py), which silently wins over any DATABASE_URL exported
# on the command line — so a .env.local pointed at production (as this
# project's local dev setup has been) makes "run the integration tests
# locally" silently run them against production instead. That happened for
# real (see the SDLC-plan commit that cleaned up the resulting test data) —
# this check exists so it can never happen again silently. If this fires,
# either point .env.local's DATABASE_URL/SUPABASE_POOLER_URL at a local
# Postgres, or temporarily move .env.local aside before running tests.
if os.environ.get("RUN_LIVE_DB") == "1":
    _resolved_host = (db_pool.DB_HOSTNAME or "").lower()
    _safe_hosts = {"localhost", "127.0.0.1", "::1"}
    if _resolved_host not in _safe_hosts:
        pytest.exit(
            f"RUN_LIVE_DB=1 tests would connect to '{_resolved_host}', which "
            f"is not a recognized local host ({sorted(_safe_hosts)}). Refusing "
            f"to run — this almost certainly means .env.local's DATABASE_URL/"
            f"SUPABASE_POOLER_URL points at a real (production) database. "
            f"Point it at a local Postgres, or move .env.local aside, before "
            f"running RUN_LIVE_DB=1 tests.",
            returncode=1,
        )


class _FakeCursor:
    def __init__(self, state):
        self.state = state
        self._rows = []
        self._one = None
        self.rowcount = 0

    async def execute(self, query, params=()):
        normalized = " ".join(query.lower().split())
        self._rows = []
        self._one = None
        self.rowcount = 0

        if normalized == "select 1":
            self._one = {"?column?": 1}
            return

        # Registration requires a verification_code (email_verifications
        # table) — the fake accepts any code for any email rather than
        # tracking real inserts/expiry, since these tests exercise the
        # register→login→chat flow, not the verification-code logic itself.
        if "select id from email_verifications where lower(email) = lower(?) and code = ?" in normalized:
            self._one = {"id": 1}
            return
        if "insert into email_verifications" in normalized:
            self.rowcount = 1
            return
        if "update email_verifications set used = true where id = ?" in normalized:
            self.rowcount = 1
            return
        if "select created_at from email_verifications" in normalized:
            self._one = None
            return

        if "insert into users" in normalized:
            email, password, created_at = params
            if email in self.state["users_by_email"]:
                raise db.PgIntegrityError("duplicate email")
            user_id = self.state["next_user_id"]
            self.state["next_user_id"] += 1
            user = {
                "id": user_id,
                "email": email,
                "password": password,
                "created_at": created_at,
                "last_login": None,
                "failed_login_attempts": 0,
                "locked_until": None,
            }
            self.state["users_by_email"][email] = user
            self.state["users_by_id"][user_id] = user
            self.rowcount = 1
            return

        if "select id, email, password, failed_login_attempts, locked_until from users where lower(email) = lower(?)" in normalized:
            email = params[0].lower()
            user = self.state["users_by_email"].get(email)
            self._one = {
                "id": user["id"],
                "email": user["email"],
                "password": user["password"],
                "failed_login_attempts": user["failed_login_attempts"],
                "locked_until": user["locked_until"],
            } if user else None
            return

        if "select id, email, password from users where lower(email) = lower(?)" in normalized:
            email = params[0].lower()
            user = self.state["users_by_email"].get(email)
            self._one = {
                "id": user["id"],
                "email": user["email"],
                "password": user["password"],
            } if user else None
            return

        if "update users set password = ? where id = ?" in normalized:
            password, user_id = params
            user = self.state["users_by_id"].get(user_id)
            if user:
                user["password"] = password
                self.rowcount = 1
            return

        if "update users set last_login" in normalized:
            ts, user_id = params[0], params[-1]
            user = self.state["users_by_id"].get(user_id)
            if user:
                user["last_login"] = ts
                user["failed_login_attempts"] = 0
                user["locked_until"] = None
                self.rowcount = 1
            return

        if "update users set failed_login_attempts" in normalized:
            user_id = params[-1]
            user = self.state["users_by_id"].get(user_id)
            if user:
                user["failed_login_attempts"] = params[0]
                if len(params) == 3:
                    user["locked_until"] = params[1]
                self.rowcount = 1
            return

        if "select pref_value from preferences" in normalized:
            self._one = None
            return

        if "insert into chat_history" in normalized:
            user_id, lang, timestamp, message, conversation_id = params
            is_bot = "values (?, ?, ?, true," in normalized
            self.state["chat_history"].append({
                "user_id": user_id,
                "lang": lang,
                "timestamp": timestamp,
                "message": message,
                "is_bot": is_bot,
                "conversation_id": conversation_id,
                "is_deleted": False,
            })
            self.rowcount = 1
            return

        if "select is_bot, message from chat_history" in normalized:
            conversation_id, limit = params
            matching = [
                row for row in self.state["chat_history"]
                if row["conversation_id"] == conversation_id and not row["is_deleted"]
            ]
            recent = matching[-limit:]
            recent.reverse()
            self._rows = [{"is_bot": r["is_bot"], "message": r["message"]} for r in recent]
            return

        if "select id from conversations where id = ? and user_id = ? and is_deleted = false" in normalized:
            conv_id, user_id = params
            match = next(
                (c for c in self.state["conversations"] if c["id"] == conv_id and c["user_id"] == user_id),
                None,
            )
            self._one = {"id": match["id"]} if match else None
            return

        if "select id from conversations where user_id = ? and lang = ? and is_deleted = false" in normalized:
            user_id, lang = params
            matches = [c for c in self.state["conversations"] if c["user_id"] == user_id and c["lang"] == lang]
            self._one = {"id": matches[-1]["id"]} if matches else None
            return

        if "insert into conversations" in normalized:
            user_id, lang, created_at, updated_at = params
            conv_id = self.state["next_conversation_id"]
            self.state["next_conversation_id"] += 1
            self.state["conversations"].append(
                {"id": conv_id, "user_id": user_id, "lang": lang, "updated_at": updated_at}
            )
            self._one = {"id": conv_id}
            self.rowcount = 1
            return

        if "insert into reminders" in normalized:
            user_id, label, reminder_time, created_at = params
            reminder_id = self.state["next_reminder_id"]
            self.state["next_reminder_id"] += 1
            self.state["reminders"].append(
                {
                    "id": reminder_id,
                    "user_id": user_id,
                    "label": label,
                    "reminder_time": reminder_time,
                    "is_active": True,
                    "created_at": created_at,
                }
            )
            self._one = {"id": reminder_id}
            self.rowcount = 1
            return

        if "delete from reminders where user_id = ? and label = ?" in normalized:
            user_id, label = params
            before = len(self.state["reminders"])
            self.state["reminders"] = [
                r
                for r in self.state["reminders"]
                if not (r["user_id"] == user_id and r["label"] == label)
            ]
            self.rowcount = before - len(self.state["reminders"])
            return

        if "delete from reminders where user_id = ? and id = ?" in normalized:
            user_id, reminder_id = params
            before = len(self.state["reminders"])
            self.state["reminders"] = [
                r
                for r in self.state["reminders"]
                if not (r["user_id"] == user_id and r["id"] == reminder_id)
            ]
            self.rowcount = before - len(self.state["reminders"])
            return

        if "update reminders set is_active = false" in normalized:
            _ts, user_id, label = params
            updated = 0
            for reminder in self.state["reminders"]:
                if reminder["user_id"] == user_id and reminder["label"] == label:
                    reminder["is_active"] = False
                    updated += 1
            self.rowcount = updated
            return

        if "select id, label, reminder_time, is_active from reminders" in normalized:
            user_id, _today = params
            self._rows = [
                {
                    "id": r["id"],
                    "label": r["label"],
                    "reminder_time": r["reminder_time"],
                    "is_active": 1 if r["is_active"] else 0,
                }
                for r in self.state["reminders"]
                if r["user_id"] == user_id
            ]
            return

    def fetchone(self):
        return self._one

    def fetchall(self):
        return self._rows


class _FakeConn:
    def __init__(self, state):
        self.state = state

    def cursor(self):
        return _FakeCursor(self.state)

    async def commit(self):
        return None

    async def close(self):
        return None


@pytest.fixture(autouse=True)
def fake_db_for_tests(monkeypatch):
    if os.environ.get("RUN_LIVE_DB") == "1":
        return

    state = {
        "next_user_id": 1,
        "users_by_email": {},
        "users_by_id": {},
        "reminders": [],
        "next_reminder_id": 1,
        "chat_history": [],
        "conversations": [],
        "next_conversation_id": 1,
    }

    async def _fake_ensure_db_initialized(strict=False):
        return True

    async def _fake_get_db():
        return _FakeConn(state)

    monkeypatch.setattr(schema, "ensure_db_initialized", _fake_ensure_db_initialized)
    monkeypatch.setattr(db, "get_db", _fake_get_db)
    config.user_game_states.clear()
