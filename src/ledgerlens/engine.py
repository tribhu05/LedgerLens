"""
Hybrid AI Parser Engine for LedgerLens.
Pairs Google Gemma 2 (2B) running locally via Ollama with a robust
deterministic regex/keyword fallback engine. 100% offline and private.
"""

import json
import logging
import re
import time
import uuid
from datetime import datetime
from typing import Optional, Tuple
import httpx

from ledgerlens.models import (
    AIHealthStatus,
    AuditRisk,
    Expense,
    ParsedExpenseResult,
    TaxCategory,
)
from ledgerlens.tax_rules import (
    calculate_deduction,
    classify_by_merchant_or_keywords,
    evaluate_audit_risk,
)

logger = logging.getLogger("ledgerlens.engine")
OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "gemma2:2b"


class HeuristicParser:
    """Zero-dependency deterministic rule/regex parser for receipts and invoices."""

    DATE_PATTERNS = [
        # YYYY-MM-DD or YYYY/MM/DD
        (r"\b(20\d{2})[-/.](0[1-9]|1[0-2])[-/.](0[1-9]|[12]\d|3[01])\b", "%Y-%m-%d"),
        # MM/DD/YYYY or MM-DD-YYYY
        (r"\b(0[1-9]|1[0-2])[-/.](0[1-9]|[12]\d|3[01])[-/.](20\d{2})\b", "%m/%d/%Y"),
        # Month DD, YYYY (e.g. Oct 14, 2026 or October 14, 2026)
        (r"\b([A-Za-z]{3,9})\s+([0-3]?\d),\s+(20\d{2})\b", "%B %d, %Y"),
    ]

    AMOUNT_PATTERNS = [
        # Total: $123.45, Total Amount: $123.45, Subtotal
        r"(?:total|amount|charged|paid|balance due)[\s:]*[$€£]?\s*([0-9]{1,6}\.[0-9]{2})\b",
        # Standard currency prefixed amount: $123.45 or USD 123.45
        r"(?:\$|USD\s*|EUR\s*|GBP\s*)([0-9]{1,6}\.[0-9]{2})\b",
        # Generic decimal amount on a line
        r"\b([0-9]{1,6}\.[0-9]{2})\b",
    ]

    CURRENCY_MAP = {
        "$": "USD",
        "USD": "USD",
        "€": "EUR",
        "EUR": "EUR",
        "£": "GBP",
        "GBP": "GBP",
        "₹": "INR",
        "INR": "INR",
        "CAD": "CAD",
    }

    @classmethod
    def parse(cls, raw_text: str) -> ParsedExpenseResult:
        """Extract structured expense fields using deterministic heuristics."""
        lines = [line.strip() for line in raw_text.strip().splitlines() if line.strip()]
        if not lines:
            return ParsedExpenseResult(
                merchant="Unknown Vendor",
                date=datetime.now().strftime("%Y-%m-%d"),
                amount=0.0,
                currency="USD",
                category=TaxCategory.OTHER_BUSINESS,
                description="Empty receipt text",
                confidence_score=0.1,
                parsed_by="deterministic-heuristic",
            )

        # 1. Extract Amount
        amount = 0.0
        currency = "USD"
        for pattern in cls.AMOUNT_PATTERNS:
            match = re.search(pattern, raw_text, re.IGNORECASE)
            if match:
                try:
                    amount = float(match.group(1))
                    break
                except ValueError:
                    continue

        # Detect currency symbol
        for symbol, curr_code in cls.CURRENCY_MAP.items():
            if symbol in raw_text:
                currency = curr_code
                break

        # 2. Extract Date
        date_str = datetime.now().strftime("%Y-%m-%d")
        for pattern, fmt in cls.DATE_PATTERNS:
            match = re.search(pattern, raw_text)
            if match:
                raw_match = match.group(0)
                try:
                    # Normalize separators
                    if fmt == "%Y-%m-%d":
                        parts = re.split(r"[-/.]", raw_match)
                        date_str = f"{parts[0]}-{int(parts[1]):02d}-{int(parts[2]):02d}"
                        break
                    elif fmt == "%m/%d/%Y":
                        parts = re.split(r"[-/.]", raw_match)
                        date_str = f"{parts[2]}-{int(parts[0]):02d}-{int(parts[1]):02d}"
                        break
                    elif fmt == "%B %d, %Y":
                        parsed_dt = datetime.strptime(raw_match, "%b %d, %Y" if len(match.group(1)) == 3 else "%B %d, %Y")
                        date_str = parsed_dt.strftime("%Y-%m-%d")
                        break
                except Exception:
                    continue

        # 3. Extract Merchant
        # Skip generic receipt or invoice header lines like "INVOICE #FIG-982341" or "TAX INVOICE"
        header_pattern = re.compile(r"^(invoice|order|receipt|tax invoice|payment receipt|official receipt)[\s#:\-0-9a-z]*$", re.IGNORECASE)
        
        merchant = ""
        for line in lines[:4]:
            cleaned = re.sub(r"^(receipt from|invoice from|order from)\s+", "", line, flags=re.IGNORECASE).strip()
            if not header_pattern.match(cleaned) and len(cleaned) > 1:
                merchant = cleaned
                break

        if not merchant and lines:
            merchant = lines[0]
        if not merchant:
            merchant = "Unknown Merchant"

        # 4. Classify Category
        category = classify_by_merchant_or_keywords(merchant, raw_text)

        # 5. Extract brief description
        description = lines[0] if len(lines) == 1 else f"{merchant} - {lines[-1][:60]}"

        confidence = 0.85 if amount > 0 else 0.40

        return ParsedExpenseResult(
            merchant=merchant[:60],
            date=date_str,
            amount=amount,
            currency=currency,
            category=category,
            description=description[:120],
            confidence_score=confidence,
            parsed_by="deterministic-heuristic",
        )


