"""
Deterministic tax rules and deduction calculations for freelancers and solopreneurs.
Adheres to standard self-employment deduction rules (IRS Schedule C guidelines).
"""

from typing import Dict, List, Optional, Tuple
from ledgerlens.models import AuditRisk, TaxCategory

# Standard deduction percentages by business expense category
DEDUCTION_RATES: Dict[TaxCategory, float] = {
    TaxCategory.SOFTWARE_SUBSCRIPTIONS: 1.00,  # 100% deductible
    TaxCategory.OFFICE_EQUIPMENT: 1.00,        # 100% deductible (Section 179 / De Minimis Safe Harbor)
    TaxCategory.HOSTING_CLOUD: 1.00,           # 100% deductible
    TaxCategory.CLIENT_MEALS: 0.50,            # 50% deductible under standard business meal rules
    TaxCategory.TRAVEL_TRANSPORT: 1.00,        # 100% deductible for legitimate business travel
    TaxCategory.EDUCATION_BOOKS: 1.00,         # 100% deductible for skills directly related to trade
    TaxCategory.LEGAL_ACCOUNTING: 1.00,        # 100% deductible
    TaxCategory.MARKETING_ADVERTISING: 1.00,   # 100% deductible
    TaxCategory.OTHER_BUSINESS: 1.00,          # 100% deductible
    TaxCategory.NON_DEDUCTIBLE: 0.00,          # 0% deductible (personal expenses)
}

# Known merchant dictionary mapping normalized merchant names to their primary category
KNOWN_MERCHANT_MAP: Dict[str, TaxCategory] = {
    "github": TaxCategory.SOFTWARE_SUBSCRIPTIONS,
    "figma": TaxCategory.SOFTWARE_SUBSCRIPTIONS,
    "jetbrains": TaxCategory.SOFTWARE_SUBSCRIPTIONS,
    "notion": TaxCategory.SOFTWARE_SUBSCRIPTIONS,
    "slack": TaxCategory.SOFTWARE_SUBSCRIPTIONS,
    "zoom": TaxCategory.SOFTWARE_SUBSCRIPTIONS,
    "openai": TaxCategory.SOFTWARE_SUBSCRIPTIONS,
    "anthropic": TaxCategory.SOFTWARE_SUBSCRIPTIONS,
    "cursor": TaxCategory.SOFTWARE_SUBSCRIPTIONS,
    "adobe": TaxCategory.SOFTWARE_SUBSCRIPTIONS,
    "canva": TaxCategory.SOFTWARE_SUBSCRIPTIONS,
    "1password": TaxCategory.SOFTWARE_SUBSCRIPTIONS,
    "linear": TaxCategory.SOFTWARE_SUBSCRIPTIONS,
    "atlassian": TaxCategory.SOFTWARE_SUBSCRIPTIONS,
    
    "aws": TaxCategory.HOSTING_CLOUD,
    "amazon web services": TaxCategory.HOSTING_CLOUD,
    "google cloud": TaxCategory.HOSTING_CLOUD,
    "gcp": TaxCategory.HOSTING_CLOUD,
    "vercel": TaxCategory.HOSTING_CLOUD,
    "netlify": TaxCategory.HOSTING_CLOUD,
    "digitalocean": TaxCategory.HOSTING_CLOUD,
    "render": TaxCategory.HOSTING_CLOUD,
    "cloudflare": TaxCategory.HOSTING_CLOUD,
    "heroku": TaxCategory.HOSTING_CLOUD,
    "mongodb atlas": TaxCategory.HOSTING_CLOUD,
    "supabase": TaxCategory.HOSTING_CLOUD,
    "railway": TaxCategory.HOSTING_CLOUD,
    
    "apple": TaxCategory.OFFICE_EQUIPMENT,
    "best buy": TaxCategory.OFFICE_EQUIPMENT,
    "logitech": TaxCategory.OFFICE_EQUIPMENT,
    "keychron": TaxCategory.OFFICE_EQUIPMENT,
    "dell": TaxCategory.OFFICE_EQUIPMENT,
    "lenovo": TaxCategory.OFFICE_EQUIPMENT,
    "micro center": TaxCategory.OFFICE_EQUIPMENT,
    
    "uber": TaxCategory.TRAVEL_TRANSPORT,
    "lyft": TaxCategory.TRAVEL_TRANSPORT,
    "delta": TaxCategory.TRAVEL_TRANSPORT,
    "united airlines": TaxCategory.TRAVEL_TRANSPORT,
    "airbnb": TaxCategory.TRAVEL_TRANSPORT,
    "amtrak": TaxCategory.TRAVEL_TRANSPORT,
    
    "starbucks": TaxCategory.CLIENT_MEALS,
    "blue bottle": TaxCategory.CLIENT_MEALS,
    "dunkin": TaxCategory.CLIENT_MEALS,
    "sweetgreen": TaxCategory.CLIENT_MEALS,
    "chipotle": TaxCategory.CLIENT_MEALS,
    "doordash": TaxCategory.CLIENT_MEALS,
    
    "udemy": TaxCategory.EDUCATION_BOOKS,
    "coursera": TaxCategory.EDUCATION_BOOKS,
    "oreilly": TaxCategory.EDUCATION_BOOKS,
    "pragmatic bookshelf": TaxCategory.EDUCATION_BOOKS,
    "frontend masters": TaxCategory.EDUCATION_BOOKS,
}

