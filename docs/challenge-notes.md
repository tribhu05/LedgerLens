# DEV Hacktoberfest 2026 Week 2 Challenge Notes: “Side Hustle”

## Overview

- **Project Name**: LedgerLens
- **Tagline**: Privacy-First Local AI Bookkeeper & Tax Deduction Engine for Freelancers.
- **Challenge Track**: DEV Hacktoberfest 2026 — Week 2: “Side Hustle”
- **Core Thesis**: *AI understands messy financial text. Deterministic tax code calculates write-offs.*

---

## 1. Fulfillment of the "Side Hustle" Challenge Theme

Freelancers, solopreneurs, and independent creators face a severe administrative dilemma:
1. **The Cost of Forgetting**: The average independent contractor misses out on over **$4,000 in legitimate annual tax deductions** because logging and itemizing receipts is painful and tedious.
2. **The Cloud Privacy Trap**: Commercial bookkeeping tools (QuickBooks, Expensify) and cloud AI wrappers require uploading confidential client invoices, customer names, bank statements, and proprietary contracts to third-party cloud servers.
3. **The Micro-SaaS Business Model**: A privacy-first local bookkeeper and deduction tracker is a utility that freelancers, contractors, and agency owners would **readily pay for** (as a one-time utility purchase or license), saving them hundreds of dollars compared to recurring $30-$60/month subscriptions.

**LedgerLens directly solves this problem:**
- Ingests messy receipt photos, email invoices, and raw bank transaction exports.
- Identifies the merchant, date, amount, currency, and business purpose using on-device open-weight AI.
- Applies statutory Schedule C deduction rules (e.g. 50% client meals, 100% software, Section 179 equipment limits).
- Flags IRS audit risks before tax season.

---

## 2. Open-Weight AI Architecture (Google Gemma 2)

LedgerLens champions open-weight, local-first artificial intelligence:

### 1. Why Open Innovation Matters Here
- **Financial Data Sovereignty**: Bank statements and client invoices contain non-disclosure agreement (NDA) protected project names and confidential pricing. Transmitting this data to proprietary closed-source APIs creates unacceptable legal and privacy exposure.
- **Zero Marginal Cost**: Local inference on **Google Gemma 2 (2B)** via Ollama costs $0.00 per token. Solopreneurs can process thousands of historical receipts without paying API rate limits or recurring API bills.
- **Offline Resilience**: Works without an internet connection on airplanes, cafes, and remote workspaces.

### 2. Gemma 2B vs. The Deterministic Tax Solver
- **Gemma's Responsibility**: Fuzzy natural language comprehension. Gemma ingests unstructured text, addresses, line items, and messy receipt formats, mapping them into typed JSON fields (`merchant`, `date`, `amount`, `currency`, `category`, `description`).
- **Deterministic Solver's Responsibility**: Statutory deduction math. **LLMs should never hallucinate financial math.** Pure Python code computes deduction percentages, applies IRS meal rules, calculates 25% tax bracket savings, and evaluates audit risks.

### 3. Honest Offline Fallback
- When Ollama is offline or unavailable, LedgerLens seamlessly falls back to a **zero-dependency regex/keyword heuristic parser**.
- The engine explicitly labels every parsed record with its source (`parsed_by: "gemma2:2b"` or `parsed_by: "deterministic-heuristic"`).

---

## 3. Product Quality & Dual Interface

- **FastAPI REST API**: Comprehensive OpenAPI (`/docs`) swagger documentation, CORS-enabled endpoints, and health monitoring for local dashboard integrations.
- **Interactive Typer & Rich CLI**:
  - `ledgerlens scan <file>`: Terminal progress spinners and colored panels.
  - `ledgerlens list`: Formatted table with deduction totals and audit risk badges.
  - `ledgerlens summary`: Real-time category deduction breakdowns and projected tax savings.
  - `ledgerlens export`: Audit-ready CSV generation.
- **Local-First Persistence**: Data remains strictly on the user's computer inside `~/.ledgerlens/expenses.json`.

---

## 4. Verification & Testing

The project includes an automated test suite across all critical business logic:
- Heuristic regex parsing across multiple receipt formats (Figma, Blue Bottle, Keychron)
- Statutory deduction calculations (meals 50%, software 100%, personal 0%)
- IRS audit risk detection (meals > $75/$150, round large expenses)
- FastAPI endpoint test suite via `TestClient`
- Typer CLI command test suite via `CliRunner`
