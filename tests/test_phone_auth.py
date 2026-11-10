from concurrent.futures import ThreadPoolExecutor

import pytest

import backend.virtual_phone.authentication as auth_module
from backend.virtual_phone.authentication import PhoneAuthentication


@pytest.fixture
def make_auth(tmp_path):
    def factory(**kwargs):
        settings = {
            "max_failures": 3,
            "lockout_seconds": 30,
            "pin_length": 4,
            "iterations": 1_000,
            "event_callback": None,
        }
        settings.update(kwargs)
        return PhoneAuthentication(tmp_path / "phone.json", **settings)

    return factory


def test_setup_validation(make_auth):
    auth = make_auth()
    assert auth.setup_pin("123", "123")[0] is False
    assert auth.setup_pin("abcd", "abcd")[0] is False
    assert auth.setup_pin("1234", "1235")[0] is False
    assert auth.setup_pin("1234", "1234")[0] is True
    assert auth.setup_pin("5678", "5678")[0] is False


def test_state_after_setup(make_auth):
    auth = make_auth()
    auth.setup_pin("1234", "1234")
    state = auth.state()
    assert state["configured"] is True
    assert state["unlocked"] is True
    assert state["pin_length"] == 4
    assert state["kdf_iterations"] == 1_000
    assert state["locked"] is False


def test_wrong_pin_counts_and_locks(make_auth):
    auth = make_auth()
    auth.setup_pin("1234", "1234")

    ok, message = auth.authenticate("0000")
    assert ok is False
    assert "2 attempts remain" in message

    ok, message = auth.authenticate("0000")
    assert ok is False
    assert "1 attempt remains" in message

    ok, message = auth.authenticate("0000")
    assert ok is False
    assert "Locked for 30 seconds" in message

    state = auth.state()
    assert state["locked"] is True
    assert state["lock_seconds"] > 0
    assert state["failed_attempts"] == 0

    ok, message = auth.authenticate("1234")
    assert ok is False
    assert "Temporarily locked" in message


def test_success_resets_failures(make_auth):
    auth = make_auth()
    auth.setup_pin("1234", "1234")
    auth.authenticate("0000")
    auth.authenticate("0000")

    ok, message = auth.authenticate("1234")
    assert ok is True
    assert "accepted" in message
    assert auth.state()["failed_attempts"] == 0
    assert auth.state()["unlocked"] is True


def test_lock(make_auth):
    auth = make_auth()
    auth.setup_pin("1234", "1234")
    ok, message = auth.lock()
    assert ok is True
    assert message == "Phone locked."
    assert auth.state()["unlocked"] is False


def test_change_pin(make_auth):
    auth = make_auth()
    auth.setup_pin("1234", "1234")

    ok, _ = auth.change_pin("0000", "5678", "5678")
    assert ok is False

    ok, message = auth.change_pin("1234", "5678", "5678")
    assert ok is True
    assert "changed" in message

    assert auth.authenticate("1234")[0] is False
    assert auth.authenticate("5678")[0] is True


def test_change_pin_validation(make_auth):
    auth = make_auth()
    auth.setup_pin("1234", "1234")
    assert auth.change_pin("1234", "12", "12")[0] is False
    assert auth.change_pin("1234", "5678", "8765")[0] is False


def test_state_persists_across_instances(make_auth, tmp_path):
    first = make_auth()
    first.setup_pin("1234", "1234")

    second = PhoneAuthentication(
        tmp_path / "phone.json",
        max_failures=3,
        lockout_seconds=30,
        pin_length=4,
        iterations=1_000,
        event_callback=None,
    )
    assert second.authenticate("1234")[0] is True


def test_pin_length_is_stored_with_state(make_auth, tmp_path):
    first = make_auth(pin_length=4)
    first.setup_pin("1234", "1234")

    # A config change must not invalidate the PIN that is already stored.
    second = PhoneAuthentication(
        tmp_path / "phone.json",
        max_failures=3,
        lockout_seconds=30,
        pin_length=6,
        iterations=1_000,
        event_callback=None,
    )
    assert second.state()["pin_length"] == 4
    assert second.authenticate("1234")[0] is True


def test_corrupt_state_falls_back_to_setup(make_auth, tmp_path):
    path = tmp_path / "phone.json"
    path.write_text("not json", encoding="utf-8")
    auth = make_auth()
    assert auth.state()["configured"] is False
    assert auth.setup_pin("1234", "1234")[0] is True


def test_partial_state_falls_back_to_setup(make_auth, tmp_path):
    path = tmp_path / "phone.json"
    path.write_text(
        '{"configured": true, "salt": "aa"}', encoding="utf-8"
    )
    auth = make_auth()
    assert auth.state()["configured"] is False
    assert auth.setup_pin("1234", "1234")[0] is True


def test_reset(make_auth):
    auth = make_auth()
    auth.setup_pin("1234", "1234")
    ok, message = auth.reset()
    assert ok is True
    assert "reset" in message.lower()
    assert auth.state()["configured"] is False


def test_lockout_expiry(make_auth, monkeypatch):
    class Clock:
        def __init__(self) -> None:
            self.now = 1_000.0

        def time(self) -> float:
            return self.now

    clock = Clock()
    monkeypatch.setattr(auth_module, "time", clock)
    auth = make_auth(lockout_seconds=30)
    auth.setup_pin("1234", "1234")

    for _ in range(3):
        auth.authenticate("0000")
    assert auth.state()["locked"] is True

    clock.now += 31
    assert auth.state()["locked"] is False
    assert auth.authenticate("1234")[0] is True


def test_concurrent_wrong_attempts_lock_safely(make_auth):
    auth = make_auth(max_failures=3)
    auth.setup_pin("1234", "1234")

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda _: auth.authenticate("0000"), range(12)))

    state = auth.state()
    assert state["configured"] is True
    assert state["locked"] is True
    # The file must still be valid JSON after concurrent writes.
    assert auth.authenticate("0000")[0] is False


def test_event_callback(make_auth):
    events = []
    auth = make_auth(event_callback=events.append)
    auth.setup_pin("1234", "1234")
    auth.lock()
    auth.authenticate("1234")
    assert any("configured" in event for event in events)
    assert any("locked" in event for event in events)
    assert any("unlocked" in event for event in events)
