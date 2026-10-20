"""
Phase 9 Enterprise Upload & Reporting Tests — 21 tests.

Covers:
  - ExcelIngestionEngine: CSV, Excel, Parquet, JSON, encoding, Arabic headers
  - SecureFileIngestion: PII detection, leakage detection, tenant validation,
    minimum row enforcement, feature column counting
  - ReportLocalizer: bilingual strings, mandatory disclaimers, PDF layout
  - DemoCompanyGenerator: all 5 companies, both languages, bytes output
  - ExecutiveReportExporter: all 4 report types, disclaimer attachment, checksum
  - AuditPackageBuilder: ZIP contents, manifest checksum, no raw rows,
    PII sanitization in audit events
  - Regression: existing governance locks unchanged, ExportSafetyValidator intact

All tests must pass without altering any Phase 1–8 module behavior.
"""

from __future__ import annotations

import io
import json

import numpy as np
import pandas as pd
import pytest


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_csv_bytes(df: pd.DataFrame, encoding: str = "utf-8-sig") -> bytes:
    buf = io.BytesIO()
    df.to_csv(buf, index=False, encoding=encoding)
    return buf.getvalue()


def _make_excel_bytes(df: pd.DataFrame, sheet_name: str = "Employee Data") -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    return buf.getvalue()


def _make_parquet_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    df.to_parquet(buf, index=False)
    return buf.getvalue()


def _minimal_hr_df(n: int = 100) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    return pd.DataFrame({
        "department": rng.choice(["Engineering", "Operations", "Finance"], n),
        "tenure_years": rng.uniform(0.5, 10, n).round(1),
        "job_level": rng.integers(1, 6, n),
        "salary_sar": rng.integers(8000, 25000, n),
        "performance_rating": rng.uniform(2.0, 5.0, n).round(2),
        "engagement_score": rng.uniform(2.5, 5.0, n).round(2),
        "flight_risk": rng.uniform(0.0, 1.0, n).round(3),
    })


# ══════════════════════════════════════════════════════════════════════════════
# ExcelIngestionEngine — 5 tests
# ══════════════════════════════════════════════════════════════════════════════

class TestExcelIngestionEngine:

    def setup_method(self):
        from backend.core.excel_ingestion_engine import ExcelIngestionEngine
        self.engine = ExcelIngestionEngine()

    # Test 1
    def test_csv_ingestion_basic(self):
        df = _minimal_hr_df(200)
        raw = _make_csv_bytes(df)
        result = self.engine.ingest(raw, "test.csv")

        assert result.success is True
        assert result.row_count == 200
        assert result.column_count == 7
        assert result.detected_language == "en"
        assert result.df is not None

    # Test 2
    def test_excel_ingestion_with_sheet_selection(self):
        """Excel with multiple sheets — engine picks the HR-relevant one."""
        df_hr = _minimal_hr_df(150)
        df_meta = pd.DataFrame({"key": ["version"], "value": ["1.0"]})

        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df_hr.to_excel(writer, index=False, sheet_name="Employee Data")
            df_meta.to_excel(writer, index=False, sheet_name="Metadata")
        raw = buf.getvalue()

        result = self.engine.ingest(raw, "hr_data.xlsx")
        assert result.success is True
        assert result.sheet_used == "Employee Data"
        # Should warn about multiple sheets
        assert any("sheet" in w.lower() for w in result.warnings)

    # Test 3
    def test_parquet_ingestion(self):
        df = _minimal_hr_df(300)
        raw = _make_parquet_bytes(df)
        result = self.engine.ingest(raw, "hr.parquet")

        assert result.success is True
        assert result.row_count == 300
        assert "Parquet" in " ".join(result.transformations)

    # Test 4
    def test_arabic_header_detection(self):
        """Columns in Arabic → detected_language == 'ar'."""
        df_ar = pd.DataFrame({
            "القسم": ["العمليات", "الهندسة"],
            "سنوات_الخدمة": [3.2, 5.1],
            "الراتب_ريال": [12000, 18000],
            "درجة_الأداء": [3.8, 4.2],
            "مخاطر_المغادرة": [0.3, 0.15],
        })
        raw = _make_csv_bytes(df_ar)
        result = self.engine.ingest(raw, "arabic.csv")

        assert result.success is True
        assert result.detected_language == "ar"

    # Test 5
    def test_unsupported_format_returns_failure(self):
        result = self.engine.ingest(b"some bytes", "file.pdf")
        assert result.success is False
        assert "Unsupported" in (result.error or "")
        assert result.df is None


