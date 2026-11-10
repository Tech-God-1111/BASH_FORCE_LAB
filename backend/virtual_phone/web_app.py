"""Local-only Flask application for the virtual phone."""

from __future__ import annotations

from flask import Flask, jsonify, request, send_from_directory

from backend.paths import FRONTEND_DIR
from backend.virtual_phone.device import VirtualPhone


def _allowed_hosts(host: str, port: int) -> set[str]:
    hosts = {host, "127.0.0.1", "localhost"}
    for name in list(hosts):
        hosts.add(f"{name}:{port}")
    if ":" in host:
        hosts.add(f"[{host}]:{port}")
    return hosts


def create_app(phone: VirtualPhone, *, host: str = "127.0.0.1", port: int = 8765) -> Flask:
    app = Flask(__name__, static_folder=None)
    app.config["MAX_CONTENT_LENGTH"] = 1024
    allowed_hosts = _allowed_hosts(host, port)

    @app.before_request
    def guard_request():
        if request.host not in allowed_hosts:
            return jsonify({"ok": False, "message": "Unexpected Host header."}), 400
        if (
            request.path.startswith("/api/")
            and request.method == "POST"
            and not request.is_json
        ):
            return (
                jsonify(
                    {"ok": False, "message": "Content-Type must be application/json."}
                ),
                415,
            )
        return None

    @app.after_request
    def security_headers(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=()"
        )
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; base-uri 'none'; "
            "form-action 'self'; frame-ancestors 'none'"
        )
        return response

    def payload(ok: bool, message: str) -> dict:
        return {"ok": ok, "message": message, **phone.status()}

    def failure_status(message: str, default: int = 400) -> int:
        if phone.status()["locked"]:
            return 429
        if "incorrect" in message.lower():
            return 401
        return default

    @app.get("/")
    def index():
        return send_from_directory(FRONTEND_DIR, "index.html")

    @app.get("/assets/<path:filename>")
    def assets(filename: str):
        return send_from_directory(FRONTEND_DIR / "assets", filename)

    @app.get("/api/state")
    def state():
        return jsonify(phone.status())

    @app.post("/api/setup-pin")
    def setup_pin():
        body = request.get_json(silent=True) or {}
        ok, message = phone.auth.setup_pin(
            body.get("pin", ""), body.get("confirmation", "")
        )
        return jsonify(payload(ok, message)), (200 if ok else 400)

    @app.post("/api/unlock")
    def unlock():
        body = request.get_json(silent=True) or {}
        ok, message = phone.auth.authenticate(body.get("pin", ""))
        status = 200 if ok else failure_status(message, default=401)
        return jsonify(payload(ok, message)), status

    @app.post("/api/lock")
    def lock():
        ok, message = phone.auth.lock()
        return jsonify(payload(ok, message)), (200 if ok else 400)

    @app.post("/api/change-pin")
    def change_pin():
        body = request.get_json(silent=True) or {}
        ok, message = phone.auth.change_pin(
            body.get("current", ""),
            body.get("pin", ""),
            body.get("confirmation", ""),
        )
        status = 200 if ok else failure_status(message)
        return jsonify(payload(ok, message)), status

    return app
