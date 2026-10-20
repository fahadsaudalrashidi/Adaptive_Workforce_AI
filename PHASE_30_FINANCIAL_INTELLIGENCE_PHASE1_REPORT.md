# Phase 30 — Financial Intelligence Phase 1 (Business Intelligence Suite, Module 1)

Financial Intelligence is the first module of a new Business Intelligence suite expanding
Adaptive_Workforce_AI beyond HR. Future planned modules — Accounting, Inventory, Procurement,
Logistics, Operations Intelligence — are each a separate future phase and are **not** built here.

---

## 1. Step 0 — Investigation Findings (before writing any code)

Searched the codebase for any existing general-ledger, revenue, expense, P&L, cash-flow, or
financial-ratio logic beyond the already-known HR-cost tool.

| File | What it actually does |
|---|---|
| `backend/core/financial_intelligence_engine.py` | Confirmed narrow: cost-of-attrition / departure cost estimation from employee-roster data (salary × separation events). No revenue, no GL, no P&L, no cash flow, no ratios. |
| `backend/core/executive_pdf_exporter.py` | Renders board PDFs from HR workforce metrics; no financial statement logic. |
| `backend/core/executive_readiness_engine.py` | HR governance/readiness scoring; no financial logic. |
| `backend/core/modality_classifier.py`, `semantic_column_mapper.py` | Generic column-type/date inference used by the router; no domain-specific financial logic, but genuinely reusable primitives (date parsing pattern referenced, not imported, to keep this module dependency-light). |
| `backend/core/saudi_schema_intelligence.py` | HR/labor-law schema detection only (leave, GOSI, EOS columns). |
| `backend/core/risk_intelligence.py` | Attrition/workforce risk, not financial risk. |
| `backend/core/payroll_budget_engine.py` | The one genuinely relevant precedent — a **Planned vs Actual variance** pattern (headcount/cost), not P&L/revenue/expense. Its variance shape (`variance = actual - planned`, `variance_pct`, magnitude-sorted) was reused verbatim for item 6 below. |

**Conclusion: no general-ledger, revenue, expense, P&L, cash-flow, or financial-ratio logic exists
anywhere in the codebase.** Everything built in this phase is new. The only reused precedent is
the variance *presentation pattern* from `payroll_budget_engine.py`.

---

## 2. Upload Shape Designed

Transaction-level / GL-export shape — **not** an employee roster (this is the first module in the
platform where that's true). Columns are detected via local-regex fuzzy matching (EN + AR), same
`_find_column(df, pattern)` convention used everywhere else in the codebase:

| Field | Required? | Detected via |
|---|---|---|
| Transaction/entry date | optional (enables period trends) | `_TRANSACTION_DATE_PATTERNS` |
| Account/category name | optional (enables category breakdown) | `_ACCOUNT_CATEGORY_PATTERNS` |
| Amount | **required**, must be numeric | `_AMOUNT_PATTERNS` |
| Type (revenue/expense indicator) | optional (improves classification accuracy) | `_TYPE_PATTERNS` |
| Department/cost center | optional (enables department rollup) | `_COST_CENTER_PATTERNS` |
| Description/vendor | optional, reserved for future analysis | `_DESCRIPTION_VENDOR_PATTERNS` |

Source: `backend/core/financial_intelligence_reporting_engine.py:1-60` (pattern constants).

---

## 3. The 6 Items Built

All in **one new file**, kept fully separate from the HR-cost `financial_intelligence_engine.py`:
`backend/core/financial_intelligence_reporting_engine.py` (706 lines).

Revenue/expense classification is a disclosed 3-method cascade (`_classify_token` at line 254,
cascade logic in `analyze_financial_intelligence` at line 391), surfaced to the user via a
`classification_method` field so nothing is silently guessed:
1. Explicit `Type` column matched against `_REVENUE_TOKENS` / `_EXPENSE_TOKENS`.
2. Account/category column keyword match.
3. Signed-amount fallback — **only** used when both positive and negative amounts are present.

| # | Item | What it computes | Honest-degradation behavior |
|---|---|---|---|
| 1 | **Revenue analysis** | Totals + by-period + by-category trends, real data only, no forecasting | If no amount column detected → `unavailable_financial_result` (line 363), never fabricated |
| 2 | **Expense analysis** | Totals + by-category + by-department (via `department_normalizer.normalize_department_series`, same as every HR module) | Department table omitted if no department column; disclosed |
| 3 | **P&L summary** | Revenue − Expense by period | Narrative explicitly labels this as "derived from the upload's own categorization," not a certified financial statement (`FINANCIAL_CONFIDENCE = "derived_from_upload_not_certified_statement"`, line 166) |
| 4 | **Cash flow view** | Net transaction movement by period (inflows − outflows) | Explicitly **not** presented as an indirect/direct-method cash-flow statement — `CASH_FLOW_DISCLAIMER_EN/AR` banner (`tone="caution"`) makes this scoping visible in the UI, same honesty discipline as the session's Zakat estimator |
| 5 | **Financial ratios** | Only expense-to-revenue ratio + expense category concentration — both genuinely computable from a transaction/GL export | `_UNAVAILABLE_RATIOS_NOTE_EN/AR` (line 194) explicitly lists current ratio, quick ratio, debt-to-equity, ROA, ROE as unavailable without balance-sheet data — never estimated |
| 6 | **Variance analysis** | Period-over-period variance (`variance = current − prior`, `variance_pct`, sorted by absolute magnitude), reusing `payroll_budget_engine.py`'s exact presentation pattern | Only computed with ≥2 periods (`_MIN_TREND_PERIODS_FOR_VARIANCE = 2`, line 164); otherwise omitted with a stated reason |

Every code path is wrapped so the function **never raises** — invalid/non-numeric amount rows are
counted and excluded with an example bad value preserved for the user, never silently dropped.

---

## 4. Ingestion & Route Decision

`secure_file_ingestion.py`'s `SecureFileIngestion.scan()` was reused as-is (parsing, PII/leakage
detection, dedup, data-quality checks are domain-agnostic value). Its HR-feature-count blocking
rule does **not** withhold the parsed DataFrame — confirmed by reading `scan()` directly — so the
route gates only on `ir.success and ir.df is not None and ir.row_count > 0`, same as every other
route. `governance_scan_passed` is deliberately **omitted** from this route's response since its
HR-feature-count message is meaningless for financial transaction data. No changes were made to
the shared `secure_file_ingestion.py` file itself.

