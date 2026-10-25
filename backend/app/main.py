"""Enterprise Payment & Notification Engine - backend API.

Endpoints
---------
GET  /health                  liveness + version info
GET  /ready                   readiness probe
GET  /api/payments            list payments (newest first)
POST /api/payments            create a payment (also emits a notification)
GET  /api/payments/<id>       fetch one payment
GET  /api/notifications       list notifications (newest first)
GET  /api/stats               totals per currency

Storage is in-memory (per process). Run with a single gunicorn worker so all
requests share one store. Persistence is out of scope for this capstone.
"""
import logging
import os
import threading
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from flask import Flask, jsonify, request

APP_VERSION = os.getenv("APP_VERSION", "1.0.0")
APP_ENV = os.getenv("APP_ENV", "local")
SERVICE_NAME = "payment-backend"

SUPPORTED_CURRENCIES = {"INR", "USD", "EUR", "GBP"}
SUPPORTED_METHODS = {"CARD", "UPI", "NETBANKING", "WALLET"}
MAX_AMOUNT = Decimal("1000000.00")
MAX_NAME_LEN = 100
MAX_BODY_BYTES = 16 * 1024

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger(SERVICE_NAME)


def _now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    """Thread-safe in-memory store for payments and notifications."""

    def __init__(self):
        self._lock = threading.Lock()
        self._payments = {}
        self._notifications = []
        self._seq = 0

    def add(self, payment, notification):
        with self._lock:
            self._payments[payment["id"]] = payment
            self._notifications.append(notification)

    def get_payment(self, payment_id):
        with self._lock:
            return self._payments.get(payment_id)

    def list_payments(self):
        with self._lock:
            return sorted(self._payments.values(), key=lambda p: p["seq"], reverse=True)

    def list_notifications(self):
        with self._lock:
            return sorted(self._notifications, key=lambda n: n["seq"], reverse=True)

    def next_seq(self):
        with self._lock:
            self._seq += 1
            return self._seq


def _clean_name(data, field, errors):
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        errors[field] = "is required and must be a non-empty string"
        return None
    value = value.strip()
    if len(value) > MAX_NAME_LEN:
        errors[field] = f"must be at most {MAX_NAME_LEN} characters"
        return None
    return value


def validate_payment(data):
    """Return (clean_payload, errors). errors is empty when valid."""
    errors = {}
    if not isinstance(data, dict):
        return None, {"body": "must be a JSON object"}

    payer = _clean_name(data, "payer", errors)
    payee = _clean_name(data, "payee", errors)
    if payer and payee and payer.lower() == payee.lower():
        errors["payee"] = "must be different from payer"

    amount = None
    raw_amount = data.get("amount")
    if isinstance(raw_amount, bool) or raw_amount is None:
        errors["amount"] = "is required and must be a number"
    else:
        try:
            amount = Decimal(str(raw_amount))
            if not amount.is_finite():
                raise InvalidOperation
            if amount <= 0:
                errors["amount"] = "must be greater than 0"
            elif amount > MAX_AMOUNT:
                errors["amount"] = f"must not exceed {MAX_AMOUNT}"
            elif amount.as_tuple().exponent < -2:
                errors["amount"] = "must have at most 2 decimal places"
        except (InvalidOperation, ValueError):
            errors["amount"] = "must be a valid number"

    currency = data.get("currency")
    if not isinstance(currency, str) or currency.strip().upper() not in SUPPORTED_CURRENCIES:
        errors["currency"] = f"must be one of {sorted(SUPPORTED_CURRENCIES)}"
    else:
        currency = currency.strip().upper()

    method = data.get("method")
    if not isinstance(method, str) or method.strip().upper() not in SUPPORTED_METHODS:
        errors["method"] = f"must be one of {sorted(SUPPORTED_METHODS)}"
    else:
        method = method.strip().upper()

    if errors:
        return None, errors
    return {
        "payer": payer,
        "payee": payee,
        "amount": amount.quantize(Decimal("0.01")),
        "currency": currency,
        "method": method,
    }, {}


def create_app(store=None):
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_BODY_BYTES
    app.config["JSON_SORT_KEYS"] = False
    store = store or Store()
    app.extensions["payment_store"] = store

    @app.get("/health")
    def health():
        return jsonify(status="ok", service=SERVICE_NAME, version=APP_VERSION, environment=APP_ENV)

    @app.get("/ready")
    def ready():
        return jsonify(status="ready")

    @app.get("/api/payments")
    def list_payments():
        payments = store.list_payments()
        return jsonify(count=len(payments), payments=[_public(p) for p in payments])

    @app.post("/api/payments")
    def create_payment():
        data = request.get_json(silent=True)
        if data is None:
            return jsonify(error="Request body must be valid JSON with Content-Type application/json"), 400
        clean, errors = validate_payment(data)
        if errors:
            return jsonify(error="Validation failed", details=errors), 422

        seq = store.next_seq()
        created = _now_iso()
        payment = {
            "id": str(uuid.uuid4()),
            "seq": seq,
            "payer": clean["payer"],
            "payee": clean["payee"],
            "amount": str(clean["amount"]),
            "currency": clean["currency"],
            "method": clean["method"],
            "status": "COMPLETED",
            "created_at": created,
        }
        notification = {
            "id": str(uuid.uuid4()),
            "seq": seq,
            "payment_id": payment["id"],
            "channel": "IN_APP",
            "recipient": clean["payee"],
            "message": (
                f"Payment of {payment['currency']} {payment['amount']} from "
                f"{payment['payer']} to {payment['payee']} completed via {payment['method']}."
            ),
            "created_at": created,
        }
        store.add(payment, notification)
        log.info("payment created id=%s amount=%s %s", payment["id"], payment["amount"], payment["currency"])
        response = jsonify(payment=_public(payment), notification=_public(notification))
        response.status_code = 201
        response.headers["Location"] = f"/api/payments/{payment['id']}"
        return response

    @app.get("/api/payments/<payment_id>")
    def get_payment(payment_id):
        payment = store.get_payment(payment_id)
        if payment is None:
            return jsonify(error="Payment not found"), 404
        return jsonify(payment=_public(payment))

    @app.get("/api/notifications")
    def list_notifications():
        notes = store.list_notifications()
        return jsonify(count=len(notes), notifications=[_public(n) for n in notes])

    @app.get("/api/stats")
    def stats():
        totals = {}
        for p in store.list_payments():
            totals[p["currency"]] = totals.get(p["currency"], Decimal("0")) + Decimal(p["amount"])
        return jsonify(
            payment_count=len(store.list_payments()),
            notification_count=len(store.list_notifications()),
            totals_by_currency={k: str(v) for k, v in sorted(totals.items())},
        )

    @app.errorhandler(404)
    def not_found(_err):
        return jsonify(error="Not found"), 404

    @app.errorhandler(405)
    def method_not_allowed(_err):
        return jsonify(error="Method not allowed"), 405

    @app.errorhandler(413)
    def too_large(_err):
        return jsonify(error=f"Request body exceeds {MAX_BODY_BYTES} bytes"), 413

    @app.errorhandler(500)
    def server_error(_err):
        log.exception("unhandled error")
        return jsonify(error="Internal server error"), 500

    return app


def _public(record):
    return {k: v for k, v in record.items() if k != "seq"}


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