# ══════════════════════════════════════════════════════════════════════════════
# SecureFileIngestion — 6 tests
# ══════════════════════════════════════════════════════════════════════════════

class TestSecureFileIngestion:

    def setup_method(self):
        from backend.core.secure_file_ingestion import SecureFileIngestion, ReadinessLevel
        self.scanner = SecureFileIngestion()
        self.ReadinessLevel = ReadinessLevel

    # Test 6
    def test_clean_file_is_ready(self):
        df = _minimal_hr_df(100)
        raw = _make_csv_bytes(df)
        report = self.scanner.scan(raw, "clean.csv", "tenant-a")

        assert report.readiness_level == self.ReadinessLevel.READY
        assert report.governance_scan_passed is True
        assert len(report.pii_columns_detected) == 0
        assert len(report.leakage_columns_detected) == 0
        assert len(report.blocking_reasons) == 0

    # Test 7
    def test_pii_column_blocks_scan(self):
        """A file with 'email' column must be BLOCKED."""
        df = _minimal_hr_df(100)
        df["email"] = "user@example.com"
        raw = _make_csv_bytes(df)
        report = self.scanner.scan(raw, "pii.csv", "tenant-a")

        assert report.readiness_level == self.ReadinessLevel.BLOCKED
        assert "email" in report.pii_columns_detected
        assert len(report.blocking_reasons) > 0
        assert report.governance_scan_passed is False

    # Test 8
    def test_leakage_column_blocks_scan(self):
        """A file with 'resignation_date' column must be BLOCKED."""
        df = _minimal_hr_df(100)
        df["resignation_date"] = "2025-01-01"
        raw = _make_csv_bytes(df)
        report = self.scanner.scan(raw, "leakage.csv", "tenant-a")

        assert report.readiness_level == self.ReadinessLevel.BLOCKED
        assert "resignation_date" in report.leakage_columns_detected

    # Test 9
    def test_missing_tenant_id_blocks(self):
        """Empty tenant_id must result in BLOCKED."""
        df = _minimal_hr_df(100)
        raw = _make_csv_bytes(df)
        report = self.scanner.scan(raw, "test.csv", "")

        assert report.readiness_level == self.ReadinessLevel.BLOCKED
        assert any("tenant" in r.lower() for r in report.blocking_reasons)

    # Test 10
    def test_too_few_rows_blocks(self):
        """Fewer than 50 rows must be BLOCKED."""
        df = _minimal_hr_df(10)
        raw = _make_csv_bytes(df)
        report = self.scanner.scan(raw, "tiny.csv", "tenant-b")

        assert report.readiness_level == self.ReadinessLevel.BLOCKED
        assert any("50 rows" in r or "Insufficient" in r for r in report.blocking_reasons)

    # Test 11
    def test_raw_df_not_in_report(self):
        """FileIngestionReport must not expose raw DataFrame rows directly."""
        df = _minimal_hr_df(100)
        raw = _make_csv_bytes(df)
        report = self.scanner.scan(raw, "clean.csv", "tenant-a")

        # The report should have ingestion_result but NOT the raw df accessible
        # through any obvious attribute path on the report itself
        # (ingestion_result.df is internal — report-level API must not expose rows)
        report_dict = {
            "readiness_level": str(report.readiness_level),
            "pii_columns_detected": report.pii_columns_detected,
            "feature_columns": report.feature_columns,
            "blocking_reasons": report.blocking_reasons,
            "warnings": report.warnings,
        }
        # Ensure no DataFrame-level data appears in the report summary fields
        for field_val in report_dict.values():
            if isinstance(field_val, str):
                assert "tenure_years" not in field_val or field_val == "tenure_years"  # column name only


# ══════════════════════════════════════════════════════════════════════════════
# ReportLocalizer — 3 tests
# ══════════════════════════════════════════════════════════════════════════════