class GemmaOllamaParser:
    """Open-weight LLM parser using Google Gemma 2 (2B) on local Ollama."""

    SYSTEM_PROMPT = """You are an expert tax accountant AI specialized in freelance Schedule C bookkeeping.
Parse the user's receipt, invoice, or transaction text into strictly valid JSON.
Valid category options:
- "Software & Subscriptions"
- "Hardware & Equipment"
- "Cloud & Infrastructure"
- "Client Meetings & Meals"
- "Business Travel & Rides"
- "Professional Development"
- "Legal & Accounting"
- "Marketing & Advertising"
- "General Business Expense"
- "Personal / Non-Deductible"

Return ONLY a JSON object matching this exact schema:
{
  "merchant": "Vendor or company name",
  "date": "YYYY-MM-DD",
  "amount": 12.34,
  "currency": "USD",
  "category": "One of the valid categories above",
  "description": "Brief business purpose"
}
Do not include markdown fences, extra commentary, or apologies. Just JSON."""

    @classmethod
    def parse(cls, raw_text: str, timeout_sec: float = 8.0) -> Optional[ParsedExpenseResult]:
        """Call local Ollama gemma2:2b to extract structured fields."""
        url = f"{OLLAMA_BASE_URL}/api/generate"
        payload = {
            "model": DEFAULT_MODEL,
            "prompt": f"{cls.SYSTEM_PROMPT}\n\nReceipt Text:\n{raw_text}\n\nJSON Output:",
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.1,
                "top_p": 0.9,
            },
        }

        try:
            with httpx.Client(timeout=timeout_sec) as client:
                resp = client.post(url, json=payload)
                if resp.status_code != 200:
                    logger.warning(f"Ollama returned HTTP {resp.status_code}")
                    return None

                data = resp.json()
                raw_response = data.get("response", "").strip()
                if not raw_response:
                    return None

                # Clean possible markdown wrap
                cleaned = re.sub(r"^```json\s*", "", raw_response)
                cleaned = re.sub(r"^```\s*", "", cleaned)
                cleaned = re.sub(r"```$", "", cleaned).strip()

                parsed_json = json.loads(cleaned)

                # Map category safely to TaxCategory enum
                category_str = parsed_json.get("category", "")
                category_match = TaxCategory.OTHER_BUSINESS
                for cat in TaxCategory:
                    if cat.value.lower() == category_str.lower() or cat.name.lower() == category_str.lower():
                        category_match = cat
                        break

                amount = float(parsed_json.get("amount", 0.0))
                date_val = parsed_json.get("date", datetime.now().strftime("%Y-%m-%d"))

                # Validate date format
                if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_val):
                    date_val = datetime.now().strftime("%Y-%m-%d")

                return ParsedExpenseResult(
                    merchant=str(parsed_json.get("merchant", "Vendor"))[:60],
                    date=date_val,
                    amount=amount,
                    currency=str(parsed_json.get("currency", "USD")).upper()[:3],
                    category=category_match,
                    description=str(parsed_json.get("description", ""))[:120],
                    confidence_score=0.95,
                    parsed_by="gemma2:2b",
                )

        except Exception as e:
            logger.info(f"Ollama local inference unavailable ({e}), falling back to heuristic engine.")
            return None


