import pytest

from backend.virtual_phone.device import VirtualPhone
from backend.virtual_phone.web_app import create_app

BASE_URL = "http://127.0.0.1:8765"


@pytest.fixture
def phone(tmp_path):
    return VirtualPhone(
        tmp_path,
        config={
            "state_file": "phone.json",
            "max_failures": 3,
            "lockout_seconds": 30,
            "pin_length": 4,
        },
        kdf_iterations=1_000,
        event_callback=None,
    )


@pytest.fixture
def client(phone):
    app = create_app(phone, host="127.0.0.1", port=8765)
    app.config.update(TESTING=True)
    return app.test_client()


def test_initial_state(client):
    response = client.get("/api/state", base_url=BASE_URL)
    assert response.status_code == 200
    data = response.get_json()
    assert data["configured"] is False
    assert data["device"] == "BFL-VIRTUAL-01"


def test_setup_pin(client):
    response = client.post(
        "/api/setup-pin",
        json={"pin": "1234", "confirmation": "1234"},
        base_url=BASE_URL,
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["ok"] is True
    assert data["configured"] is True
    assert data["unlocked"] is True


def test_setup_validation(client):
    response = client.post(
        "/api/setup-pin",
        json={"pin": "12", "confirmation": "12"},
        base_url=BASE_URL,
    )
    assert response.status_code == 400
    assert response.get_json()["ok"] is False


def test_unlock_success_and_failure(client):
    client.post(
        "/api/setup-pin",
        json={"pin": "1234", "confirmation": "1234"},
        base_url=BASE_URL,
    )
    client.post("/api/lock", json={}, base_url=BASE_URL)

    wrong = client.post("/api/unlock", json={"pin": "0000"}, base_url=BASE_URL)
    assert wrong.status_code == 401
    assert wrong.get_json()["ok"] is False

    correct = client.post("/api/unlock", json={"pin": "1234"}, base_url=BASE_URL)
    assert correct.status_code == 200
    assert correct.get_json()["unlocked"] is True


def test_lockout_returns_429(client):
    client.post(
        "/api/setup-pin",
        json={"pin": "1234", "confirmation": "1234"},
        base_url=BASE_URL,
    )
    for _ in range(3):
        client.post("/api/unlock", json={"pin": "0000"}, base_url=BASE_URL)

    locked = client.post("/api/unlock", json={"pin": "1234"}, base_url=BASE_URL)
    assert locked.status_code == 429
    assert locked.get_json()["locked"] is True


def test_non_json_body_rejected(client):
    response = client.post(
        "/api/unlock",
        data="pin=1234",
        content_type="application/x-www-form-urlencoded",
        base_url=BASE_URL,
    )
    assert response.status_code == 415


def test_host_header_rejected(client):
    response = client.get(
        "/api/state",
        headers={"Host": "evil.example"},
        base_url=BASE_URL,
    )
    assert response.status_code == 400


def test_security_headers(client):
    response = client.get("/", base_url=BASE_URL)
    assert response.status_code == 200
    assert "default-src 'self'" in response.headers["Content-Security-Policy"]
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert "camera=()" in response.headers["Permissions-Policy"]
    assert response.headers["Cache-Control"] == "no-store"


def test_change_pin(client):
    client.post(
        "/api/setup-pin",
        json={"pin": "1234", "confirmation": "1234"},
        base_url=BASE_URL,
    )

    wrong = client.post(
        "/api/change-pin",
        json={"current": "0000", "pin": "5678", "confirmation": "5678"},
        base_url=BASE_URL,
    )
    assert wrong.status_code == 401

    changed = client.post(
        "/api/change-pin",
        json={"current": "1234", "pin": "5678", "confirmation": "5678"},
        base_url=BASE_URL,
    )
    assert changed.status_code == 200

    assert (
        client.post("/api/unlock", json={"pin": "1234"}, base_url=BASE_URL).status_code
        == 401
    )
    assert (
        client.post("/api/unlock", json={"pin": "5678"}, base_url=BASE_URL).status_code
        == 200
    )


def test_oversized_body_rejected(client):
    response = client.post(
        "/api/unlock",
        json={"pin": "1" * 2_000},
        base_url=BASE_URL,
    )
    assert response.status_code == 413
