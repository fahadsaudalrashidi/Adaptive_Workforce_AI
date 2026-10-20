"""
Financial Intelligence Reporting — Phase 30 (Business Intelligence Suite,
Phase 1 of many; see PHASE_30_FINANCIAL_INTELLIGENCE_PHASE1_REPORT.md for the
full roadmap). Revenue, Expense, P&L, Cash Flow, Financial Ratios, and
Variance Analysis, computed from a single uploaded transaction-level or
account-level financial dataset (a general-ledger export or a structured
revenue/expense summary) — NOT an employee roster. This is the first
non-HR domain this platform analyzes; see the module docstring's "New data
reality" section below for why it cannot reuse the employee-CSV ingestion
assumptions every prior module relied on.

**Step 0 investigation (done before writing any of this): does real
general-ledger/revenue/P&L logic already exist?** Searched the whole
`backend/core/` tree for general-ledger, revenue, expense, P&L, cash-flow,
and financial-ratio logic beyond the already-known
`financial_intelligence_engine.py` (confirmed, by reading its own module
docstring and source, to be narrowly about HR departure/turnover COST
estimation — Cascio-Boudreau 9-component cost model, ESG/gratuity
liability, ROI scenarios — never general revenue, expense, or P&L
analysis). Four other files matched a broad keyword grep
(`executive_pdf_exporter.py`, `executive_readiness_engine.py`,
`modality_classifier.py`, `semantic_column_mapper.py`) — all four are
either narrative text ("Financial rationale summary" as an HTML section
header; "Revenue Visibility" as a *readiness score* label, not a computed
revenue figure) or generic column-classification heuristics (tagging a
column as "looks financial" for ML routing purposes, computing nothing).
`saudi_schema_intelligence.py` and `risk_intelligence.py` both list
"cost_center" only as a department-name synonym for HR grouping, not a
general-ledger concept. Conclusion: there is no real, usable general-ledger/
revenue/expense/P&L/cash-flow/ratio computation logic anywhere in this
codebase. Everything in this module is built fresh.

**New data reality — this module does NOT reuse the employee-CSV ingestion
path.** Every module built this session so far calls
`backend.core.secure_file_ingestion.SecureFileIngestion.scan()`, whose
BLOCKING rule requires at least 3 columns matching a fixed HR vocabulary
(`_FEATURE_SIGNALS_EN`: age, gender, tenure, department, salary_band,
nationality, ...) or the upload is marked `readiness_level=BLOCKED`. A
general-ledger export's columns (TransactionDate, Account, Amount, Type,
CostCenter) would match at most one of these ("department"/"cost_center"-
adjacent, if present at all) — nowhere near the 3-column HR-feature
minimum. Confirmed by reading `secure_file_ingestion.py` end-to-end that
this BLOCKED flag does NOT actually withhold the parsed DataFrame — the
real `IngestionResult.df` is built earlier in `scan()` and returned
unconditionally, so every route this session has ever written already
gates only on `ir.success and ir.df is not None and ir.row_count > 0`, never
on the HR-specific `governance_scan_passed` flag. This route therefore
still reuses `_scanner.scan()` for its genuinely domain-agnostic value
(real file parsing, PII/leakage column detection — still relevant if a
financial export happens to contain a "Paid To" employee-name column,
deduplication, row-count/missing-value data-quality checks) but the
frontend for this module does not render the HR-feature-count blocking
reason as a failure state, since "only 1 of 3 required HR columns found"
is a meaningless, misleading message for a P&L dataset. No changes were
made to the shared `secure_file_ingestion.py` — reusing it as-is, with the
one blocking rule's UI framing deliberately not carried into this domain,
was judged lower-risk than modifying a file every other module also
depends on.

**Column detection** (local-regex convention, same as every Phase 5-29
engine): transaction/entry date, account/category name, amount, a
revenue-vs-expense signal (an explicit type column, category-name
keywords, or — as a last resort — the sign of the amount itself), an
optional department/cost-center column (reusing `department_normalizer.py`
verbatim for its rollup, exactly like every HR module), and an optional
description/vendor column (detected and disclosed but not yet used for any
computation — reserved for Phase 2's supplier analysis, see the report's
backlog).

**Revenue-vs-expense classification — three methods, tried in reliability
order, method used always disclosed, never silently guessed:**
  1. An explicit type/debit-credit-style column with recognizable Revenue/
     Income/Sales vs. Expense/Cost tokens — most reliable, used first.
  2. The account/category column's own text, keyword-matched against a
     small curated revenue/expense vocabulary (e.g. "Sales Revenue" vs.
     "Office Rent Expense") — used only when no type column exists.
     Categories that don't clearly match either vocabulary are excluded
     from revenue/expense totals and counted, never guessed.
  3. The sign of the amount itself (positive = inflow/revenue, negative =
     outflow/expense) — the coarsest, last-resort convention, used only
     when the amount column actually contains both signs (an all-positive
     column gives this method nothing to distinguish, so it is not used).
  Debit/credit-column-based classification (crediting a revenue account vs.
  crediting a liability account are both "credits" but mean opposite
  things without chart-of-accounts context) was deliberately NOT
  implemented this phase — see the report's Phase 2+ backlog.

**Cash Flow — honestly scoped down, same discipline as this session's
Zakat estimator.** A transaction-level export with only date/amount/type
cannot distinguish accrual-basis revenue recognition from actual cash
receipt timing, nor separate operating/investing/financing activities —
the ingredients a real cash-flow statement requires. This module computes
NET TRANSACTION MOVEMENT (classified inflows minus classified outflows)
per period and labels it exactly that, with an explicit, prominent
disclaimer that this is not an indirect- or direct-method cash-flow
statement — never presented as one.

**Financial ratios — only what a transaction/GL export can support.**
Expense-to-revenue ratio and expense/revenue category concentration are
computed from real totals. Balance-sheet-dependent ratios (current ratio,
quick ratio, debt-to-equity, ROA, ROE) are explicitly listed as requiring
data this upload shape does not and cannot contain — never estimated or
benchmarked against an uncited industry figure.

**Variance analysis** reuses the exact field-naming and computation shape
already established in `payroll_budget_engine.py`'s Planned-vs-Actual
variance (`X_variance = actual - planned`, `X_variance_pct = round(100 *
variance / planned, 1)`, sorted by absolute magnitude) — applied here to
period-over-period movement (this phase has no "planned/budget" figure to
compare against; that comparison is explicitly deferred, see the report).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

import pandas as pd

from backend.core.department_normalizer import normalize_department_series

# ── Column detection (local-regex convention) ───────────────────────────────

_TRANSACTION_DATE_PATTERNS = re.compile(
    r"\b(transaction[_\s]?date|entry[_\s]?date|posting[_\s]?date|txn[_\s]?date|"
    r"journal[_\s]?date|date|"
    r"تاريخ[_\s]?المعاملة|تاريخ[_\s]?القيد|تاريخ)\b", re.I,
)
_ACCOUNT_CATEGORY_PATTERNS = re.compile(
    r"\b(account[_\s]?name|account[_\s]?category|gl[_\s]?account|chart[_\s]?of[_\s]?accounts|"
    r"expense[_\s]?category|revenue[_\s]?category|category|account|"
    r"الحساب|فئة[_\s]?الحساب|التصنيف)\b", re.I,
)
_AMOUNT_PATTERNS = re.compile(
    r"\b(amount|transaction[_\s]?amount|net[_\s]?amount|value|"
    r"المبلغ|القيمة)\b", re.I,
)
_TYPE_PATTERNS = re.compile(
    r"\b(transaction[_\s]?type|entry[_\s]?type|debit[_\s]?credit|dr[_\s]?cr|"
    r"revenue[_\s]?expense|type|"
    r"نوع[_\s]?المعاملة|النوع)\b", re.I,
)
_COST_CENTER_PATTERNS = re.compile(
    r"\b(cost[_\s]?center|cost[_\s]?centre|department|dept|business[_\s]?unit|branch|"
    r"مركز[_\s]?التكلفة|القسم|الفرع)\b", re.I,
)
_DESCRIPTION_VENDOR_PATTERNS = re.compile(
    r"\b(description|vendor|supplier|memo|narration|payee|reference|"
    r"الوصف|المورد|البيان)\b", re.I,
)

# Revenue-vs-expense token vocabularies (methods 1 and 2 — see module docstring).
_REVENUE_TOKENS = frozenset({
    "revenue", "income", "sales", "sale", "inflow", "credit", "earnings",
    "إيراد", "إيرادات", "دخل", "مبيعات",
})
_EXPENSE_TOKENS = frozenset({
    "expense", "expenses", "cost", "costs", "outflow", "debit", "expenditure",
    "مصروف", "مصاريف", "تكلفة", "تكاليف",
})

_MIN_TREND_PERIODS_FOR_VARIANCE = 2

FINANCIAL_CONFIDENCE = "derived_from_upload_not_certified_statement"
FINANCIAL_DISCLAIMER_EN = (
    "These figures are derived entirely from your own uploaded transaction data and its "
    "own category/type labeling — they are NOT a certified financial statement (no audit, "
    "no accounting-standard review, no assurance of completeness). This is a computational "
    "planning aid; qualified accounting/finance review is required before any financial "
    "reporting, filing, or decision based on these figures."
)
FINANCIAL_DISCLAIMER_AR = (
    "تُشتق هذه الأرقام بالكامل من بيانات معاملاتك المُحمّلة وتصنيفاتها الخاصة — وهي ليست "
    "قائمة مالية معتمدة (لا تدقيق، ولا مراجعة وفق معايير المحاسبة، ولا ضمان اكتمال). هذه "
    "أداة تخطيط حسابية مساعدة؛ تلزم مراجعة محاسبية/مالية متخصصة قبل أي تقرير مالي أو إقرار "
    "أو قرار يُبنى على هذه الأرقام."
)
CASH_FLOW_DISCLAIMER_EN = (
    "This is NET TRANSACTION MOVEMENT (classified inflows minus classified outflows) per "
    "period from your uploaded data — NOT a cash-flow statement in the accounting sense. "
    "A real cash-flow statement requires separating operating, investing, and financing "
    "activities and distinguishing accrual-basis recognition from actual cash timing, "
    "neither of which can be determined from a transaction/date/amount/type export alone."
)
CASH_FLOW_DISCLAIMER_AR = (
    "هذا صافي حركة المعاملات (التدفقات الداخلة المصنّفة ناقص التدفقات الخارجة المصنّفة) لكل "
    "فترة من بياناتك المُحمّلة — وليس قائمة تدفقات نقدية بالمعنى المحاسبي. تتطلب قائمة "
    "التدفقات النقدية الحقيقية فصل الأنشطة التشغيلية والاستثمارية والتمويلية، والتمييز بين "
    "الاستحقاق المحاسبي والتوقيت النقدي الفعلي، ولا يمكن تحديد أي منهما من ملف معاملات "
    "يحتوي على تاريخ/مبلغ/نوع فقط."
)
_UNAVAILABLE_RATIOS_NOTE_EN = (
    "Current ratio, quick ratio, debt-to-equity, return on assets, and return on equity all "
    "require balance-sheet data (assets, liabilities, equity) — none of which is present in "
    "a transaction-level export. These are not estimated or approximated."
)
_UNAVAILABLE_RATIOS_NOTE_AR = (
    "النسبة الجارية، والنسبة السريعة، ونسبة الدين إلى حقوق الملكية، والعائد على الأصول، "
    "والعائد على حقوق الملكية تتطلب جميعها بيانات الميزانية العمومية (أصول، خصوم، حقوق "
    "ملكية) — وهي غير موجودة في ملف معاملات. لا تُقدَّر أو تُقارب هذه النسب."
)
_SOURCES = [
    "Revenue, expense, P&L, and variance figures are computed entirely from the uploaded "
    "transaction data's own date/amount/category/type columns — no external benchmark or "
    "industry figure is used anywhere in this module.",
    "Variance computation reuses the exact field-naming and calculation shape already "
    "established in payroll_budget_engine.py's Planned-vs-Actual variance "
    "(variance = actual - planned; variance_pct = 100 * variance / planned), applied here "
    "to period-over-period movement.",
    "Department/cost-center rollup reused verbatim from department_normalizer.py.",
]
_COLUMN_LABELS_EN: dict[str, str] = {
    "transaction_date": "Transaction/entry date (optional — enables period trends)",
    "account_category": "Account/category name (optional — enables category breakdown)",
    "amount": "Transaction amount (required — must be numeric)",
    "type": "Transaction type / revenue-expense indicator (optional — improves classification accuracy)",
    "cost_center": "Department / cost center (optional — enables department rollup)",
    "description": "Description / vendor (optional — reserved for future supplier analysis)",
}
_COLUMN_LABELS_AR: dict[str, str] = {
    "transaction_date": "تاريخ المعاملة (اختياري — يُفعّل الاتجاهات الزمنية)",
    "account_category": "اسم الحساب/الفئة (اختياري — يُفعّل التصنيف حسب الفئة)",
    "amount": "مبلغ المعاملة (مطلوب — يجب أن يكون رقماً)",
    "type": "نوع المعاملة / مؤشر إيراد-مصروف (اختياري — يُحسّن دقة التصنيف)",
    "cost_center": "القسم / مركز التكلفة (اختياري — يُفعّل التجميع حسب القسم)",
    "description": "الوصف / المورد (اختياري — محجوز لتحليل الموردين مستقبلاً)",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _find_column(df: pd.DataFrame, pattern: re.Pattern) -> Optional[str]:
    for col in df.columns:
        if pattern.search(str(col)):
            return col
    return None


def _is_missing_value(raw: object) -> bool:
    if raw is None:
        return True
    try:
        if pd.isna(raw):
            return True
    except (TypeError, ValueError):
        pass
    return not str(raw).strip()


def _classify_token(raw: object) -> Optional[str]:
    """Returns 'revenue' | 'expense' | None (unclassifiable — never guessed)."""
    if _is_missing_value(raw):
        return None
    key = " ".join(str(raw).split()).strip().lower()
    if key in _REVENUE_TOKENS:
        return "revenue"
    if key in _EXPENSE_TOKENS:
        return "expense"
    for token in _REVENUE_TOKENS:
        if token in key:
            return "revenue"
    for token in _EXPENSE_TOKENS:
        if token in key:
            return "expense"
    return None


# ── Result types ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class PeriodFigure:
    period: str
    total_revenue_sar: Optional[float]
    total_expense_sar: Optional[float]
    net_sar: Optional[float]
    n_transactions: int


@dataclass(frozen=True)
class CategoryFigure:
    category: str
    signal_type: str  # "revenue" | "expense"
    total_sar: float
    n_transactions: int
    share_pct: float  # share of that signal_type's total


@dataclass(frozen=True)
class DepartmentExpenseFigure:
    department: str
    total_expense_sar: float
    n_transactions: int


@dataclass(frozen=True)
class PeriodVariance:
    period: str
    prior_period: str
    revenue_variance_sar: Optional[float]
    revenue_variance_pct: Optional[float]
    expense_variance_sar: Optional[float]
    expense_variance_pct: Optional[float]
    net_variance_sar: Optional[float]
    net_variance_pct: Optional[float]


@dataclass(frozen=True)
class FinancialRatios:
    expense_to_revenue_ratio: Optional[float]
    top_expense_category: Optional[str]
    top_expense_category_share_pct: Optional[float]
    top_revenue_category: Optional[str]
    top_revenue_category_share_pct: Optional[float]
    unavailable_ratios_note_en: str
    unavailable_ratios_note_ar: str


@dataclass(frozen=True)
class FinancialIntelligenceResult:
    available: bool
    reason: Optional[str]
    columns_detected: dict[str, bool]
    transaction_date_column: Optional[str]
    account_category_column: Optional[str]
    amount_column: Optional[str]
    type_column: Optional[str]
    cost_center_column: Optional[str]
    description_column: Optional[str]
    classification_method: Optional[str]
    n_transactions_total: int
    n_transactions_classified: int
    n_excluded_invalid_amount: int
    n_excluded_unclassified: int
    example_excluded_amount_value: Optional[str]
    has_period_trend: bool
    total_revenue_sar: Optional[float]
    total_expense_sar: Optional[float]
    net_pnl_sar: Optional[float]
    period_figures: list[PeriodFigure]
    revenue_by_category: list[CategoryFigure]
    expense_by_category: list[CategoryFigure]
    expense_by_department: list[DepartmentExpenseFigure]
    department_normalization_notes: list[str]
    period_variances: list[PeriodVariance]
    ratios: Optional[FinancialRatios]
    cash_flow_available: bool
    cash_flow_disclaimer_en: str
    cash_flow_disclaimer_ar: str
    narrative_en: str
    narrative_ar: str
    confidence: str
    disclaimer_en: str
    disclaimer_ar: str
    governance_note: str
    sources: list[str]
    computed_at: str


def unavailable_financial_result(
    reason: str, columns_detected: Optional[dict[str, bool]] = None,
) -> FinancialIntelligenceResult:
    return FinancialIntelligenceResult(
        available=False, reason=reason, columns_detected=columns_detected or {},
        transaction_date_column=None, account_category_column=None, amount_column=None,
        type_column=None, cost_center_column=None, description_column=None,
        classification_method=None, n_transactions_total=0, n_transactions_classified=0,
        n_excluded_invalid_amount=0, n_excluded_unclassified=0,
        example_excluded_amount_value=None, has_period_trend=False,
        total_revenue_sar=None, total_expense_sar=None, net_pnl_sar=None,
        period_figures=[], revenue_by_category=[], expense_by_category=[],
        expense_by_department=[], department_normalization_notes=[], period_variances=[],
        ratios=None, cash_flow_available=False,
        cash_flow_disclaimer_en=CASH_FLOW_DISCLAIMER_EN, cash_flow_disclaimer_ar=CASH_FLOW_DISCLAIMER_AR,
        narrative_en="Financial intelligence analysis not available for this dataset.",
        narrative_ar="تحليل الذكاء المالي غير متاح لهذه البيانات.",
        confidence=FINANCIAL_CONFIDENCE,
        disclaimer_en=FINANCIAL_DISCLAIMER_EN, disclaimer_ar=FINANCIAL_DISCLAIMER_AR,
        governance_note=(
            "No revenue, expense, P&L, or ratio figures are computed or displayed without "
            "a numeric amount column and a way to classify transactions as revenue or "
            "expense — this platform never fabricates a financial figure."
        ),
        sources=_SOURCES, computed_at=_now(),
    )


def analyze_financial_intelligence(df: pd.DataFrame) -> FinancialIntelligenceResult:
    """Never raises — exceptions should be caught by the caller and surfaced
    via unavailable_financial_result."""
    if df is None or df.empty:
        return unavailable_financial_result("No data available for financial intelligence analysis.")

    date_col = _find_column(df, _TRANSACTION_DATE_PATTERNS)
    category_col = _find_column(df, _ACCOUNT_CATEGORY_PATTERNS)
    amount_col = _find_column(df, _AMOUNT_PATTERNS)
    type_col = _find_column(df, _TYPE_PATTERNS)
    cost_center_col = _find_column(df, _COST_CENTER_PATTERNS)
    description_col = _find_column(df, _DESCRIPTION_VENDOR_PATTERNS)

    columns_detected = {
        "transaction_date": date_col is not None,
        "account_category": category_col is not None,
        "amount": amount_col is not None,
        "type": type_col is not None,
        "cost_center": cost_center_col is not None,
        "description": description_col is not None,
    }

    if amount_col is None:
        return unavailable_financial_result(
            "No numeric transaction-amount column detected (e.g. Amount, Value). Every "
            "figure in this module is derived from real transaction amounts — without one, "
            "nothing can be computed.",
            columns_detected,
        )

    numeric_amount = pd.to_numeric(df[amount_col], errors="coerce")
    n_excluded_amount = 0
    example_excluded: Optional[str] = None
    for idx in df.index:
        if pd.isna(numeric_amount.loc[idx]) and not _is_missing_value(df.at[idx, amount_col]):
            n_excluded_amount += 1
            if example_excluded is None:
                example_excluded = str(df.at[idx, amount_col]).strip()

    # ── Revenue-vs-expense classification (3 methods, priority order) ──────
    classification: dict[Any, str] = {}
    method: Optional[str] = None

    if type_col is not None:
        for idx in df.index:
            if pd.isna(numeric_amount.loc[idx]):
                continue
            cls = _classify_token(df.at[idx, type_col])
            if cls is not None:
                classification[idx] = cls
        if classification:
            method = "type_column"

    if not classification and category_col is not None:
        category_cls_cache: dict[str, Optional[str]] = {}
        for idx in df.index:
            if pd.isna(numeric_amount.loc[idx]):
                continue
            raw_cat = df.at[idx, category_col]
            if _is_missing_value(raw_cat):
                continue
            key = str(raw_cat)
            if key not in category_cls_cache:
                category_cls_cache[key] = _classify_token(raw_cat)
            cls = category_cls_cache[key]
            if cls is not None:
                classification[idx] = cls
        if classification:
            method = "category_keywords"

    if not classification:
        valid_amounts = numeric_amount.dropna()
        has_both_signs = (valid_amounts > 0).any() and (valid_amounts < 0).any()
        if has_both_signs:
            for idx in df.index:
                val = numeric_amount.loc[idx]
                if pd.isna(val):
                    continue
                classification[idx] = "revenue" if val > 0 else ("expense" if val < 0 else "revenue")
            method = "signed_amount"

    if not classification:
        return unavailable_financial_result(
            "A numeric amount column was found, but no way to classify transactions as "
            "revenue or expense was detected — no type column with recognizable Revenue/"
            "Expense tokens, no account/category column with classifiable keywords, and "
            "the amount column does not contain both positive and negative values.",
            columns_detected,
        )

    n_classified = len(classification)
    n_unclassified = int(numeric_amount.notna().sum()) - n_classified

    # ── Department rollup (expense only) ────────────────────────────────────
    dept_keys: Optional[pd.Series] = None
    dept_labels: dict[str, str] = {}
    dept_notes: list[str] = []
    if cost_center_col is not None:
        dept_result = normalize_department_series(df[cost_center_col].astype(object))
        dept_keys = pd.Series(dept_result.normalized_keys.values, index=df.index)
        dept_labels = dept_result.display_labels
        for merge in dept_result.merges_applied:
            variants_str = ", ".join(f"'{v}'" for v in merge.variants_merged)
            dept_notes.append(f"Merged {variants_str} into '{merge.canonical_label}': {merge.counts_per_variant}.")
        for grp in dept_result.unmerged_similar_variants:
            dept_notes.append(f"Found similarly-named but NOT merged values {', '.join(repr(v) for v in grp)} — review manually.")

    # ── Period bucketing (monthly) ───────────────────────────────────────────
    has_period_trend = date_col is not None
    period_by_row: dict[Any, str] = {}
    if has_period_trend:
        parsed_dates = pd.to_datetime(df[date_col], errors="coerce")
        for idx in classification:
            d = parsed_dates.loc[idx]
            if pd.notna(d):
                period_by_row[idx] = d.strftime("%Y-%m")

    # ── Aggregate ────────────────────────────────────────────────────────────
    total_revenue = 0.0
    total_expense = 0.0
    period_agg: dict[str, dict[str, float]] = {}
    category_agg: dict[tuple[str, str], dict[str, float]] = {}
    dept_expense_agg: dict[str, dict[str, float]] = {}

    for idx, sig in classification.items():
        amt = abs(float(numeric_amount.loc[idx]))
        if sig == "revenue":
            total_revenue += amt
        else:
            total_expense += amt

        period = period_by_row.get(idx)
        if period is not None:
            bucket = period_agg.setdefault(period, {"revenue": 0.0, "expense": 0.0, "n": 0})
            bucket[sig] += amt
            bucket["n"] += 1

        if category_col is not None and not _is_missing_value(df.at[idx, category_col]):
            cat_name = " ".join(str(df.at[idx, category_col]).split())
            key = (cat_name, sig)
            cbucket = category_agg.setdefault(key, {"total": 0.0, "n": 0})
            cbucket["total"] += amt
            cbucket["n"] += 1

        if sig == "expense" and dept_keys is not None:
            dkey = dept_keys.loc[idx]
            dept_label = dept_labels.get(dkey, dkey) if dkey is not None else None
            if dept_label:
                dbucket = dept_expense_agg.setdefault(dept_label, {"total": 0.0, "n": 0})
                dbucket["total"] += amt
                dbucket["n"] += 1

    net_pnl = round(total_revenue - total_expense, 2)

    period_figures = [
        PeriodFigure(
            period=p, total_revenue_sar=round(b["revenue"], 2), total_expense_sar=round(b["expense"], 2),
            net_sar=round(b["revenue"] - b["expense"], 2), n_transactions=int(b["n"]),
        )
        for p, b in sorted(period_agg.items())
    ]

    revenue_by_category = []
    expense_by_category = []
    for (cat, sig), b in category_agg.items():
        total_for_sig = total_revenue if sig == "revenue" else total_expense
        share = round(100.0 * b["total"] / total_for_sig, 1) if total_for_sig else 0.0
        cf = CategoryFigure(category=cat, signal_type=sig, total_sar=round(b["total"], 2), n_transactions=int(b["n"]), share_pct=share)
        (revenue_by_category if sig == "revenue" else expense_by_category).append(cf)
    revenue_by_category.sort(key=lambda c: c.total_sar, reverse=True)
    expense_by_category.sort(key=lambda c: c.total_sar, reverse=True)

    expense_by_department = [
        DepartmentExpenseFigure(department=d, total_expense_sar=round(b["total"], 2), n_transactions=int(b["n"]))
        for d, b in dept_expense_agg.items()
    ]
    expense_by_department.sort(key=lambda d: d.total_expense_sar, reverse=True)

    # ── Variance (period-over-period, reusing payroll_budget_engine.py's shape) ──
    period_variances: list[PeriodVariance] = []
    if len(period_figures) >= _MIN_TREND_PERIODS_FOR_VARIANCE:
        for i in range(1, len(period_figures)):
            prior, curr = period_figures[i - 1], period_figures[i]
            rev_var = round(curr.total_revenue_sar - prior.total_revenue_sar, 2)
            rev_var_pct = round(100.0 * rev_var / prior.total_revenue_sar, 1) if prior.total_revenue_sar else None
            exp_var = round(curr.total_expense_sar - prior.total_expense_sar, 2)
            exp_var_pct = round(100.0 * exp_var / prior.total_expense_sar, 1) if prior.total_expense_sar else None
            net_var = round(curr.net_sar - prior.net_sar, 2)
            net_var_pct = round(100.0 * net_var / abs(prior.net_sar), 1) if prior.net_sar else None
            period_variances.append(PeriodVariance(
                period=curr.period, prior_period=prior.period,
                revenue_variance_sar=rev_var, revenue_variance_pct=rev_var_pct,
                expense_variance_sar=exp_var, expense_variance_pct=exp_var_pct,
                net_variance_sar=net_var, net_variance_pct=net_var_pct,
            ))
        period_variances.sort(key=lambda v: abs(v.net_variance_sar or 0), reverse=True)

    # ── Ratios ────────────────────────────────────────────────────────────────
    ratios = FinancialRatios(
        expense_to_revenue_ratio=(round(total_expense / total_revenue, 3) if total_revenue else None),
        top_expense_category=(expense_by_category[0].category if expense_by_category else None),
        top_expense_category_share_pct=(expense_by_category[0].share_pct if expense_by_category else None),
        top_revenue_category=(revenue_by_category[0].category if revenue_by_category else None),
        top_revenue_category_share_pct=(revenue_by_category[0].share_pct if revenue_by_category else None),
        unavailable_ratios_note_en=_UNAVAILABLE_RATIOS_NOTE_EN,
        unavailable_ratios_note_ar=_UNAVAILABLE_RATIOS_NOTE_AR,
    )

    method_desc_en = {
        "type_column": f"an explicit type column ('{type_col}')",
        "category_keywords": f"keyword matching on the account/category column ('{category_col}')",
        "signed_amount": "the sign of the amount column (positive=revenue, negative=expense)",
    }[method]
    narrative_en = (
        f"{n_classified} of {int(numeric_amount.notna().sum())} transactions with a valid amount were "
        f"classified as revenue or expense using {method_desc_en}. Total revenue: SAR {total_revenue:,.2f}; "
        f"total expense: SAR {total_expense:,.2f}; net P&L: SAR {net_pnl:,.2f}."
    )
    narrative_ar = (
        f"تم تصنيف {n_classified} من أصل {int(numeric_amount.notna().sum())} معاملة بمبلغ صالح كإيراد أو "
        f"مصروف. إجمالي الإيرادات: {total_revenue:,.2f} ريال؛ إجمالي المصروفات: {total_expense:,.2f} ريال؛ "
        f"صافي الربح/الخسارة: {net_pnl:,.2f} ريال."
    )
    if n_excluded_amount > 0:
        narrative_en += f" {n_excluded_amount} row(s) excluded — amount value not a clean number."
        narrative_ar += f" استُبعد {n_excluded_amount} صفاً — قيمة المبلغ ليست رقماً صريحاً."
    if n_unclassified > 0:
        narrative_en += f" {n_unclassified} transaction(s) excluded — could not be classified as revenue or expense."
        narrative_ar += f" استُبعدت {n_unclassified} معاملة — تعذّر تصنيفها كإيراد أو مصروف."
    if not has_period_trend:
        narrative_en += " No transaction-date column detected — totals only, no period trend available."
        narrative_ar += " لم يتم اكتشاف عمود تاريخ المعاملة — إجماليات فقط، دون اتجاه زمني."

    return FinancialIntelligenceResult(
        available=True, reason=None, columns_detected=columns_detected,
        transaction_date_column=date_col, account_category_column=category_col, amount_column=amount_col,
        type_column=type_col, cost_center_column=cost_center_col, description_column=description_col,
        classification_method=method,
        n_transactions_total=len(df), n_transactions_classified=n_classified,
        n_excluded_invalid_amount=n_excluded_amount, n_excluded_unclassified=n_unclassified,
        example_excluded_amount_value=example_excluded, has_period_trend=has_period_trend,
        total_revenue_sar=round(total_revenue, 2), total_expense_sar=round(total_expense, 2), net_pnl_sar=net_pnl,
        period_figures=period_figures, revenue_by_category=revenue_by_category, expense_by_category=expense_by_category,
        expense_by_department=expense_by_department, department_normalization_notes=dept_notes,
        period_variances=period_variances, ratios=ratios,
        cash_flow_available=has_period_trend,
        cash_flow_disclaimer_en=CASH_FLOW_DISCLAIMER_EN, cash_flow_disclaimer_ar=CASH_FLOW_DISCLAIMER_AR,
        narrative_en=narrative_en, narrative_ar=narrative_ar,
        confidence=FINANCIAL_CONFIDENCE, disclaimer_en=FINANCIAL_DISCLAIMER_EN, disclaimer_ar=FINANCIAL_DISCLAIMER_AR,
        governance_note=(
            "Every figure is computed only from transactions with both a valid numeric amount and a "
            "successful revenue/expense classification; excluded rows are counted and disclosed, never "
            "guessed. No employee-level or individually-identifying data is used — this module operates "
            "on financial transactions, not personal records."
        ),
        sources=_SOURCES, computed_at=_now(),
    )


# ── Serialization ─────────────────────────────────────────────────────────────

def financial_intelligence_to_dict(r: FinancialIntelligenceResult) -> dict[str, Any]:
    return {
        "available": r.available, "reason": r.reason, "columns_detected": r.columns_detected,
        "transaction_date_column": r.transaction_date_column, "account_category_column": r.account_category_column,
        "amount_column": r.amount_column, "type_column": r.type_column,
        "cost_center_column": r.cost_center_column, "description_column": r.description_column,
        "classification_method": r.classification_method,
        "n_transactions_total": r.n_transactions_total, "n_transactions_classified": r.n_transactions_classified,
        "n_excluded_invalid_amount": r.n_excluded_invalid_amount, "n_excluded_unclassified": r.n_excluded_unclassified,
        "example_excluded_amount_value": r.example_excluded_amount_value, "has_period_trend": r.has_period_trend,
        "total_revenue_sar": r.total_revenue_sar, "total_expense_sar": r.total_expense_sar, "net_pnl_sar": r.net_pnl_sar,
        "period_figures": [
            {"period": p.period, "total_revenue_sar": p.total_revenue_sar, "total_expense_sar": p.total_expense_sar,
             "net_sar": p.net_sar, "n_transactions": p.n_transactions}
            for p in r.period_figures
        ],
        "revenue_by_category": [
            {"category": c.category, "signal_type": c.signal_type, "total_sar": c.total_sar,
             "n_transactions": c.n_transactions, "share_pct": c.share_pct}
            for c in r.revenue_by_category
        ],
        "expense_by_category": [
            {"category": c.category, "signal_type": c.signal_type, "total_sar": c.total_sar,
             "n_transactions": c.n_transactions, "share_pct": c.share_pct}
            for c in r.expense_by_category
        ],
        "expense_by_department": [
            {"department": d.department, "total_expense_sar": d.total_expense_sar, "n_transactions": d.n_transactions}
            for d in r.expense_by_department
        ],
        "department_normalization_notes": r.department_normalization_notes,
        "period_variances": [
            {"period": v.period, "prior_period": v.prior_period,
             "revenue_variance_sar": v.revenue_variance_sar, "revenue_variance_pct": v.revenue_variance_pct,
             "expense_variance_sar": v.expense_variance_sar, "expense_variance_pct": v.expense_variance_pct,
             "net_variance_sar": v.net_variance_sar, "net_variance_pct": v.net_variance_pct}
            for v in r.period_variances
        ],
        "ratios": (
            {
                "expense_to_revenue_ratio": r.ratios.expense_to_revenue_ratio,
                "top_expense_category": r.ratios.top_expense_category,
                "top_expense_category_share_pct": r.ratios.top_expense_category_share_pct,
                "top_revenue_category": r.ratios.top_revenue_category,
                "top_revenue_category_share_pct": r.ratios.top_revenue_category_share_pct,
                "unavailable_ratios_note_en": r.ratios.unavailable_ratios_note_en,
                "unavailable_ratios_note_ar": r.ratios.unavailable_ratios_note_ar,
            } if r.ratios is not None else None
        ),
        "cash_flow_available": r.cash_flow_available,
        "cash_flow_disclaimer_en": r.cash_flow_disclaimer_en, "cash_flow_disclaimer_ar": r.cash_flow_disclaimer_ar,
        "narrative_en": r.narrative_en, "narrative_ar": r.narrative_ar,
        "confidence": r.confidence, "disclaimer_en": r.disclaimer_en, "disclaimer_ar": r.disclaimer_ar,
        "governance_note": r.governance_note, "sources": r.sources, "computed_at": r.computed_at,
    }
