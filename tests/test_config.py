import json

import pytest

from backend.config import ConfigError, load_config


def test_load_committed_config():
    config = load_config()
    assert config["lab"]["name"] == "BASH FORCE LAB"
    assert config["virtual_phone"]["host"] == "127.0.0.1"
    assert config["kdf"]["iterations"] > 0


def test_missing_file(tmp_path):
    with pytest.raises(ConfigError):
        load_config(tmp_path / "missing.json")


def test_invalid_json(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(path)


def test_defaults_are_merged(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps({"lab": {"max_failed_attempts": 2}}), encoding="utf-8"
    )
    config = load_config(path)
    assert config["lab"]["max_failed_attempts"] == 2
    assert config["lab"]["name"] == "BASH FORCE LAB"
    assert config["virtual_phone"]["port"] == 8765


def test_non_loopback_host_rejected(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps({"virtual_phone": {"host": "0.0.0.0"}}), encoding="utf-8"
    )
    with pytest.raises(ConfigError):
        load_config(path)


def test_state_file_must_stay_in_project(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps({"virtual_phone": {"state_file": "../outside.json"}}),
        encoding="utf-8",
    )
    with pytest.raises(ConfigError):
        load_config(path)


def test_bad_pin_length_rejected(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps({"virtual_phone": {"pin_length": 2}}), encoding="utf-8"
    )
    with pytest.raises(ConfigError):
        load_config(path)
