"""
Tests for local-first storage and tax aggregation.
"""

from pathlib import Path
from ledgerlens.models import AuditRisk, Expense, TaxCategory
from ledgerlens.storage import LedgerStorage


def test_storage_lifecycle(tmp_path: Path):
    db_file = tmp_path / "test_expenses.json"
    store = LedgerStorage(storage_path=db_file)

    exp1 = Expense(
        id="exp-1",
        merchant="Vercel",
        date="2026-10-01",
        amount=20.00,
        currency="USD",
        category=TaxCategory.HOSTING_CLOUD,
        description="Hosting",
        deductible_percentage=1.0,
        deductible_amount=20.00,
        confidence_score=0.9,
        parsed_by="test",
        audit_risk=AuditRisk.LOW,
        created_at="2026-10-01T10:00:00",
    )

    exp2 = Expense(
        id="exp-2",
        merchant="Starbucks",
        date="2026-10-02",
        amount=50.00,
        currency="USD",
        category=TaxCategory.CLIENT_MEALS,
        description="Client meeting",
        deductible_percentage=0.5,
        deductible_amount=25.00,
        confidence_score=0.8,
        parsed_by="test",
        audit_risk=AuditRisk.LOW,
        created_at="2026-10-02T10:00:00",
    )

    store.add_expense(exp1)
    store.add_expense(exp2)

    all_exp = store.list_expenses()
    assert len(all_exp) == 2

    # Filter by category
    cloud_exp = store.list_expenses(category=TaxCategory.HOSTING_CLOUD)
    assert len(cloud_exp) == 1
    assert cloud_exp[0].merchant == "Vercel"

    # Compute summary
    summary = store.compute_tax_summary()
    assert summary.total_expenses_count == 2
    assert summary.total_gross_amount == 70.00
    assert summary.total_deductible_amount == 45.00
    assert summary.estimated_tax_savings_25pct == round(45.00 * 0.25, 2)

    # Delete
    deleted = store.delete_expense("exp-1")
    assert deleted is True
    assert len(store.list_expenses()) == 1

    # Clear
    store.clear()
    assert len(store.list_expenses()) == 0
