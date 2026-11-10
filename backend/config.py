"""Configuration loading and validation.

The committed config.json is intentionally small. Defaults live here so a
missing optional key never crashes the CLI with a raw KeyError.
"""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any

from backend.paths import CONFIG_FILE, ROOT

LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}

DEFAULTS: dict[str, Any] = {
    "lab": {
        "name": "BASH FORCE LAB",
        "version": "2.1.0",
        "max_dictionary_entries": 100,
        "max_failed_attempts": 5,
        "lockout_seconds": 15,
    },
    "demo_account": {
        "username": "student",
        "password": "LabPass2026!",
    },
    "virtual_phone": {
        "host": "127.0.0.1",
        "port": 8765,
        "max_failures": 5,
        "lockout_seconds": 30,
        "pin_length": 4,
        "lock_on_start": True,
        "state_file": "data/virtual_phone.json",
    },
    "kdf": {
        "name": "pbkdf2_hmac_sha256",
        "iterations": 240_000,
    },
    "bash": {
        "timeout_seconds": 15,
    },
}


class ConfigError(RuntimeError):
    """Raised when config.json cannot be loaded or fails validation."""


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _require_int(section: dict[str, Any], key: str, minimum: int, maximum: int | None = None) -> int:
    value = section.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"{key} must be an integer.")
    if value < minimum or (maximum is not None and value > maximum):
        bounds = f"between {minimum} and {maximum}" if maximum is not None else f">= {minimum}"
        raise ConfigError(f"{key} must be {bounds}.")
    return value


def _validate(config: dict[str, Any]) -> None:
    lab = config["lab"]
    phone = config["virtual_phone"]
    kdf = config["kdf"]
    bash = config["bash"]

    _require_int(lab, "max_dictionary_entries", 1, 10_000)
    _require_int(lab, "max_failed_attempts", 1, 100)
    _require_int(lab, "lockout_seconds", 0, 86_400)
    _require_int(phone, "port", 1, 65_535)
    _require_int(phone, "max_failures", 1, 100)
    _require_int(phone, "lockout_seconds", 0, 86_400)
    _require_int(phone, "pin_length", 4, 8)
    _require_int(kdf, "iterations", 1_000, 10_000_000)
    _require_int(bash, "timeout_seconds", 1, 600)

    if phone.get("host") not in LOOPBACK_HOSTS:
        raise ConfigError(
            "virtual_phone.host must be a loopback address "
            f"({', '.join(sorted(LOOPBACK_HOSTS))}); the phone is a local-only lab."
        )

    if not isinstance(phone.get("lock_on_start"), bool):
        raise ConfigError("virtual_phone.lock_on_start must be true or false.")

    state_file = phone.get("state_file")
    if not isinstance(state_file, str) or not state_file.strip():
        raise ConfigError("virtual_phone.state_file must be a non-empty path.")
    state_path = (ROOT / state_file).resolve()
    if not state_path.is_relative_to(ROOT.resolve()):
        raise ConfigError("virtual_phone.state_file must stay inside the project directory.")


def load_config(path: Path | None = None) -> dict[str, Any]:
    """Load config.json, merge defaults, and validate the result."""

    config_path = path or Path(os.environ.get("BFL_CONFIG", CONFIG_FILE))
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigError(f"Configuration file not found: {config_path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Invalid JSON in {config_path}: {exc}") from exc
    except OSError as exc:
        raise ConfigError(f"Could not read {config_path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ConfigError(f"{config_path} must contain a JSON object.")

    config = _deep_merge(DEFAULTS, raw)
    _validate(config)
    return config
