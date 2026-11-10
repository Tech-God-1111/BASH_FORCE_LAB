"""In-memory lockout guard used by the mock account demo."""

from __future__ import annotations

import math
from dataclasses import dataclass
from time import monotonic


@dataclass
class LockoutGuard:
    max_failures: int = 5
    lockout_seconds: int = 15
    failures: int = 0
    locked_until: float = 0.0

    def is_locked(self) -> bool:
        if self.locked_until and monotonic() >= self.locked_until:
            self.locked_until = 0.0
            return False
        return self.locked_until > 0.0

    def remaining(self) -> int:
        return max(0, math.ceil(self.locked_until - monotonic()))

    def record_failure(self) -> bool:
        """Count a failure and return True when this one triggered a lockout."""

        self.failures += 1
        if self.failures >= self.max_failures:
            self.locked_until = monotonic() + self.lockout_seconds
            self.failures = 0
            return True
        return False

    def record_success(self) -> None:
        self.failures = 0
        self.locked_until = 0.0
