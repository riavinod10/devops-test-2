import pytest

from app.main import Store, create_app

VALID = {"payer": "Alice", "payee": "Bob", "amount": 1500.5, "currency": "inr", "method": "upi"}


@pytest.fixture()
def client():
    app = create_app(Store())
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.get_json()
    assert body["status"] == "ok"
    assert body["service"] == "payment-backend"
    assert body["version"]


def test_ready(client):
    assert client.get("/ready").get_json() == {"status": "ready"}


def test_create_payment_normalises_and_emits_notification(client):
    r = client.post("/api/payments", json=VALID)
    assert r.status_code == 201
    body = r.get_json()
    p = body["payment"]
    assert p["amount"] == "1500.50"
    assert p["currency"] == "INR"
    assert p["method"] == "UPI"
    assert p["status"] == "COMPLETED"
    assert r.headers["Location"] == f"/api/payments/{p['id']}"
    assert body["notification"]["payment_id"] == p["id"]
    assert "Alice" in body["notification"]["message"]

    notes = client.get("/api/notifications").get_json()
    assert notes["count"] == 1


def test_get_and_list_payments(client):
    first = client.post("/api/payments", json=VALID).get_json()["payment"]
    second = client.post("/api/payments", json={**VALID, "payer": "Carol", "amount": "20"}).get_json()["payment"]

    listing = client.get("/api/payments").get_json()
    assert listing["count"] == 2
    assert listing["payments"][0]["id"] == second["id"]  # newest first
    assert "seq" not in listing["payments"][0]

    one = client.get(f"/api/payments/{first['id']}")
    assert one.status_code == 200
    assert one.get_json()["payment"]["payer"] == "Alice"


def test_unknown_payment_404(client):
    r = client.get("/api/payments/does-not-exist")
    assert r.status_code == 404
    assert r.get_json()["error"] == "Payment not found"


def test_stats(client):
    client.post("/api/payments", json=VALID)
    client.post("/api/payments", json={**VALID, "amount": "99.50"})
    client.post("/api/payments", json={**VALID, "currency": "USD", "amount": 10})
    s = client.get("/api/stats").get_json()
    assert s["payment_count"] == 3
    assert s["notification_count"] == 3
    assert s["totals_by_currency"] == {"INR": "1600.00", "USD": "10.00"}


@pytest.mark.parametrize(
    "payload,field",
    [
        ({k: v for k, v in VALID.items() if k != "payer"}, "payer"),
        ({**VALID, "payee": "alice"}, "payee"),
        ({**VALID, "amount": -5}, "amount"),
        ({**VALID, "amount": 0}, "amount"),
        ({**VALID, "amount": "abc"}, "amount"),
        ({**VALID, "amount": True}, "amount"),
        ({**VALID, "amount": "10.999"}, "amount"),
        ({**VALID, "amount": 2000000}, "amount"),
        ({**VALID, "amount": "NaN"}, "amount"),
        ({**VALID, "currency": "XYZ"}, "currency"),
        ({**VALID, "method": "CHEQUE"}, "method"),
        ({**VALID, "payer": "x" * 101}, "payer"),
    ],
)
def test_validation_errors(client, payload, field):
    r = client.post("/api/payments", json=payload)
    assert r.status_code == 422
    assert field in r.get_json()["details"]


def test_non_json_body_rejected(client):
    r = client.post("/api/payments", data="not json", content_type="text/plain")
    assert r.status_code == 400


def test_json_array_body_rejected(client):
    r = client.post("/api/payments", json=[1, 2, 3])
    assert r.status_code == 422


def test_oversized_body_rejected(client):
    r = client.post("/api/payments", data="x" * (17 * 1024), content_type="application/json")
    assert r.status_code == 413


def test_unknown_route_and_method(client):
    assert client.get("/nope").status_code == 404
    assert client.delete("/api/payments").status_code == 405
