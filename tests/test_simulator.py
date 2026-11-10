import pytest

from backend.simulator import LocalAuthSimulator


@pytest.fixture(autouse=True)
def silence_log(monkeypatch):
    monkeypatch.setattr("backend.simulator.log_event", lambda event: None)


@pytest.fixture
def simulator():
    return LocalAuthSimulator(
        "student", "LabPass2026!", max_failures=2, lockout_seconds=10, iterations=1_000
    )


def test_correct_and_wrong_credentials(simulator):
    assert simulator.authenticate("student", "LabPass2026!")[0] is True
    assert simulator.authenticate("student", "wrong")[0] is False


def test_lockout_after_failures():
    auth = LocalAuthSimulator(
        "student", "pw", max_failures=2, lockout_seconds=10, iterations=1_000
    )
    assert auth.authenticate("student", "wrong")[0] is False
    ok, message = auth.authenticate("student", "wrong")
    assert ok is False
    assert message.startswith("LOCKED")
    assert auth.authenticate("student", "pw")[0] is False


def test_dictionary_demo_finds_entry(tmp_path):
    wordlist = tmp_path / "words.txt"
    wordlist.write_text("# comment\n\npassword\nLabPass2026!\n", encoding="utf-8")
    auth = LocalAuthSimulator(
        "student", "LabPass2026!", max_failures=5, lockout_seconds=10, iterations=1_000
    )
    result = auth.dictionary_demo("student", wordlist, max_entries=10)
    assert result["status"] == "found"
    assert result["tested"] == 2


def test_dictionary_demo_limit(tmp_path):
    wordlist = tmp_path / "words.txt"
    wordlist.write_text("one\ntwo\nthree\n", encoding="utf-8")
    auth = LocalAuthSimulator(
        "student", "pw", max_failures=5, lockout_seconds=10, iterations=1_000
    )
    result = auth.dictionary_demo("student", wordlist, max_entries=1)
    assert result["status"] == "limit"


def test_dictionary_demo_missing_file(tmp_path):
    auth = LocalAuthSimulator(
        "student", "pw", max_failures=5, lockout_seconds=10, iterations=1_000
    )
    result = auth.dictionary_demo("student", tmp_path / "missing.txt", max_entries=10)
    assert result["status"] == "error"