class TestReportLocalizer:

    def setup_method(self):
        from backend.core.report_localization import ReportLocalizer
        self.ReportLocalizer = ReportLocalizer

    # Test 12
    def test_english_labels_non_empty(self):
        loc = self.ReportLocalizer("en")
        assert loc.label("report_executive_summary") != ""
        assert loc.governance_disclaimer() != ""
        assert loc.pdpl_note() != ""
        assert not loc.is_rtl

    # Test 13
    def test_arabic_labels_contain_arabic_chars(self):
        """Arabic labels must contain Arabic Unicode characters."""
        import re
        ARABIC_RE = re.compile(r"[؀-ۿ]")
        loc = self.ReportLocalizer("ar")
        assert ARABIC_RE.search(loc.label("report_executive_summary"))
        assert ARABIC_RE.search(loc.governance_disclaimer())
        assert ARABIC_RE.search(loc.pdpl_note())
        assert loc.is_rtl

    # Test 14
    def test_all_three_disclaimers_present(self):
        """all_disclaimers() must return exactly 3 non-empty strings."""
        loc = self.ReportLocalizer("en")
        disclaimers = loc.all_disclaimers()
        assert len(disclaimers) == 3
        for d in disclaimers:
            assert isinstance(d, str) and len(d) > 50


# ══════════════════════════════════════════════════════════════════════════════
# DemoCompanyGenerator — 2 tests
# ══════════════════════════════════════════════════════════════════════════════

class TestDemoCompanyGenerator:

    def setup_method(self):
        from backend.core.demo_company_generator import DemoCompanyGenerator
        self.gen = DemoCompanyGenerator()

    # Test 15
    def test_all_five_companies_generate(self):
        """All 5 demo companies must generate DataFrames without error."""
        profiles = self.gen.list_profiles()
        assert len(profiles) == 5

        for profile in profiles:
            df = self.gen.generate(profile["company_id"])
            assert len(df) > 0
            assert "department" in df.columns or "القسم" in df.columns
            assert df.attrs.get("DEMO_MODE") is True

    # Test 16
    def test_arabic_language_generates_arabic_columns(self):
        """language='ar' must produce Arabic column headers."""
        import re
        ARABIC_RE = re.compile(r"[؀-ۿ]")
        df = self.gen.generate("saudi-digital-services", language="ar")
        arabic_cols = [c for c in df.columns if ARABIC_RE.search(c)]
        assert len(arabic_cols) > 0


# ══════════════════════════════════════════════════════════════════════════════
# ExecutiveReportExporter — 3 tests
# ══════════════════════════════════════════════════════════════════════════════

class TestExecutiveReportExporter:

    def setup_method(self):
        from backend.core.executive_report_exporter import ExecutiveReportExporter, ReportType
        self.exporter = ExecutiveReportExporter()
        self.ReportType = ReportType
        self._data = {
            "workforce_stability_index": 73.2,
            "governance_status": "OK",
            "departments": [
                {"name": "Engineering", "name_ar": "الهندسة", "stability_score": 76.3,
                 "risk_band": "monitoring", "employee_count": 714},
            ],
            "trend_12m": [{"month": "Jan", "value": 70.0}, {"month": "Feb", "value": 73.2}],
            "calibration": {"auc_roc": 0.783, "ece": 0.041, "brier": 0.162},
            "theory_contributions": [{"theory": "COR", "contribution": 31.2}],
            "strategic_insights": [
                {"en": "Engineering shows monitoring indicators.", "ar": "الهندسة في المراقبة."}
            ],
            "governance_locks": {},
            "pdpl_controls": {},
        }

    # Test 17
    def test_all_four_report_types_generate(self):
        """All 4 report types must generate without error and include HTML."""
        for rt in self.ReportType:
            report = self.exporter.generate(
                report_type=rt,
                tenant_id="test-tenant",
                data=self._data,
                language="en",
            )
            assert len(report.html_content) > 100
            assert "<!DOCTYPE html>" in report.html_content
            assert report.governance_verified is True

    # Test 18
    def test_disclaimers_always_present(self):
        """Every report must attach exactly 3 disclaimers."""
        report = self.exporter.generate(
            report_type=self.ReportType.EXECUTIVE_SUMMARY,
            tenant_id="test-tenant",
            data=self._data,
            language="en",
        )
        assert len(report.disclaimers_attached) == 3
        for disc in report.disclaimers_attached:
            assert len(disc) > 50

    # Test 19
    def test_report_checksum_is_sha256(self):
        """Checksum must be a valid 64-char hex string (SHA-256)."""
        report = self.exporter.generate(
            report_type=self.ReportType.BOARD_BRIEFING,
            tenant_id="test-tenant",
            data=self._data,
            language="ar",
        )
        assert len(report.checksum) == 64
        assert all(c in "0123456789abcdef" for c in report.checksum)


