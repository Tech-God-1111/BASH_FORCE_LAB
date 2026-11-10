"""Tokenize a command line without executing a shell."""

import shlex


def parse_command(line: str) -> list[str]:
    try:
        return shlex.split(line)
    except ValueError as exc:
        raise ValueError(f"Invalid command syntax: {exc}") from exc
