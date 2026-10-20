"""
Tests for backend.core.accounting_intelligence_engine — Phase 31.

Fixtures:
  - accounting_gl_test_data.csv: 25 balanced double-entry journal entries
    (50 lines), covering GL/Trial Balance/Balance Sheet/AR-AP/Anomalies.
    All expected figures below were independently computed with pandas
    directly against this CSV (see the build script this phase used) —
    documented inline with the formula, not re-derived from the engine.
  - accounting_gl_imbalanced_test_data.csv: 3 deliberately unbalanced
    entries (total debit 14,200 vs total credit 13,700 — a 500 SAR gap
    from an equipment purchase posted as 3,000 debit but only 2,500
    credit) to test the Trial Balance imbalance flag.
  - financial_transactions_test_data.csv (Phase 30's fixture): used to
    prove this module honestly degrades on Phase 30's simpler single-
    amount shape — the core cross-module non-overlap proof.
"""
from __future__ import annotations

import pandas as pd
import pytest

from backend.core.accounting_intelligence_engine import (
    analyze_accounting_intelligence,
    analyze_ar_ap_aging,
    analyze_balance_sheet,
    analyze_general_ledger,
    analyze_journal_anomalies,
    analyze_trial_balance,
)

MAIN_FIXTURE = "accounting_gl_test_data.csv"
IMBALANCED_FIXTURE = "accounting_gl_imbalanced_test_data.csv"
PHASE30_FIXTURE = "financial_transactions_test_data.csv"


@pytest.fixture
def main_df():
    return pd.read_csv(MAIN_FIXTURE)


@pytest.fixture
def imbalanced_df():
    return pd.read_csv(IMBALANCED_FIXTURE)


@pytest.fixture
def phase30_df():
    return pd.read_csv(PHASE30_FIXTURE)


# ── Section 1: General Ledger Analysis ──────────────────────────────────────

class TestGeneralLedger:
    def test_hand_computed_totals(self, main_df):
        """25 double-entry transactions = 50 journal lines across 13 accounts."""
        r = analyze_general_ledger(main_df)
        assert r.available is True
        assert r.n_transactions_total == 50
        assert r.n_accounts == 13

    def test_cash_account_debit_credit_totals(self, main_df):
        """Cash: debits 50000+20000+4200+2800=77000; credits 8000+2000+9000+
        610+630+600+650+620+6200=28310 (verified via pandas groupby)."""
        r = analyze_general_ledger(main_df)
        cash = next(a for a in r.accounts if a.account == "Cash")
        assert cash.total_debit_sar == 77000.0
        assert cash.total_credit_sar == 28310.0
        assert cash.net_sar == round(77000.0 - 28310.0, 2)
        assert cash.n_transactions == 13

    def test_not_available_without_debit_credit_columns(self, phase30_df):
        r = analyze_general_ledger(phase30_df)
        assert r.available is False
        assert "debit" in r.reason.lower() and "credit" in r.reason.lower()

    def test_not_available_no_data(self):
        r = analyze_general_ledger(pd.DataFrame())
        assert r.available is False


# ── Section 2: Trial Balance ─────────────────────────────────────────────────

class TestTrialBalance:
    def test_hand_computed_balanced(self, main_df):
        r = analyze_trial_balance(main_df)
        assert r.available is True
        assert r.total_debit_sar == 128660.0
        assert r.total_credit_sar == 128660.0
        assert r.difference_sar == 0.0
        assert r.is_balanced is True
        assert len(r.lines) == 13

    def test_hand_computed_imbalance_flagged(self, imbalanced_df):
        """Debit 10000+3000+1200=14200; Credit 10000+2500+1200=13700; gap=500."""
        r = analyze_trial_balance(imbalanced_df)
        assert r.available is True
        assert r.total_debit_sar == 14200.0
        assert r.total_credit_sar == 13700.0
        assert r.difference_sar == 500.0
        assert r.is_balanced is False

    def test_not_available_without_debit_credit_columns(self, phase30_df):
        r = analyze_trial_balance(phase30_df)
        assert r.available is False
        assert "single signed amount" in r.reason.lower() or "debit" in r.reason.lower()


# ── Section 3: Balance Sheet ──────────────────────────────────────────────────

