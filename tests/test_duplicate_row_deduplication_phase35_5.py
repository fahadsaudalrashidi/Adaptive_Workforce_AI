"""
Phase 35.5 (correction) — Duplicate-row deduplication tests.

Covers the confirmed live-testing bug: a duplicate row (same EmployeeID,
identical values) was counted twice, corrupting at-risk percentages (Sales
showed "2/3" (67%) instead of the correct "1/2" (50%)). The fix runs
deduplication once at the pipeline level, inside SecureFileIngestion.scan(),
before any downstream module (risk scoring, overtime cost, payroll movement)
reads the dataframe — see backend/core/secure_file_ingestion.py::_deduplicate.

Governance requirement: duplicates must never be dropped silently — every
scan() call that removes rows must surface a disclosure warning stating how
many were found/removed and how they were matched.

Phase 8 correction (this file's `TestDeduplicateCompositeKeyForLongitudinalData`
class): a second confirmed live-testing bug — the ID-only matching above
wrongly stripped legitimate multi-period payroll data. A 60-employee x
18-period upload (1,080 rows, the same EmployeeID legitimately repeating 18
times across different Period values) was collapsed to 60 rows, destroying
17/18 of every employee's real monthly history. The fix adds a composite
(id, period) key: when a recognisable period/date column is ALSO present
(see `_PERIOD_COLUMN_PATTERNS`, kept in sync with
payroll_movement_tracker.py's own period detection), two rows are only
duplicates when both the ID and the period match. With no period column
present, behaviour is byte-for-byte unchanged from the original fix above.

Run: py -m pytest tests/test_duplicate_row_deduplication_phase35_5.py -v
"""

from __future__ import annotations

import io

import numpy as np
import pandas as pd
import pytest

from backend.core.secure_file_ingestion import SecureFileIngestion


def _make_csv_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    df.to_csv(buf, index=False, encoding="utf-8-sig")
    return buf.getvalue()


def _minimal_hr_df(n: int = 60) -> pd.DataFrame:
    """>= 50 rows, so scans stay READY/CONDITIONAL rather than BLOCKED on
    the minimum-row-count governance rule."""
    rng = np.random.default_rng(0)
    return pd.DataFrame({
        "EmployeeID": [f"EMP{i:03d}" for i in range(n)],
        "department": rng.choice(["Engineering", "Operations", "Finance"], n),
        "tenure_years": rng.uniform(0.5, 10, n).round(1),
        "job_level": rng.integers(1, 6, n),
        "salary_sar": rng.integers(8000, 25000, n),
        "performance_rating": rng.uniform(2.0, 5.0, n).round(2),
        "engagement_score": rng.uniform(2.5, 5.0, n).round(2),
        "flight_risk": rng.uniform(0.0, 1.0, n).round(3),
    })


class TestDeduplicateUnit:
    def setup_method(self):
        self.scanner = SecureFileIngestion()

    def test_id_based_exact_duplicate_is_removed(self):
        """The exact EMP001 case from live testing: same EmployeeID, identical
        row, appears twice — must collapse to one row."""
        df = pd.DataFrame({
            "EmployeeID": ["EMP001", "EMP001", "EMP002"],
            "Department": ["Sales", "Sales", "Sales"],
            "flight_risk": [1.0, 1.0, 0.0],
        })
        deduped, notes = self.scanner._deduplicate(df)
        assert len(deduped) == 2
        assert sorted(deduped["EmployeeID"]) == ["EMP001", "EMP002"]
        assert len(notes) == 1
        assert "1 duplicate row(s) removed" in notes[0]
        assert "EmployeeID" in notes[0]

    def test_no_duplicates_produces_no_notes(self):
        df = pd.DataFrame({
            "EmployeeID": ["EMP001", "EMP002", "EMP003"],
            "Department": ["Sales", "Finance", "Engineering"],
        })
        deduped, notes = self.scanner._deduplicate(df)
        assert len(deduped) == 3
        assert notes == []

    def test_full_row_fallback_when_no_id_column(self):
        """No employee-ID column present — dedupe only on exact full-row match."""
        df = pd.DataFrame({
            "Department": ["Sales", "Sales", "Finance"],
            "salary_sar": [10000, 10000, 12000],
        })
        deduped, notes = self.scanner._deduplicate(df)
        assert len(deduped) == 2
        assert len(notes) == 1
        assert "no employee-ID column was found" in notes[0]

    def test_partial_overlap_without_id_column_is_not_merged(self):
        """Two rows that share SOME but not all values, with no ID column,
        must NOT be treated as duplicates."""
        df = pd.DataFrame({
            "Department": ["Sales", "Sales"],
            "salary_sar": [10000, 11000],
        })
        deduped, notes = self.scanner._deduplicate(df)
        assert len(deduped) == 2
        assert notes == []

    def test_different_employee_ids_with_identical_other_values_not_merged(self):
        """Two DIFFERENT employees who happen to have identical non-ID field
        values must not be merged — the ID column is authoritative."""
        df = pd.DataFrame({
            "EmployeeID": ["EMP001", "EMP002"],
            "Department": ["Sales", "Sales"],
            "salary_sar": [10000, 10000],
        })
        deduped, notes = self.scanner._deduplicate(df)
        assert len(deduped) == 2
        assert notes == []

    def test_empty_dataframe_returns_unchanged(self):
        df = pd.DataFrame()
        deduped, notes = self.scanner._deduplicate(df)
        assert deduped.empty
        assert notes == []


