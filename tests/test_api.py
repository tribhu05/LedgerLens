"""
Integration tests for LedgerLens FastAPI endpoints.
"""

from fastapi.testclient import TestClient
from ledgerlens.api import app, storage


client = TestClient(app)


def setup_function():
    storage.clear()


def teardown_function():
    storage.clear()


def test_root_endpoint():
    resp = client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["service"] == "LedgerLens"


def test_health_endpoint():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data


def test_parse_endpoint():
    payload = {
        "raw_text": "GitHub Inc. - $21.00 USD on 2026-10-01 for Team Plan",
        "force_heuristic": True,
    }
    resp = client.post("/api/expenses/parse", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["amount"] == 21.00
    assert "GitHub" in data["merchant"]


def test_scan_and_save_endpoint():
    payload = {
        "raw_text": "Blue Bottle Coffee - $14.50 on 2026-10-02 Client discussion",
        "force_heuristic": True,
    }
    resp = client.post("/api/expenses/scan", json=payload)
    assert resp.status_code == 201
    expense = resp.json()
    assert expense["amount"] == 14.50
    assert expense["category"] == "Client Meetings & Meals"
    assert expense["deductible_amount"] == 7.25  # 50%

    # Verify listing
    list_resp = client.get("/api/expenses")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

    # Verify tax summary
    tax_resp = client.get("/api/tax-summary")
    assert tax_resp.status_code == 200
    summary = tax_resp.json()
    assert summary["total_expenses_count"] == 1
    assert summary["total_gross_amount"] == 14.50
    assert summary["total_deductible_amount"] == 7.25
