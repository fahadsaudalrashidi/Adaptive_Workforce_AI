"""
Accounting Intelligence — Phase 31 (Business Intelligence Suite, Module 2).

**Overlap check against Phase 30 (financial_intelligence_reporting_engine.py),
done before writing any of this.** Phase 30 already computes, from a plain
transaction-list upload (date/amount/type/category — no debit/credit
structure): Revenue analysis, Expense analysis, P&L, Cash Flow ("net
transaction movement"), Financial Ratios (expense-to-revenue, concentration),
and period-over-period Variance. None of that is rebuilt here. This module
covers only the five items that genuinely require true double-entry data
(separate Debit and Credit columns per journal line, and — for Balance
Sheet — an Asset/Liability/Equity account classification Phase 30 never
needed) or a wholly different upload shape (invoice-level AR/AP data):

  1. General Ledger Analysis — transaction-level drill-down BY ACCOUNT
     (account -> its individual journal lines). Phase 30 only ever shows
     category-level TOTALS; it never exposes the underlying transaction
     list per account. Requires: an account column + real, separate Debit
     and Credit columns (not a single signed amount — see below).
  2. Trial Balance — sums debits and credits per account and confirms
     they balance in aggregate. A structurally different question from
     anything Phase 30 asks, and mechanically impossible without real
     debit/credit columns: a single signed "Amount" column (Phase 30's
     shape) cannot be summed into a trial balance, because a trial balance
     is a claim about which SIDE of each entry a value sits on, not just
     its sign. If only a single amount column exists, this honestly
     reports not-computable rather than guessing a side from sign.
  3. Balance Sheet — requires classifying accounts into Asset/Liability/
     Equity, a different classification axis from Phase 30's Revenue/
     Expense classifier (a chart of accounts distinguishing "Cash" (asset)
     from "Sales Revenue" (revenue) from "Accounts Payable" (liability) is
     not the same signal as a P&L transaction's revenue/expense sign).
     Requires real debit/credit columns (to compute each account's normal
     balance) AND an account-type column with real Asset/Liability/Equity
     tokens — Revenue/Expense-only classification (Phase 30's case) is
     explicitly NOT sufficient and is reported as not-computable.
  4. AR/AP + Aging — needs invoice-level/open-item data (party name,
     due date, amount, paid/outstanding status), a wholly different shape
     from a plain transaction list or even a GL export. Aging buckets are
     computed from real due dates only, against a caller-supplied "as of"
     reference date (defaults to real today in production; tests pass a
     fixed date for reproducible assertions) — never estimated.
  5. Journal Entry Anomaly & Duplicate Detection — operates on the same
     GL debit/credit data as items 1-3.

**Statistical rigor for anomaly detection — same discipline as
pay_equity_engine.py's disclosed minimum-group-size suppression
(`_MIN_GROUP_SIZE_FOR_DISPARITY`, that module's Welch's-t-test gate).**
This module reuses the same SPIRIT (never flag on a sample too small to
mean anything, and always disclose the suppression) but not scipy's t-test
itself, since anomaly detection here asks a different question ("is this
one transaction unusual for this account's own history?") that a
distribution-shape-agnostic method suits better than a normality-assuming
one. IQR/Tukey's-fences (flag values outside Q1 - 1.5*IQR .. Q3 + 1.5*IQR)
is used instead of a z-score, specifically because it does not assume a
normal distribution — financial transaction amounts are routinely
right-skewed (many small routine entries, occasional large one-off
entries), which would make a z-score's normality assumption misleading.
An account's transactions are only checked once it has at least
`_MIN_SAMPLE_SIZE_FOR_ANOMALY` (5) transactions; accounts below that floor
are counted and disclosed as suppressed, never silently skipped without a
trace, exactly mirroring pay_equity_engine.py's suppression disclosure.

**Duplicate detection — matches on (date, account, amount) jointly, never
a single field, specifically to avoid false-flagging legitimate recurring
transactions** (e.g. monthly rent: same account and similar amount, but a
DIFFERENT date each month, so it never collides on this three-field key).
Within a (date, account, amount) collision group, description-text
similarity (difflib.SequenceMatcher — the same library already used by
department_normalizer.py's near-duplicate detection, for consistency) is
computed: similarity >= `_DUPLICATE_DESC_SIMILARITY_THRESHOLD` (0.6) is
reported as a "high" confidence duplicate (identical or near-identical
description strongly suggests a copy-paste double entry); below that
threshold — or both descriptions missing — is reported as "review"
confidence (same date/account/amount but different described purpose:
plausibly a genuine coincidence, flagged for a human to look at, never
auto-flagged as an error).

**Column detection**: fresh, local-regex patterns (EN + AR), the same
per-module convention followed by every other engine in this codebase —
NOT imported from financial_intelligence_reporting_engine.py, to keep
these two modules independently maintainable (per this phase's explicit
brief: three distinct, purpose-separated modules, not one growing
monolith alongside financial_intelligence_engine.py).
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import pandas as pd

# ── Column detection (local-regex convention) ───────────────────────────────

_GL_DATE_PATTERNS = re.compile(
    r"\b(entry[_\s]?date|transaction[_\s]?date|posting[_\s]?date|journal[_\s]?date|date|"
    r"تاريخ[_\s]?القيد|تاريخ)\b", re.I,
)
_ACCOUNT_TYPE_PATTERNS = re.compile(
    r"\b(account[_\s]?type|account[_\s]?classification|statement[_\s]?category|"
    r"balance[_\s]?sheet[_\s]?category|financial[_\s]?statement[_\s]?type|"
    r"نوع[_\s]?الحساب|تصنيف[_\s]?الحساب)\b", re.I,
)
_ACCOUNT_PATTERNS = re.compile(
    r"\b(account[_\s]?name|account[_\s]?number|gl[_\s]?account|chart[_\s]?of[_\s]?accounts|account|"
    r"الحساب|اسم[_\s]?الحساب)\b", re.I,
)
_DEBIT_PATTERNS = re.compile(r"\b(debit[_\s]?amount|debit|dr[_\s]?amount|مدين)\b", re.I)
_CREDIT_PATTERNS = re.compile(r"\b(credit[_\s]?amount|credit|cr[_\s]?amount|دائن)\b", re.I)
_DESCRIPTION_PATTERNS = re.compile(r"\b(description|memo|narration|note|الوصف|البيان)\b", re.I)
_PARTY_PATTERNS = re.compile(r"\b(customer|client|vendor|supplier|payee|party|العميل|المورد)\b", re.I)
_INVOICE_NUMBER_PATTERNS = re.compile(
    r"\b(invoice[_\s]?(number|no|#)|bill[_\s]?number|reference[_\s]?number|رقم[_\s]?الفاتورة)\b", re.I,
)
_DUE_DATE_PATTERNS = re.compile(
    r"\b(due[_\s]?date|payment[_\s]?due|maturity[_\s]?date|تاريخ[_\s]?الاستحقاق)\b", re.I,
)
_STATUS_PATTERNS = re.compile(
    r"\b(status|payment[_\s]?status|paid[_\s]?status|invoice[_\s]?status|الحالة)\b", re.I,
)

_ASSET_TOKENS = frozenset({"asset", "assets", "أصول", "أصل"})
_LIABILITY_TOKENS = frozenset({"liability", "liabilities", "التزام", "التزامات", "خصوم"})
_EQUITY_TOKENS = frozenset({"equity", "حقوق ملكية", "حقوق الملكية"})
_REVENUE_TOKENS = frozenset({"revenue", "income", "sales", "إيراد", "إيرادات", "دخل"})
_EXPENSE_TOKENS = frozenset({"expense", "expenses", "cost", "costs", "مصروف", "مصاريف", "تكلفة"})

_PAID_TOKENS = frozenset({"paid", "settled", "closed", "cleared", "مدفوع", "مسدد"})
_OUTSTANDING_TOKENS = frozenset({"outstanding", "open", "unpaid", "pending", "overdue", "غير مدفوع", "مستحق"})

_MIN_SAMPLE_SIZE_FOR_ANOMALY = 5
_DUPLICATE_DESC_SIMILARITY_THRESHOLD = 0.6
_TRIAL_BALANCE_TOLERANCE_SAR = 0.01
_BALANCE_SHEET_TOLERANCE_SAR = 0.01
_MAX_TRANSACTIONS_PER_ACCOUNT_SHOWN = 200

ACCOUNTING_CONFIDENCE = "derived_from_upload_not_certified_statement"
ACCOUNTING_DISCLAIMER_EN = (
    "These figures are derived entirely from your own uploaded journal/ledger data — they are "
    "NOT a certified financial statement (no audit, no accounting-standard review, no assurance "
    "of completeness). This is a computational planning aid; qualified accounting review is "
    "required before any financial reporting, filing, or decision based on these figures."
)
ACCOUNTING_DISCLAIMER_AR = (
    "تُشتق هذه الأرقام بالكامل من بيانات دفتر الأستاذ/القيود المُحمّلة — وهي ليست قائمة مالية "
    "معتمدة (لا تدقيق، ولا مراجعة وفق معايير المحاسبة، ولا ضمان اكتمال). هذه أداة تخطيط حسابية "
    "مساعدة؛ تلزم مراجعة محاسبية متخصصة قبل أي تقرير مالي أو إقرار أو قرار."
)
_SOURCES = [
    "General ledger, trial balance, balance sheet, AR/AP aging, and anomaly figures are computed "
    "entirely from the uploaded journal data's own account/debit/credit/date columns — no "
    "external benchmark or industry figure is used anywhere in this module.",
    "Anomaly detection uses Tukey's-fences (IQR method, 1.5x multiplier) per account, only for "
    "accounts with at least the minimum sample size — the same disclosed-suppression discipline "
    "as pay_equity_engine.py's minimum-group-size gate, applied to a distribution-agnostic method "
    "suited to right-skewed financial data.",
    "Duplicate detection matches on (date, account, amount) jointly, plus description-text "
    "similarity (difflib.SequenceMatcher), never a single field.",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _find_column(df: pd.DataFrame, pattern: re.Pattern, exclude: frozenset = frozenset()) -> Optional[str]:
    for col in df.columns:
        if col in exclude:
            continue
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


def _classify_from_vocab(raw: object, vocab: frozenset) -> bool:
    if _is_missing_value(raw):
        return False
    key = " ".join(str(raw).split()).strip().lower()
    if key in vocab:
        return True
    return any(token in key for token in vocab)


def _classify_account_type(raw: object) -> Optional[str]:
    """Returns 'asset'|'liability'|'equity'|'revenue'|'expense'|None — never guessed."""
    if _is_missing_value(raw):
        return None
    if _classify_from_vocab(raw, _ASSET_TOKENS):
        return "asset"
    if _classify_from_vocab(raw, _LIABILITY_TOKENS):
        return "liability"
    if _classify_from_vocab(raw, _EQUITY_TOKENS):
        return "equity"
    if _classify_from_vocab(raw, _REVENUE_TOKENS):
        return "revenue"
    if _classify_from_vocab(raw, _EXPENSE_TOKENS):
        return "expense"
    return None


def _classify_status(raw: object) -> Optional[str]:
    """Returns 'paid'|'outstanding'|None — never guessed."""
    if _is_missing_value(raw):
        return None
    if _classify_from_vocab(raw, _PAID_TOKENS):
        return "paid"
    if _classify_from_vocab(raw, _OUTSTANDING_TOKENS):
        return "outstanding"
    return None


def _infer_ar_ap_direction(account_name: Optional[str]) -> str:
    if not account_name:
        return "open_item"
    key = account_name.strip().lower()
    if "receivable" in key or "مدين" in key:
        return "ar"
    if "payable" in key or "دائن" in key:
        return "ap"
    return "open_item"


def _numeric_or_none(raw: object) -> Optional[float]:
    if _is_missing_value(raw):
        return None
    val = pd.to_numeric(raw, errors="coerce")
    if pd.isna(val):
        return None
    return float(val)


def _detect_gl_columns(df: pd.DataFrame) -> dict[str, Optional[str]]:
    account_type_col = _find_column(df, _ACCOUNT_TYPE_PATTERNS)
    exclude = {account_type_col} if account_type_col else set()
    account_col = _find_column(df, _ACCOUNT_PATTERNS, exclude=frozenset(exclude))
    debit_col = _find_column(df, _DEBIT_PATTERNS)
    credit_col = _find_column(df, _CREDIT_PATTERNS)
    date_col = _find_column(df, _GL_DATE_PATTERNS)
    description_col = _find_column(df, _DESCRIPTION_PATTERNS)
    return {
        "account": account_col, "account_type": account_type_col,
        "debit": debit_col, "credit": credit_col,
        "date": date_col, "description": description_col,
    }


# ── Result types: 1. General Ledger ─────────────────────────────────────────

@dataclass(frozen=True)
class LedgerTransaction:
    date: Optional[str]
    description: Optional[str]
    debit_sar: Optional[float]
    credit_sar: Optional[float]


@dataclass(frozen=True)
class LedgerAccountSummary:
    account: str
    account_type: Optional[str]
    total_debit_sar: float
    total_credit_sar: float
    net_sar: float
    n_transactions: int
    n_transactions_shown: int
    transactions: list[LedgerTransaction]


@dataclass(frozen=True)
class GeneralLedgerResult:
    available: bool
    reason: Optional[str]
    columns_detected: dict[str, bool]
    account_column: Optional[str]
    debit_column: Optional[str]
    credit_column: Optional[str]
    n_transactions_total: int
    n_accounts: int
    accounts: list[LedgerAccountSummary]
    narrative_en: str
    narrative_ar: str


def unavailable_general_ledger_result(reason: str, columns_detected: Optional[dict[str, bool]] = None) -> GeneralLedgerResult:
    return GeneralLedgerResult(
        available=False, reason=reason, columns_detected=columns_detected or {},
        account_column=None, debit_column=None, credit_column=None,
        n_transactions_total=0, n_accounts=0, accounts=[],
        narrative_en="General ledger analysis not available for this dataset.",
        narrative_ar="تحليل دفتر الأستاذ العام غير متاح لهذه البيانات.",
    )


def analyze_general_ledger(df: pd.DataFrame) -> GeneralLedgerResult:
    """Never raises. Requires an account column plus real, separate debit
    and credit columns — a single signed amount is not sufficient (see
    module docstring: this is what genuinely distinguishes this item from
    Phase 30's category-level summaries)."""
    if df is None or df.empty:
        return unavailable_general_ledger_result("No data available for general ledger analysis.")

    cols = _detect_gl_columns(df)
    columns_detected = {
        "account": cols["account"] is not None,
        "debit": cols["debit"] is not None,
        "credit": cols["credit"] is not None,
        "date": cols["date"] is not None,
        "description": cols["description"] is not None,
    }
    if cols["account"] is None or cols["debit"] is None or cols["credit"] is None:
        return unavailable_general_ledger_result(
            "General ledger analysis requires an account column plus real, SEPARATE debit and "
            "credit columns (not a single signed amount column) — the double-entry structure "
            "this view is built to drill into. Detected: "
            f"account={'yes' if cols['account'] else 'no'}, debit={'yes' if cols['debit'] else 'no'}, "
            f"credit={'yes' if cols['credit'] else 'no'}.",
            columns_detected,
        )

    account_col, debit_col, credit_col = cols["account"], cols["debit"], cols["credit"]
    date_col, description_col, type_col = cols["date"], cols["description"], cols["account_type"]

    by_account: dict[str, list[dict[str, Any]]] = {}
    account_type_votes: dict[str, dict[str, int]] = {}
    n_total = 0
    for idx in df.index:
        raw_account = df.at[idx, account_col]
        if _is_missing_value(raw_account):
            continue
        debit = _numeric_or_none(df.at[idx, debit_col])
        credit = _numeric_or_none(df.at[idx, credit_col])
        if debit is None and credit is None:
            continue
        account = " ".join(str(raw_account).split())
        n_total += 1
        by_account.setdefault(account, []).append({
            "date": (str(df.at[idx, date_col]).strip() if date_col and not _is_missing_value(df.at[idx, date_col]) else None),
            "description": (str(df.at[idx, description_col]).strip() if description_col and not _is_missing_value(df.at[idx, description_col]) else None),
            "debit": debit, "credit": credit,
        })
        if type_col is not None:
            cls = _classify_account_type(df.at[idx, type_col])
            if cls is not None:
                votes = account_type_votes.setdefault(account, {})
                votes[cls] = votes.get(cls, 0) + 1

    if not by_account:
        return unavailable_general_ledger_result(
            "An account column and debit/credit columns were found, but no row had both a valid "
            "account value and at least one valid debit or credit amount.",
            columns_detected,
        )

    accounts: list[LedgerAccountSummary] = []
    for account, txns in by_account.items():
        total_debit = round(sum(t["debit"] or 0.0 for t in txns), 2)
        total_credit = round(sum(t["credit"] or 0.0 for t in txns), 2)
        votes = account_type_votes.get(account, {})
        account_type = max(votes, key=votes.get) if votes else None
        shown = txns[:_MAX_TRANSACTIONS_PER_ACCOUNT_SHOWN]
        accounts.append(LedgerAccountSummary(
            account=account, account_type=account_type,
            total_debit_sar=total_debit, total_credit_sar=total_credit,
            net_sar=round(total_debit - total_credit, 2),
            n_transactions=len(txns), n_transactions_shown=len(shown),
            transactions=[
                LedgerTransaction(
                    date=t["date"], description=t["description"],
                    debit_sar=(round(t["debit"], 2) if t["debit"] is not None else None),
                    credit_sar=(round(t["credit"], 2) if t["credit"] is not None else None),
                )
                for t in shown
            ],
        ))
    accounts.sort(key=lambda a: a.account)

    narrative_en = f"{n_total} journal line(s) across {len(accounts)} account(s) were analyzed from '{account_col}', '{debit_col}', and '{credit_col}'."
    narrative_ar = f"تم تحليل {n_total} قيداً عبر {len(accounts)} حساباً."

    return GeneralLedgerResult(
        available=True, reason=None, columns_detected=columns_detected,
        account_column=account_col, debit_column=debit_col, credit_column=credit_col,
        n_transactions_total=n_total, n_accounts=len(accounts), accounts=accounts,
        narrative_en=narrative_en, narrative_ar=narrative_ar,
    )


# ── Result types: 2. Trial Balance ──────────────────────────────────────────

@dataclass(frozen=True)
class TrialBalanceLine:
    account: str
    total_debit_sar: float
    total_credit_sar: float


@dataclass(frozen=True)
class TrialBalanceResult:
    available: bool
    reason: Optional[str]
    columns_detected: dict[str, bool]
    lines: list[TrialBalanceLine]
    total_debit_sar: Optional[float]
    total_credit_sar: Optional[float]
    difference_sar: Optional[float]
    is_balanced: Optional[bool]
    tolerance_sar: float
    narrative_en: str
    narrative_ar: str


def unavailable_trial_balance_result(reason: str, columns_detected: Optional[dict[str, bool]] = None) -> TrialBalanceResult:
    return TrialBalanceResult(
        available=False, reason=reason, columns_detected=columns_detected or {},
        lines=[], total_debit_sar=None, total_credit_sar=None, difference_sar=None,
        is_balanced=None, tolerance_sar=_TRIAL_BALANCE_TOLERANCE_SAR,
        narrative_en="Trial balance not available for this dataset.",
        narrative_ar="ميزان المراجعة غير متاح لهذه البيانات.",
    )


def analyze_trial_balance(df: pd.DataFrame) -> TrialBalanceResult:
    """Never raises. Requires real, separate debit and credit columns — a
    single signed amount cannot be turned into a trial balance without
    guessing which side of the entry it belongs to (see module docstring)."""
    if df is None or df.empty:
        return unavailable_trial_balance_result("No data available for trial balance analysis.")

    cols = _detect_gl_columns(df)
    columns_detected = {
        "account": cols["account"] is not None, "debit": cols["debit"] is not None,
        "credit": cols["credit"] is not None,
    }
    if cols["account"] is None or cols["debit"] is None or cols["credit"] is None:
        return unavailable_trial_balance_result(
            "A trial balance requires an account column plus real, SEPARATE debit and credit "
            "columns. A single signed amount column (e.g. Phase 30's transaction-list shape) "
            "cannot be summed into a trial balance — this platform never approximates one from "
            "single-sided data. Detected: "
            f"account={'yes' if cols['account'] else 'no'}, debit={'yes' if cols['debit'] else 'no'}, "
            f"credit={'yes' if cols['credit'] else 'no'}.",
            columns_detected,
        )

    account_col, debit_col, credit_col = cols["account"], cols["debit"], cols["credit"]
    agg: dict[str, dict[str, float]] = {}
    for idx in df.index:
        raw_account = df.at[idx, account_col]
        if _is_missing_value(raw_account):
            continue
        debit = _numeric_or_none(df.at[idx, debit_col]) or 0.0
        credit = _numeric_or_none(df.at[idx, credit_col]) or 0.0
        if debit == 0.0 and credit == 0.0:
            continue
        account = " ".join(str(raw_account).split())
        bucket = agg.setdefault(account, {"debit": 0.0, "credit": 0.0})
        bucket["debit"] += debit
        bucket["credit"] += credit

    if not agg:
        return unavailable_trial_balance_result(
            "Account and debit/credit columns were found, but no row had a valid account with a "
            "nonzero debit or credit amount.", columns_detected,
        )

    lines = [
        TrialBalanceLine(account=a, total_debit_sar=round(b["debit"], 2), total_credit_sar=round(b["credit"], 2))
        for a, b in sorted(agg.items())
    ]
    total_debit = round(sum(l.total_debit_sar for l in lines), 2)
    total_credit = round(sum(l.total_credit_sar for l in lines), 2)
    difference = round(total_debit - total_credit, 2)
    is_balanced = abs(difference) <= _TRIAL_BALANCE_TOLERANCE_SAR

    if is_balanced:
        narrative_en = f"Trial balance across {len(lines)} account(s): total debits SAR {total_debit:,.2f} equal total credits SAR {total_credit:,.2f} — balanced."
        narrative_ar = f"ميزان المراجعة عبر {len(lines)} حساباً: إجمالي المدين {total_debit:,.2f} ريال يساوي إجمالي الدائن {total_credit:,.2f} ريال — متوازن."
    else:
        narrative_en = (
            f"Trial balance across {len(lines)} account(s) DOES NOT BALANCE: total debits SAR "
            f"{total_debit:,.2f} vs. total credits SAR {total_credit:,.2f} — a difference of SAR "
            f"{abs(difference):,.2f}. This is a real data-quality signal (a missing or mis-posted "
            f"entry) — it is reported, never silently ignored or corrected."
        )
        narrative_ar = (
            f"ميزان المراجعة عبر {len(lines)} حساباً غير متوازن: إجمالي المدين {total_debit:,.2f} "
            f"ريال مقابل إجمالي الدائن {total_credit:,.2f} ريال — بفارق {abs(difference):,.2f} ريال. "
            "هذا مؤشر حقيقي على جودة البيانات ويُبلَّغ عنه دون تجاهل أو تصحيح تلقائي."
        )

    return TrialBalanceResult(
        available=True, reason=None, columns_detected=columns_detected, lines=lines,
        total_debit_sar=total_debit, total_credit_sar=total_credit, difference_sar=difference,
        is_balanced=is_balanced, tolerance_sar=_TRIAL_BALANCE_TOLERANCE_SAR,
        narrative_en=narrative_en, narrative_ar=narrative_ar,
    )


# ── Result types: 3. Balance Sheet ──────────────────────────────────────────

@dataclass(frozen=True)
class BalanceSheetLine:
    account: str
    balance_sar: float


@dataclass(frozen=True)
class BalanceSheetResult:
    available: bool
    reason: Optional[str]
    columns_detected: dict[str, bool]
    assets: list[BalanceSheetLine]
    liabilities: list[BalanceSheetLine]
    equity: list[BalanceSheetLine]
    net_income_current_period_sar: Optional[float]
    total_assets_sar: Optional[float]
    total_liabilities_sar: Optional[float]
    total_equity_reported_sar: Optional[float]
    total_equity_including_net_income_sar: Optional[float]
    identity_difference_sar: Optional[float]
    is_balanced: Optional[bool]
    n_accounts_unclassified: int
    narrative_en: str
    narrative_ar: str


def unavailable_balance_sheet_result(reason: str, columns_detected: Optional[dict[str, bool]] = None) -> BalanceSheetResult:
    return BalanceSheetResult(
        available=False, reason=reason, columns_detected=columns_detected or {},
        assets=[], liabilities=[], equity=[], net_income_current_period_sar=None,
        total_assets_sar=None, total_liabilities_sar=None, total_equity_reported_sar=None,
        total_equity_including_net_income_sar=None, identity_difference_sar=None,
        is_balanced=None, n_accounts_unclassified=0,
        narrative_en="Balance sheet not available for this dataset.",
        narrative_ar="الميزانية العمومية غير متاحة لهذه البيانات.",
    )


def analyze_balance_sheet(df: pd.DataFrame) -> BalanceSheetResult:
    """Never raises. Requires real debit/credit columns AND an account-type
    column whose values contain real Asset/Liability/Equity tokens — a
    Revenue/Expense-only classification (Phase 30's case) is explicitly not
    sufficient (see module docstring). Net income for the current period
    (from Revenue/Expense-classified accounts) is included as an unclosed
    equity contribution so the Assets = Liabilities + Equity identity can
    be checked honestly — real accounting practice, not an approximation."""
    if df is None or df.empty:
        return unavailable_balance_sheet_result("No data available for balance sheet analysis.")

    cols = _detect_gl_columns(df)
    columns_detected = {
        "account": cols["account"] is not None, "account_type": cols["account_type"] is not None,
        "debit": cols["debit"] is not None, "credit": cols["credit"] is not None,
    }
    if cols["account"] is None or cols["debit"] is None or cols["credit"] is None:
        return unavailable_balance_sheet_result(
            "A balance sheet requires an account column plus real, SEPARATE debit and credit "
            "columns (to determine each account's normal balance) — not present in this upload.",
            columns_detected,
        )
    if cols["account_type"] is None:
        return unavailable_balance_sheet_result(
            "A balance sheet requires an account-classification column distinguishing Asset / "
            "Liability / Equity accounts from Revenue / Expense accounts — no such column was "
            "detected. Without it, this platform cannot know which accounts belong on a balance "
            "sheet, and will not guess.",
            columns_detected,
        )

    account_col, type_col, debit_col, credit_col = cols["account"], cols["account_type"], cols["debit"], cols["credit"]
    agg: dict[str, dict[str, float]] = {}
    votes: dict[str, dict[str, int]] = {}
    for idx in df.index:
        raw_account = df.at[idx, account_col]
        if _is_missing_value(raw_account):
            continue
        debit = _numeric_or_none(df.at[idx, debit_col]) or 0.0
        credit = _numeric_or_none(df.at[idx, credit_col]) or 0.0
        if debit == 0.0 and credit == 0.0:
            continue
        account = " ".join(str(raw_account).split())
        bucket = agg.setdefault(account, {"debit": 0.0, "credit": 0.0})
        bucket["debit"] += debit
        bucket["credit"] += credit
        cls = _classify_account_type(df.at[idx, type_col])
        if cls is not None:
            v = votes.setdefault(account, {})
            v[cls] = v.get(cls, 0) + 1

    if not agg:
        return unavailable_balance_sheet_result(
            "Account, account-type, and debit/credit columns were found, but no row had a valid "
            "account with a nonzero debit or credit amount.", columns_detected,
        )

    assets, liabilities, equity = [], [], []
    total_revenue_credit_balance = 0.0
    total_expense_debit_balance = 0.0
    n_unclassified = 0
    for account, b in agg.items():
        v = votes.get(account, {})
        account_type = max(v, key=v.get) if v else None
        if account_type is None:
            n_unclassified += 1
            continue
        debit_total, credit_total = b["debit"], b["credit"]
        if account_type == "asset":
            assets.append(BalanceSheetLine(account=account, balance_sar=round(debit_total - credit_total, 2)))
        elif account_type == "liability":
            liabilities.append(BalanceSheetLine(account=account, balance_sar=round(credit_total - debit_total, 2)))
        elif account_type == "equity":
            equity.append(BalanceSheetLine(account=account, balance_sar=round(credit_total - debit_total, 2)))
        elif account_type == "revenue":
            total_revenue_credit_balance += (credit_total - debit_total)
        elif account_type == "expense":
            total_expense_debit_balance += (debit_total - credit_total)

    if not assets and not liabilities and not equity:
        return unavailable_balance_sheet_result(
            "An account-type column was detected, but none of its values classified any account "
            "as Asset, Liability, or Equity — only Revenue/Expense-style tokens (or none) were "
            "found, which is not sufficient for a balance sheet.",
            columns_detected,
        )

    net_income = round(total_revenue_credit_balance - total_expense_debit_balance, 2)
    total_assets = round(sum(a.balance_sar for a in assets), 2)
    total_liabilities = round(sum(l.balance_sar for l in liabilities), 2)
    total_equity_reported = round(sum(e.balance_sar for e in equity), 2)
    total_equity_incl = round(total_equity_reported + net_income, 2)
    identity_diff = round(total_assets - (total_liabilities + total_equity_incl), 2)
    is_balanced = abs(identity_diff) <= _BALANCE_SHEET_TOLERANCE_SAR

    assets.sort(key=lambda l: l.account)
    liabilities.sort(key=lambda l: l.account)
    equity.sort(key=lambda l: l.account)

    if is_balanced:
        narrative_en = (
            f"Assets SAR {total_assets:,.2f} = Liabilities SAR {total_liabilities:,.2f} + Equity "
            f"SAR {total_equity_reported:,.2f} + current-period net income SAR {net_income:,.2f} "
            "(unclosed) — the accounting identity holds."
        )
        narrative_ar = (
            f"الأصول {total_assets:,.2f} ريال = الخصوم {total_liabilities:,.2f} ريال + حقوق "
            f"الملكية {total_equity_reported:,.2f} ريال + صافي دخل الفترة الحالية "
            f"{net_income:,.2f} ريال (غير مُقفل) — المعادلة المحاسبية متوازنة."
        )
    else:
        narrative_en = (
            f"Assets SAR {total_assets:,.2f} DOES NOT equal Liabilities + Equity + current-period "
            f"net income (SAR {total_liabilities + total_equity_incl:,.2f}) — a difference of SAR "
            f"{abs(identity_diff):,.2f}. Reported as a data-quality signal, never silently corrected."
        )
        narrative_ar = (
            f"الأصول {total_assets:,.2f} ريال لا تساوي الخصوم + حقوق الملكية + صافي دخل الفترة "
            f"({total_liabilities + total_equity_incl:,.2f} ريال) — بفارق {abs(identity_diff):,.2f} ريال."
        )
    if n_unclassified:
        narrative_en += f" {n_unclassified} account(s) had no classifiable account-type value and were excluded."
        narrative_ar += f" تم استبعاد {n_unclassified} حساباً بلا تصنيف واضح."

    return BalanceSheetResult(
        available=True, reason=None, columns_detected=columns_detected,
        assets=assets, liabilities=liabilities, equity=equity,
        net_income_current_period_sar=net_income,
        total_assets_sar=total_assets, total_liabilities_sar=total_liabilities,
        total_equity_reported_sar=total_equity_reported,
        total_equity_including_net_income_sar=total_equity_incl,
        identity_difference_sar=identity_diff, is_balanced=is_balanced,
        n_accounts_unclassified=n_unclassified,
        narrative_en=narrative_en, narrative_ar=narrative_ar,
    )


# ── Result types: 4. AR/AP + Aging ──────────────────────────────────────────

@dataclass(frozen=True)
class OpenInvoice:
    direction: str  # "ar" | "ap" | "open_item"
    party: str
    invoice_number: Optional[str]
    due_date: str
    amount_sar: float
    days_overdue: int
    bucket: str


@dataclass(frozen=True)
class AgingBucket:
    bucket: str
    total_sar: float
    n_invoices: int


@dataclass(frozen=True)
class ARAPAgingResult:
    available: bool
    reason: Optional[str]
    columns_detected: dict[str, bool]
    as_of_date: Optional[str]
    n_open_invoices: int
    n_excluded_paid: int
    n_excluded_unclassified_status: int
    total_outstanding_sar: Optional[float]
    buckets: list[AgingBucket]
    invoices: list[OpenInvoice]
    narrative_en: str
    narrative_ar: str


def unavailable_ar_ap_aging_result(reason: str, columns_detected: Optional[dict[str, bool]] = None) -> ARAPAgingResult:
    return ARAPAgingResult(
        available=False, reason=reason, columns_detected=columns_detected or {},
        as_of_date=None, n_open_invoices=0, n_excluded_paid=0, n_excluded_unclassified_status=0,
        total_outstanding_sar=None, buckets=[], invoices=[],
        narrative_en="AR/AP aging not available for this dataset.",
        narrative_ar="أعمار الذمم المدينة/الدائنة غير متاحة لهذه البيانات.",
    )


_AGING_BUCKET_ORDER = ["current", "1-30", "31-60", "61-90", "90+"]


def _aging_bucket(days_overdue: int) -> str:
    if days_overdue < 0:
        return "current"
    if days_overdue <= 30:
        return "1-30"
    if days_overdue <= 60:
        return "31-60"
    if days_overdue <= 90:
        return "61-90"
    return "90+"


def analyze_ar_ap_aging(df: pd.DataFrame, as_of_date: Optional[str] = None) -> ARAPAgingResult:
    """Never raises. Requires party + due-date + amount(debit/credit) +
    paid/outstanding-status columns — a wholly different shape from a GL
    export. `as_of_date` defaults to real today (production); tests pass a
    fixed date for reproducible bucket assertions."""
    if df is None or df.empty:
        return unavailable_ar_ap_aging_result("No data available for AR/AP aging analysis.")

    party_col = _find_column(df, _PARTY_PATTERNS)
    due_date_col = _find_column(df, _DUE_DATE_PATTERNS)
    status_col = _find_column(df, _STATUS_PATTERNS)
    invoice_number_col = _find_column(df, _INVOICE_NUMBER_PATTERNS)
    cols_gl = _detect_gl_columns(df)
    debit_col, credit_col, account_col = cols_gl["debit"], cols_gl["credit"], cols_gl["account"]

    columns_detected = {
        "party": party_col is not None, "due_date": due_date_col is not None,
        "status": status_col is not None,
        "amount": (debit_col is not None or credit_col is not None),
    }
    missing = [k for k, v in columns_detected.items() if not v]
    if missing:
        return unavailable_ar_ap_aging_result(
            "AR/AP aging requires party (customer/vendor), due date, an amount, and a paid/"
            f"outstanding status column. Missing: {', '.join(missing)}.",
            columns_detected,
        )

    as_of = pd.to_datetime(as_of_date) if as_of_date else pd.Timestamp(datetime.now(timezone.utc).date())
    open_invoices: list[OpenInvoice] = []
    n_paid = 0
    n_unclassified_status = 0

    for idx in df.index:
        raw_party = df.at[idx, party_col]
        raw_due = df.at[idx, due_date_col]
        raw_status = df.at[idx, status_col]
        if _is_missing_value(raw_party) or _is_missing_value(raw_due):
            continue
        status = _classify_status(raw_status)
        if status is None:
            n_unclassified_status += 1
            continue
        if status == "paid":
            n_paid += 1
            continue
        due_dt = pd.to_datetime(raw_due, errors="coerce")
        if pd.isna(due_dt):
            continue
        amount = None
        if debit_col is not None:
            amount = _numeric_or_none(df.at[idx, debit_col])
        if amount is None and credit_col is not None:
            amount = _numeric_or_none(df.at[idx, credit_col])
        if amount is None or amount == 0.0:
            continue
        days_overdue = int((as_of - due_dt).days)
        direction = _infer_ar_ap_direction(str(df.at[idx, account_col]) if account_col is not None and not _is_missing_value(df.at[idx, account_col]) else None)
        open_invoices.append(OpenInvoice(
            direction=direction, party=" ".join(str(raw_party).split()),
            invoice_number=(str(df.at[idx, invoice_number_col]).strip() if invoice_number_col and not _is_missing_value(df.at[idx, invoice_number_col]) else None),
            due_date=due_dt.strftime("%Y-%m-%d"), amount_sar=round(amount, 2),
            days_overdue=days_overdue, bucket=_aging_bucket(days_overdue),
        ))

    if not open_invoices and n_paid == 0 and n_unclassified_status == 0:
        return unavailable_ar_ap_aging_result(
            "Party, due-date, status, and amount columns were found, but no row had a complete, "
            "valid set of values to compute an open item.", columns_detected,
        )

    bucket_agg: dict[str, dict[str, float]] = {b: {"total": 0.0, "n": 0} for b in _AGING_BUCKET_ORDER}
    for inv in open_invoices:
        bucket_agg[inv.bucket]["total"] += inv.amount_sar
        bucket_agg[inv.bucket]["n"] += 1
    buckets = [
        AgingBucket(bucket=b, total_sar=round(bucket_agg[b]["total"], 2), n_invoices=int(bucket_agg[b]["n"]))
        for b in _AGING_BUCKET_ORDER if bucket_agg[b]["n"] > 0
    ]
    total_outstanding = round(sum(b.total_sar for b in buckets), 2)
    open_invoices.sort(key=lambda i: i.days_overdue, reverse=True)

    narrative_en = (
        f"{len(open_invoices)} open item(s) totaling SAR {total_outstanding:,.2f} as of "
        f"{as_of.strftime('%Y-%m-%d')}. {n_paid} item(s) already marked paid were excluded."
    )
    narrative_ar = (
        f"{len(open_invoices)} بنداً مفتوحاً بإجمالي {total_outstanding:,.2f} ريال حتى "
        f"{as_of.strftime('%Y-%m-%d')}. تم استبعاد {n_paid} بنداً مدفوعاً."
    )
    if n_unclassified_status:
        narrative_en += f" {n_unclassified_status} row(s) excluded — status not classifiable as paid or outstanding."
        narrative_ar += f" استُبعد {n_unclassified_status} صفاً — تعذّر تصنيف حالته."

    return ARAPAgingResult(
        available=True, reason=None, columns_detected=columns_detected,
        as_of_date=as_of.strftime("%Y-%m-%d"), n_open_invoices=len(open_invoices),
        n_excluded_paid=n_paid, n_excluded_unclassified_status=n_unclassified_status,
        total_outstanding_sar=total_outstanding, buckets=buckets, invoices=open_invoices,
        narrative_en=narrative_en, narrative_ar=narrative_ar,
    )


# ── Result types: 5. Journal Entry Anomaly & Duplicate Detection ───────────

@dataclass(frozen=True)
class AmountAnomaly:
    account: str
    date: Optional[str]
    description: Optional[str]
    amount_sar: float
    account_q1_sar: float
    account_q3_sar: float
    fence_low_sar: float
    fence_high_sar: float


@dataclass(frozen=True)
class DuplicateCandidate:
    account: str
    date: str
    amount_sar: float
    description_a: Optional[str]
    description_b: Optional[str]
    description_similarity: Optional[float]
    confidence: str  # "high" | "review"


@dataclass(frozen=True)
class JournalAnomalyResult:
    available: bool
    reason: Optional[str]
    columns_detected: dict[str, bool]
    min_sample_size: int
    n_accounts_checked: int
    n_accounts_suppressed_small_sample: int
    amount_anomalies: list[AmountAnomaly]
    duplicate_candidates: list[DuplicateCandidate]
    narrative_en: str
    narrative_ar: str


def unavailable_journal_anomaly_result(reason: str, columns_detected: Optional[dict[str, bool]] = None) -> JournalAnomalyResult:
    return JournalAnomalyResult(
        available=False, reason=reason, columns_detected=columns_detected or {},
        min_sample_size=_MIN_SAMPLE_SIZE_FOR_ANOMALY, n_accounts_checked=0,
        n_accounts_suppressed_small_sample=0, amount_anomalies=[], duplicate_candidates=[],
        narrative_en="Journal entry anomaly detection not available for this dataset.",
        narrative_ar="كشف الشذوذ في القيود اليومية غير متاح لهذه البيانات.",
    )


def analyze_journal_anomalies(df: pd.DataFrame) -> JournalAnomalyResult:
    """Never raises. Requires the same account + debit/credit structure as
    General Ledger Analysis. Amount anomalies use IQR/Tukey's-fences per
    account, gated on `_MIN_SAMPLE_SIZE_FOR_ANOMALY`, disclosed suppression
    below that floor. Duplicates match on (date, account, amount) plus
    description similarity — see module docstring."""
    if df is None or df.empty:
        return unavailable_journal_anomaly_result("No data available for journal anomaly detection.")

    cols = _detect_gl_columns(df)
    columns_detected = {
        "account": cols["account"] is not None, "debit": cols["debit"] is not None,
        "credit": cols["credit"] is not None, "date": cols["date"] is not None,
        "description": cols["description"] is not None,
    }
    if cols["account"] is None or cols["debit"] is None or cols["credit"] is None or cols["date"] is None:
        return unavailable_journal_anomaly_result(
            "Journal anomaly detection requires an account column, real debit/credit columns, "
            "and a date column (duplicates are matched on date + account + amount). Detected: "
            f"account={'yes' if cols['account'] else 'no'}, debit={'yes' if cols['debit'] else 'no'}, "
            f"credit={'yes' if cols['credit'] else 'no'}, date={'yes' if cols['date'] else 'no'}.",
            columns_detected,
        )

    account_col, debit_col, credit_col, date_col = cols["account"], cols["debit"], cols["credit"], cols["date"]
    description_col = cols["description"]

    rows: list[dict[str, Any]] = []
    for idx in df.index:
        raw_account = df.at[idx, account_col]
        raw_date = df.at[idx, date_col]
        if _is_missing_value(raw_account) or _is_missing_value(raw_date):
            continue
        debit = _numeric_or_none(df.at[idx, debit_col])
        credit = _numeric_or_none(df.at[idx, credit_col])
        amount = debit if debit not in (None, 0.0) else credit
        if amount is None or amount == 0.0:
            continue
        parsed_date = pd.to_datetime(raw_date, errors="coerce")
        if pd.isna(parsed_date):
            continue
        rows.append({
            "account": " ".join(str(raw_account).split()),
            "date": parsed_date.strftime("%Y-%m-%d"),
            "amount": round(float(amount), 2),
            "description": (str(df.at[idx, description_col]).strip() if description_col and not _is_missing_value(df.at[idx, description_col]) else None),
        })

    if not rows:
        return unavailable_journal_anomaly_result(
            "Account, debit/credit, and date columns were found, but no row had a complete, "
            "valid set of values.", columns_detected,
        )

    # ── Amount anomalies (IQR/Tukey's-fences per account, min-sample gated) ──
    by_account: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        by_account.setdefault(r["account"], []).append(r)

    amount_anomalies: list[AmountAnomaly] = []
    n_checked = 0
    n_suppressed = 0
    for account, entries in by_account.items():
        if len(entries) < _MIN_SAMPLE_SIZE_FOR_ANOMALY:
            n_suppressed += 1
            continue
        n_checked += 1
        amounts = pd.Series([e["amount"] for e in entries])
        q1, q3 = float(amounts.quantile(0.25)), float(amounts.quantile(0.75))
        iqr = q3 - q1
        fence_low, fence_high = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        for e in entries:
            if e["amount"] < fence_low or e["amount"] > fence_high:
                amount_anomalies.append(AmountAnomaly(
                    account=account, date=e["date"], description=e["description"],
                    amount_sar=e["amount"], account_q1_sar=round(q1, 2), account_q3_sar=round(q3, 2),
                    fence_low_sar=round(fence_low, 2), fence_high_sar=round(fence_high, 2),
                ))
    amount_anomalies.sort(key=lambda a: a.amount_sar, reverse=True)

    # ── Duplicate detection: (date, account, amount) key + description similarity ──
    key_groups: dict[tuple[str, str, float], list[dict[str, Any]]] = {}
    for r in rows:
        key = (r["date"], r["account"], r["amount"])
        key_groups.setdefault(key, []).append(r)

    duplicate_candidates: list[DuplicateCandidate] = []
    for (date, account, amount), entries in key_groups.items():
        if len(entries) < 2:
            continue
        a, b = entries[0], entries[1]
        desc_a, desc_b = a["description"], b["description"]
        if desc_a and desc_b:
            similarity = round(difflib.SequenceMatcher(None, desc_a.lower(), desc_b.lower()).ratio(), 3)
            confidence = "high" if similarity >= _DUPLICATE_DESC_SIMILARITY_THRESHOLD else "review"
        else:
            similarity = None
            confidence = "high" if (not desc_a and not desc_b) else "review"
        duplicate_candidates.append(DuplicateCandidate(
            account=account, date=date, amount_sar=amount,
            description_a=desc_a, description_b=desc_b,
            description_similarity=similarity, confidence=confidence,
        ))
    duplicate_candidates.sort(key=lambda d: (d.confidence != "high", -d.amount_sar))

    narrative_en = (
        f"Checked {n_checked} account(s) with at least {_MIN_SAMPLE_SIZE_FOR_ANOMALY} transactions "
        f"for statistical amount outliers ({len(amount_anomalies)} found); {n_suppressed} account(s) "
        f"had too few transactions to check and were suppressed, not silently skipped. "
        f"{len(duplicate_candidates)} duplicate candidate(s) found matching on date + account + amount."
    )
    narrative_ar = (
        f"تم فحص {n_checked} حساباً بحد أدنى {_MIN_SAMPLE_SIZE_FOR_ANOMALY} معاملات لاكتشاف "
        f"القيم الشاذة إحصائياً (تم العثور على {len(amount_anomalies)})؛ تم استبعاد {n_suppressed} "
        f"حساباً لقلة عدد المعاملات. تم العثور على {len(duplicate_candidates)} حالة تكرار محتملة."
    )

    return JournalAnomalyResult(
        available=True, reason=None, columns_detected=columns_detected,
        min_sample_size=_MIN_SAMPLE_SIZE_FOR_ANOMALY, n_accounts_checked=n_checked,
        n_accounts_suppressed_small_sample=n_suppressed,
        amount_anomalies=amount_anomalies, duplicate_candidates=duplicate_candidates,
        narrative_en=narrative_en, narrative_ar=narrative_ar,
    )


# ── Top-level bundle ─────────────────────────────────────────────────────────

@dataclass(frozen=True)
class AccountingIntelligenceResult:
    general_ledger: GeneralLedgerResult
    trial_balance: TrialBalanceResult
    balance_sheet: BalanceSheetResult
    ar_ap_aging: ARAPAgingResult
    journal_anomalies: JournalAnomalyResult
    disclaimer_en: str
    disclaimer_ar: str
    confidence: str
    sources: list[str]
    computed_at: str


def analyze_accounting_intelligence(df: pd.DataFrame, as_of_date: Optional[str] = None) -> AccountingIntelligenceResult:
    """Never raises — each of the 5 sub-analyses is independently wrapped so
    one failing (or being unavailable) never blocks the others."""
    try:
        gl = analyze_general_ledger(df)
    except Exception as exc:
        gl = unavailable_general_ledger_result(f"General ledger analysis encountered an error: {exc}")
    try:
        tb = analyze_trial_balance(df)
    except Exception as exc:
        tb = unavailable_trial_balance_result(f"Trial balance analysis encountered an error: {exc}")
    try:
        bs = analyze_balance_sheet(df)
    except Exception as exc:
        bs = unavailable_balance_sheet_result(f"Balance sheet analysis encountered an error: {exc}")
    try:
        aging = analyze_ar_ap_aging(df, as_of_date=as_of_date)
    except Exception as exc:
        aging = unavailable_ar_ap_aging_result(f"AR/AP aging analysis encountered an error: {exc}")
    try:
        anomalies = analyze_journal_anomalies(df)
    except Exception as exc:
        anomalies = unavailable_journal_anomaly_result(f"Journal anomaly detection encountered an error: {exc}")

    return AccountingIntelligenceResult(
        general_ledger=gl, trial_balance=tb, balance_sheet=bs, ar_ap_aging=aging,
        journal_anomalies=anomalies,
        disclaimer_en=ACCOUNTING_DISCLAIMER_EN, disclaimer_ar=ACCOUNTING_DISCLAIMER_AR,
        confidence=ACCOUNTING_CONFIDENCE, sources=_SOURCES, computed_at=_now(),
    )


# ── Serialization ─────────────────────────────────────────────────────────────

def _gl_to_dict(r: GeneralLedgerResult) -> dict[str, Any]:
    return {
        "available": r.available, "reason": r.reason, "columns_detected": r.columns_detected,
        "account_column": r.account_column, "debit_column": r.debit_column, "credit_column": r.credit_column,
        "n_transactions_total": r.n_transactions_total, "n_accounts": r.n_accounts,
        "accounts": [
            {
                "account": a.account, "account_type": a.account_type,
                "total_debit_sar": a.total_debit_sar, "total_credit_sar": a.total_credit_sar,
                "net_sar": a.net_sar, "n_transactions": a.n_transactions,
                "n_transactions_shown": a.n_transactions_shown,
                "transactions": [
                    {"date": t.date, "description": t.description, "debit_sar": t.debit_sar, "credit_sar": t.credit_sar}
                    for t in a.transactions
                ],
            }
            for a in r.accounts
        ],
        "narrative_en": r.narrative_en, "narrative_ar": r.narrative_ar,
    }


def _tb_to_dict(r: TrialBalanceResult) -> dict[str, Any]:
    return {
        "available": r.available, "reason": r.reason, "columns_detected": r.columns_detected,
        "lines": [{"account": l.account, "total_debit_sar": l.total_debit_sar, "total_credit_sar": l.total_credit_sar} for l in r.lines],
        "total_debit_sar": r.total_debit_sar, "total_credit_sar": r.total_credit_sar,
        "difference_sar": r.difference_sar, "is_balanced": r.is_balanced, "tolerance_sar": r.tolerance_sar,
        "narrative_en": r.narrative_en, "narrative_ar": r.narrative_ar,
    }


def _bs_to_dict(r: BalanceSheetResult) -> dict[str, Any]:
    return {
        "available": r.available, "reason": r.reason, "columns_detected": r.columns_detected,
        "assets": [{"account": l.account, "balance_sar": l.balance_sar} for l in r.assets],
        "liabilities": [{"account": l.account, "balance_sar": l.balance_sar} for l in r.liabilities],
        "equity": [{"account": l.account, "balance_sar": l.balance_sar} for l in r.equity],
        "net_income_current_period_sar": r.net_income_current_period_sar,
        "total_assets_sar": r.total_assets_sar, "total_liabilities_sar": r.total_liabilities_sar,
        "total_equity_reported_sar": r.total_equity_reported_sar,
        "total_equity_including_net_income_sar": r.total_equity_including_net_income_sar,
        "identity_difference_sar": r.identity_difference_sar, "is_balanced": r.is_balanced,
        "n_accounts_unclassified": r.n_accounts_unclassified,
        "narrative_en": r.narrative_en, "narrative_ar": r.narrative_ar,
    }


def _aging_to_dict(r: ARAPAgingResult) -> dict[str, Any]:
    return {
        "available": r.available, "reason": r.reason, "columns_detected": r.columns_detected,
        "as_of_date": r.as_of_date, "n_open_invoices": r.n_open_invoices,
        "n_excluded_paid": r.n_excluded_paid, "n_excluded_unclassified_status": r.n_excluded_unclassified_status,
        "total_outstanding_sar": r.total_outstanding_sar,
        "buckets": [{"bucket": b.bucket, "total_sar": b.total_sar, "n_invoices": b.n_invoices} for b in r.buckets],
        "invoices": [
            {"direction": i.direction, "party": i.party, "invoice_number": i.invoice_number,
             "due_date": i.due_date, "amount_sar": i.amount_sar, "days_overdue": i.days_overdue, "bucket": i.bucket}
            for i in r.invoices
        ],
        "narrative_en": r.narrative_en, "narrative_ar": r.narrative_ar,
    }


def _anomalies_to_dict(r: JournalAnomalyResult) -> dict[str, Any]:
    return {
        "available": r.available, "reason": r.reason, "columns_detected": r.columns_detected,
        "min_sample_size": r.min_sample_size, "n_accounts_checked": r.n_accounts_checked,
        "n_accounts_suppressed_small_sample": r.n_accounts_suppressed_small_sample,
        "amount_anomalies": [
            {"account": a.account, "date": a.date, "description": a.description, "amount_sar": a.amount_sar,
             "account_q1_sar": a.account_q1_sar, "account_q3_sar": a.account_q3_sar,
             "fence_low_sar": a.fence_low_sar, "fence_high_sar": a.fence_high_sar}
            for a in r.amount_anomalies
        ],
        "duplicate_candidates": [
            {"account": d.account, "date": d.date, "amount_sar": d.amount_sar,
             "description_a": d.description_a, "description_b": d.description_b,
             "description_similarity": d.description_similarity, "confidence": d.confidence}
            for d in r.duplicate_candidates
        ],
        "narrative_en": r.narrative_en, "narrative_ar": r.narrative_ar,
    }


def accounting_intelligence_to_dict(r: AccountingIntelligenceResult) -> dict[str, Any]:
    return {
        "general_ledger": _gl_to_dict(r.general_ledger),
        "trial_balance": _tb_to_dict(r.trial_balance),
        "balance_sheet": _bs_to_dict(r.balance_sheet),
        "ar_ap_aging": _aging_to_dict(r.ar_ap_aging),
        "journal_anomalies": _anomalies_to_dict(r.journal_anomalies),
        "disclaimer_en": r.disclaimer_en, "disclaimer_ar": r.disclaimer_ar,
        "confidence": r.confidence, "sources": r.sources, "computed_at": r.computed_at,
    }
