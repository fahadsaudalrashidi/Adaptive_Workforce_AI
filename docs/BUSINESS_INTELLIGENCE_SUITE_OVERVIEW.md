# Business Intelligence Suite — Consolidated Overview

All six originally-planned Business Intelligence domains are now built (Phases 30–35). This
document is the single reference for the suite as a whole — routes/pages, shared utilities and
who uses them, and the complete Phase 2 backlog consolidated from all six individual phase
reports — so a future session doesn't need to re-read six separate documents to get oriented.

---

## 1. The Six Domains

| # | Domain | Engine | Route | Frontend Page | Report |
|---|---|---|---|---|---|
| 1 | Financial Intelligence | `backend/core/financial_intelligence_reporting_engine.py` | `POST /api/local/financial-intelligence` | `FinancialIntelligence.tsx` | [PHASE_30](PHASE_30_FINANCIAL_INTELLIGENCE_PHASE1_REPORT.md) |
| 2 | Accounting Intelligence | `backend/core/accounting_intelligence_engine.py` | `POST /api/local/accounting-intelligence` | `AccountingIntelligence.tsx` | [PHASE_31](PHASE_31_ACCOUNTING_INTELLIGENCE_REPORT.md) |
| 3 | Inventory Intelligence | `backend/core/inventory_intelligence_engine.py` | `POST /api/local/inventory-intelligence` | `InventoryIntelligence.tsx` | [PHASE_32](PHASE_32_INVENTORY_INTELLIGENCE_REPORT.md) |
| 4 | Procurement Intelligence | `backend/core/procurement_intelligence_engine.py` | `POST /api/local/procurement-intelligence` | `ProcurementIntelligence.tsx` | [PHASE_33](PHASE_33_PROCUREMENT_INTELLIGENCE_REPORT.md) |
| 5 | Logistics Intelligence | `backend/core/logistics_intelligence_engine.py` | `POST /api/local/logistics-intelligence` | `LogisticsIntelligence.tsx` | [PHASE_34](PHASE_34_LOGISTICS_INTELLIGENCE_REPORT.md) |
| 6 | Operations Intelligence | `backend/core/operations_intelligence_engine.py` | `POST /api/local/operations-intelligence` | `OperationsIntelligence.tsx` | [PHASE_35](PHASE_35_OPERATIONS_INTELLIGENCE_REPORT.md) |

All six live under the **"Business Intelligence"** secondary nav group in `Sidebar.tsx` (created in
Phase 30, positioned directly after "Executive Command" and before the HR-focused "Analysis"
group), each with its own `badge: 'new'` entry. Each module is a fully independent engine — no
module imports another's column-detection or domain logic — verified by an explicit cross-module
"honest degradation" test/screenshot pair in every phase (uploading any other domain's fixture
produces `available: false` everywhere, never a false positive).

Every route follows the same shape: upload → `secure_file_ingestion.SecureFileIngestion.scan()`
(reused as-is for its domain-agnostic parsing/PII/leakage/dedup value, never gating on the
HR-feature-count `governance_scan_passed` flag) → the domain's `analyze_*_intelligence(df)` →
JSON. Every result is a bundle of independently-`available`-gated sub-results, one per "item"
within the domain (5–6 items per domain, 33 total across the suite).

---

## 2. Shared Utilities Across the Suite

