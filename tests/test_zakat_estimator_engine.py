"""
Phase 37 — Zakat Base Estimator tests.

This module is manual-entry-only (no dataframe/upload — see the engine's
module docstring for the investigation that led to this design and the
decision to scope down to an explicitly-labeled SIMPLIFIED TRADITIONAL
formula rather than the real, materially more complex ZATCA 2024 Bylaws
methodology). Tests cover: hand-computed base/liability figures, the
strict "missing required field -> named, not defaulted to zero" rule, the
zakat-base floor at zero (never negative), and that the methodology-gap
disclosure is present on every result (available or not).

Run: py -m pytest tests/test_zakat_estimator_engine.py -v
"""

from __future__ import annotations

import pytest

from backend.core.zakat_estimator_engine import (
    ZAKAT_RATE,
    ZakatInputs,
    estimate_zakat_base,
    zakat_estimate_to_dict,
)


class TestHandComputedFigures:
    def test_basic_positive_base(self):
        inputs = ZakatInputs(
            total_equity_sar=5_000_000.0,
            long_term_liabilities_provisions_sar=1_200_000.0,
            net_fixed_assets_sar=2_000_000.0,
            other_deductions_sar=200_000.0,
        )
        r = estimate_zakat_base(inputs)
        assert r.available is True
        # 5,000,000 + 1,200,000 - 2,000,000 - 200,000 = 4,000,000
        assert r.zakat_base_sar == pytest.approx(4_000_000.0)
        assert r.zakat_rate == ZAKAT_RATE
        assert r.estimated_zakat_liability_sar == pytest.approx(4_000_000.0 * 0.025)
        assert r.estimated_zakat_liability_sar == pytest.approx(100_000.0)

    def test_other_deductions_defaults_to_zero_when_omitted(self):
        inputs = ZakatInputs(
            total_equity_sar=1_000_000.0,
            long_term_liabilities_provisions_sar=100_000.0,
            net_fixed_assets_sar=300_000.0,
        )
        r = estimate_zakat_base(inputs)
        assert r.available is True
        assert r.other_deductions_sar == 0.0
        assert r.zakat_base_sar == pytest.approx(800_000.0)

    def test_base_floored_at_zero_never_negative(self):
        inputs = ZakatInputs(
            total_equity_sar=100_000.0,
            long_term_liabilities_provisions_sar=50_000.0,
            net_fixed_assets_sar=900_000.0,  # far exceeds equity+liabilities
            other_deductions_sar=0.0,
        )
        r = estimate_zakat_base(inputs)
        assert r.available is True
        assert r.zakat_base_sar == 0.0
        assert r.estimated_zakat_liability_sar == 0.0


class TestStrictMissingFieldHandling:
    def test_missing_equity_named_not_defaulted(self):
        inputs = ZakatInputs(
            total_equity_sar=None,
            long_term_liabilities_provisions_sar=100_000.0,
            net_fixed_assets_sar=50_000.0,
        )
        r = estimate_zakat_base(inputs)
        assert r.available is False
        assert "total_equity_sar" in r.missing_fields
        assert r.zakat_base_sar is None
        assert r.estimated_zakat_liability_sar is None
        assert "Total Equity" in r.reason

    def test_missing_multiple_fields_all_named(self):
        inputs = ZakatInputs(
            total_equity_sar=None,
            long_term_liabilities_provisions_sar=None,
            net_fixed_assets_sar=100_000.0,
        )
        r = estimate_zakat_base(inputs)
        assert r.available is False
        assert set(r.missing_fields) == {"total_equity_sar", "long_term_liabilities_provisions_sar"}

    def test_missing_field_never_silently_zeroed(self):
        """A missing net_fixed_assets must NOT be treated as 0 — that would
        fabricate a higher-than-real base for a real tax-adjacent figure."""
        inputs = ZakatInputs(
            total_equity_sar=1_000_000.0,
            long_term_liabilities_provisions_sar=200_000.0,
            net_fixed_assets_sar=None,
        )
        r = estimate_zakat_base(inputs)
        assert r.available is False
        assert r.zakat_base_sar is None  # NOT computed as if net_fixed_assets=0


class TestMethodologyGapDisclosure:
    def test_gap_note_present_on_available_result(self):
        inputs = ZakatInputs(total_equity_sar=1.0, long_term_liabilities_provisions_sar=1.0, net_fixed_assets_sar=0.0)
        r = estimate_zakat_base(inputs)
        assert "SIMPLIFIED TRADITIONAL" in r.methodology_gap_note_en
        assert "ZATCA" in r.methodology_gap_note_en
        assert "cannot be used" not in r.methodology_gap_note_en.lower() or "cannot" in r.methodology_gap_note_en.lower()

    def test_gap_note_present_on_unavailable_result_too(self):
        """Even the honest 'missing field' result must carry the same
        methodology disclosure — the disclaimer is not conditional on success."""
        inputs = ZakatInputs(total_equity_sar=None, long_term_liabilities_provisions_sar=1.0, net_fixed_assets_sar=1.0)
        r = estimate_zakat_base(inputs)
        assert r.available is False
        assert "SIMPLIFIED TRADITIONAL" in r.methodology_gap_note_en
        assert r.disclaimer_en != ""

    def test_disclaimer_explicitly_states_not_a_filing(self):
        inputs = ZakatInputs(total_equity_sar=1.0, long_term_liabilities_provisions_sar=1.0, net_fixed_assets_sar=0.0)
        r = estimate_zakat_base(inputs)
        assert "NOT a ZATCA filing" in r.disclaimer_en

    def test_sources_cited(self):
        inputs = ZakatInputs(total_equity_sar=1.0, long_term_liabilities_provisions_sar=1.0, net_fixed_assets_sar=0.0)
        r = estimate_zakat_base(inputs)
        assert len(r.sources) >= 3
        assert any("zatca" in s.lower() for s in r.sources)


class TestSerialization:
    def test_to_dict_serializes_available(self):
        inputs = ZakatInputs(
            total_equity_sar=2_000_000.0,
            long_term_liabilities_provisions_sar=500_000.0,
            net_fixed_assets_sar=700_000.0,
        )
        r = estimate_zakat_base(inputs)
        d = zakat_estimate_to_dict(r)
        assert d["available"] is True
        assert d["zakat_base_sar"] == pytest.approx(1_800_000.0)
        assert d["zakat_rate"] == 0.025

    def test_to_dict_serializes_unavailable(self):
        inputs = ZakatInputs(total_equity_sar=None, long_term_liabilities_provisions_sar=None, net_fixed_assets_sar=None)
        r = estimate_zakat_base(inputs)
        d = zakat_estimate_to_dict(r)
        assert d["available"] is False
        assert d["zakat_base_sar"] is None
        assert len(d["missing_fields"]) == 3
