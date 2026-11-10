import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

import backend.bash_executor as bash_executor


def test_unknown_script_is_rejected():
    with pytest.raises(ValueError):
        bash_executor.run_diagnostic("evil.sh")


def test_missing_script_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(bash_executor, "BASH_DIR", tmp_path)
    with pytest.raises(FileNotFoundError):
        bash_executor.run_diagnostic("system_info.sh")


def test_runs_without_shell_and_passes_environment(monkeypatch, tmp_path):
    script = tmp_path / "system_info.sh"
    script.write_text("echo hi\n", encoding="utf-8")
    monkeypatch.setattr(bash_executor, "BASH_DIR", tmp_path)
    monkeypatch.setattr(
        bash_executor, "_bash_candidates", lambda: iter([Path("bash")])
    )

    captured = {}

    def fake_run(args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return SimpleNamespace(returncode=0, stdout="hello\n", stderr="")

    monkeypatch.setattr(bash_executor.subprocess, "run", fake_run)

    code, output = bash_executor.run_diagnostic("system_info.sh", timeout=5)
    assert code == 0
    assert output == "hello"
    assert captured["kwargs"]["shell"] is False
    assert captured["kwargs"]["timeout"] == 5
    assert captured["kwargs"]["encoding"] == "utf-8"
    assert "BFL_PYTHON" in captured["kwargs"]["env"]
    assert captured["kwargs"]["env"]["BFL_PROJECT_ROOT"]


def test_timeout(monkeypatch):
    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="bash", timeout=5)

    monkeypatch.setattr(
        bash_executor, "_bash_candidates", lambda: iter([Path("bash")])
    )
    monkeypatch.setattr(bash_executor.subprocess, "run", fake_run)

    code, output = bash_executor.run_diagnostic("system_info.sh", timeout=5)
    assert code == 124
    assert "timed out" in output


def test_no_bash_available(monkeypatch):
    monkeypatch.setattr(bash_executor, "_bash_candidates", lambda: iter(()))
    code, output = bash_executor.run_diagnostic("system_info.sh")
    assert code == 127
    assert "Git Bash" in output
