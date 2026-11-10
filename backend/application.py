"""BASH FORCE LAB command-line application."""

from __future__ import annotations

import getpass
import json
import os
import random
import time
import webbrowser
from datetime import datetime

from backend.bash_executor import run_diagnostic
from backend.command_parser import parse_command
from backend.config import load_config
from backend.hash_engine import hash_password, verify_password
from backend.logger import log_event, recent_events
from backend.password_analyzer import analyze_password
from backend.paths import REPORT_DIR, ROOT
from backend.phone_server import PhoneServer
from backend.simulator import LocalAuthSimulator
from backend.virtual_phone.brute_force import estimate_seconds_per_guess, run_pin_space
from backend.virtual_phone.device import VirtualPhone


class Application:
    def __init__(self, config: dict | None = None) -> None:
        self.config = config or load_config()
        lab = self.config["lab"]
        phone = self.config["virtual_phone"]

        self.max_entries = int(lab["max_dictionary_entries"])
        self.max_failures = int(lab["max_failed_attempts"])
        self.lockout_seconds = int(lab["lockout_seconds"])
        self.username = str(self.config["demo_account"]["username"])
        self.password = str(self.config["demo_account"]["password"])
        self.kdf_iterations = int(self.config["kdf"]["iterations"])
        self.bash_timeout = int(self.config["bash"]["timeout_seconds"])

        self.auth = self._new_simulator()
        self.phone = VirtualPhone(
            ROOT,
            config=phone,
            kdf_iterations=self.kdf_iterations,
            event_callback=log_event,
        )
        self.phone_server = PhoneServer(
            self.phone, str(phone["host"]), int(phone["port"])
        )

        if bool(phone.get("lock_on_start", True)):
            status = self.phone.status()
            if status["configured"] and status["unlocked"]:
                self.phone.auth.lock()

        self._commands = self._build_commands()

    # --------------------------------------------------------------- startup

    def _new_simulator(self) -> LocalAuthSimulator:
        return LocalAuthSimulator(
            self.username,
            self.password,
            self.max_failures,
            self.lockout_seconds,
            iterations=self.kdf_iterations,
        )

    def _build_commands(self) -> dict[tuple[str, ...], object]:
        return {
            ("help",): self._help,
            ("?",): self._help,
            ("clear",): self._clear,
            ("sysinfo",): self._cmd_sysinfo,
            ("environment",): self._cmd_environment,
            ("audit",): self._cmd_audit,
            ("password",): self._password_help,
            ("password", "analyze"): self._password_analysis,
            ("password", "hash"): self._hash_demo,
            ("simulate",): self._simulate_help,
            ("simulate", "dictionary"): self._dictionary_demo,
            ("simulate", "lockout"): self._lockout_demo,
            ("phone",): self._phone_help,
            ("phone", "launch"): self._phone_launch,
            ("phone", "status"): self._phone_status,
            ("phone", "lock"): self._phone_lock,
            ("phone", "stop"): self._phone_stop,
            ("phone", "reset"): self._phone_reset,
            ("phone", "change-pin"): self._phone_change_pin,
            ("phone", "bruteforce"): self._phone_bruteforce,
            ("logs",): self._logs,
            ("report",): self._report,
        }

    def run(self) -> None:
        log_event("BASH FORCE LAB command terminal started")
        self._banner()
        try:
            while True:
                try:
                    raw = input("BFL:~$ ").strip()
                    if not raw:
                        continue
                    if not self.dispatch(raw):
                        break
                except EOFError:
                    print()
                    break
                except KeyboardInterrupt:
                    print("\nUse 'exit' to close BFL.")
                except (OSError, ValueError, KeyError) as exc:
                    print(f"Operation error: {exc}")
                    log_event(f"Operation error: {type(exc).__name__}: {exc}")
        finally:
            self.phone_server.stop()

        log_event("Application exited")
        print("BFL closed. Learn Security. Build Defenses.")

    def _banner(self) -> None:
        name = self.config["lab"]["name"]
        version = self.config["lab"]["version"]
        print("\n" + "=" * 58)
        print(f"{name + ' v' + version:^58}")
        print("       Python + Bash + Virtual Phone Laboratory".center(58))
        print("=" * 58)
        print("Type 'help' to view available commands.\n")

    # -------------------------------------------------------------- dispatch

    def dispatch(self, raw: str) -> bool:
        tokens = parse_command(raw)
        if not tokens:
            return True

        first = tokens[0].lower()
        if first in {"exit", "quit"}:
            return False

        key = (first, tokens[1].lower()) if len(tokens) > 1 else (first,)
        handler = self._commands.get(key)
        if handler is None:
            if first in {"phone", "password", "simulate"}:
                print(f"Unknown {first} subcommand. Type '{first}' for usage.")
            else:
                print("Unknown command. Type 'help' for available commands.")
            return True

        handler(tokens)
        return True

    @staticmethod
    def _help(args: list[str] | None = None) -> None:
        print(
            """
BASH FORCE LAB COMMANDS
-----------------------
help                    Show this command list
sysinfo                 Display local system information through Git Bash
environment             Check the Bash/Python environment
audit                   Run the read-only project audit
password analyze        Analyze a sample password (input hidden)
password hash           Demonstrate salted PBKDF2 hashing and verification
simulate dictionary     Run the bounded local mock-account dictionary demo
simulate lockout        Demonstrate the mock account's defensive lockout
phone launch            Start and open the graphical virtual phone
phone status            Show phone authentication and server status
phone lock              Lock the virtual phone
phone change-pin        Change the virtual phone PIN
phone stop              Stop the local phone web server
phone reset             Delete the PIN state and start over
phone bruteforce        Offline keyspace demo (full or quick sample)
logs                    Display recent activity
report                  Generate a session report
clear                   Clear the terminal display
exit                    Close BASH FORCE LAB
"""
        )

    @staticmethod
    def _password_help(args: list[str] | None = None) -> None:
        print("Usage: password analyze | password hash")

    @staticmethod
    def _simulate_help(args: list[str] | None = None) -> None:
        print("Usage: simulate dictionary | simulate lockout")

    @staticmethod
    def _phone_help(args: list[str] | None = None) -> None:
        print(
            "Usage: phone launch | status | lock | change-pin | stop | reset | bruteforce"
        )

    # ------------------------------------------------------------ diagnostics

    def _bash(self, script: str) -> None:
        code, output = run_diagnostic(script, timeout=self.bash_timeout)
        print(f"\n[ Bash: {script} | exit {code} ]\n{output or '(no output)'}")
        log_event(f"Bash diagnostic executed: {script}, exit={code}")

    def _cmd_sysinfo(self, args: list[str]) -> None:
        self._bash("system_info.sh")

    def _cmd_environment(self, args: list[str]) -> None:
        self._bash("environment_check.sh")

    def _cmd_audit(self, args: list[str]) -> None:
        self._bash("security_audit.sh")

    # --------------------------------------------------------------- password

    def _password_analysis(self, args: list[str]) -> None:
        try:
            sample = getpass.getpass("Enter a sample password (input hidden): ")
        except (EOFError, KeyboardInterrupt):
            print("\nCancelled.")
            return
        result = analyze_password(sample)
        for key, value in result.items():
            print(f"{key.replace('_', ' ').title()}: {value}")
        log_event("Password strength analysis completed")

    def _hash_demo(self, args: list[str]) -> None:
        try:
            sample = getpass.getpass("Enter a dummy password (input hidden): ")
        except (EOFError, KeyboardInterrupt):
            print("\nCancelled.")
            return
        if not sample:
            print("No sample entered.")
            return

        salt_one, digest_one = hash_password(sample, self.kdf_iterations)
        salt_two, digest_two = hash_password(sample, self.kdf_iterations)
        print(f"Algorithm: PBKDF2-HMAC-SHA256\nIterations: {self.kdf_iterations:,}")
        print(f"Salt 1: {salt_one}\nHash 1: {digest_one}")
        print(f"Salt 2: {salt_two}\nHash 2: {digest_two}")
        print("Verification (correct password):", verify_password(
            sample, salt_one, digest_one, self.kdf_iterations
        ))
        print("Verification (wrong password):  ", verify_password(
            sample + "-wrong", salt_one, digest_one, self.kdf_iterations
        ))
        print("Salts differ:", salt_one != salt_two)
        log_event("Password hashing demonstration completed")

    # --------------------------------------------------------------- simulate

    def _dictionary_demo(self, args: list[str]) -> None:
        print("LOCAL MOCK ACCOUNT ONLY. No network or physical device access.")
        if input("Type LOCAL to continue: ").strip() != "LOCAL":
            print("Cancelled.")
            return

        self.auth = self._new_simulator()
        result = self.auth.dictionary_demo(
            self.username,
            ROOT / "data" / "sample_passwords.txt",
            self.max_entries,
        )
        print(
            f"Result: {result['status']}\n"
            f"Tested entries: {result['tested']}\n{result['message']}"
        )
        log_event(f"Local dictionary demonstration ended: {result['status']}")

    def _lockout_demo(self, args: list[str]) -> None:
        print("Testing the mock account's defensive lockout policy.")
        self.auth = self._new_simulator()
        for attempt in range(1, self.max_failures + 2):
            _, message = self.auth.authenticate(
                self.username, "intentionally-wrong-demo-password"
            )
            print(f"Attempt {attempt}: {message}")
            if message.startswith("LOCKED"):
                break
        print("This guard is in-memory; restarting BFL resets the mock account.")
        log_event("Account lockout demonstration completed")

    # ------------------------------------------------------------------ phone

    def _phone_launch(self, args: list[str]) -> None:
        try:
            url = self.phone_server.start()
        except OSError as exc:
            print(f"Could not start the phone server: {exc}")
            print("Close the other BFL instance or change virtual_phone.port in config.json.")
            log_event(f"Virtual phone server failed to start: {exc}")
            return

        print(f"Virtual phone: {url}")
        try:
            webbrowser.open(url)
        except OSError:
            print("Could not open a browser automatically; use the URL above.")
        log_event(
            f"Local virtual phone server started on "
            f"{self.phone_server.host}:{self.phone_server.port}"
        )

    def _phone_status(self, args: list[str]) -> None:
        data = {
            "server": {
                "running": self.phone_server.is_running,
                "url": self.phone_server.url,
            },
            **self.phone.status(),
        }
        print(json.dumps(data, indent=2))

    def _phone_lock(self, args: list[str]) -> None:
        _, message = self.phone.auth.lock()
        print(message)

    def _phone_stop(self, args: list[str]) -> None:
        if not self.phone_server.is_running:
            print("The virtual phone server is not running.")
            return
        self.phone_server.stop()
        print("Virtual phone server stopped.")
        log_event("Local virtual phone server stopped")

    def _phone_reset(self, args: list[str]) -> None:
        print("This deletes the configured PIN and resets the virtual phone.")
        if input("Type RESET to continue: ").strip() != "RESET":
            print("Cancelled.")
            return
        _, message = self.phone.auth.reset()
        print(message)
        log_event("Virtual phone reset from BFL terminal")

    def _phone_change_pin(self, args: list[str]) -> None:
        try:
            current = getpass.getpass("Current PIN: ")
            new_pin = getpass.getpass("New PIN: ")
            confirmation = getpass.getpass("Confirm new PIN: ")
        except (EOFError, KeyboardInterrupt):
            print("\nCancelled.")
            return
        ok, message = self.phone.auth.change_pin(current, new_pin, confirmation)
        print(message)

    def _phone_bruteforce(self, args: list[str]) -> None:
        state_path = self.phone.state_path
        if not self.phone.status()["configured"]:
            print("Set up a PIN first with 'phone launch'.")
            return

        try:
            per_guess = estimate_seconds_per_guess(state_path, samples=3)
        except ValueError as exc:
            print(exc)
            return

        full_seconds = per_guess * 10_000
        quick_seconds = per_guess * 1_000

        print("\nOFFLINE PIN BRUTE-FORCE DEMO")
        print("-" * 58)
        print("This attacks only the salted PBKDF2 digest stored for this")
        print(f"  project's own virtual phone: {state_path.relative_to(ROOT)}")
        print("It does not use the live unlock screen, so the app's attempt")
        print("limit and lockout do not apply -- an offline attacker never")
        print("has to go through the lock screen. No network or real device.")
        print()
        print(
            f"Local cost: {per_guess * 1000:.0f} ms per guess. "
            f"Full keyspace: about {self._format_duration(full_seconds)}; "
            f"quick sample: about {self._format_duration(quick_seconds)}."
        )

        choice = input(
            "Type LOCAL for the full 0000-9999 sweep, QUICK for 1,000 "
            "sampled candidates, or Enter to cancel: "
        ).strip().upper()
        if choice in {"LOCAL", "FULL"}:
            candidates = None
        elif choice == "QUICK":
            sampled = sorted(random.Random(0).sample(range(10_000), 1_000))
            candidates = tuple(f"{number:04d}" for number in sampled)
        else:
            print("Cancelled.")
            return

        started = time.monotonic()
        last = {"done": 0}

        def report(done: int, total_count: int) -> None:
            last["done"] = done
            elapsed = time.monotonic() - started
            rate = done / elapsed if elapsed > 0 else 0
            eta = (total_count - done) / rate if rate > 0 else 0
            print(
                f"\r  {done}/{total_count} tried | {rate:.1f}/s | "
                f"ETA {self._format_duration(eta)}",
                end="",
                flush=True,
            )

        try:
            result = run_pin_space(
                state_path,
                candidates=candidates,
                progress_every=50,
                on_progress=report,
            )
        except KeyboardInterrupt:
            elapsed = time.monotonic() - started
            print(
                f"\nCancelled after {last['done']} attempts in "
                f"{self._format_duration(elapsed)}."
            )
            log_event(
                f"Offline PIN brute-force demo cancelled after {last['done']} attempts"
            )
            return
        except ValueError as exc:
            print(f"\n{exc}")
            return

        print()  # leave the progress line
        data = result.as_dict()
        if data["found"]:
            print(f"PIN recovered: {data['pin']}")
        else:
            print("No match found in the tested candidates.")
        print(f"Attempts: {data['attempts']} / {data['keyspace_size']}")
        print(
            f"Elapsed: {data['elapsed_seconds']}s "
            f"({data['attempts_per_second']} attempts/sec)"
        )
        print()
        print("Takeaway: a 4-digit PIN has only 10,000 possibilities, and")
        print("an offline attacker is limited by the hash cost, not by the")
        print("live lockout counter. PBKDF2 iterations make each guess slow;")
        print("a longer PIN or a stronger KDF makes the keyspace harder.")

        log_event(
            f"Offline PIN brute-force demo completed: found={data['found']}, "
            f"attempts={data['attempts']}, elapsed={data['elapsed_seconds']}s"
        )

    # ------------------------------------------------------------- log/report

    @staticmethod
    def _logs(args: list[str] | None = None) -> None:
        print("\n".join(recent_events(30)) or "No activity recorded.")

    def _report(self, args: list[str] | None = None) -> None:
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now()
        path = REPORT_DIR / f"session_report_{stamp.strftime('%Y%m%d_%H%M%S_%f')}.txt"
        lines = [
            "BASH FORCE LAB - SESSION REPORT",
            "=" * 34,
            f"Generated: {stamp.astimezone().isoformat(timespec='seconds')}",
            "",
            "Recent activity:",
            *recent_events(100),
            "",
        ]
        path.write_text("\n".join(lines), encoding="utf-8")
        print(f"Report saved: {path.relative_to(ROOT)}")
        log_event("Session report generated")

    @staticmethod
    def _clear(args: list[str] | None = None) -> None:
        os.system("cls" if os.name == "nt" else "clear")

    @staticmethod
    def _format_duration(seconds: float) -> str:
        if seconds < 60:
            return f"{seconds:.0f}s"
        return f"{seconds / 60:.1f} min"