class TestDeduplicateFullScan:
    def setup_method(self):
        self.scanner = SecureFileIngestion()

    def test_duplicate_emp001_row_reduces_analyzed_row_count(self):
        """Full pipeline: uploading a file with a duplicated EMP001 row must
        result in the analyzed dataframe (ingestion_result.df) having one
        fewer row than the raw upload, with a disclosure warning."""
        df = _minimal_hr_df(60)
        dup_row = df.iloc[[0]].copy()   # exact duplicate of the first row (same EmployeeID)
        df_with_dup = pd.concat([df, dup_row], ignore_index=True)
        assert len(df_with_dup) == 61

        raw = _make_csv_bytes(df_with_dup)
        report = self.scanner.scan(raw, "dup.csv", "tenant-a")

        assert report.ingestion_result.row_count == 60
        assert len(report.ingestion_result.df) == 60
        assert any("duplicate row(s) removed" in w for w in report.warnings)
        assert any("EmployeeID" in w for w in report.warnings)

    def test_no_duplicates_leaves_row_count_unchanged(self):
        df = _minimal_hr_df(60)
        raw = _make_csv_bytes(df)
        report = self.scanner.scan(raw, "clean.csv", "tenant-a")

        assert report.ingestion_result.row_count == 60
        assert not any("duplicate row(s) removed" in w for w in report.warnings)

    def test_duplicate_disclosure_never_silent(self):
        """Governance requirement: removing rows must always be visible in
        report.warnings, never silently applied."""
        df = _minimal_hr_df(55)
        dup_rows = df.iloc[[0, 1, 2]].copy()
        df_with_dups = pd.concat([df, dup_rows], ignore_index=True)

        raw = _make_csv_bytes(df_with_dups)
        report = self.scanner.scan(raw, "multi_dup.csv", "tenant-a")

        assert report.ingestion_result.row_count == 55
        dup_warnings = [w for w in report.warnings if "duplicate row(s) removed" in w]
        assert len(dup_warnings) == 1
        assert "3 duplicate row(s) removed" in dup_warnings[0]


# Phase 40: TestDuplicateRowAtRiskPercentageFix (the regression proof that a
# duplicated at-risk employee no longer inflated employee_risk_scoring.py's
# department at-risk percentage) was removed along with that engine. The
# underlying dedup mechanism it also exercised remains fully covered by the
# other tests in this file (test_id_based_exact_duplicate_is_removed,
# test_duplicate_emp001_row_reduces_analyzed_row_count, etc.) — see
# PHASE_40_EXECUTIVE_PAGES_REMOVAL_REPORT.md.


def _longitudinal_payroll_df(n_emp: int = 60, n_periods: int = 18) -> pd.DataFrame:
    """The exact shape that surfaced the live bug: n_emp employees, each
    legitimately appearing once per period (e.g. one row per employee per
    month) — NOT duplicates, real longitudinal history."""
    rng = np.random.default_rng(11)
    periods = [f"2024-{(i % 12) + 1:02d}" if i < 12 else f"2025-{(i - 12) % 12 + 1:02d}"
               for i in range(n_periods)]
    rows = []
    for e in range(n_emp):
        eid = f"EMP{e:03d}"
        base_salary = int(rng.integers(8000, 25000))
        for p in periods:
            rows.append({
                "EmployeeID": eid,
                "Period": p,
                "Department": rng.choice(["Sales", "Finance", "Engineering"]),
                "MonthlyIncome": base_salary + int(rng.integers(-200, 200)),
            })
    return pd.DataFrame(rows)