| Utility | Origin | Used by (within the BI suite) | Notes |
|---|---|---|---|
| `secure_file_ingestion.SecureFileIngestion.scan()` | Pre-existing (whole session) | All 6 | Domain-agnostic parsing/PII/leakage/dedup; `governance_scan_passed` deliberately never gated on since its HR-feature-count rule is meaningless outside HR data |
| Period-variance presentation pattern (`variance = current − prior`, `variance_pct`, sorted by absolute magnitude) | `payroll_budget_engine.py` (pre-existing) | Financial Intelligence (Phase 30, revenue/expense variance — the first BI-suite reuse), Procurement Intelligence (Phase 33, price trend), Logistics Intelligence (Phase 34, cost trend), Operations Intelligence (Phase 35, quality/defect trend) | Accounting and Inventory Intelligence do not use this exact shape — their items (Trial Balance, ABC, Reorder Point, etc.) don't have a natural period-over-period comparison in their Phase 1 scope |
| TF-IDF / word-frequency theme extraction (`extract_top_terms_tfidf`, `extract_top_terms_word_frequency`, `scrub_pii`, `SKLEARN_AVAILABLE`, `MIN_DOCUMENT_FREQUENCY=3`, `MIN_RESPONSES_FOR_AGGREGATE=5`) | `exit_interview_intelligence_engine.py` — promoted from `_`-prefixed private to public functions in Phase 34 specifically for this reuse | Logistics Intelligence (Phase 34, return-reason themes), Operations Intelligence (Phase 35, downtime-cause themes) | Each domain builds its OWN theme dictionary (return reasons vs. downtime causes vs. the original HR attrition constructs) — only the extraction mechanism and the suppression floor are shared, never the domain-specific keyword lists, since those don't overlap semantically across domains |
| `delivery_performance_utils.compute_on_time_performance()` | Extracted from Procurement Intelligence in Phase 34 | Procurement Intelligence (Phase 33, refactored to call it; inbound supplier deliveries), Logistics Intelligence (Phase 34, built to call it from the start; outbound carrier deliveries) | Same expected-vs-actual-date arithmetic, genuinely identical computation, different real-world meaning per domain |
| Constructed-heuristic composite scoring (`is_validated_instrument=False`, `confidence="constructed_heuristic_not_validated"`) | `succession_readiness_engine.py` (pre-existing, HR) | Procurement Intelligence (Phase 33, Supplier Performance Score), Logistics Intelligence (Phase 34, Carrier Performance Score) | Operations Intelligence (Phase 35) deliberately does NOT use this pattern for Bottleneck Identification — a ranked-list-plus-threshold-flag design suited the "minimum sample size before confidently flagging" requirement better than a blended weighted score |
| Minimum-sample / disclosed-suppression discipline (never confidently flag/theme/trend from too few observations; suppressed items still counted and disclosed, never silently dropped) | `pay_equity_engine.py`'s `_MIN_GROUP_SIZE_FOR_DISPARITY` (pre-existing, HR) | All 6, independently re-thresholded per domain: Accounting's anomaly/duplicate detection (n≥5 for outliers, exact-match tiers for duplicates), Procurement's price-trend gate (≥2 periods AND ≥4 POs), Logistics' delay-concentration flag (≥3 late shipments) and returns themes (≥3 shipments), Operations' bottleneck confidence (≥3 periods) and downtime themes (≥3 records) | Not a shared function — each domain's threshold is independently chosen and documented for its own statistical context — but the same discipline (disclose suppression, never guess from thin samples) is applied everywhere |
| `department_normalizer.normalize_department_series()` | Pre-existing (whole session, HR-wide) | Financial Intelligence only (Phase 30, expense-by-department rollup) | The other five BI-suite domains group by supplier/SKU/carrier/operational-unit, not department, so this HR-specific utility wasn't applicable to them |

---

## 3. Consolidated Phase 2 Backlog (all six domains, one place)

### Financial Intelligence (Phase 30)
- Budget vs Actual at the GL level (distinct from the payroll-specific version)
- Department/branch cost analysis (deeper than the basic rollup built)
- Supplier analysis, AR/AP, aging, invoice-level analysis — **now superseded**: Procurement
  Intelligence (Phase 33) and Accounting Intelligence's AR/AP Aging (Phase 31) cover these
- Anomaly detection — **now superseded** by Accounting Intelligence's Journal Anomaly Detection (Phase 31)
- Forecasting
- Debit/credit-column-based classification (a 4th revenue/expense classification method)

### Accounting Intelligence (Phase 31)
- Budget vs Actual at the GL level (distinct from the payroll-specific version)
- Department/branch cost analysis
- Supplier analysis — **now superseded** by Procurement Intelligence (Phase 33)
- Aging-based collections workflow (beyond the aging buckets already built)
- Invoice-level line-item analysis
- Forecasting
- Debit/credit-column-based classification for Phase 30's revenue/expense signal
- True payment-to-invoice matching (current AR/AP status is read from a snapshot status field,
  not derived by matching settlement transactions back to their originating invoice)

