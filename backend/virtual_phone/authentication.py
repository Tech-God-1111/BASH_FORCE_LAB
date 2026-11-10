"""PIN authentication for the local virtual phone.

State is a small JSON file, but it is written atomically and every
load/modify/save cycle holds a re-entrant lock because Flask serves requests
from multiple threads.
"""

from __future__ import annotations

import json
import math
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Callable

from backend.hash_engine import ALGORITHM, ITERATIONS, hash_password, verify_password

EventCallback = Callable[[str], None]


class PhoneAuthentication:
    STATE_VERSION = 1
    MAX_ITERATIONS = 10_000_000

    def __init__(
        self,
        state_path: Path,
        *,
        max_failures: int = 5,
        lockout_seconds: int = 30,
        pin_length: int = 4,
        iterations: int = ITERATIONS,
        event_callback: EventCallback | None = None,
    ) -> None:
        if max_failures < 1:
            raise ValueError("max_failures must be at least 1.")
        if lockout_seconds < 0:
            raise ValueError("lockout_seconds cannot be negative.")
        if not 4 <= pin_length <= 8:
            raise ValueError("pin_length must be between 4 and 8.")
        if iterations < 1:
            raise ValueError("iterations must be positive.")

        self.path = Path(state_path)
        self.max_failures = max_failures
        self.lockout_seconds = lockout_seconds
        self.pin_length = pin_length
        self.iterations = iterations
        self._event_callback = event_callback
        self._lock = threading.RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._save(self._default_state())

    # ------------------------------------------------------------------ state

    def _default_state(self) -> dict:
        return {
            "version": self.STATE_VERSION,
            "configured": False,
            "pin_length": self.pin_length,
            "kdf": {"name": ALGORITHM, "iterations": self.iterations},
            "salt": "",
            "digest": "",
            "failed_attempts": 0,
            "locked_until": 0.0,
            "unlocked": False,
        }

    @staticmethod
    def _safe_int(value: object, default: int) -> int:
        try:
            return int(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _safe_float(value: object, default: float) -> float:
        try:
            return float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return default

    def _safe_iterations(self, value: object) -> int:
        iterations = self._safe_int(value, self.iterations)
        if iterations < 1:
            return self.iterations
        return min(iterations, self.MAX_ITERATIONS)

    def _safe_pin_length(self, value: object) -> int:
        length = self._safe_int(value, self.pin_length)
        return length if 4 <= length <= 8 else self.pin_length

    @staticmethod
    def _material_ok(data: dict) -> bool:
        salt = data.get("salt")
        digest = data.get("digest")
        if not isinstance(salt, str) or not isinstance(digest, str):
            return False
        if not salt or not digest:
            return False
        try:
            bytes.fromhex(salt)
            bytes.fromhex(digest)
        except ValueError:
            return False
        return True

    def _is_configured(self, data: dict) -> bool:
        return bool(data.get("configured")) and self._material_ok(data)

    def _state_iterations(self, data: dict) -> int:
        kdf = data.get("kdf")
        if not isinstance(kdf, dict):
            return self.iterations
        return self._safe_iterations(kdf.get("iterations", self.iterations))

    def _load(self) -> dict:
        with self._lock:
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                raw = {}
            if not isinstance(raw, dict):
                raw = {}

            data = self._default_state()
            for key in data:
                if key in raw:
                    data[key] = raw[key]

            kdf = raw.get("kdf")
            data["kdf"] = {
                "name": ALGORITHM,
                "iterations": self._safe_iterations(
                    kdf.get("iterations") if isinstance(kdf, dict) else self.iterations
                ),
            }
            data["configured"] = bool(raw.get("configured", False))
            data["pin_length"] = self._safe_pin_length(
                raw.get("pin_length", self.pin_length)
            )
            data["unlocked"] = bool(raw.get("unlocked", False))
            data["failed_attempts"] = max(
                0, self._safe_int(raw.get("failed_attempts"), 0)
            )
            data["locked_until"] = max(
                0.0, self._safe_float(raw.get("locked_until"), 0.0)
            )
            data["salt"] = raw.get("salt") if isinstance(raw.get("salt"), str) else ""
            data["digest"] = (
                raw.get("digest") if isinstance(raw.get("digest"), str) else ""
            )

            if not self._is_configured(data):
                data.update(
                    {
                        "configured": False,
                        "salt": "",
                        "digest": "",
                        "failed_attempts": 0,
                        "locked_until": 0.0,
                        "unlocked": False,
                    }
                )
            return data

    def _save(self, data: dict) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_name = tempfile.mkstemp(
                dir=self.path.parent, prefix=".virtual_phone-", suffix=".tmp"
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as stream:
                    json.dump(data, stream, indent=2)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(tmp_name, self.path)
                if os.name != "nt":
                    os.chmod(self.path, 0o600)
            finally:
                try:
                    os.unlink(tmp_name)
                except FileNotFoundError:
                    pass

    def _emit(self, message: str) -> None:
        if self._event_callback is None:
            return
        try:
            self._event_callback(message)
        except OSError:
            # Logging must never break authentication.
            pass

    # ---------------------------------------------------------------- helpers

    def _valid_pin(self, pin: object, length: int | None = None) -> bool:
        expected = length if length is not None else self.pin_length
        return (
            isinstance(pin, str)
            and len(pin) == expected
            and pin.isascii()
            and pin.isdigit()
        )

    def _remaining_seconds(self, data: dict, now: float) -> int:
        return max(0, math.ceil(data["locked_until"] - now))

    def _failed_attempt(self, data: dict, now: float, prefix: str = "Incorrect PIN.") -> tuple[bool, str]:
        failures = int(data["failed_attempts"]) + 1
        if failures >= self.max_failures:
            data.update(
                {
                    "failed_attempts": 0,
                    "locked_until": now + self.lockout_seconds,
                    "unlocked": False,
                }
            )
            self._save(data)
            self._emit("Virtual phone lockout triggered")
            return False, (
                f"Attempt limit reached. Locked for {self.lockout_seconds} seconds."
            )

        data.update({"failed_attempts": failures, "unlocked": False})
        self._save(data)
        self._emit("Virtual phone unlock failed")
        left = self.max_failures - failures
        noun = "attempt" if left == 1 else "attempts"
        verb = "remains" if left == 1 else "remain"
        return False, f"{prefix} {left} {noun} {verb}."

    # ----------------------------------------------------------------- public

    def state(self) -> dict:
        with self._lock:
            data = self._load()
            now = time.time()
            remaining = self._remaining_seconds(data, now)
            locked = data["locked_until"] > now
            return {
                "configured": self._is_configured(data),
                "unlocked": bool(data["unlocked"]) and not locked,
                "locked": locked,
                "lock_seconds": remaining,
                "failed_attempts": int(data["failed_attempts"]),
                "max_failures": self.max_failures,
                "lockout_seconds": self.lockout_seconds,
                "pin_length": int(data["pin_length"]),
                "kdf_iterations": self._state_iterations(data),
                "device": "BFL-VIRTUAL-01",
            }

    def setup_pin(self, pin: object, confirmation: object) -> tuple[bool, str]:
        with self._lock:
            if not self._valid_pin(pin):
                return False, f"PIN must contain exactly {self.pin_length} digits."
            if pin != confirmation:
                return False, "PIN entries do not match."

            data = self._load()
            if self._is_configured(data):
                return False, "A PIN is already configured."

            iterations = self._state_iterations(data)
            salt, digest = hash_password(str(pin), iterations)
            data.update(
                {
                    "configured": True,
                    "pin_length": self.pin_length,
                    "kdf": {"name": ALGORITHM, "iterations": iterations},
                    "salt": salt,
                    "digest": digest,
                    "failed_attempts": 0,
                    "locked_until": 0.0,
                    "unlocked": True,
                }
            )
            self._save(data)
            self._emit("Virtual phone PIN configured")
            return True, "PIN configured. Virtual phone unlocked."

    def authenticate(self, pin: object) -> tuple[bool, str]:
        with self._lock:
            data = self._load()
            if not self._is_configured(data):
                return False, "Set up a PIN first."

            length = int(data["pin_length"])
            if not self._valid_pin(pin, length):
                return False, f"Enter a {length}-digit PIN."

            now = time.time()
            remaining = self._remaining_seconds(data, now)
            if remaining > 0:
                return False, f"Temporarily locked. Try again in {remaining} seconds."

            if verify_password(
                str(pin), data["salt"], data["digest"], self._state_iterations(data)
            ):
                data.update(
                    {"failed_attempts": 0, "locked_until": 0.0, "unlocked": True}
                )
                self._save(data)
                self._emit("Virtual phone unlocked")
                return True, "PIN accepted. Welcome."

            return self._failed_attempt(data, now)

    def change_pin(
        self, current: object, new_pin: object, confirmation: object
    ) -> tuple[bool, str]:
        with self._lock:
            data = self._load()
            if not self._is_configured(data):
                return False, "Set up a PIN first."

            length = int(data["pin_length"])
            if not self._valid_pin(new_pin, length):
                return False, f"New PIN must contain exactly {length} digits."
            if new_pin != confirmation:
                return False, "New PIN entries do not match."

            now = time.time()
            remaining = self._remaining_seconds(data, now)
            if remaining > 0:
                return False, f"Temporarily locked. Try again in {remaining} seconds."

            if not verify_password(
                str(current), data["salt"], data["digest"], self._state_iterations(data)
            ):
                return self._failed_attempt(
                    data, now, prefix="Current PIN is incorrect."
                )

            iterations = self._state_iterations(data)
            salt, digest = hash_password(str(new_pin), iterations)
            data.update(
                {
                    "kdf": {"name": ALGORITHM, "iterations": iterations},
                    "salt": salt,
                    "digest": digest,
                    "failed_attempts": 0,
                    "locked_until": 0.0,
                    "unlocked": True,
                }
            )
            self._save(data)
            self._emit("Virtual phone PIN changed")
            return True, "PIN changed. Virtual phone unlocked."

    def lock(self) -> tuple[bool, str]:
        with self._lock:
            data = self._load()
            data["unlocked"] = False
            self._save(data)
            self._emit("Virtual phone locked")
            return True, "Phone locked."

    def reset(self) -> tuple[bool, str]:
        with self._lock:
            try:
                self.path.unlink()
            except FileNotFoundError:
                pass
            self._save(self._default_state())
            self._emit("Virtual phone reset")
            return True, "Virtual phone reset. Set up a new PIN."
