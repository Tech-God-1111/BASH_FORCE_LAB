"""Virtual phone container."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from backend.hash_engine import ITERATIONS
from backend.virtual_phone.authentication import PhoneAuthentication


class VirtualPhone:
    def __init__(
        self,
        root: Path,
        *,
        config: dict | None = None,
        kdf_iterations: int = ITERATIONS,
        event_callback: Callable[[str], None] | None = None,
    ) -> None:
        settings = config or {}
        self.root = Path(root).resolve()
        state_file = settings.get("state_file", "data/virtual_phone.json")
        state_path = (self.root / str(state_file)).resolve()
        if not state_path.is_relative_to(self.root):
            raise ValueError("The virtual phone state file must stay inside the project.")

        self.auth = PhoneAuthentication(
            state_path,
            max_failures=int(settings.get("max_failures", 5)),
            lockout_seconds=int(settings.get("lockout_seconds", 30)),
            pin_length=int(settings.get("pin_length", 4)),
            iterations=kdf_iterations,
            event_callback=event_callback,
        )

    @property
    def state_path(self) -> Path:
        return self.auth.path

    def status(self) -> dict:
        return self.auth.state()
