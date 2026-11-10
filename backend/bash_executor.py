"""Run only allowlisted, read-only Bash diagnostics.

The script name is checked against a fixed allowlist, the resolved path must
stay inside bash/, and the process runs without a shell and with a timeout.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from backend.paths import BASH_DIR, ROOT

ALLOWED = frozenset({"environment_check.sh", "system_info.sh", "security_audit.sh"})


def _bash_candidates():
    override = os.environ.get("BFL_BASH")
    if override:
        yield Path(override)

    if os.name == "nt":
        yield Path(r"C:\Program Files\Git\bin\bash.exe")
        yield Path(r"C:\Program Files\Git\usr\bin\bash.exe")

    found = shutil.which("bash")
    if found:
        yield Path(found)

    if os.name != "nt":
        yield Path("bash")


def run_diagnostic(script_name: str, timeout: int = 15) -> tuple[int, str]:
    if script_name not in ALLOWED:
        raise ValueError("That diagnostic is not allowlisted.")

    script = (BASH_DIR / script_name).resolve()
    if script.parent != BASH_DIR.resolve() or not script.is_file():
        raise FileNotFoundError("Allowlisted diagnostic script is missing.")

    env = os.environ.copy()
    env["BFL_PYTHON"] = sys.executable
    env["BFL_PROJECT_ROOT"] = str(ROOT)

    for executable in _bash_candidates():
        try:
            result = subprocess.run(
                [str(executable), str(script)],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                check=False,
                shell=False,
                env=env,
            )
            return result.returncode, (result.stdout + result.stderr).strip()
        except FileNotFoundError:
            continue
        except subprocess.TimeoutExpired:
            return 124, f"Diagnostic timed out after {timeout} seconds."
        except OSError:
            continue

    return 127, "Git Bash was not found. Install Git for Windows or set BFL_BASH."
