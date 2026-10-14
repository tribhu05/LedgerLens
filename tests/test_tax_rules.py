"""
Unit tests for tax rules, statutory deductions, and IRS audit risk flags.
"""

from ledgerlens.models import AuditRisk, TaxCategory
from ledgerlens.tax_rules import (
    calculate_deduction,
    classify_by_merchant_or_keywords,
    evaluate_audit_risk,
    get_deduction_rate,
)


def test_deduction_rates():
    assert get_deduction_rate(TaxCategory.SOFTWARE_SUBSCRIPTIONS) == 1.0
    assert get_deduction_rate(TaxCategory.HOSTING_CLOUD) == 1.0
    assert get_deduction_rate(TaxCategory.CLIENT_MEALS) == 0.50
    assert get_deduction_rate(TaxCategory.NON_DEDUCTIBLE) == 0.0


def test_calculate_deduction_meals():
    rate, amt = calculate_deduction(100.0, TaxCategory.CLIENT_MEALS)
    assert rate == 0.50
    assert amt == 50.0


def test_calculate_deduction_software():
    rate, amt = calculate_deduction(29.99, TaxCategory.SOFTWARE_SUBSCRIPTIONS)
    assert rate == 1.00
    assert amt == 29.99


def test_classify_known_merchants():
    assert classify_by_merchant_or_keywords("GitHub Inc.", "") == TaxCategory.SOFTWARE_SUBSCRIPTIONS
    assert classify_by_merchant_or_keywords("Amazon Web Services", "") == TaxCategory.HOSTING_CLOUD
    assert classify_by_merchant_or_keywords("Keychron", "") == TaxCategory.OFFICE_EQUIPMENT
    assert classify_by_merchant_or_keywords("Starbucks Coffee", "") == TaxCategory.CLIENT_MEALS
    assert classify_by_merchant_or_keywords("Uber BV", "") == TaxCategory.TRAVEL_TRANSPORT


def test_classify_by_keywords():
    assert classify_by_merchant_or_keywords("Random Vendor", "Monthly cloud server hosting") == TaxCategory.HOSTING_CLOUD
    assert classify_by_merchant_or_keywords("Local Shop", "Ergonomic mechanical keyboard for desk") == TaxCategory.OFFICE_EQUIPMENT
    assert classify_by_merchant_or_keywords("Unregistered Seller", "Nothing specific") == TaxCategory.OTHER_BUSINESS


def test_evaluate_audit_risk_normal():
    risk, reason = evaluate_audit_risk(15.00, TaxCategory.SOFTWARE_SUBSCRIPTIONS, "Figma monthly")
    assert risk == AuditRisk.LOW
    assert reason is None


def test_evaluate_audit_risk_high_meal():
    risk, reason = evaluate_audit_risk(180.00, TaxCategory.CLIENT_MEALS, "Dinner with client")
    assert risk == AuditRisk.HIGH
    assert "over $150" in reason


def test_evaluate_audit_risk_medium_meal():
    risk, reason = evaluate_audit_risk(85.00, TaxCategory.CLIENT_MEALS, "Lunch")
    assert risk == AuditRisk.MEDIUM
    assert "over $75" in reason


def test_evaluate_audit_risk_large_round_number():
    risk, reason = evaluate_audit_risk(1000.00, TaxCategory.OTHER_BUSINESS, "Misc")
    assert risk == AuditRisk.MEDIUM
    assert "Round-dollar" in reason