class TestDeduplicateCompositeKeyForLongitudinalData:
    """Phase 8 correction: ID-only dedup wrongly stripped legitimate
    multi-period payroll data. See secure_file_ingestion.py::_deduplicate's
    period_col branch."""

    def setup_method(self):
        self.scanner = SecureFileIngestion()

    def test_same_employee_across_many_legitimate_periods_is_not_stripped(self):
        """The exact reported bug: 60 employees x 18 periods = 1,080 rows,
        same EmployeeID repeating 18 times with a different Period each
        time. Pre-fix: collapsed to 60 rows. Post-fix: all 1,080 kept,
        zero duplicate-removal notes."""
        df = _longitudinal_payroll_df(n_emp=60, n_periods=18)
        assert len(df) == 1080

        deduped, notes = self.scanner._deduplicate(df)
        assert len(deduped) == 1080
        assert notes == []

    def test_actual_duplicate_same_employee_same_period_is_removed(self):
        """A genuine duplicate — same EmployeeID AND same Period appearing
        twice — must still be caught and removed."""
        df = _longitudinal_payroll_df(n_emp=60, n_periods=18)
        dup_row = df.iloc[[0]].copy()  # exact repeat of EMP000's first period
        df_with_dup = pd.concat([df, dup_row], ignore_index=True)
        assert len(df_with_dup) == 1081

        deduped, notes = self.scanner._deduplicate(df_with_dup)
        assert len(deduped) == 1080
        assert len(notes) == 1
        assert "1 duplicate (employee, period) row(s) removed" in notes[0]

    def test_composite_dedup_disclosure_names_both_matched_columns(self):
        """The disclosure message must be accurate about HOW rows were
        matched — not imply plain employee-level dedup when it's actually
        period-aware (silently misleading governance disclosure would be
        worse than the original bug)."""
        df = _longitudinal_payroll_df(n_emp=10, n_periods=3)
        dup_row = df.iloc[[0]].copy()
        df_with_dup = pd.concat([df, dup_row], ignore_index=True)

        _, notes = self.scanner._deduplicate(df_with_dup)
        assert len(notes) == 1
        assert "EmployeeID" in notes[0]
        assert "Period" in notes[0]
        assert "different periods is legitimate longitudinal data" in notes[0]

    def test_no_period_column_still_uses_id_only_dedup(self):
        """Scoped narrowly: with an ID column but NO period column, behaviour
        must be byte-for-byte the original ID-only dedup (Overtime, Fairness,
        Nitaqat, Succession, and every other one-row-per-employee module
        must see zero behaviour change from this fix)."""
        df = pd.DataFrame({
            "EmployeeID": ["EMP001", "EMP001", "EMP002"],
            "Department": ["Sales", "Sales", "Sales"],
            "flight_risk": [1.0, 1.0, 0.0],
        })
        deduped, notes = self.scanner._deduplicate(df)
        assert len(deduped) == 2
        assert len(notes) == 1
        assert "1 duplicate row(s) removed" in notes[0]
        assert "(employee, period)" not in notes[0]

    def test_full_scan_end_to_end_preserves_multi_period_row_count(self):
        """Full pipeline: SecureFileIngestion.scan() on the same 1,080-row
        longitudinal upload must report row_count == 1080, not 60."""
        df = _longitudinal_payroll_df(n_emp=60, n_periods=18)
        raw = _make_csv_bytes(df)
        report = self.scanner.scan(raw, "payroll_longitudinal.csv", "tenant-a")

        assert report.ingestion_result.row_count == 1080
        assert len(report.ingestion_result.df) == 1080
        assert not any("duplicate row(s) removed" in w for w in report.warnings)
        assert not any("duplicate (employee, period) row(s) removed" in w for w in report.warnings)

    def test_full_scan_end_to_end_removes_genuine_period_duplicate_only(self):
        df = _longitudinal_payroll_df(n_emp=60, n_periods=18)
        dup_row = df.iloc[[0]].copy()
        df_with_dup = pd.concat([df, dup_row], ignore_index=True)
        raw = _make_csv_bytes(df_with_dup)
        report = self.scanner.scan(raw, "payroll_longitudinal_dup.csv", "tenant-a")

        assert report.ingestion_result.row_count == 1080
        assert any("1 duplicate (employee, period) row(s) removed" in w for w in report.warnings)
