# Phase 31 — Accounting Intelligence (Business Intelligence Suite, Module 2)

Accounting Intelligence covers only the items that genuinely require true double-entry accounting
data (separate Debit/Credit columns, and — for Balance Sheet — an Asset/Liability/Equity
classification) or a wholly different upload shape (invoice-level AR/AP data). Everything Phase 30's
Financial Intelligence module already computes from a plain transaction list is deliberately not
rebuilt here.

---

## 1. Non-Duplication With Phase 30 — Explicit Diff

| Module | Owns | Upload shape required |
|---|---|---|
| **Phase 30** `financial_intelligence_reporting_engine.py` | Revenue analysis, Expense analysis, P&L summary, Cash Flow ("net transaction movement"), Financial Ratios (expense-to-revenue, concentration), period-over-period Variance | A single signed **Amount** column + optional Type/Category — no debit/credit structure needed |
| **Phase 31** `accounting_intelligence_engine.py` | General Ledger drill-down (account → individual transactions), Trial Balance, Balance Sheet, AR/AP Aging, Journal Entry Anomaly & Duplicate Detection | Real, **separate Debit and Credit** columns (+ Account-type classification for Balance Sheet; + invoice-level Party/DueDate/Status for AR/AP) |

None of Phase 30's five items (Revenue, Expense, P&L, Cash Flow, Ratios, Variance) are recomputed
or re-exposed in this module. The reverse is proven live: uploading Phase 30's own fixture
(`financial_transactions_test_data.csv` — Amount + Type, no Debit/Credit) into the new Accounting
Intelligence page makes **all five** of this phase's items honestly report not-computable
(screenshots 09–11, and `TestCrossModuleDifferentiation` in the test suite) — the two modules
cannot silently overlap because their column requirements don't intersect.

---

## 2. The 5 Items Built

All in one new file, kept separate from both `financial_intelligence_engine.py` (HR-cost) and
`financial_intelligence_reporting_engine.py` (Phase 30): `backend/core/accounting_intelligence_engine.py`
(1,174 lines).

