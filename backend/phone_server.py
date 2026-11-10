"""Lifecycle helper for the local virtual-phone web server."""

from __future__ import annotations

import threading

from werkzeug.serving import make_server

from backend.virtual_phone.device import VirtualPhone
from backend.virtual_phone.web_app import create_app


class PhoneServer:
    def __init__(self, phone: VirtualPhone, host: str, port: int) -> None:
        if host not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("The virtual phone server may only bind to loopback.")
        self.phone = phone
        self.host = host
        self.port = port
        self._server = None
        self._thread: threading.Thread | None = None

    @property
    def url(self) -> str:
        display_host = f"[{self.host}]" if ":" in self.host else self.host
        return f"http://{display_host}:{self.port}"

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> str:
        if self.is_running:
            return self.url
        app = create_app(self.phone, host=self.host, port=self.port)
        self._server = make_server(self.host, self.port, app, threaded=True)
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="bfl-phone-server",
            daemon=True,
        )
        self._thread.start()
        return self.url

    def stop(self) -> None:
        try:
            if self._server is not None:
                self._server.shutdown()
            if self._thread is not None:
                self._thread.join(timeout=3)
        finally:
            self._server = None
            self._thread = None
