"""Salted PBKDF2-HMAC-SHA256 helpers shared by the demo and the virtual phone."""

from __future__ import annotations

import hashlib
import hmac
import secrets

ITERATIONS = 240_000
ALGORITHM = "pbkdf2_hmac_sha256"


def _check_iterations(iterations: int) -> int:
    if isinstance(iterations, bool) or not isinstance(iterations, int) or iterations < 1:
        raise ValueError("iterations must be a positive integer.")
    return iterations


def hash_password(password: str, iterations: int = ITERATIONS) -> tuple[str, str]:
    """Return (salt_hex, digest_hex) for a password or PIN."""

    _check_iterations(iterations)
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), iterations
    )
    return salt, digest.hex()


def verify_password(
    password: str, salt: str, expected_hash: str, iterations: int = ITERATIONS
) -> bool:
    """Constant-time verification. Corrupt salt material simply fails closed."""

    _check_iterations(iterations)
    try:
        salt_bytes = bytes.fromhex(salt)
    except (TypeError, ValueError):
        return False
    actual = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt_bytes, iterations
    ).hex()
    return hmac.compare_digest(actual, str(expected_hash))