| # | Item | Data requirement | Honest-degradation behavior |
|---|---|---|---|
| 1 | **General Ledger Analysis** (`analyze_general_ledger`, line 309) | Account column + real, separate Debit and Credit columns | `unavailable_general_ledger_result` (line 299) if debit/credit aren't both present — a single signed amount is explicitly not sufficient |
| 2 | **Trial Balance** (`analyze_trial_balance`, line 437) | Same as above | Sums debit/credit per account, flags imbalance if `abs(total_debit - total_credit) > 0.01` SAR — a real data-quality signal, never silently corrected. Not computable from a single-amount upload — never approximated |
| 3 | **Balance Sheet** (`analyze_balance_sheet`, line 554) | Debit/Credit + an Account-type column with real Asset/Liability/Equity tokens | Two distinct honest-degradation paths: missing debit/credit → not computable; debit/credit present but no Asset/Liability/Equity classification (Revenue/Expense-only, i.e. Phase 30's classification axis) → explicitly not sufficient, reported as such |
| 4 | **AR/AP + Aging** (`analyze_ar_ap_aging`, line 752) | Party (customer/vendor) + Due date + Amount + Paid/outstanding status — invoice-level, not GL-level | Aging buckets (current, 1-30, 31-60, 61-90, 90+) computed from real due dates only, against a caller-supplied `as_of_date` (defaults to real today in production; tests pass a fixed date) |
| 5 | **Journal Entry Anomaly & Duplicate Detection** (`analyze_journal_anomalies`, line 904) | Same GL data as items 1–3 (+ date, for duplicate matching) | Amount anomalies: IQR/Tukey's-fences per account, gated on `_MIN_SAMPLE_SIZE_FOR_ANOMALY = 5` (line 135) — accounts below that floor are counted and disclosed as suppressed, mirroring `pay_equity_engine.py`'s `_MIN_GROUP_SIZE_FOR_DISPARITY` suppression discipline. Duplicates matched on (date, account, amount) jointly + description similarity via `difflib.SequenceMatcher` — never a single field, specifically so legitimate recurring transactions (different dates) don't false-positive |

**Why IQR instead of a z-score for anomalies**: financial transaction amounts are routinely
right-skewed (many small routine entries, occasional large one-offs), which would make a
z-score's normality assumption misleading. Tukey's-fences make no distributional assumption.

**Balance Sheet's honest accounting subtlety**: the identity `Assets = Liabilities + Equity` only
holds once the current period's unclosed net income (from Revenue/Expense-classified accounts) is
included as an equity contribution — real accounting practice (the "closing entry"), not an
approximation. This is computed and clearly labeled `net_income_current_period_sar` /
"Net Income (Unclosed)" rather than silently folded into equity.

---

## 3. Fixture Design

`accounting_gl_test_data.csv` (repo root, 50 rows / 25 balanced double-entry journal
transactions) — built via a scratch script and cross-verified with pandas before any test was
written:

- **Balanced by construction**: every transaction is a real debit=credit pair; total debits =
  total credits = SAR 128,660.00 exactly.
- **13 accounts** spanning Asset/Liability/Equity/Revenue/Expense, including Cash, Accounts
  Receivable, Accounts Payable, Share Capital, Sales Revenue, Rent/Salaries/Utilities/Consulting/
  Insurance/Office Supplies Expense.
- **AR/AP invoice-level data**: 8 open items with due dates spread across 5 aging buckets (one
  deliberately already `Paid` to prove exclusion), attached to the same GL rows via a `Party`
  column that serves both customer and vendor names — a realistic combined AR/AP subledger export.
- **Anomaly test data**: Utilities Expense has 6 entries, 5 routine (~600–650 SAR) and one 6,200
  SAR outlier; Cash's own 13-line history also produces 2 emergent outliers (the 50,000 capital
  injection and 20,000 loan — correctly flagged as statistically unusual one-off financing events,
  not errors).
- **Duplicate test data**: an Insurance Expense pair with near-identical (not byte-identical)
  descriptions ("Quarterly insurance premium" vs "...premium payment", similarity ≈0.871) for the
  "high confidence" case, and a Consulting Expense pair sharing date/account/amount but with
  genuinely different descriptions (similarity ≈0.382) for the "review" case — proving a
  same-amount coincidence isn't auto-flagged as a confirmed error.
- **Recurring-transaction control**: Utilities Expense's 6 entries land on 6 different dates, so
  none collide on the (date, account, amount) duplicate key — proving legitimate recurring
  transactions are never false-flagged.

`accounting_gl_imbalanced_test_data.csv` (6 rows / 3 transactions) — a second, small fixture with
a deliberate SAR 500.00 posting error (an equipment purchase entered as 3,000 debit but only 2,500
credited), used only to test the Trial Balance imbalance flag without disturbing the main
fixture's clean "balanced" assertions.

