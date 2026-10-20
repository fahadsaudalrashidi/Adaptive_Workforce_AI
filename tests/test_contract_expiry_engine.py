"""
Phase 18 — Contract Expiry & Renewal Monitoring engine tests.

Covers, each with real computed-value assertions (not smoke-only tests):
  1. Urgency-tier boundary math (`_tier_for_days`), hand-verified against
     known day-counts independent of any calendar date.
  2. Column detection: ContractEndDate and IqamaExpiry/VisaExpiry are two
     genuinely separate signals — a fixture carrying both must report both
     columns independently and never merge/average them.
  3. "Not detected" against every real HR-shaped fixture already in this
     repo (none of them track contract or Iqama/visa expiry) — the expected,
     honest-degradation case for this feature against this session's data.
  4. Messy data: mixed date formats, one unparseable value, one missing
     value — using `contract_expiry_test_data.csv` built for this phase.
  5. Both cross-link scenarios (Phase 8 decoupled-engine / route-layer-join
     pattern): Succession Readiness + contract-expiry ("high-readiness
     employee with contract expiring soon"), and Nitaqat + Iqama-expiry
     ("non-Saudi employee with expiring Iqama"). These tests call each
     engine's public function directly and perform the join in the test
     itself, exactly mirroring how the route layer is required to do it —
     contract_expiry_engine.py never imports succession_readiness_engine.py
     or nitaqat_compliance_engine.py, and neither imports it back.

Tier-boundary integration assertions use dates computed as offsets from
`datetime.now()` at test-run time (not fixed calendar dates), so they remain
correct regardless of which day the suite runs — mirroring the engine's own
`as_of = datetime.now(timezone.utc)` computation.

Run: py -m pytest tests/test_contract_expiry_engine.py -v
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest

from backend.core.contract_expiry_engine import (
    CROSS_LINK_HORIZON_DAYS,
    _tier_for_days,
    analyze_contract_expiry,
    contract_expiry_to_dict,
    get_expiry_signals_by_record_id,
    unavailable_contract_expiry_result,
)
from backend.core.nitaqat_compliance_engine import get_saudi_status_by_record_id
from backend.core.succession_readiness_engine import analyze_succession_readiness

_ROOT = Path(__file__).resolve().parent.parent
_MESSY_FIXTURE = _ROOT / "contract_expiry_test_data.csv"


def _offset_date(days: int) -> str:
    """ISO date `days` from now (UTC) — used to build calendar-drift-safe fixtures."""
    return (datetime.now(timezone.utc) + timedelta(days=days)).strftime("%Y-%m-%d")


# ── 1. Urgency-tier boundary math — hand-verified, no calendar dependency ──

def test_tier_boundaries_hand_computed():
    assert _tier_for_days(-1) == "overdue"
    assert _tier_for_days(0) == "critical_0_30"
    assert _tier_for_days(30) == "critical_0_30"
    assert _tier_for_days(31) == "urgent_31_60"
    assert _tier_for_days(60) == "urgent_31_60"
    assert _tier_for_days(61) == "upcoming_61_90"
    assert _tier_for_days(90) == "upcoming_61_90"
    assert _tier_for_days(91) == "monitored_90_plus"
    assert _tier_for_days(365) == "monitored_90_plus"
    assert _tier_for_days(-500) == "overdue"


# ── 2. Not detected — real fixtures already in this repo ───────────────────

def test_real_employee_fixture_has_no_expiry_column_and_is_unavailable():
    df = pd.read_csv(_ROOT / "test_employee_data.csv")
    result = analyze_contract_expiry(df)
    assert result.available is False
    assert result.columns_detected["contract_end_date"] is False
    assert result.columns_detected["iqama_or_visa_expiry"] is False
    assert result.candidates == []
    assert "column" in result.reason.lower()


def test_messy_test_data_fixture_has_no_expiry_column():
    df = pd.read_csv(_ROOT / "messy_test_data.csv")
    result = analyze_contract_expiry(df)
    assert result.available is False


def test_messy_recruitment_data_fixture_has_no_expiry_column():
    df = pd.read_csv(_ROOT / "messy_recruitment_data.csv")
    result = analyze_contract_expiry(df)
    assert result.available is False


def test_succession_test_data_fixture_has_no_expiry_column():
    df = pd.read_csv(_ROOT / "succession_test_data.csv")
    result = analyze_contract_expiry(df)
    assert result.available is False


def test_nitaqat_test_data_fixture_has_no_expiry_column():
    df = pd.read_csv(_ROOT / "nitaqat_test_data.csv")
    result = analyze_contract_expiry(df)
    assert result.available is False


def test_nitaqat_realistic_multidept_fixture_has_no_expiry_column():
    df = pd.read_csv(_ROOT / "nitaqat_realistic_multidept_test_data.csv")
    result = analyze_contract_expiry(df)
    assert result.available is False


def test_pay_equity_realistic_fixture_has_no_expiry_column():
    df = pd.read_csv(_ROOT / "pay_equity_realistic_test_data.csv")
    result = analyze_contract_expiry(df)
    assert result.available is False


def test_payroll_longitudinal_fixture_has_no_expiry_column():
    df = pd.read_csv(_ROOT / "payroll_longitudinal_test_data.csv")
    result = analyze_contract_expiry(df)
    assert result.available is False


def test_unavailable_result_never_fabricates_and_lists_activating_columns():
    result = unavailable_contract_expiry_result(
        "No contract-end-date or Iqama/visa-expiry column detected.",
        {"contract_end_date": False, "iqama_or_visa_expiry": False, "department": True},
    )
    assert result.available is False
    assert result.candidates == []
    assert result.contract_tier_counts == {}
    assert result.iqama_tier_counts == {}
    d = contract_expiry_to_dict(result)
    assert d["columns_detected"]["department"] is True
    assert d["columns_detected"]["contract_end_date"] is False


# ── 3. Two genuinely separate signals — messy real-ish fixture ─────────────

def test_messy_fixture_detects_both_columns_as_distinct():
    df = pd.read_csv(_MESSY_FIXTURE)
    result = analyze_contract_expiry(df)
    assert result.available is True
    assert result.contract_end_column == "ContractEndDate"
    assert result.iqama_expiry_column == "IqamaExpiry"


def test_messy_fixture_contract_and_iqama_are_not_conflated():
    """EMP001 has a different ContractEndDate (2026-09-15) and IqamaExpiry
    (2026-08-25) — the two signals must produce two distinct candidate
    entries for the same employee, not one merged value."""
    import hashlib
    emp001_id = "EMP-" + hashlib.sha256("EMP001".encode()).hexdigest()[:6].upper()
    df = pd.read_csv(_MESSY_FIXTURE)
    result = analyze_contract_expiry(df)
    by_signal = {c.signal_type: c for c in result.candidates if c.record_id_safe == emp001_id}
    assert "contract" in by_signal and "iqama" in by_signal
    assert by_signal["contract"].expiry_date == "2026-09-15"
    assert by_signal["iqama"].expiry_date == "2026-08-25"
    assert by_signal["contract"].days_remaining != by_signal["iqama"].days_remaining


def test_messy_fixture_invalid_and_missing_dates_excluded_and_disclosed():
    """EMP007's ContractEndDate ('not-a-real-date') and EMP009's
    ContractEndDate/IqamaExpiry (an alternate 'DD-Mon-YYYY' format that
    pandas' column-wide format inference fails to parse alongside the
    majority ISO-formatted rows) are unparseable; EMP008's IqamaExpiry is
    blank. All must be excluded from tiering, counted, and disclosed —
    never guessed."""
    df = pd.read_csv(_MESSY_FIXTURE)
    result = analyze_contract_expiry(df)
    assert result.n_contract_records_valid == 8
    assert result.n_iqama_records_valid == 8
    assert result.n_invalid_dates_excluded == 4
    assert len(result.date_quality_warnings) == 2
    assert any("contract" in w.lower() for w in result.date_quality_warnings)
    assert any("iqama" in w.lower() for w in result.date_quality_warnings)


def test_messy_fixture_department_rollup_present():
    df = pd.read_csv(_MESSY_FIXTURE)
    result = analyze_contract_expiry(df)
    assert result.columns_detected["department"] is True
    depts = {d.department for d in result.department_breakdown}
    assert "Engineering" in depts


# ── 4. Exact tier assertions — dynamic dates, calendar-drift-safe ──────────

def test_tiering_on_dynamically_built_dataframe():
    df = pd.DataFrame({
        "EmployeeID": ["E1", "E2", "E3", "E4", "E5"],
        "Department": ["Ops", "Ops", "Ops", "Ops", "Ops"],
        "ContractEndDate": [
            _offset_date(-10),   # overdue
            _offset_date(15),    # critical_0_30
            _offset_date(45),    # urgent_31_60
            _offset_date(75),    # upcoming_61_90
            _offset_date(200),   # monitored_90_plus
        ],
    })
    result = analyze_contract_expiry(df)
    assert result.available is True
    assert result.contract_tier_counts == {
        "overdue": 1,
        "critical_0_30": 1,
        "urgent_31_60": 1,
        "upcoming_61_90": 1,
        "monitored_90_plus": 1,
    }
    tiers_by_id = {c.record_id_safe: c.urgency_tier for c in result.candidates}
    assert len(tiers_by_id) == 4  # monitored_90_plus is aggregate-only, not row-level


def test_missing_id_falls_back_to_row_label_not_dropped():
    df = pd.DataFrame({
        "Department": ["Ops"],
        "ContractEndDate": [_offset_date(5)],
    })
    result = analyze_contract_expiry(df)
    assert result.available is True
    assert len(result.candidates) == 1
    assert result.candidates[0].record_id_safe.startswith("ROW-")


# ── 5. get_expiry_signals_by_record_id — cross-link join surface ───────────

def test_signals_map_none_when_no_id_column():
    df = pd.DataFrame({
        "Department": ["Ops"],
        "ContractEndDate": [_offset_date(5)],
    })
    assert get_expiry_signals_by_record_id(df) is None


def test_signals_map_none_when_neither_expiry_column_present():
    df = pd.DataFrame({"EmployeeID": ["E1"], "Department": ["Ops"]})
    assert get_expiry_signals_by_record_id(df) is None


def test_signals_map_none_on_empty_dataframe():
    assert get_expiry_signals_by_record_id(pd.DataFrame()) is None


def test_signals_map_reproduces_exact_hash_scheme():
    import hashlib
    df = pd.DataFrame({
        "EmployeeID": ["E-42"],
        "ContractEndDate": [_offset_date(10)],
    })
    signals = get_expiry_signals_by_record_id(df)
    assert signals is not None
    expected_id = "EMP-" + hashlib.sha256("E-42".encode()).hexdigest()[:6].upper()
    assert expected_id in signals
    assert signals[expected_id]["contract_days_remaining"] == 10
    assert signals[expected_id]["iqama_days_remaining"] is None


def test_signals_map_excludes_missing_id_rows():
    df = pd.DataFrame({
        "EmployeeID": ["E1", None],
        "ContractEndDate": [_offset_date(5), _offset_date(5)],
    })
    signals = get_expiry_signals_by_record_id(df)
    assert signals is not None
    assert len(signals) == 1


def test_signals_map_on_messy_fixture_returns_both_signals_independently():
    df = pd.read_csv(_MESSY_FIXTURE)
    signals = get_expiry_signals_by_record_id(df)
    assert signals is not None
    assert len(signals) > 0
    assert all(
        set(v.keys()) == {"contract_days_remaining", "iqama_days_remaining"}
        for v in signals.values()
    )
    # At least one employee has genuinely different day-counts for the two signals.
    assert any(
        v["contract_days_remaining"] != v["iqama_days_remaining"]
        for v in signals.values()
        if v["contract_days_remaining"] is not None and v["iqama_days_remaining"] is not None
    )


# ── 6. Cross-link scenario 1: Succession Readiness + contract-expiry ───────
# Mirrors the exact join the route layer must perform: intersect
# get_expiry_signals_by_record_id() with succession's high_readiness_record_ids,
# flagging "high-readiness employee with contract OR Iqama expiring within
# CROSS_LINK_HORIZON_DAYS days" using the soonest of either signal.

def test_cross_link_high_readiness_with_expiring_contract():
    df = pd.DataFrame({
        "EmployeeID": ["HR1", "HR2", "HR3", "HR4"],
        "Department": ["Eng", "Eng", "Eng", "Eng"],
        "PerformanceRating": [5, 5, 2, 2],
        "YearsAtCompany": [8, 8, 1, 1],
        "ContractEndDate": [
            _offset_date(20),    # HR1: high readiness + expiring soon -> should flag
            _offset_date(300),   # HR2: high readiness + far out -> should NOT flag
            _offset_date(20),    # HR3: low readiness + expiring soon -> should NOT flag
            _offset_date(300),   # HR4: low readiness + far out
        ],
    })
    succession_result = analyze_succession_readiness(df)
    high_readiness_ids = set(succession_result.high_readiness_record_ids)
    assert len(high_readiness_ids) >= 1

    signals = get_expiry_signals_by_record_id(df)
    assert signals is not None

    # Route-layer join: high readiness AND (contract or iqama) within horizon.
    flagged = []
    for rid in high_readiness_ids:
        sig = signals.get(rid)
        if sig is None:
            continue
        candidates_days = [d for d in (sig["contract_days_remaining"], sig["iqama_days_remaining"]) if d is not None]
        if candidates_days and min(candidates_days) <= CROSS_LINK_HORIZON_DAYS:
            flagged.append(rid)

    assert len(flagged) == 1
    # Confirm it's HR1 by hash, not HR2.
    import hashlib
    hr1_id = "EMP-" + hashlib.sha256("HR1".encode()).hexdigest()[:6].upper()
    hr2_id = "EMP-" + hashlib.sha256("HR2".encode()).hexdigest()[:6].upper()
    assert hr1_id in flagged
    assert hr2_id not in flagged


# ── 7. Cross-link scenario 2: Nitaqat + Iqama-expiry ────────────────────────
# Mirrors the route-layer join for "non-Saudi employee with expiring Iqama"
# — deliberately uses ONLY iqama_days_remaining (not contract), since
# Nitaqat/Saudization is specifically about legal work-authorization status.

def test_cross_link_non_saudi_with_expiring_iqama():
    df = pd.DataFrame({
        "EmployeeID": ["NS1", "NS2", "NS3", "NS4"],
        "Nationality": ["Non-Saudi", "Non-Saudi", "Saudi", "Saudi"],
        "IqamaExpiry": [
            _offset_date(15),    # NS1: non-Saudi + expiring soon -> should flag
            _offset_date(300),   # NS2: non-Saudi + far out -> should NOT flag
            _offset_date(15),    # NS3: Saudi (Iqama not applicable) -> should NOT flag
            _offset_date(300),
        ],
    })
    saudi_status = get_saudi_status_by_record_id(df)
    assert saudi_status is not None
    non_saudi_ids = {rid for rid, is_saudi in saudi_status.items() if is_saudi is False}
    assert len(non_saudi_ids) == 2

    signals = get_expiry_signals_by_record_id(df)
    assert signals is not None

    flagged = []
    for rid in non_saudi_ids:
        sig = signals.get(rid)
        if sig is None or sig["iqama_days_remaining"] is None:
            continue
        if sig["iqama_days_remaining"] <= CROSS_LINK_HORIZON_DAYS:
            flagged.append(rid)

    assert len(flagged) == 1
    import hashlib
    ns1_id = "EMP-" + hashlib.sha256("NS1".encode()).hexdigest()[:6].upper()
    ns2_id = "EMP-" + hashlib.sha256("NS2".encode()).hexdigest()[:6].upper()
    assert ns1_id in flagged
    assert ns2_id not in flagged


def test_cross_link_returns_none_when_datasets_share_no_id_column():
    """If the succession-relevant upload and the expiry-relevant upload
    don't share a real named ID column, the join must refuse rather than
    guess — same Phase 8 safety rule."""
    df = pd.DataFrame({
        "Department": ["Eng"],
        "PerformanceRating": [5],
        "YearsAtCompany": [8],
        "ContractEndDate": [_offset_date(10)],
    })
    assert get_expiry_signals_by_record_id(df) is None
