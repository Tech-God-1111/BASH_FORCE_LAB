import backend.security_defense as security_defense
from backend.security_defense import LockoutGuard


class FakeClock:
    def __init__(self, start: float = 1000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now


def test_failures_lock_and_expire(monkeypatch):
    clock = FakeClock()
    monkeypatch.setattr(security_defense, "monotonic", clock)
    guard = LockoutGuard(max_failures=3, lockout_seconds=10)

    assert guard.record_failure() is False
    assert guard.record_failure() is False
    assert guard.record_failure() is True
    assert guard.is_locked() is True
    assert guard.remaining() == 10

    clock.now += 4
    assert guard.is_locked() is True
    assert guard.remaining() == 6

    clock.now += 7
    assert guard.is_locked() is False
    assert guard.remaining() == 0
    assert guard.failures == 0


def test_success_resets_counter(monkeypatch):
    clock = FakeClock()
    monkeypatch.setattr(security_defense, "monotonic", clock)
    guard = LockoutGuard(max_failures=3, lockout_seconds=10)

    guard.record_failure()
    guard.record_failure()
    guard.record_success()

    assert guard.record_failure() is False
    assert guard.failures == 1
    assert guard.is_locked() is False
