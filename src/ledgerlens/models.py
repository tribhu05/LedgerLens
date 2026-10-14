"""
Data models and schemas for LedgerLens.
"""

from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class TaxCategory(str, Enum):
    SOFTWARE_SUBSCRIPTIONS = "Software & Subscriptions"
    OFFICE_EQUIPMENT = "Hardware & Equipment"
    HOSTING_CLOUD = "Cloud & Infrastructure"
    CLIENT_MEALS = "Client Meetings & Meals"
    TRAVEL_TRANSPORT = "Business Travel & Rides"
    EDUCATION_BOOKS = "Professional Development"
    LEGAL_ACCOUNTING = "Legal & Accounting"
    MARKETING_ADVERTISING = "Marketing & Advertising"
    OTHER_BUSINESS = "General Business Expense"
    NON_DEDUCTIBLE = "Personal / Non-Deductible"


class AuditRisk(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ParsedExpenseResult(BaseModel):
    merchant: str = Field(description="Name of the vendor, business, or merchant")
    date: str = Field(description="Date of expense formatted as YYYY-MM-DD")
    amount: float = Field(description="Total monetary expense amount")
    currency: str = Field(default="USD", description="Currency ISO code, e.g. USD, EUR, INR")
    category: TaxCategory = Field(default=TaxCategory.OTHER_BUSINESS, description="Classified tax deduction category")
    description: str = Field(default="", description="Brief business purpose or item summary")
    confidence_score: float = Field(default=0.8, ge=0.0, le=1.0, description="Confidence in classification")
    parsed_by: str = Field(default="deterministic-heuristic", description="Engine used to parse (gemma or heuristic)")


class Expense(BaseModel):
    id: str = Field(description="Unique identifier for the expense")
    merchant: str
    date: str
    amount: float
    currency: str = "USD"
    category: TaxCategory
    description: str = ""
    deductible_percentage: float = Field(default=1.0, ge=0.0, le=1.0)
    deductible_amount: float = 0.0
    confidence_score: float = 0.8
    parsed_by: str = "deterministic-heuristic"
    audit_risk: AuditRisk = AuditRisk.LOW
    audit_flag_reason: Optional[str] = None
    created_at: str


class ParseReceiptRequest(BaseModel):
    raw_text: str = Field(..., description="Raw text from receipt, invoice, email, or bank transaction line")
    force_heuristic: bool = Field(default=False, description="Force deterministic engine instead of calling Gemma")


class CategoryBreakdown(BaseModel):
    category_name: str
    count: int
    gross_total: float
    deductible_total: float
    deductible_percentage: float


class TaxSummary(BaseModel):
    total_expenses_count: int
    total_gross_amount: float
    total_deductible_amount: float
    estimated_tax_savings_25pct: float
    categories: List[CategoryBreakdown]
    audit_risk_alerts: List[str]


class AIHealthStatus(BaseModel):
    status: str
    ollama_running: bool
    model_name: str
    model_available: bool
    latency_ms: Optional[float] = None
    message: str
