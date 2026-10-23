import asyncio
import hashlib
import time

import pytest

from app.services import auth


def _legacy_hash(password: str, iterations: int = 390000, salt: str = "00" * 16) -> str:
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), iterations).hex()
    return f"pbkdf2_sha256${iterations}${salt}${digest}"


def test_new_hashes_use_the_current_cost():
    assert auth.hash_password("correct horse").startswith("pbkdf2_sha256$600000$")


def test_an_older_hash_still_verifies_but_is_flagged_for_rehash():
    stored = _legacy_hash("correct horse")
    assert auth.verify_password("correct horse", stored) is True
    assert auth.needs_rehash(stored) is True
    assert auth.needs_rehash(auth.hash_password("correct horse")) is False


def test_there_is_no_plaintext_fallback():
    assert auth.verify_password("secret123", "secret123") is False
    assert auth.needs_rehash("secret123") is True


@pytest.mark.parametrize("password", ["密碼🔑pässwörd", "𝔘𝔫𝔦𝔠𝔬𝔡𝔢-12345", "a" * 128, "  spaced  "])
def test_unusual_passwords_round_trip(password):
    assert auth.verify_password(password, auth.hash_password(password)) is True
    assert auth.verify_password(password + "x", auth.hash_password(password)) is False


@pytest.mark.parametrize("stored", ["pbkdf2_sha256$600000$salt$notahex", "pbkdf2_sha256$abc$s$d", "pbkdf2_sha256$", "", None])
def test_a_malformed_stored_hash_is_a_failed_login_not_an_error(stored):
    assert auth.verify_password("密碼🔑", stored) is False


def test_password_length_bounds():
    assert auth.validate_password_strength("x" * 7)[0] is False
    assert auth.validate_password_strength("x" * 8)[0] is True
    assert auth.validate_password_strength("x" * 128)[0] is True
    ok, message = auth.validate_password_strength("x" * 129)
    assert ok is False and "128" in message


def test_hashing_does_not_stall_the_event_loop():
    stored = auth.hash_password("correct horse")
    started = time.perf_counter()
    auth.verify_password("correct horse", stored)
    one_hash = time.perf_counter() - started

    async def scenario():
        worst_gap, stop = 0.0, False

        async def heartbeat():
            nonlocal worst_gap
            last = time.perf_counter()
            while not stop:
                await asyncio.sleep(0.005)
                now = time.perf_counter()
                worst_gap = max(worst_gap, now - last)
                last = now

        beat = asyncio.create_task(heartbeat())
        await asyncio.gather(*[auth.verify_password_async("correct horse", stored) for _ in range(4)])
        stop = True
        await beat
        return worst_gap

    # Run inline, four hashes block the loop for roughly four hashes' time.
    assert asyncio.run(scenario()) < one_hash * 2
