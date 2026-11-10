import pytest

from backend.hash_engine import hash_password, verify_password


def test_hash_and_verify_round_trip():
    salt, digest = hash_password("correct horse", 1_000)
    assert verify_password("correct horse", salt, digest, 1_000) is True


def test_wrong_password_fails():
    salt, digest = hash_password("correct horse", 1_000)
    assert verify_password("wrong horse", salt, digest, 1_000) is False


def test_salts_are_unique_for_same_password():
    salt_one, digest_one = hash_password("same", 1_000)
    salt_two, digest_two = hash_password("same", 1_000)
    assert salt_one != salt_two
    assert digest_one != digest_two


def test_corrupt_salt_fails_closed():
    assert verify_password("x", "not-hex", "00", 1_000) is False


def test_invalid_iterations_rejected():
    with pytest.raises(ValueError):
        hash_password("x", 0)
    with pytest.raises(ValueError):
        verify_password("x", "00", "00", -1)