# Keyword rules for heuristic categorization
CATEGORY_KEYWORDS: List[Tuple[TaxCategory, List[str]]] = [
    (TaxCategory.HOSTING_CLOUD, ["cloud", "hosting", "server", "domain", "dns", "bandwidth", "vps", "compute", "database", "cluster"]),
    (TaxCategory.SOFTWARE_SUBSCRIPTIONS, ["subscription", "saas", "license", "monthly plan", "annual plan", "software", "api credits", "pro plan", "team plan"]),
    (TaxCategory.OFFICE_EQUIPMENT, ["keyboard", "monitor", "mouse", "laptop", "macbook", "headset", "webcam", "desk", "chair", "charger", "cable", "adapter", "hard drive", "ssd"]),
    (TaxCategory.CLIENT_MEALS, ["coffee", "cafe", "restaurant", "lunch", "dinner", "breakfast", "catering", "bistro", "bakery", "diner"]),
    (TaxCategory.TRAVEL_TRANSPORT, ["ride", "taxi", "flight", "airline", "hotel", "lodging", "train", "parking", "transit", "metro"]),
    (TaxCategory.EDUCATION_BOOKS, ["course", "tutorial", "workshop", "conference", "book", "ebook", "bootcamp", "training"]),
    (TaxCategory.LEGAL_ACCOUNTING, ["incorporation", "tax filing", "cpa", "attorney", "legal", "notary", "trademark", "accounting fee"]),
    (TaxCategory.MARKETING_ADVERTISING, ["ads", "advertising", "sponsorship", "billboard", "newsletter sponsor", "meta ads", "google ads", "flyer", "promoted"]),
]


def get_deduction_rate(category: TaxCategory) -> float:
    """Return the statutory deduction rate for a given tax category."""
    return DEDUCTION_RATES.get(category, 1.00)


def calculate_deduction(amount: float, category: TaxCategory) -> Tuple[float, float]:
    """Calculate deductible percentage and monetary deduction amount."""
    rate = get_deduction_rate(category)
    deductible_amount = round(amount * rate, 2)
    return rate, deductible_amount


def classify_by_merchant_or_keywords(merchant: str, text: str) -> TaxCategory:
    """Classify an expense category using deterministic merchant matches and keywords."""
    clean_merchant = merchant.strip().lower()
    
    # 1. Exact or substring match in known merchants
    for known_name, category in KNOWN_MERCHANT_MAP.items():
        if known_name in clean_merchant:
            return category

    # 2. Keyword scanning in combined text
    combined = f"{merchant} {text}".lower()
    for category, keywords in CATEGORY_KEYWORDS:
        if any(kw in combined for kw in keywords):
            return category

    return TaxCategory.OTHER_BUSINESS


def evaluate_audit_risk(amount: float, category: TaxCategory, description: str) -> Tuple[AuditRisk, Optional[str]]:
    """
    Evaluate tax audit risk based on IRS red flag patterns:
    - High-value meals (> $100) requires documented client business purpose.
    - Suspicious round numbers ($500, $1000) without itemized receipts.
    - Large generic expenses without descriptions.
    """
    if category == TaxCategory.NON_DEDUCTIBLE:
        return AuditRisk.HIGH, "Personal or non-deductible expense flagged."

    if category == TaxCategory.CLIENT_MEALS and amount > 150.0:
        return AuditRisk.HIGH, "Client meals over $150 require documented attendee names and explicit business agenda."

    if category == TaxCategory.CLIENT_MEALS and amount > 75.0:
        return AuditRisk.MEDIUM, "Meals over $75 require itemized receipts under IRS regulations."

    if amount >= 500.0 and amount % 50 == 0 and len(description.strip()) < 10:
        return AuditRisk.MEDIUM, "Round-dollar large expense ($500+) lacks itemized description."

    if amount > 2500.0 and category == TaxCategory.OFFICE_EQUIPMENT:
        return AuditRisk.MEDIUM, "Equipment over $2,500 exceeds De Minimis safe harbor threshold and may require Section 179 depreciation."

    return AuditRisk.LOW, None
