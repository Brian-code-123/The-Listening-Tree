"""Password hashing/verification and input validation for auth flows.

Hand-rolled PBKDF2-HMAC-SHA256 (stdlib `hashlib`, not a library like
passlib/bcrypt/argon2) — acceptable for this project's scale but noted as
non-standard practice; see the "Design decisions and trade-offs" section of
the README for why, and what it costs.
"""
import asyncio
import functools
import hashlib
import hmac
import re
import secrets

from app.core import config

PBKDF2_ITERATIONS = 600000
PBKDF2_SCHEME = "pbkdf2_sha256"
MAX_PASSWORD_LENGTH = 128


def _derive(password: str, salt: str, iterations: int) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations).hex()


def hash_password(password: str) -> str:
    """Hash password using PBKDF2-HMAC-SHA256 with per-user random salt."""
    salt = secrets.token_hex(16)
    return f"{PBKDF2_SCHEME}${PBKDF2_ITERATIONS}${salt}${_derive(password, salt, PBKDF2_ITERATIONS)}"


def is_password_hashed(stored: str) -> bool:
    return isinstance(stored, str) and stored.startswith(f"{PBKDF2_SCHEME}$")


def _parse(stored):
    """(iterations, salt, digest) of a stored hash, or None if it is not one."""
    if not is_password_hashed(stored):
        return None
    try:
        scheme, iter_str, salt, expected = stored.split("$", 3)
        return int(iter_str), salt, expected
    except ValueError:
        return None


def verify_password(password: str, stored: str) -> bool:
    """True when `password` matches a stored PBKDF2 hash. Anything that is not
    a well-formed hash (including a plaintext value) never matches."""
    parsed = _parse(stored)
    if parsed is None:
        return False
    iterations, salt, expected = parsed
    if not 1 <= iterations <= 5_000_000:
        return False
    return hmac.compare_digest(_derive(password, salt, iterations).encode(), expected.encode())


def needs_rehash(stored: str) -> bool:
    """True when a stored value should be replaced with a current-cost hash on
    the next successful login."""
    parsed = _parse(stored)
    return parsed is None or parsed[0] < PBKDF2_ITERATIONS


# PBKDF2 is deliberately slow (~0.2s of CPU). Run directly in an async handler
# it freezes every other request on the instance, so handlers use these.
async def hash_password_async(password: str) -> str:
    return await asyncio.to_thread(hash_password, password)


async def verify_password_async(password: str, stored: str) -> bool:
    return await asyncio.to_thread(verify_password, password, stored)


def code_digest(email: str, code: str) -> str:
    """What is stored for a verification code: a keyed hash, so reading the table
    does not reveal live codes. Tied to the (lower-cased) address."""
    message = f"{email.strip().lower()}:{code}".encode()
    return hmac.new(config.SECRET_KEY.encode(), message, hashlib.sha256).hexdigest()


@functools.lru_cache(maxsize=1)
def dummy_hash() -> str:
    """A valid hash of a throwaway password, made on first use rather than at
    import so it does not add to every serverless cold start."""
    return hash_password(secrets.token_hex(16))


def validate_email(email: str) -> tuple[bool, str]:
    """Validate email format per RFC 5322 basic pattern.

    Returns:
        (is_valid, error_message)
    """
    # RFC 5322 basic email pattern (simplified but covers most cases)
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, email):
        return False, "Invalid email format"
    return True, ""


def validate_password_strength(password: str) -> tuple[bool, str]:
    """Validate password meets minimum strength requirements.

    Requirements:
    - Minimum 8 characters, at most MAX_PASSWORD_LENGTH

    Returns:
        (is_valid, error_message)
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters"
    if len(password) > MAX_PASSWORD_LENGTH:
        return False, f"Password must be at most {MAX_PASSWORD_LENGTH} characters"
    return True, ""
