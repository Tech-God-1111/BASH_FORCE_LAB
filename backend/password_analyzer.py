"""Rough educational password-entropy estimate.

This deliberately is not a real strength estimator. It ignores dictionary
words, keyboard patterns, reuse, and breach data; the note in the result says
so. It only gives learners a feel for length x character-pool size.
"""

from __future__ import annotations

import math
import string
from typing import Any

GROUPS = (
    (string.ascii_lowercase, "lowercase"),
    (string.ascii_uppercase, "uppercase"),
    (string.digits, "digits"),
    (string.punctuation, "symbols"),
    (" ", "spaces"),
)


def analyze_password(password: str) -> dict[str, Any]:
    if not password:
        return {
            "length": 0,
            "pool": 0,
            "entropy_bits": 0.0,
            "rating": "Empty",
            "character_groups": [],
            "note": "Enter a password to analyze.",
        }

    pool = 0
    present: list[str] = []
    for chars, label in GROUPS:
        if any(ch in chars for ch in password):
            pool += len(chars)
            present.append(label)

    # Non-ASCII letters, emoji, and anything outside the five ASCII groups.
    covered = set("".join(chars for chars, _ in GROUPS))
    if any(ch not in covered for ch in password):
        pool += 100
        present.append("other")

    bits = len(password) * math.log2(pool) if pool else 0.0
    rating = "Weak" if bits < 40 else "Moderate" if bits < 70 else "Strong"
    return {
        "length": len(password),
        "pool": pool,
        "entropy_bits": round(bits, 1),
        "character_groups": present,
        "rating": rating,
        "note": (
            "Rough educational estimate; real password strength also depends "
            "on predictability, reuse, and breach data."
        ),
    }
