"""
FastAPI REST API application for LedgerLens.
Provides endpoints for receipt parsing, expense management, and real-time tax summaries.
"""

from typing import List, Optional
from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware

from ledgerlens.engine import LedgerEngine
from ledgerlens.models import (
    AIHealthStatus,
    Expense,
    ParseReceiptRequest,
    ParsedExpenseResult,
    TaxCategory,
    TaxSummary,
)
from ledgerlens.storage import LedgerStorage

app = FastAPI(
    title="LedgerLens API",
    description="Privacy-First Local AI Bookkeeper & Tax Deduction Engine for Freelancers",
    version="1.0.0",
)

# Enable CORS for local development and dashboards
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

storage = LedgerStorage()


@app.get("/", tags=["General"])
def root():
    """Service metadata and quick health summary."""
    health = LedgerEngine.check_health()
    return {
        "service": "LedgerLens",
        "tagline": "Privacy-First Local AI Bookkeeper for Freelancers",
        "version": "1.0.0",
        "ai_engine": health.model_name if health.ollama_running else "deterministic-heuristic",
        "docs_url": "/docs",
    }


@app.get("/api/health", response_model=AIHealthStatus, tags=["System"])
def get_ai_health():
    """Inspect local Ollama connectivity and Gemma 2B availability."""
    return LedgerEngine.check_health()


@app.post("/api/expenses/parse", response_model=ParsedExpenseResult, tags=["Parsing"])
def parse_receipt_text(payload: ParseReceiptRequest):
    """Parse raw receipt, invoice, or bank statement line into structured expense data."""
    if not payload.raw_text.strip():
        raise HTTPException(status_code=400, detail="Receipt text cannot be empty.")
    return LedgerEngine.parse_text(payload.raw_text, force_heuristic=payload.force_heuristic)


@app.post("/api/expenses/scan", response_model=Expense, status_code=status.HTTP_201_CREATED, tags=["Expenses"])
def scan_and_save_expense(payload: ParseReceiptRequest):
    """Parse raw receipt text, compute statutory tax deductions, and persist to local database."""
    if not payload.raw_text.strip():
        raise HTTPException(status_code=400, detail="Receipt text cannot be empty.")
    expense = LedgerEngine.create_expense_from_text(payload.raw_text, force_heuristic=payload.force_heuristic)
    return storage.add_expense(expense)


@app.get("/api/expenses", response_model=List[Expense], tags=["Expenses"])
def list_expenses(category: Optional[TaxCategory] = Query(None, description="Filter by tax category")):
    """List all recorded business expenses."""
    return storage.list_expenses(category=category)


@app.get("/api/expenses/{expense_id}", response_model=Expense, tags=["Expenses"])
def get_expense(expense_id: str):
    """Retrieve an expense by ID."""
    expense = storage.get_expense(expense_id)
    if not expense:
        raise HTTPException(status_code=404, detail=f"Expense with ID '{expense_id}' not found.")
    return expense


@app.delete("/api/expenses/{expense_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Expenses"])
def delete_expense(expense_id: str):
    """Delete an expense by ID."""
    deleted = storage.delete_expense(expense_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Expense with ID '{expense_id}' not found.")
    return None


@app.get("/api/tax-summary", response_model=TaxSummary, tags=["Tax Intelligence"])
def get_tax_summary():
    """Generate aggregated tax deduction report, category breakdown, and IRS audit flags."""
    return storage.compute_tax_summary()