class TestBalanceSheet:
    def test_hand_computed_identity_holds(self, main_df):
        """Assets 69290 = Liabilities 27950 + Equity 50000 + Net Income (-8660).
        Independently verified via pandas groupby(['Account','AccountType'])."""
        r = analyze_balance_sheet(main_df)
        assert r.available is True
        assert r.total_assets_sar == 69290.0
        assert r.total_liabilities_sar == 27950.0
        assert r.total_equity_reported_sar == 50000.0
        assert r.net_income_current_period_sar == -8660.0
        assert r.total_equity_including_net_income_sar == round(50000.0 - 8660.0, 2)
        assert r.identity_difference_sar == 0.0
        assert r.is_balanced is True

    def test_hand_computed_asset_accounts(self, main_df):
        """Cash 77000-28310=48690; AR 15400-2800=12600; Office Equipment 8000-0=8000."""
        r = analyze_balance_sheet(main_df)
        by_account = {a.account: a.balance_sar for a in r.assets}
        assert by_account["Cash"] == 48690.0
        assert by_account["Accounts Receivable"] == 12600.0
        assert by_account["Office Equipment"] == 8000.0

    def test_hand_computed_liability_accounts(self, main_df):
        """Accounts Payable 7950-0=7950 (credit-normal); Loan Payable 20000-0=20000."""
        r = analyze_balance_sheet(main_df)
        by_account = {a.account: a.balance_sar for a in r.liabilities}
        assert by_account["Accounts Payable"] == 7950.0
        assert by_account["Loan Payable"] == 20000.0

    def test_not_available_without_account_type_column(self, main_df):
        """Same debit/credit data, but drop AccountType — balance sheet must
        honestly degrade rather than guessing which accounts are BS accounts."""
        df = main_df.drop(columns=["AccountType"])
        r = analyze_balance_sheet(df)
        assert r.available is False
        assert "classification" in r.reason.lower() or "asset" in r.reason.lower()

    def test_not_available_without_debit_credit_columns(self, phase30_df):
        r = analyze_balance_sheet(phase30_df)
        assert r.available is False


# ── Section 4: AR/AP + Aging ─────────────────────────────────────────────────

class TestARAPAging:
    def test_hand_computed_buckets(self, main_df):
        """as_of=2026-04-15. current=900(1); 1-30=6000+3500+1200=10700(3);
        31-60=950(1); 61-90=2200(1); 90+=1800(1); Customer C's 2800 (paid)
        excluded. Total outstanding = 900+10700+950+2200+1800=16550."""
        r = analyze_ar_ap_aging(main_df, as_of_date="2026-04-15")
        assert r.available is True
        assert r.total_outstanding_sar == 16550.0
        assert r.n_open_invoices == 7
        assert r.n_excluded_paid == 1
        by_bucket = {b.bucket: (b.total_sar, b.n_invoices) for b in r.buckets}
        assert by_bucket["current"] == (900.0, 1)
        assert by_bucket["1-30"] == (10700.0, 3)
        assert by_bucket["31-60"] == (950.0, 1)
        assert by_bucket["61-90"] == (2200.0, 1)
        assert by_bucket["90+"] == (1800.0, 1)

    def test_paid_invoice_excluded_from_aging(self, main_df):
        r = analyze_ar_ap_aging(main_df, as_of_date="2026-04-15")
        parties = [i.party for i in r.invoices]
        assert "Customer C" not in parties

    def test_ar_vs_ap_direction_inferred_from_account(self, main_df):
        r = analyze_ar_ap_aging(main_df, as_of_date="2026-04-15")
        by_party = {i.party: i.direction for i in r.invoices}
        assert by_party["Customer A"] == "ar"
        assert by_party["Vendor X"] == "ap"

    def test_defaults_to_real_today_when_as_of_not_supplied(self, main_df):
        """Production default: no as_of_date -> uses real today, not a fixed
        date. Just confirms it runs and returns a real ISO date, not that any
        particular bucket totals hold (those depend on the current date)."""
        r = analyze_ar_ap_aging(main_df)
        assert r.available is True
        assert r.as_of_date is not None

    def test_not_available_without_party_due_date_status(self, phase30_df):
        r = analyze_ar_ap_aging(phase30_df, as_of_date="2026-04-15")
        assert r.available is False
        assert "party" in r.reason.lower()


# ── Section 5: Journal Entry Anomaly & Duplicate Detection ─────────────────

