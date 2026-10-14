"""
Local-first persistence for LedgerLens.
Stores expense data in a lightweight JSON store with automatic schema validation.
100% private: no data ever leaves the local device.
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional

from ledgerlens.models import (
    AuditRisk,
    CategoryBreakdown,
    Expense,
    TaxCategory,
    TaxSummary,
)
from ledgerlens.tax_rules import DEDUCTION_RATES

DEFAULT_DATA_DIR = Path.home() / ".ledgerlens"
DEFAULT_DATA_FILE = DEFAULT_DATA_DIR / "expenses.json"


class LedgerStorage:
    """Manages reading, writing, and analytical aggregation of local expenses."""

    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or DEFAULT_DATA_FILE
        self._ensure_storage()

    def _ensure_storage(self) -> None:
        """Create parent directory and empty JSON file if non-existent."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.storage_path.exists():
            self._save_raw([])

    def _load_raw(self) -> List[dict]:
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _save_raw(self, items: List[dict]) -> None:
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(items, f, indent=2)

    def add_expense(self, expense: Expense) -> Expense:
        """Append a new expense and persist to disk."""
        items = self._load_raw()
        # Avoid duplicate IDs
        items = [i for i in items if i.get("id") != expense.id]
        items.append(expense.model_dump())
        self._save_raw(items)
        return expense

    def get_expense(self, expense_id: str) -> Optional[Expense]:
        """Fetch single expense by ID."""
        items = self._load_raw()
        for item in items:
            if item.get("id") == expense_id:
                return Expense(**item)
        return None

    def list_expenses(self, category: Optional[TaxCategory] = None) -> List[Expense]:
        """List all stored expenses, optionally filtered by tax category."""
        items = self._load_raw()
        expenses = [Expense(**item) for item in items]
        if category:
            expenses = [e for e in expenses if e.category == category]
        # Sort newest first
        expenses.sort(key=lambda e: e.date, reverse=True)
        return expenses

    def delete_expense(self, expense_id: str) -> bool:
        """Delete an expense by ID."""
        items = self._load_raw()
        initial_len = len(items)
        items = [i for i in items if i.get("id") != expense_id]
        if len(items) < initial_len:
            self._save_raw(items)
            return True
        return False

    def clear(self) -> None:
        """Clear all stored expenses."""
        self._save_raw([])

    def compute_tax_summary(self) -> TaxSummary:
        """Compute aggregated deductible totals, category breakdowns, and audit alerts."""
        expenses = self.list_expenses()
        total_gross = sum(e.amount for e in expenses)
        total_deductible = sum(e.deductible_amount for e in expenses)
        
        # Self-employment + standard freelance bracket estimated at 25% tax savings
        estimated_tax_savings = round(total_deductible * 0.25, 2)

        # Category aggregates
        by_cat: Dict[TaxCategory, List[Expense]] = {}
        for cat in TaxCategory:
            by_cat[cat] = []
        for e in expenses:
            by_cat[e.category].append(e)

        categories_breakdown: List[CategoryBreakdown] = []
        for cat, exp_list in by_cat.items():
            if exp_list:
                gross = sum(e.amount for e in exp_list)
                ded = sum(e.deductible_amount for e in exp_list)
                rate = DEDUCTION_RATES.get(cat, 1.0)
                categories_breakdown.append(
                    CategoryBreakdown(
                        category_name=cat.value,
                        count=len(exp_list),
                        gross_total=round(gross, 2),
                        deductible_total=round(ded, 2),
                        deductible_percentage=rate,
                    )
                )

        # Audit alerts
        audit_alerts: List[str] = []
        for e in expenses:
            if e.audit_risk in (AuditRisk.MEDIUM, AuditRisk.HIGH) and e.audit_flag_reason:
                audit_alerts.append(f"[{e.audit_risk.value}] {e.merchant} (${e.amount:.2f}): {e.audit_flag_reason}")

        return TaxSummary(
            total_expenses_count=len(expenses),
            total_gross_amount=round(total_gross, 2),
            total_deductible_amount=round(total_deductible, 2),
            estimated_tax_savings_25pct=estimated_tax_savings,
            categories=categories_breakdown,
            audit_risk_alerts=audit_alerts,
        )