### Inventory Intelligence (Phase 32)
- Demand forecasting
- Waste/damage analysis
- Multi-warehouse comparison (the `Warehouse` column is detected but not yet used for a rollup)
- **Inventory carrying-cost analysis — OWNERSHIP QUESTION STILL OPEN.** Flagged in Phase 32 as
  belonging to either Inventory or Financial Intelligence; not resolved by any later phase.
  Operations Intelligence's Phase 35 "cost per unit of operation" is a DIFFERENT metric (cost to
  produce one unit of output) and does not resolve this — carrying cost (cost of holding stock
  over time: warehousing, insurance, capital cost, obsolescence risk) still has no owner. This
  remains the one genuinely undecided ownership question across the whole suite.
- Anything requiring purchase-order data — **now superseded** by Procurement Intelligence (Phase 33)

### Procurement Intelligence (Phase 33)
- Supplier risk scoring beyond the performance composite (needs external data — financial health,
  credit ratings — this platform cannot access)
- Live external market-price comparison (this platform has no live market-price search capability)

### Logistics Intelligence (Phase 34)
- Delay forecasting/prediction
- Supply-chain risk scoring beyond the carrier performance composite (same external-data
  limitation as Procurement's deferred risk scoring)
- **Route optimization — explicitly flagged as a different KIND of feature**, not a reporting gap.
  Every item across all 6 BI-suite domains is a reporting/analytics feature (describes what
  already happened in uploaded data). Route optimization is a combinatorial/operations-research
  problem (e.g. vehicle routing, network-flow minimization) that computes a *new* recommended
  plan — a different algorithmic toolkit entirely, not "more reporting to build later."
- Delay-reason/cause breakdown (the `delay_reason` column is fuzzy-detected and will activate
  automatically the moment a real upload contains one — not stubbed, just never exercised because
  the Phase 34 fixture has no such column)

### Operations Intelligence (Phase 35)
- True SLA-compliance tracking (needs contractually-defined SLA targets this platform has no way
  to know unless explicitly provided in the upload — a real SLA-target column would be an easy
  Phase 2 addition if one is ever detected, but none is assumed or defaulted)
- Predictive/forecasting capability (consistent with every other domain's deferral)

### Cross-cutting backlog items (span multiple domains)
- **Forecasting/prediction, in general**: deferred identically across all 6 domains (Financial,
  Accounting, Inventory, Procurement, Logistics, Operations) — a clear, consistent signal that a
  dedicated forecasting capability (if built) should likely be its own cross-domain effort rather
  than reimplemented 6 times.
- **Risk scoring beyond a constructed-heuristic composite**: deferred identically in Procurement
  and Logistics for the same reason (no external data access) — likely the same constraint would
  apply to any future "supplier/carrier/operational risk" feature elsewhere in the suite.
- **The Inventory carrying-cost ownership question** (above) is the only genuinely unresolved
  cross-domain decision left in the suite.

---

## 4. Suite-Wide Test Coverage Summary

| Domain | New tests (at time of its phase) | Fixture(s) |
|---|---|---|
| Financial Intelligence | 20 | `financial_transactions_test_data.csv` |
| Accounting Intelligence | 28 | `accounting_gl_test_data.csv`, `accounting_gl_imbalanced_test_data.csv` |
| Inventory Intelligence | 30 | `inventory_transactions_test_data.csv`, `inventory_snapshot_only_test_data.csv` |
| Procurement Intelligence | 30 | `procurement_transactions_test_data.csv` |
| Logistics Intelligence | 29 | `logistics_shipments_test_data.csv` |
| Operations Intelligence | 33 | `operations_units_test_data.csv` |
| **Suite total** | **170** | 8 fixtures |

Full backend regression suite after Phase 35: **1786 passed, 1 skipped, 1 pre-existing unrelated
failure** (`test_health_wheel_imported`, present before Phase 30 began and unrelated to the BI
suite) — zero regressions introduced across all six phases, including in the two shared-utility
refactors (`delivery_performance_utils.py` extraction from Procurement; the Exit Interview
public-function promotion).
