"""Offline PIN keyspace demonstration.

Scope and safety boundary
--------------------------
This module attacks ONLY the local state file created by this same project's
virtual phone. It reads the salt, digest, and KDF parameters that setup_pin()
wrote to disk and tries PIN candidates directly in memory.

It does not call PhoneAuthentication.authenticate() and does not go through
the Flask API, so the live attempt limit / lockout is irrelevant here. That is
the lesson: a lockout only limits attempts through the live unlock screen.
Anyone who obtains the stored salt and digest can test the keyspace offline,
limited only by the hashing cost.

No network access, no real device, and no third-party accounts are involved.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

from backend.hash_engine import ITERATIONS

DEFAULT_KEYSPACE = 10_000
ProgressCallback = Callable[[int, int], None]


@dataclass(frozen=True)
class BruteForceResult:
    found: bool
    pin: str | None
    attempts: int
    elapsed_seconds: float
    keyspace_size: int

    def as_dict(self) -> dict:
        return {
            "found": self.found,
            "pin": self.pin,
            "attempts": self.attempts,
            "keyspace_size": self.keyspace_size,
            "elapsed_seconds": round(self.elapsed_seconds, 3),
            "attempts_per_second": (
                round(self.attempts / self.elapsed_seconds, 2)
                if self.elapsed_seconds > 0
                else None
            ),
        }


def _load_hash_material(state_path: Path) -> tuple[bytes, str, int]:
    try:
        raw = json.loads(Path(state_path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(
            "No virtual phone state exists yet. Run 'phone launch' and set a PIN first."
        ) from exc
    except json.JSONDecodeError as exc:
        raise ValueError(
            "The virtual phone state file is corrupt. Run 'phone reset' and set a new PIN."
        ) from exc
    except OSError as exc:
        raise ValueError(f"Could not read the virtual phone state: {exc}") from exc

    if not isinstance(raw, dict):
        raise ValueError("The virtual phone state file has an unexpected format.")
    if not raw.get("configured") or not raw.get("salt") or not raw.get("digest"):
        raise ValueError(
            "No PIN has been configured on the virtual phone yet. "
            "Run 'phone launch' and set a PIN first."
        )

    try:
        salt = bytes.fromhex(str(raw["salt"]))
    except (TypeError, ValueError) as exc:
        raise ValueError("The stored salt is not valid hex. Reset the virtual phone.") from exc

    kdf = raw.get("kdf")
    iterations = ITERATIONS
    if isinstance(kdf, dict):
        try:
            iterations = int(kdf.get("iterations", ITERATIONS))
        except (TypeError, ValueError):
            iterations = ITERATIONS
    if iterations < 1:
        iterations = ITERATIONS

    return salt, str(raw["digest"]), iterations


def estimate_seconds_per_guess(state_path: Path, samples: int = 3) -> float:
    """Measure the local cost of one PBKDF2 guess."""

    if samples < 1:
        raise ValueError("samples must be at least 1.")
    salt, _digest, iterations = _load_hash_material(state_path)
    start = time.perf_counter()
    for number in range(samples):
        hashlib.pbkdf2_hmac("sha256", f"{number:04d}".encode(), salt, iterations)
    return (time.perf_counter() - start) / samples


def _full_keyspace():
    for number in range(DEFAULT_KEYSPACE):
        yield f"{number:04d}"


def run_pin_space(
    state_path: Path,
    *,
    candidates: Sequence[str] | None = None,
    progress_every: int = 100,
    on_progress: ProgressCallback | None = None,
) -> BruteForceResult:
    """Try candidates against the stored digest. Stops at the first match."""

    salt, digest, iterations = _load_hash_material(state_path)
    if progress_every < 1:
        raise ValueError("progress_every must be at least 1.")

    sequence = _full_keyspace() if candidates is None else candidates
    total = DEFAULT_KEYSPACE if candidates is None else len(candidates)

    start = time.perf_counter()
    attempts = 0
    for candidate in sequence:
        attempts += 1
        candidate_digest = hashlib.pbkdf2_hmac(
            "sha256", str(candidate).encode("utf-8"), salt, iterations
        ).hex()

        if on_progress and (attempts % progress_every == 0 or attempts == total):
            on_progress(attempts, total)

        if hmac.compare_digest(candidate_digest, digest):
            return BruteForceResult(
                True,
                str(candidate),
                attempts,
                time.perf_counter() - start,
                total,
            )

    return BruteForceResult(
        False, None, attempts, time.perf_counter() - start, total
    )


def run_full_pin_space(
    state_path: Path,
    progress_every: int = 500,
    on_progress: ProgressCallback | None = None,
) -> BruteForceResult:
    """Backward-compatible wrapper for the full 0000-9999 sweep."""

    return run_pin_space(
        state_path,
        progress_every=progress_every,
        on_progress=on_progress,
    )