class LedgerEngine:
    """Unified engine that coordinates AI parsing, tax deductions, and audit risk."""

    @classmethod
    def check_health(cls) -> AIHealthStatus:
        """Inspect local Ollama connectivity and verify gemma2:2b availability."""
        t0 = time.time()
        try:
            with httpx.Client(timeout=2.0) as client:
                resp = client.get(f"{OLLAMA_BASE_URL}/api/tags")
                if resp.status_code == 200:
                    models = resp.json().get("models", [])
                    available_names = [m.get("name") for m in models]
                    has_gemma = any(DEFAULT_MODEL in name for name in available_names)
                    latency = round((time.time() - t0) * 1000, 2)
                    return AIHealthStatus(
                        status="ready" if has_gemma else "model_missing",
                        ollama_running=True,
                        model_name=DEFAULT_MODEL,
                        model_available=has_gemma,
                        latency_ms=latency,
                        message=f"Connected to local Ollama. {DEFAULT_MODEL} is active." if has_gemma
                        else f"Ollama running but {DEFAULT_MODEL} not pulled.",
                    )
        except Exception as e:
            pass

        return AIHealthStatus(
            status="offline",
            ollama_running=False,
            model_name=DEFAULT_MODEL,
            model_available=False,
            latency_ms=None,
            message="Ollama offline. Running with 100% functional deterministic heuristic engine.",
        )

    @classmethod
    def parse_text(cls, raw_text: str, force_heuristic: bool = False) -> ParsedExpenseResult:
        """Parse raw receipt or document string, prioritizing Gemma then Heuristic."""
        if not force_heuristic:
            gemma_result = GemmaOllamaParser.parse(raw_text)
            if gemma_result:
                return gemma_result

        return HeuristicParser.parse(raw_text)

    @classmethod
    def create_expense_from_text(cls, raw_text: str, force_heuristic: bool = False) -> Expense:
        """Parse raw receipt text and assemble a fully calculated Expense entity."""
        parsed = cls.parse_text(raw_text, force_heuristic=force_heuristic)
        
        # Calculate tax deductions
        ded_pct, ded_amt = calculate_deduction(parsed.amount, parsed.category)
        
        # Evaluate IRS audit risk
        risk, reason = evaluate_audit_risk(parsed.amount, parsed.category, parsed.description)

        return Expense(
            id=str(uuid.uuid4())[:8],
            merchant=parsed.merchant,
            date=parsed.date,
            amount=parsed.amount,
            currency=parsed.currency,
            category=parsed.category,
            description=parsed.description,
            deductible_percentage=ded_pct,
            deductible_amount=ded_amt,
            confidence_score=parsed.confidence_score,
            parsed_by=parsed.parsed_by,
            audit_risk=risk,
            audit_flag_reason=reason,
            created_at=datetime.now().isoformat(),
        )