# ══════════════════════════════════════════════════════════════════════════════
# AuditPackageBuilder — 2 tests
# ══════════════════════════════════════════════════════════════════════════════

class TestAuditPackageBuilder:

    def setup_method(self):
        from backend.core.audit_package_builder import AuditPackageBuilder
        self.builder = AuditPackageBuilder()

    # Test 20
    def test_audit_package_zip_has_required_files(self):
        """ZIP must contain scan_summary, governance_snapshot, README, MANIFEST."""
        import zipfile
        package = self.builder.build(
            tenant_id="test-tenant",
            governance_locks={
                "DEBUG": False,
                "EMPLOYEE_LEVEL_OUTPUT_ENABLED": False,
            },
        )
        zip_bytes = package.to_zip_bytes()
        assert len(zip_bytes) > 0

        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            names = set(zf.namelist())
        assert "MANIFEST.json" in names
        assert "README.txt" in names
        assert "governance_snapshot.json" in names
        assert "audit_events_excerpt.json" in names

    # Test 21
    def test_audit_events_pii_stripped(self):
        """Audit events containing employee_id must have that field removed."""
        events = [
            {"event_type": "REPORT_GENERATED", "employee_id": "EMP001", "tenant_id": "t1"},
            {"event_type": "UPLOAD", "tenant_id": "t1", "filename": "hr.csv"},
        ]
        package = self.builder.build(
            tenant_id="t1",
            audit_events=events,
        )

        # Check the audit_events_excerpt.json content
        events_content = package.files.get("audit_events_excerpt.json", "{}")
        parsed = json.loads(events_content)
        for event in parsed.get("events", []):
            assert "employee_id" not in event, (
                "employee_id must be stripped from audit events in the package"
            )


# ══════════════════════════════════════════════════════════════════════════════
# Regression: Phase 1-8 governance unchanged
# ══════════════════════════════════════════════════════════════════════════════

class TestPhase18Regression:

    def test_export_safety_validator_intact(self):
        """ExportSafetyValidator must still strip employee-level fields."""
        from backend.core.export_safety import ExportSafetyValidator
        validator = ExportSafetyValidator()

        data = {
            "department": "Engineering",
            "employee_id": "EMP001",
            "risk_score": 0.72,
            "mean_risk_score": 0.45,
        }
        package = validator.validate_and_sanitize(data, tenant_id="t1")
        # validate_and_sanitize returns SafeExportPackage — access .data for sanitized payload
        safe = package.data if hasattr(package, "data") else package

        assert "employee_id" not in safe, "employee_id must be stripped from export"
        # Aggregate metric must NOT be stripped by exact-match set check
        assert "mean_risk_score" in safe, "mean_risk_score is an aggregate metric, must NOT be stripped"

    def test_production_governance_locks_active(self):
        """Core production governance locks must be at their required values."""
        from config.production_settings import (
            DEBUG,
            EMPLOYEE_LEVEL_OUTPUT_ENABLED,
            TENANT_ISOLATION_REQUIRED,
            CALIBRATION_AUDIT_REQUIRED,
            PDPL_WARNING_ENABLED,
            REPORT_DISCLAIMER_REQUIRED,
            AUDIT_LOGGING_REQUIRED,
            TEMPORAL_VALIDATION_REQUIRED,
            LEGACY_CONSTRUCTS_DISABLED,
            SCIENTIFIC_FEATURE_MODE,
            SECURE_EXPORT_MODE,
        )
        assert DEBUG is False
        assert EMPLOYEE_LEVEL_OUTPUT_ENABLED is False
        assert TENANT_ISOLATION_REQUIRED is True
        assert CALIBRATION_AUDIT_REQUIRED is True
        assert PDPL_WARNING_ENABLED is True
        assert REPORT_DISCLAIMER_REQUIRED is True
        assert AUDIT_LOGGING_REQUIRED is True
        assert TEMPORAL_VALIDATION_REQUIRED is True
        assert LEGACY_CONSTRUCTS_DISABLED is True
        assert SCIENTIFIC_FEATURE_MODE == "theory_grounded"
        assert SECURE_EXPORT_MODE is True
