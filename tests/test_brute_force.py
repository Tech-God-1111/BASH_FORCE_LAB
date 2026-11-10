import pytest

from backend.virtual_phone.authentication import PhoneAuthentication
from backend.virtual_phone.brute_force import (
    estimate_seconds_per_guess,
    run_full_pin_space,
    run_pin_space,
)


def make_state(tmp_path, pin="0420", iterations=500):
    auth = PhoneAuthentication(
        tmp_path / "phone.json",
        max_failures=5,
        lockout_seconds=30,
        pin_length=4,
        iterations=iterations,
        event_callback=None,
    )
    assert auth.setup_pin(pin, pin)[0] is True
    return auth.path


def test_full_space_finds_pin(tmp_path):
    path = make_state(tmp_path)
    result = run_pin_space(path, progress_every=100)
    assert result.found is True
    assert result.pin == "0420"
    assert result.attempts == 421
    assert result.keyspace_size == 10_000
    assert result.elapsed_seconds >= 0


def test_subset_not_found(tmp_path):
    path = make_state(tmp_path)
    result = run_pin_space(path, candidates=("0000", "0001"))
    assert result.found is False
    assert result.pin is None
    assert result.attempts == 2
    assert result.keyspace_size == 2


def test_progress_callback(tmp_path):
    path = make_state(tmp_path)
    updates = []
    result = run_pin_space(
        path,
        candidates=("0000", "0001", "0002", "0003", "0420"),
        progress_every=2,
        on_progress=lambda done, total: updates.append((done, total)),
    )
    assert result.found is True
    assert updates[0] == (2, 5)
    assert updates[-1] == (5, 5)


def test_estimate_is_positive(tmp_path):
    path = make_state(tmp_path)
    assert estimate_seconds_per_guess(path, samples=2) > 0


def test_missing_state_raises(tmp_path):
    with pytest.raises(ValueError):
        run_pin_space(tmp_path / "missing.json")


def test_corrupt_state_raises(tmp_path):
    path = tmp_path / "phone.json"
    path.write_text("not json", encoding="utf-8")
    with pytest.raises(ValueError):
        run_pin_space(path)


def test_unconfigured_state_raises(tmp_path):
    auth = PhoneAuthentication(
        tmp_path / "phone.json",
        iterations=500,
        event_callback=None,
    )
    with pytest.raises(ValueError):
        run_pin_space(auth.path)


def test_result_as_dict(tmp_path):
    path = make_state(tmp_path)
    data = run_pin_space(path, candidates=("0420",)).as_dict()
    assert data["found"] is True
    assert data["pin"] == "0420"
    assert data["keyspace_size"] == 1
    assert data["attempts_per_second"] is not None


def test_full_wrapper(tmp_path):
    path = make_state(tmp_path)
    result = run_full_pin_space(path, progress_every=500)
    assert result.found is True
    assert result.pin == "0420"