**A real interaction found during live verification**: the shared ingestion pipeline
(`secure_file_ingestion.py`, reused as-is per this session's established decision) removes
byte-for-byte identical duplicate *rows* before any analysis runs. The fixture's original
duplicate-detection test pair was two fully identical rows, which the pipeline silently
deduplicated away before this module ever saw them (50 rows → 48). Fixed by making the pair
near-identical instead of byte-identical (a more realistic simulation of an accidental duplicate
entry in practice, e.g. entered by two different people) — this is now what both the test suite
and the live route exercise. Documented here rather than hidden.

---

## 4. Test Results

**New tests**: `tests/test_accounting_intelligence_engine.py` — 28/28 passing, organized into 7
sections: General Ledger, Trial Balance, Balance Sheet, AR/AP Aging, Journal Anomalies,
cross-module honest degradation (Phase 30 fixture → all 5 items unavailable), and bundle/
serialization sanity. Every "hand-computed" figure was independently derived with pandas
(`groupby`, `.quantile()`) separately from the engine's own code path before the engine was run
against it, then cross-checked.

**Full regression suite**: `1664 passed, 1 skipped, 1 failed` (the same pre-existing, unrelated
`test_health_wheel_imported` failure present before this phase — 1636 baseline + 28 new tests =
1664). **Zero regressions introduced.**

---

## 5. Live Browser Verification

Playwright run against the live backend + Vite dev server. Zero console/page errors across the
entire run (`CONSOLE_ERRORS: []`).

| Screenshot | Confirmed |
|---|---|
| General Ledger tab | 50 journal lines, 13 accounts; Cash Dr 77,000.00 / Cr 28,310.00 / Net 48,690.00 — exact match |
| General Ledger drill-down | Expanding "Cash" reveals its 13 individual transaction lines with dates/descriptions/amounts |
| Trial Balance | Total debits SAR 128,660.00 = total credits SAR 128,660.00, difference SAR 0.00, "balanced" — exact match |
| Balance Sheet | Assets 69,290.00 = Liabilities 27,950.00 + Equity 50,000.00 + Net Income −8,660.00 (unclosed) — identity holds exactly, per-account lines match |
| AR/AP Aging | Total outstanding SAR 16,550.00, 7 open invoices, 1 paid item excluded; all 5 buckets match exactly (current 900/1, 1-30 10,700/3, 31-60 950/1, 61-90 2,200/1, 90+ 1,800/1) |
| Anomalies & Duplicates | 5 accounts checked, 8 suppressed; 4 anomalies (Cash 50,000 & 20,000, Utilities Expense 6,200, Accounts Receivable 6,000) with correct normal ranges shown; 4 duplicate rows (2 "High" confidence pairs, 2 "Review" confidence pairs) — exact match |
| Trial Balance imbalance flag | Uploading the deliberately-unbalanced fixture shows a critical red banner: "DOES NOT BALANCE... difference of SAR 500.00... never silently ignored or corrected" — exact match |
| Cross-module: General Ledger tab on Phase 30's fixture | "General ledger data not detected" — Account and date correctly shown as detected (green), Debit/Credit correctly shown as missing |
| Cross-module: Balance Sheet tab on Phase 30's fixture | "Balance sheet not computable from this upload" — same pattern |
| Cross-module: AR/AP Aging tab on Phase 30's fixture | "AR/AP invoice-level data not detected" — all 4 required columns correctly shown as missing |

---

## 6. Scope Confirmation

Every item from the original Accounting Intelligence request was built this phase. Nothing from
that list remains outstanding. Deliberately deferred, out of this phase's scope (unchanged from
Phase 30's backlog, plus one new item surfaced during this build):

- Budget vs Actual at the GL level, department/branch cost analysis, supplier analysis, aging-based
  collections workflow, invoice-level line-item analysis, forecasting (carried over from Phase 30's
  backlog — still not built).
- **Debit/credit-column-based classification for Phase 30's revenue/expense signal** — now that
  this phase has real debit/credit data to draw on, Phase 30 could in principle be upgraded to use
  it as a 4th classification method. Left as a Phase 30 enhancement, not built here, to keep this
  phase's scope to the 5 requested items only.
- **Payment-to-invoice matching** — this phase's AR/AP status is read directly from a `PaidStatus`
  column on the invoice-creating row (a realistic "snapshot" export), not derived by matching later
  settlement transactions back to their originating invoice. True payment-matching is a materially
  larger feature, explicitly out of scope here.

---

## Regression Count

**1664 passed, 1 skipped, 1 pre-existing unrelated failure. Zero regressions.**

## Environment Note

The dev environment's known stale/ghost `127.0.0.1:8000` TCP socket (documented in Phase 30) was
present again during this phase's live verification. Same workaround applied: `executive-ui/vite.config.ts`'s
proxy target was pointed at the machine's LAN IP (`192.168.100.2:8000`) instead of `localhost:8000`.
This is a committed config change, left in place since it is what currently works in this environment.