class TestJournalAnomalies:
    def test_hand_computed_amount_anomalies(self, main_df):
        """IQR/Tukey's-fences per account (min sample 5), independently
        computed via pandas .quantile(0.25/0.75):
        Cash (n=13): Q1=630, Q3=8000, IQR=7370, upper fence=19055 ->
            flags 20000 and 50000.
        Utilities Expense (n=6): Q1=612.5, Q3=645, IQR=32.5, upper
            fence=693.75 -> flags 6200.
        Accounts Receivable (n=6): Q1=2350, Q3=3325, IQR=975, upper
            fence=4787.5 -> flags 6000.
        Accounts Payable (n=7) and Sales Revenue (n=6): checked, 0 flags.
        """
        r = analyze_journal_anomalies(main_df)
        assert r.available is True
        assert r.n_accounts_checked == 5
        assert r.n_accounts_suppressed_small_sample == 8
        flagged = {(a.account, a.amount_sar) for a in r.amount_anomalies}
        assert ("Cash", 50000.0) in flagged
        assert ("Cash", 20000.0) in flagged
        assert ("Utilities Expense", 6200.0) in flagged
        assert ("Accounts Receivable", 6000.0) in flagged
        assert len(r.amount_anomalies) == 4

    def test_small_sample_accounts_suppressed_not_flagged(self, main_df):
        r = analyze_journal_anomalies(main_df)
        flagged_accounts = {a.account for a in r.amount_anomalies}
        assert "Rent Expense" not in flagged_accounts  # n=1, suppressed
        assert "Loan Payable" not in flagged_accounts  # n=1, suppressed

    def test_hand_computed_near_duplicate_high_confidence(self, main_df):
        """Insurance Expense: same date/account/amount, near-identical (not
        byte-identical) descriptions ('Quarterly insurance premium' vs
        'Quarterly insurance premium payment') -> similarity ~0.871
        (independently computed via difflib), above the 0.6 threshold ->
        'high' confidence. Deliberately NOT byte-identical across all
        columns so the ingestion pipeline's own exact-duplicate-row removal
        (reused from every other module) doesn't strip one of the two rows
        before this module ever sees them — see the Phase 31 report."""
        r = analyze_journal_anomalies(main_df)
        dup = next(d for d in r.duplicate_candidates if d.account == "Insurance Expense")
        assert dup.amount_sar == 1500.0
        assert dup.confidence == "high"
        assert dup.description_similarity > 0.6
        assert dup.description_similarity < 1.0

    def test_hand_computed_review_confidence_different_descriptions(self, main_df):
        """Consulting Expense: same date/account/amount (500) but DIFFERENT
        descriptions ('Legal consultation...' vs 'IT consulting...') ->
        low similarity (~0.38, independently computed via difflib), 'review'
        confidence, never auto-flagged as a confirmed duplicate."""
        r = analyze_journal_anomalies(main_df)
        dup = next(d for d in r.duplicate_candidates if d.account == "Consulting Expense")
        assert dup.amount_sar == 500.0
        assert dup.confidence == "review"
        assert dup.description_similarity < 0.6

    def test_recurring_monthly_expense_not_flagged_as_duplicate(self, main_df):
        """Utilities Expense has 6 entries on 6 DIFFERENT dates — a legitimate
        recurring transaction. None should collide on the (date, account,
        amount) key and get flagged as a duplicate."""
        r = analyze_journal_anomalies(main_df)
        assert not any(d.account == "Utilities Expense" for d in r.duplicate_candidates)

    def test_not_available_without_debit_credit_date(self, phase30_df):
        r = analyze_journal_anomalies(phase30_df)
        assert r.available is False


# ── Section 6: Cross-module honest degradation (Phase 30 fixture) ──────────

class TestCrossModuleDifferentiation:
    """The core non-overlap proof: Phase 30's simpler transaction-list shape
    (Amount + Type, no Debit/Credit) must make ALL FIVE Phase 31 items
    honestly report not-computable — proving the two modules are correctly
    differentiated, never accidentally duplicating each other's function."""

    def test_all_five_items_unavailable_on_phase30_fixture(self, phase30_df):
        r = analyze_accounting_intelligence(phase30_df)
        assert r.general_ledger.available is False
        assert r.trial_balance.available is False
        assert r.balance_sheet.available is False
        assert r.ar_ap_aging.available is False
        assert r.journal_anomalies.available is False

    def test_never_fabricates_on_empty_data(self):
        r = analyze_accounting_intelligence(pd.DataFrame())
        assert r.general_ledger.available is False
        assert r.trial_balance.available is False
        assert r.balance_sheet.available is False
        assert r.ar_ap_aging.available is False
        assert r.journal_anomalies.available is False


# ── Section 7: Bundle + serialization sanity ────────────────────────────────

class TestBundleAndSerialization:
    def test_analyze_accounting_intelligence_bundles_all_five(self, main_df):
        r = analyze_accounting_intelligence(main_df, as_of_date="2026-04-15")
        assert r.general_ledger.available is True
        assert r.trial_balance.available is True
        assert r.balance_sheet.available is True
        assert r.ar_ap_aging.available is True
        assert r.journal_anomalies.available is True

    def test_to_dict_contains_all_sections(self, main_df):
        from backend.core.accounting_intelligence_engine import accounting_intelligence_to_dict
        r = analyze_accounting_intelligence(main_df, as_of_date="2026-04-15")
        d = accounting_intelligence_to_dict(r)
        for key in ["general_ledger", "trial_balance", "balance_sheet", "ar_ap_aging", "journal_anomalies", "disclaimer_en", "disclaimer_ar", "sources"]:
            assert key in d

    def test_one_sub_analysis_never_raises_uncaught(self):
        """Malformed input (wrong dtype columns) must degrade honestly, not
        raise, at both the sub-function and bundle level."""
        df = pd.DataFrame({"Account": [None, None], "Debit": ["x", "y"], "Credit": ["z", "w"]})
        r = analyze_accounting_intelligence(df)
        assert r.general_ledger.available is False