Route: `POST /api/local/financial-intelligence` — `backend/api/local_analysis_routes.py:3406-3471`.

---

## 5. Frontend

`executive-ui/src/pages/FinancialIntelligence.tsx` (527 lines) — one upload feeding one API call
and 6 tabs (Revenue / Expense / P&L / Cash Flow / Ratios / Variance), since all 6 are different
presentations of the same transaction-level analysis (unlike `SaudiLaborLawCalculators.tsx`'s
3 independent calculators). SAR figures use exact 2-decimal precision (`sar()`, Phase 28
convention) — never K-abbreviated.

**Navigation decision**: a new secondary nav group, **"Business Intelligence"**, was created
(placed directly after "Executive Command," before "Analysis") rather than folding this into the
existing "Financial Planning" group (currently Zakat only). Reasoning: Financial Intelligence is
the first of many non-HR domains to come; Zakat is a narrow HR-financial calculator, a different
kind of thing entirely. `Sidebar.tsx`, badge `new`.

---

## 6. Test Results

**New tests**: `tests/test_financial_intelligence_reporting_engine.py` — 20/20 passing.
- 7 hand-computed-value tests against a new 14-row synthetic fixture (`financial_transactions_test_data.csv`, Jan–Feb 2026)
- 5 classification-method-priority tests
- 6 honest-degradation tests (no amount column, no classification signal, invalid values excluded, no date column, <2 periods, `unavailable_financial_result` never fabricates)
- 1 full `to_dict` serialization sanity test

**Full regression suite**: `1636 passed, 1 skipped, 1 failed` (`test_health_wheel_imported` in
`test_phase29_extended.py` — pre-existing, unrelated to this phase, present before this build
started). **Zero regressions introduced.**

---

## 7. Live Browser Verification

Playwright run against the live backend + Vite dev server, `financial_transactions_test_data.csv`
(14 rows) then `test_employee_data.csv` (200-row real employee roster, zero financial columns).
Zero console/page errors across the entire run (`CONSOLE_ERRORS: []`).

| Screenshot | Confirmed |
|---|---|
| Revenue tab | Total Revenue SAR 74,000.00 — exact match |
| Expense tab | Total Expense SAR 37,200.00; Top category Salaries Expense 67.2%; 3 departments; category table (Salaries 25,000/67.2%, Office Rent 8,000/21.5%, Utilities 2,200/5.9%, Marketing 2,000/5.4%); department table (HR 25,000, Operations 10,200) — exact match |
| P&L tab | Revenue 74,000.00 − Expense 37,200.00 = Net 36,800.00 — exact match |
| Cash Flow tab | Prominent caution-toned "not a certified cash-flow statement" banner rendered |
| Ratios tab | Expense-to-revenue ratio computed; dedicated "not available" banner listing balance-sheet-dependent ratios |
| Variance tab | 2026-02 vs 2026-01: Revenue Δ −5.3% (critical), Expense Δ +18.8% (caution), Net Δ SAR −5,200.00 — exact match; banner cites reuse of Payroll Budget Planner's variance shape |
| Honest degradation (employee CSV) | "Financial data not detected in this upload" — specific missing-column checklist shown (only "Department/cost center" auto-detected, correctly, since HR data has departments too); sidebar remains "NO DATASET" |

All figures traced exactly to the hand-computed fixture across three independent channels: bare
Python function, pytest suite, and live browser UI.

---

## 8. Phase 2+ Backlog (explicitly deferred, not built now)

- Budget vs Actual at the GL level (distinct from the payroll-specific version already built)
- Department/branch cost analysis (deeper than the basic department rollup built here)
- Supplier analysis
- Accounts Receivable / Accounts Payable
- Aging analysis
- Invoice-level analysis
- Anomaly detection
- Forecasting
- Debit/credit-column-based classification (a 4th classification method, deliberately deferred — the 3-method cascade already covers the fixture and typical exports; adding it without a real debit/credit-column example to validate against risked guessing)
- Accounting, Inventory, Procurement, Logistics, Operations Intelligence — each a separate future BI-suite phase

---

## Regression Count

**1636 passed, 1 skipped, 1 pre-existing unrelated failure. Zero regressions.**
