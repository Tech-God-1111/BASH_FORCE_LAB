# BASH FORCE LAB

**A Python + Bash cybersecurity learning demonstrator with a local graphical virtual phone.**

BASH FORCE LAB is a self-contained lab for studying password hashing, dictionary attacks, account lockout, and the difference between online and offline attacks. Everything runs against the project's own mock account and its own virtual phone. No real devices or external services are involved.

## Safety boundary

This is a software-only simulation. It does not connect to, inspect, unlock, or send authentication attempts to a physical phone or an external service. The virtual phone server binds to loopback only, and the Bash integration runs only allowlisted, read-only diagnostic scripts with `shell=False` and a timeout.

The offline PIN demo deliberately attacks the local `data/virtual_phone.json` file created by this project. That file never contains a plaintext PIN.

## Features

- Command-oriented BFL terminal (no numbered menu).
- Allowlisted local Git Bash diagnostics with an optional `BFL_BASH` override.
- Educational password-strength estimate and salted PBKDF2-HMAC-SHA256 demonstration.
- Isolated mock-account dictionary and defensive lockout demonstrations.
- Activity log with rotation and timestamped session reports.
- Graphical virtual phone with first-run PIN setup, lock/unlock, home screen, and simulated Settings, Security, Lockout Demo, Gallery, Calculator, Files, and About apps.
- PIN stored as a random-salt PBKDF2-HMAC-SHA256 digest; the PIN itself is never stored.
- Configurable attempt limit and lockout duration.
- Thread-safe, atomic JSON state writes.
- Web hardening: loopback-only host validation, CSP, frame denial, JSON-only API, request size limit.
- Offline PIN keyspace demo with a measured cost estimate, ETA, cancellation, and a quick sample mode.

## Requirements

- Python 3.10+
- Git for Windows (Git Bash) on Windows
- Flask (see `requirements.txt`)

## Setup

Extract the project folder, then in Windows PowerShell:

```powershell
cd BASH_FORCE_LAB
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

For an exact reproduction of the tested environment, use `requirements.lock` instead of `requirements.txt`.

Linux/macOS works with `python3 -m venv`, `source .venv/bin/activate`, and the system `bash` on `PATH`.

## First run

1. Start BFL with `python main.py`.
2. Run `phone launch`.
3. The browser opens `http://127.0.0.1:8765`.
4. Create and confirm a four-digit PIN.
5. Use **LOCK DEVICE** and the PIN to exercise the unlock flow.

No phone state is shipped with the project. The state file is created on first run, contains no PIN until you set one, and is excluded by `.gitignore`.

By default, BFL locks the virtual phone on startup, so restarting the CLI behaves like rebooting a device. Set `virtual_phone.lock_on_start` to `false` if you want the device to stay unlocked across restarts.

## BFL commands

```text
help
sysinfo
environment
audit
password analyze
password hash
simulate dictionary
simulate lockout
phone launch
phone status
phone lock
phone change-pin
phone stop
phone reset
phone bruteforce
logs
report
clear
exit
```

`password analyze` and `password hash` hide input with `getpass`.

`phone status` shows both the authentication state and whether the local web server is running.

`phone stop` shuts down the local web server without exiting BFL.

`phone reset` deletes the PIN state after you type `RESET`. Use it if you forget the PIN or want to apply a new PIN length.

`phone bruteforce` demonstrates an offline attack against the stored digest:

- `LOCAL` runs the full 0000-9999 keyspace.
- `QUICK` tests 1,000 deterministically sampled candidates.
- Enter cancels.

The command measures the local PBKDF2 cost first and prints an estimate. The full sweep is intentionally slow; on the reference machine at 240,000 iterations it is roughly 15 minutes worst case. Ctrl+C cancels and prints partial statistics. The live lockout does not apply because the attack runs offline against the extracted hash.

## Configuration

Edit `config.json`:

| Section | Key | Meaning |
|---|---|---|
| `lab` | `max_dictionary_entries` | Maximum wordlist entries tested |
| `lab` | `max_failed_attempts` | Mock-account failure threshold |
| `lab` | `lockout_seconds` | Mock-account lockout duration |
| `virtual_phone` | `host`, `port` | Loopback address and web port |
| `virtual_phone` | `max_failures`, `lockout_seconds` | Phone policy |
| `virtual_phone` | `pin_length` | 4-8 digits for a new PIN |
| `virtual_phone` | `lock_on_start` | Lock the device when BFL starts |
| `virtual_phone` | `state_file` | Runtime state path (must stay inside the project) |
| `kdf` | `iterations` | PBKDF2 work factor for new PINs |
| `bash` | `timeout_seconds` | Diagnostic timeout |

The phone state stores its own KDF iteration count and PIN length at setup time, so changing the config does not invalidate an existing PIN. Use `phone reset` to reconfigure with a different PIN length.

The default 240,000 iterations keeps the offline demo usable. OWASP currently recommends a higher PBKDF2-HMAC-SHA256 work factor (600,000 iterations at the time of writing); raising it makes each guess slower and the demo longer. Check the current OWASP guidance before treating the value as production advice.

## Testing and linting

```bash
pip install -r requirements-dev.txt
ruff check .
pytest -q
```

The test suite covers hashing, lockout expiry, PIN setup/change/reset, corrupt state recovery, concurrent unlock attempts, the offline keyspace demo, the HTTP API, configuration validation, the command parser, and the Bash allowlist. Tests use temporary state files and never touch the real `data/` or `logs/` directories. CI runs the suite on Linux and Windows for Python 3.10 and 3.12.

## Architecture

```text
main.py
  -> backend.application.Application
       -> command parser + command registry
       -> backend.simulator.LocalAuthSimulator      (mock account demos)
       -> backend.virtual_phone.device.VirtualPhone (PIN state)
       -> backend.phone_server.PhoneServer          (local Flask server)
            -> backend.virtual_phone.web_app         (HTTP API + static files)
       -> backend.bash_executor                     (allowlisted diagnostics)
  -> frontend/index.html + assets                    (virtual phone UI)
```

Runtime state lives in `data/virtual_phone.json`; logs live in `logs/activity.log`; reports go to `reports/`.

## Web API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/state` | Current phone state |
| POST | `/api/setup-pin` | Set the first PIN |
| POST | `/api/unlock` | Verify a PIN |
| POST | `/api/lock` | Lock the device |
| POST | `/api/change-pin` | Change the PIN with the current PIN |

POST endpoints require `Content-Type: application/json`. A locked device returns `429`; an incorrect PIN returns `401`; validation failures return `400`.

## Troubleshooting

**"Git Bash was not found."** Install Git for Windows. If Bash is in a non-standard location, set `BFL_BASH` to the full path of `bash.exe`.

**"Could not start the phone server" / port in use.** Close the other BFL instance, or change `virtual_phone.port` in `config.json`.

**Forgot the virtual phone PIN.** Run `phone reset` and type `RESET`, then launch the phone and set a new PIN.

**Browser does not open automatically.** Use the printed URL; the server is already running.

**The full brute-force demo is slow.** Use `QUICK`, or lower `kdf.iterations` for a new PIN. The slowness is the lesson: offline guessing is limited by hash cost.

## Notes on the demos

- `simulate dictionary` runs against an in-memory mock account only. The sample wordlist intentionally contains the demo password so the demo reaches a deterministic "found" result.
- `simulate lockout` demonstrates the mock account's in-memory guard. Restarting BFL resets it.
- `phone bruteforce` is the offline attack. It bypasses the live lockout by design and works only on this project's local state file.
- The Lockout Demo app inside the virtual phone is a client-side policy demonstration. It does not send guesses to the PIN verifier; its lockout timer is shortened to five seconds for the demo.

Learn Security. Understand Attacks. Build Defenses.
