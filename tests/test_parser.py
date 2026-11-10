import pytest

from backend.command_parser import parse_command


def test_simple_split():
    assert parse_command("password analyze") == ["password", "analyze"]


def test_quotes_are_respected():
    assert parse_command('say "hello world"') == ["say", "hello world"]


def test_empty_input():
    assert parse_command("   ") == []


def test_unmatched_quote_raises():
    with pytest.raises(ValueError):
        parse_command('say "unterminated')
