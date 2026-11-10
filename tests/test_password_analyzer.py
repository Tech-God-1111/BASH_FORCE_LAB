from backend.password_analyzer import analyze_password


def test_empty_password():
    result = analyze_password("")
    assert result["rating"] == "Empty"
    assert result["length"] == 0


def test_groups_and_entropy():
    result = analyze_password("Abc123!x")
    assert result["length"] == 8
    assert "lowercase" in result["character_groups"]
    assert "uppercase" in result["character_groups"]
    assert "digits" in result["character_groups"]
    assert "symbols" in result["character_groups"]
    assert result["entropy_bits"] > 0


def test_non_ascii_counts_as_other():
    result = analyze_password("pässwörd")
    assert "other" in result["character_groups"]
    assert result["entropy_bits"] > 0


def test_rating_thresholds():
    assert analyze_password("abc")["rating"] == "Weak"
    assert analyze_password("A-longer-passphrase-2026!")["rating"] == "Strong"
