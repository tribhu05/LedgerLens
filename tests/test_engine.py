"""
Tests for receipt parsing engine (heuristic and unified engine).
"""

from pathlib import Path
from ledgerlens.engine import HeuristicParser, LedgerEngine
from ledgerlens.models import TaxCategory


def test_heuristic_parser_figma():
    sample = """INVOICE #FIG-982341
Figma, Inc.
Date: 2026-10-05
Amount: $15.00 USD
Total: $15.00"""
    res = HeuristicParser.parse(sample)
    assert "Figma" in res.merchant
    assert res.amount == 15.00
    assert res.currency == "USD"
    assert res.date == "2026-10-05"
    assert res.category == TaxCategory.SOFTWARE_SUBSCRIPTIONS


def test_heuristic_parser_coffee_meal():
    sample = """Blue Bottle Coffee
115 Sansome St
Date: 10/12/2026
1x Oat Milk Cortado $6.50
Total Paid: $35.42"""
    res = HeuristicParser.parse(sample)
    assert "Blue Bottle" in res.merchant
    assert res.amount == 35.42
    assert res.date == "2026-10-12"
    assert res.category == TaxCategory.CLIENT_MEALS


def test_heuristic_parser_month_name_date():
    sample = """Keychron Official Store
Date: October 08, 2026
Total: $214.00 USD"""
    res = HeuristicParser.parse(sample)
    assert res.amount == 214.00
    assert res.date == "2026-10-08"
    assert res.category == TaxCategory.OFFICE_EQUIPMENT


def test_create_expense_from_text():
    sample = "GitHub Inc. subscription charge of $10.00 on 2026-10-01"
    exp = LedgerEngine.create_expense_from_text(sample, force_heuristic=True)
    assert exp.amount == 10.00
    assert exp.category == TaxCategory.SOFTWARE_SUBSCRIPTIONS
    assert exp.deductible_percentage == 1.0
    assert exp.deductible_amount == 10.00
    assert exp.parsed_by == "deterministic-heuristic"


def test_check_health():
    health = LedgerEngine.check_health()
    assert health.model_name == "gemma2:2b"
    assert health.status in ("ready", "model_missing", "offline")
