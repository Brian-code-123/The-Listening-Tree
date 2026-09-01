"""Password hashing/verification and input validation for auth flows.

Hand-rolled PBKDF2-HMAC-SHA256 (stdlib `hashlib`, not a library like
passlib/bcrypt/argon2) — acceptable for this project's scale but noted as
non-standard practice; see docs/REQUIREMENTS.md for the tradeoff discussion.
"""
import hashlib
import hmac
import re
import secrets

PBKDF2_ITERATIONS = 390000
PBKDF2_SCHEME = "pbkdf2_sha256"

LOGIN_MAX_ATTEMPTS = 5
LOGIN_LOCKOUT_MINUTES = 15


def hash_password(password: str) -> str:
    """Hash password using PBKDF2-HMAC-SHA256 with per-user random salt."""
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PBKDF2_ITERATIONS,
    ).hex()
    return f"{PBKDF2_SCHEME}${PBKDF2_ITERATIONS}${salt}${digest}"


def is_password_hashed(stored: str) -> bool:
    return isinstance(stored, str) and stored.startswith(f"{PBKDF2_SCHEME}$")


def verify_password(password: str, stored: str) -> bool:
    """Verify a plaintext password against hashed or legacy plaintext storage."""
    if not stored:
        return False
    if not is_password_hashed(stored):
        return hmac.compare_digest(password, stored)

    try:
        scheme, iter_str, salt, expected = stored.split("$", 3)
        if scheme != PBKDF2_SCHEME:
            return False
        iterations = int(iter_str)
        computed = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            iterations,
        ).hex()
        return hmac.compare_digest(computed, expected)
    except Exception:
        return False


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
    - Minimum 8 characters

    Returns:
        (is_valid, error_message)
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters"
    return True, ""
