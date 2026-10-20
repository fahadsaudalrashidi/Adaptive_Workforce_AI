"""
Phase 30 — Financial Intelligence Reporting engine tests (Business
Intelligence Suite, Phase 1). First non-HR domain this platform analyzes —
a transaction-level/general-ledger dataset, not an employee roster.

Covers, each with real hand-computed-value assertions:
  1. Revenue/expense/P&L/ratios/variance computed exactly against a
     constructed 14-row, 2-month synthetic transaction fixture (all figures
     hand-computed independently in the test docstring and cross-checked).
  2. All three revenue-vs-expense classification methods, in priority
     order: explicit type column, account/category keyword matching, and
     signed-amount fallback — each verified in isolation.
  3. Honest degradation: no amount column at all; an amount column with no
     usable classification signal (no type, no classifiable category, no
     sign variation); invalid/non-numeric amount values excluded and
     disclosed, never guessed.
  4. Department expense rollup reusing department_normalizer.py (real
     reuse, not reimplementation — "HR" normalizes to "Human Resources").
  5. Period-over-period variance reusing payroll_budget_engine.py's exact
     variance/variance_pct field shape, applied to period movement.
  6. Cash-flow honest scoping: cash_flow_available tracks whether a period
     trend exists, and the disclaimer is always present and never silently
     omitted.

Run: py -m pytest tests/test_financial_intelligence_reporting_engine.py -v
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from backend.core.financial_intelligence_reporting_engine import (
    analyze_financial_intelligence,
    financial_intelligence_to_dict,
    unavailable_financial_result,
)

_ROOT = Path(__file__).resolve().parent.parent
_FIXTURE = _ROOT / "financial_transactions_test_data.csv"


# ── 1. Hand-computed figures against the main fixture ──────────────────────
#
# Fixture (14 rows, Jan + Feb 2026):
#   Jan revenue: Sales Revenue 10000+15000+5000=30000, Consulting Income 8000
#                -> Jan total revenue = 38000
#   Jan expense: Office Rent 4000, Salaries 12000, Utilities 1000
#                -> Jan total expense = 17000  (Jan net = 21000)
#   Feb revenue: Sales Revenue 12000+18000=30000, Consulting Income 6000
#                -> Feb total revenue = 36000
#   Feb expense: Office Rent 4000, Salaries 13000, Utilities 1200, Marketing 2000
#                -> Feb total expense = 20200  (Feb net = 15800)
#   Grand total revenue = 74000, expense = 37200, net P&L = 36800

def test_total_revenue_expense_and_pnl_hand_computed():
    df = pd.read_csv(_FIXTURE)
    result = analyze_financial_intelligence(df)
    assert result.available is True
    assert result.classification_method == "type_column"
    assert result.total_revenue_sar == 74000.0
    assert result.total_expense_sar == 37200.0
    assert result.net_pnl_sar == 36800.0
    assert result.n_transactions_classified == 14


def test_period_figures_hand_computed():
    df = pd.read_csv(_FIXTURE)
    result = analyze_financial_intelligence(df)
    assert result.has_period_trend is True
    periods = {p.period: p for p in result.period_figures}
    assert set(periods.keys()) == {"2026-01", "2026-02"}
    assert periods["2026-01"].total_revenue_sar == 38000.0
    assert periods["2026-01"].total_expense_sar == 17000.0
    assert periods["2026-01"].net_sar == 21000.0
    assert periods["2026-01"].n_transactions == 7
    assert periods["2026-02"].total_revenue_sar == 36000.0
    assert periods["2026-02"].total_expense_sar == 20200.0
    assert periods["2026-02"].net_sar == 15800.0


def test_revenue_by_category_hand_computed():
    """Sales Revenue = 10000+15000+5000+12000+18000 = 60000 (81.1% of 74000).
    Consulting Income = 8000+6000 = 14000 (18.9%)."""
    df = pd.read_csv(_FIXTURE)
    result = analyze_financial_intelligence(df)
    by_cat = {c.category: c for c in result.revenue_by_category}
    assert by_cat["Sales Revenue"].total_sar == 60000.0
    assert by_cat["Sales Revenue"].share_pct == pytest.approx(81.1, abs=0.05)
    assert by_cat["Sales Revenue"].n_transactions == 5
    assert by_cat["Consulting Income"].total_sar == 14000.0
    assert by_cat["Consulting Income"].share_pct == pytest.approx(18.9, abs=0.05)
    # Sorted descending by total.
    assert result.revenue_by_category[0].category == "Sales Revenue"


def test_expense_by_category_hand_computed():
    """Salaries = 12000+13000=25000 (67.2%); Office Rent = 4000+4000=8000
    (21.5%); Utilities = 1000+1200=2200 (5.9%); Marketing = 2000 (5.4%)."""
    df = pd.read_csv(_FIXTURE)
    result = analyze_financial_intelligence(df)
    by_cat = {c.category: c for c in result.expense_by_category}
    assert by_cat["Salaries Expense"].total_sar == 25000.0
    assert by_cat["Salaries Expense"].share_pct == pytest.approx(67.2, abs=0.05)
    assert by_cat["Office Rent Expense"].total_sar == 8000.0
    assert by_cat["Utilities Expense"].total_sar == 2200.0
    assert by_cat["Marketing Expense"].total_sar == 2000.0
    assert result.expense_by_category[0].category == "Salaries Expense"


def test_expense_by_department_reuses_department_normalizer():
    """HR = Salaries 25000; Operations = Office Rent 8000 + Utilities 2200 =
    10200; Sales = Marketing 2000. 'HR' must normalize to 'Human Resources'
    via department_normalizer.py's own curated table — real reuse, not a
    bypassed/reimplemented normalizer."""
    df = pd.read_csv(_FIXTURE)
    result = analyze_financial_intelligence(df)
    by_dept = {d.department: d for d in result.expense_by_department}
    assert "Human Resources" in by_dept
    assert by_dept["Human Resources"].total_expense_sar == 25000.0
    assert by_dept["Operations"].total_expense_sar == 10200.0
    assert by_dept["Sales"].total_expense_sar == 2000.0


def test_ratios_hand_computed():
    """Expense-to-revenue = 37200/74000 = 0.50270... -> 0.503 (3dp)."""
    df = pd.read_csv(_FIXTURE)
    result = analyze_financial_intelligence(df)
    assert result.ratios is not None
    assert result.ratios.expense_to_revenue_ratio == pytest.approx(0.503, abs=0.001)
    assert result.ratios.top_expense_category == "Salaries Expense"
    assert result.ratios.top_expense_category_share_pct == pytest.approx(67.2, abs=0.05)
    assert result.ratios.top_revenue_category == "Sales Revenue"
    # Balance-sheet-dependent ratios must be explicitly disclosed as unavailable.
    assert "balance-sheet" in result.ratios.unavailable_ratios_note_en.lower()
    assert "current ratio" in result.ratios.unavailable_ratios_note_en.lower()


def test_period_variance_hand_computed():
    """Feb vs Jan: revenue_variance = 36000-38000 = -2000 (-5.3%);
    expense_variance = 20200-17000 = 3200 (+18.8%);
    net_variance = 15800-21000 = -5200 (-24.8%, relative to |21000|)."""
    df = pd.read_csv(_FIXTURE)
    result = analyze_financial_intelligence(df)
    assert len(result.period_variances) == 1
    v = result.period_variances[0]
    assert v.period == "2026-02"
    assert v.prior_period == "2026-01"
    assert v.revenue_variance_sar == -2000.0
    assert v.revenue_variance_pct == pytest.approx(-5.3, abs=0.05)
    assert v.expense_variance_sar == 3200.0
    assert v.expense_variance_pct == pytest.approx(18.8, abs=0.05)
    assert v.net_variance_sar == -5200.0
    assert v.net_variance_pct == pytest.approx(-24.8, abs=0.05)


def test_cash_flow_available_and_disclaimer_always_present():
    df = pd.read_csv(_FIXTURE)
    result = analyze_financial_intelligence(df)
    assert result.cash_flow_available is True
    assert "not a cash-flow statement" in result.cash_flow_disclaimer_en.lower()
    assert "net transaction movement" in result.cash_flow_disclaimer_en.lower()


# ── 2. Classification methods, each verified in isolation ──────────────────

def test_classification_via_explicit_type_column():
    df = pd.DataFrame({
        "Date": ["2026-01-01", "2026-01-02"],
        "Type": ["Revenue", "Expense"],
        "Amount": [5000, 2000],
    })
    result = analyze_financial_intelligence(df)
    assert result.classification_method == "type_column"
    assert result.total_revenue_sar == 5000.0
    assert result.total_expense_sar == 2000.0


def test_classification_via_category_keywords_when_no_type_column():
    df = pd.DataFrame({
        "Date": ["2026-01-01", "2026-01-02"],
        "Account": ["Sales Revenue", "Rent Expense"],
        "Amount": [5000, 2000],
    })
    result = analyze_financial_intelligence(df)
    assert result.classification_method == "category_keywords"
    assert result.total_revenue_sar == 5000.0
    assert result.total_expense_sar == 2000.0


def test_classification_via_signed_amount_as_last_resort():
    """No type column, no classifiable category — falls back to the sign of
    the amount itself. 10000 (positive) = revenue; 3000+500 (negative) =
    expense = 3500 total."""
    df = pd.DataFrame({
        "Date": ["2026-01-01", "2026-01-02", "2026-01-03"],
        "Description": ["Deposit", "Rent", "Utilities"],
        "Amount": [10000, -3000, -500],
    })
    result = analyze_financial_intelligence(df)
    assert result.classification_method == "signed_amount"
    assert result.total_revenue_sar == 10000.0
    assert result.total_expense_sar == 3500.0


def test_signed_amount_fallback_not_used_when_all_positive():
    """An all-positive amount column with no type/category signal gives the
    sign-based method nothing to distinguish, so it must NOT be used —
    the whole result must be unavailable rather than guessing everything
    is revenue."""
    df = pd.DataFrame({
        "Date": ["2026-01-01", "2026-01-02"],
        "Value": [100, 200],
    })
    result = analyze_financial_intelligence(df)
    assert result.available is False


def test_type_column_takes_priority_over_category_keywords():
    """When both a type column AND a classifiable category column exist,
    the explicit type column wins (method='type_column'), per the
    documented reliability-priority order."""
    df = pd.DataFrame({
        "Date": ["2026-01-01"],
        "Account": ["Sales Revenue"],  # would classify as revenue via keywords
        "Type": ["Expense"],           # explicit type says expense — must win
        "Amount": [1000],
    })
    result = analyze_financial_intelligence(df)
    assert result.classification_method == "type_column"
    assert result.total_expense_sar == 1000.0
    assert result.total_revenue_sar == 0.0


# ── 3. Honest degradation ───────────────────────────────────────────────────

def test_no_amount_column_is_unavailable():
    df = pd.DataFrame({"Date": ["2026-01-01"], "Account": ["Sales"]})
    result = analyze_financial_intelligence(df)
    assert result.available is False
    assert result.columns_detected["amount"] is False
    assert "amount" in result.reason.lower()


def test_no_classification_signal_is_unavailable():
    df = pd.DataFrame({"Date": ["2026-01-01", "2026-01-02"], "Value": [100, 200]})
    result = analyze_financial_intelligence(df)
    assert result.available is False
    assert result.columns_detected["amount"] is True


def test_invalid_amount_values_excluded_and_disclosed_not_guessed():
    df = pd.DataFrame({
        "Date": ["2026-01-01", "2026-01-02", "2026-01-03"],
        "Type": ["Revenue", "Revenue", "Expense"],
        "Amount": [5000, "not a number", 2000],
    })
    result = analyze_financial_intelligence(df)
    assert result.available is True
    assert result.n_excluded_invalid_amount == 1
    assert result.example_excluded_amount_value == "not a number"
    assert result.total_revenue_sar == 5000.0  # the bad row excluded, not guessed


def test_no_date_column_still_computes_totals_but_no_trend():
    """Honest partial capability: missing the date column degrades to
    totals-only, not full unavailability — same principle as every other
    honest-degradation module this session."""
    df = pd.DataFrame({
        "Type": ["Revenue", "Expense"],
        "Amount": [5000, 2000],
    })
    result = analyze_financial_intelligence(df)
    assert result.available is True
    assert result.has_period_trend is False
    assert result.period_figures == []
    assert result.period_variances == []
    assert result.cash_flow_available is False
    assert result.total_revenue_sar == 5000.0
    assert "no period trend" in result.narrative_en.lower() or "no transaction-date" in result.narrative_en.lower()


def test_variance_not_computed_with_fewer_than_two_periods():
    df = pd.DataFrame({
        "Date": ["2026-01-01", "2026-01-02"],
        "Type": ["Revenue", "Expense"],
        "Amount": [5000, 2000],
    })
    result = analyze_financial_intelligence(df)
    assert len(result.period_figures) == 1
    assert result.period_variances == []


def test_unavailable_result_never_fabricates():
    result = unavailable_financial_result("No amount column.", {"amount": False})
    assert result.available is False
    assert result.total_revenue_sar is None
    assert result.total_expense_sar is None
    assert result.period_figures == []
    assert result.ratios is None
    d = financial_intelligence_to_dict(result)
    assert d["total_revenue_sar"] is None


# ── 4. Serialization round-trip sanity ──────────────────────────────────────

def test_to_dict_serializes_all_six_views():
    df = pd.read_csv(_FIXTURE)
    result = analyze_financial_intelligence(df)
    d = financial_intelligence_to_dict(result)
    # Revenue, Expense, P&L (totals), Cash Flow (availability+disclaimer),
    # Ratios, Variance — all six views represented in the serialized payload.
    assert d["total_revenue_sar"] == 74000.0
    assert d["total_expense_sar"] == 37200.0
    assert d["net_pnl_sar"] == 36800.0
    assert len(d["revenue_by_category"]) > 0
    assert len(d["expense_by_category"]) > 0
    assert d["cash_flow_available"] is True
    assert d["ratios"] is not None
    assert len(d["period_variances"]) == 1
