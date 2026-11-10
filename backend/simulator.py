"""Isolated mock account used by the dictionary and lockout demonstrations."""

from __future__ import annotations

from pathlib import Path

from backend.hash_engine import ITERATIONS, hash_password, verify_password
from backend.logger import log_event
from backend.security_defense import LockoutGuard


class LocalAuthSimulator:
    """A deliberately isolated mock login; it never sends network requests."""

    def __init__(
        self,
        username: str,
        password: str,
        max_failures: int,
        lockout_seconds: int,
        iterations: int = ITERATIONS,
    ) -> None:
        self.username = username
        self.iterations = iterations
        self.salt, self.password_hash = hash_password(password, iterations)
        self.guard = LockoutGuard(max_failures, lockout_seconds)

    def authenticate(self, username: str, password: str) -> tuple[bool, str]:
        if self.guard.is_locked():
            return False, f"LOCKED: try again in {self.guard.remaining()} seconds."

        # Always run the KDF, even for an unknown username, so this lab does
        # not accidentally teach a username-timing side channel.
        password_ok = verify_password(
            password, self.salt, self.password_hash, self.iterations
        )
        if username != self.username or not password_ok:
            locked = self.guard.record_failure()
            log_event("Mock login failed")
            if locked:
                return False, "LOCKED: the mock account reached its failure limit."
            return False, "Incorrect demo credentials."

        self.guard.record_success()
        log_event("Mock login succeeded")
        return True, "Authentication successful in the local mock lab."

    def dictionary_demo(
        self, username: str, wordlist_path: Path, max_entries: int
    ) -> dict:
        if not wordlist_path.exists():
            return {
                "status": "error",
                "message": "Dictionary file not found.",
                "tested": 0,
            }

        tested = 0
        for raw in wordlist_path.read_text(encoding="utf-8").splitlines():
            candidate = raw.strip()
            if not candidate or candidate.startswith("#"):
                continue
            if tested >= max_entries:
                return {
                    "status": "limit",
                    "message": "Demo entry limit reached.",
                    "tested": tested,
                }
            if self.guard.is_locked():
                return {
                    "status": "locked",
                    "message": "Mock account lockout stopped the simulation.",
                    "tested": tested,
                }

            tested += 1
            ok, message = self.authenticate(username, candidate)
            if ok:
                return {
                    "status": "found",
                    "message": "A matching entry was found in the dummy lab.",
                    "tested": tested,
                }
            if message.startswith("LOCKED"):
                return {
                    "status": "locked",
                    "message": "Mock account lockout stopped the simulation.",
                    "tested": tested,
                }

        return {
            "status": "not_found",
            "message": "No match in the supplied sample list.",
            "tested": tested,
        }
